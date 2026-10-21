import time
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import Audit, Criteria, Job, Match, Outbox, Product, User

VERSION = "deterministic-v1"
CANDIDATE_SQL = """
SELECT u.id AS user_id, p.id AS product_id,
 p.criteria_complete, p.verification_status,
 p.lender, p.product_name, p.source_url, p.rate_representation, p.retrieved_at,
 c.minimum_monthly_income, c.minimum_credit_score, c.age_min, c.age_max,
 c.employment_requirements, c.qualitative_requirements
FROM users u JOIN loan_products p ON p.active = true
JOIN product_criteria c ON c.product_id = p.id
WHERE u.job_id = :job_id
 AND (p.verification_status = 'VERIFIED' OR (:demo AND p.verification_status = 'DEMO_FIXTURE'))
 AND (c.minimum_monthly_income IS NULL OR u.monthly_income >= c.minimum_monthly_income)
 AND (c.minimum_credit_score IS NULL OR u.credit_score >= c.minimum_credit_score)
 AND (c.age_min IS NULL OR u.age >= c.age_min)
 AND (c.age_max IS NULL OR u.age <= c.age_max)
 AND (c.employment_requirements IS NULL OR CAST(c.employment_requirements AS jsonb) = 'null'::jsonb OR CAST(c.employment_requirements AS jsonb) ? u.employment_status)
"""


def advanced(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    unknown = [
        key
        for key in (
            "minimum_monthly_income",
            "minimum_credit_score",
            "age_min",
            "age_max",
            "employment_requirements",
        )
        if candidate[key] is None
    ]
    unknown.extend(candidate["qualitative_requirements"] or [])
    if not candidate["criteria_complete"]:
        unknown.append("Source does not establish complete eligibility criteria")
    return ("REVIEW_REQUIRED" if unknown else "POSSIBLY_ELIGIBLE", unknown)


def match_record(job_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    status, uncertainty = advanced(candidate)
    return {
        "job_id": job_id, "user_id": candidate["user_id"], "product_id": candidate["product_id"],
        "matching_version": VERSION, "status": status,
        "matched_criteria": {"structured_rules": "PASSED", "product_snapshot": {
            key: value if isinstance(value, list | dict | bool | int | float) or value is None else str(value)
            for key, value in candidate.items()
        }}, "uncertainty": uncertainty,
    }


def run_matching(
    job_id: str, evaluations: list[dict[str, Any]] | None = None, execution_id: str | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    proposed = (
        {(item["user_id"], item["product_id"]): item["status"] for item in evaluations}
        if evaluations is not None
        else None
    )
    if evaluations is not None and len(proposed or {}) != len(evaluations):
        raise ValueError("Duplicate evaluated candidate")
    with Session(engine()) as db, db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.status != "COMPLETED":
            raise ValueError("A completed ingestion job is required")
        previous = db.scalar(select(Audit).where(Audit.job_id == job_id, Audit.workflow == "B"))
        if previous:
            if previous.status == "PARTITIONING":
                raise ValueError("Continue this job through the paged matching workflow")
            if previous.metrics.get("matching_version") != VERSION:
                raise ValueError(
                    "Matching version changed; create a new upload job to preserve this job's audit"
                )
            return previous.metrics
        users = db.scalar(select(func.count()).select_from(User).where(User.job_id == job_id)) or 0
        products = (
            db.scalar(
                select(func.count())
                .select_from(Product)
                .join(Criteria)
                .where(
                    Product.active,
                    Product.verification_status.in_(
                        ["VERIFIED", "DEMO_FIXTURE"] if settings().demo_mode else ["VERIFIED"]
                    ),
                )
            )
            or 0
        )
        sql_started = time.perf_counter()
        # Server-side cursor avoids materializing all candidates in Python memory.
        result = db.execute(
            text(CANDIDATE_SQL).execution_options(stream_results=True, yield_per=500),
            {"job_id": job_id, "demo": settings().demo_mode},
        )
        sql_seconds = time.perf_counter() - sql_started
        candidates = persisted = 0
        batch = []
        mapped = result.mappings()

        def fetched() -> Any:
            nonlocal sql_seconds
            while True:
                start_fetch = time.perf_counter()
                chunk = mapped.fetchmany(settings().batch_size)
                sql_seconds += time.perf_counter() - start_fetch
                if not chunk:
                    return
                yield from chunk

        for row in fetched():
            candidate = dict(row)
            candidates += 1
            record = match_record(job_id, candidate)
            status = record["status"]
            if (
                proposed is not None
                and proposed.pop((candidate["user_id"], candidate["product_id"]), None) != status
            ):
                raise ValueError(
                    "Workflow evaluation disagrees with current criteria; retry from SQL prefilter"
                )
            batch.append(record)
            if len(batch) >= settings().batch_size:
                db.execute(insert(Match).values(batch).on_conflict_do_nothing())
                persisted += len(batch)
                batch.clear()
        result.close()
        if proposed:
            raise ValueError("Workflow supplied unsupported candidates")
        # Cursor consumption includes persistence; measure isolated SQL separately with EXPLAIN in benchmark.
        candidate_pipeline_seconds = time.perf_counter() - sql_started
        if batch:
            db.execute(insert(Match).values(batch).on_conflict_do_nothing())
            persisted += len(batch)
        naive = users * products
        metrics = {
            "matching_version": VERSION,
            "total_users": users,
            "total_active_products": products,
            "naive_candidates": naive,
            "sql_candidates": candidates,
            "advanced_candidates": candidates,
            "matches_created": persisted,
            "llm_evaluations": 0,
            "estimated_llm_calls_avoided": naive,
            "reduction_percentage": round(100 * (1 - candidates / naive), 3) if naive else 0,
            "candidate_pipeline_seconds": candidate_pipeline_seconds,
            "sql_execution_seconds": sql_seconds,
            "sql_timing_scope": "backend cursor execute plus fetch, including client transfer; excludes persistence",
            "sql_prefilter_passes": 2 if execution_id else 1,
            "matching_seconds": time.perf_counter() - started,
        }
        if execution_id:
            metrics["persisted_by_n8n_execution_id"] = execution_id
        db.add(
            Audit(
                job_id=job_id,
                workflow="B",
                status="PERSISTED" if execution_id else "COMPLETED",
                metrics=metrics,
            )
        )
        if not execution_id:  # Domain-only tests/adapters; HTTP always requires n8n evaluation and final ack.
            db.execute(insert(Outbox).values(job_id=job_id, workflow="C").on_conflict_do_nothing())
        return metrics


def complete_matching(job_id: str, execution_id: str) -> dict[str, Any]:
    """Called by B's final HTTP node, after metrics validation. Never enqueue C on persistence alone."""
    with Session(engine()) as db, db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        audit = db.scalar(select(Audit).where(Audit.job_id == job_id, Audit.workflow == "B"))
        if not job or not audit or audit.status not in {"PERSISTED", "COMPLETED"}:
            raise ValueError("Matching must persist successfully before completion")
        if audit.status == "PERSISTED":
            audit.status = "COMPLETED"
            audit.metrics = {**audit.metrics, "completed_by_n8n_execution_id": execution_id}
            db.execute(insert(Outbox).values(job_id=job_id, workflow="C").on_conflict_do_nothing())
        return {"job_id": job_id, "status": audit.status, "metrics": audit.metrics}


def naive_pairs(db: Session, job_id: str) -> set[tuple[int, int, str]]:
    """Benchmark oracle only; production always uses the SQL prefilter."""
    users = db.scalars(select(User).where(User.job_id == job_id)).all()
    products = db.execute(
        select(Product, Criteria)
        .join(Criteria)
        .where(
            Product.active,
            Product.verification_status.in_(
                ["VERIFIED", "DEMO_FIXTURE"] if settings().demo_mode else ["VERIFIED"]
            ),
        )
    ).all()
    pairs = set()
    for user in users:
        for product, criteria in products:
            if any(
                threshold is not None and actual < threshold
                for actual, threshold in [
                    (user.monthly_income, criteria.minimum_monthly_income),
                    (user.credit_score, criteria.minimum_credit_score),
                    (user.age, criteria.age_min),
                ]
            ):
                continue
            if criteria.age_max is not None and user.age > criteria.age_max:
                continue
            if (
                criteria.employment_requirements is not None
                and user.employment_status not in criteria.employment_requirements
            ):
                continue
            values = {
                key: getattr(criteria, key)
                for key in [
                    "minimum_monthly_income",
                    "minimum_credit_score",
                    "age_min",
                    "age_max",
                    "employment_requirements",
                    "qualitative_requirements",
                ]
            }
            values["criteria_complete"] = product.criteria_complete
            pairs.add((user.id, product.id, advanced(values)[0]))
    return pairs
