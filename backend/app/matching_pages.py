"""Job-locked keyset pages; partial matches never release notifications."""

import hashlib
import json
import time
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.matching import CANDIDATE_SQL, VERSION, match_record
from app.models import Audit, Criteria, Job, Match, Product, User

PAGE_SIZE = 1000
PAGE_SQL = (
    "SELECT * FROM (" + CANDIDATE_SQL + ") AS eligible "
    "WHERE (user_id,product_id) > (:after_user_id,:after_product_id) "
    "ORDER BY user_id,product_id LIMIT :page_size"
)


def view(job_id: str, audit: Audit | None) -> dict[str, Any]:
    metrics = audit.metrics if audit else {}
    cursor = metrics.get("cursor", [0, 0])
    return {
        "job_id": job_id,
        "after_user_id": cursor[0],
        "after_product_id": cursor[1],
        "page_size": PAGE_SIZE,
        "more": audit is None or audit.status == "PARTITIONING",
        **metrics,
    }


def progress(job_id: str) -> dict[str, Any]:
    with Session(engine()) as db:
        job = db.get(Job, job_id)
        if not job or job.status != "COMPLETED":
            raise ValueError("A completed ingestion job is required")
        audit = db.scalar(select(Audit).where(Audit.job_id == job_id, Audit.workflow == "B"))
        if audit and audit.metrics.get("matching_version") != VERSION:
            raise ValueError("Matching version changed; create a new job")
        return view(job_id, audit)


def persist_page(
    job_id: str,
    evaluations: list[dict[str, Any]],
    execution_id: str,
    after_user_id: int,
    after_product_id: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    incoming = (after_user_id, after_product_id)
    proposed = {(x["user_id"], x["product_id"]): x["status"] for x in evaluations}
    if len(proposed) != len(evaluations):
        raise ValueError("Duplicate evaluated candidate")
    with Session(engine()) as db, db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.status != "COMPLETED":
            raise ValueError("A completed ingestion job is required")
        audit = db.scalar(select(Audit).where(Audit.job_id == job_id, Audit.workflow == "B"))
        if audit:
            if audit.metrics.get("matching_version") != VERSION:
                raise ValueError("Matching version changed; create a new job")
            if audit.status in {"PERSISTED", "COMPLETED"}:
                return view(job_id, audit)
            if audit.status != "PARTITIONING":
                raise ValueError("Unsupported matching audit state")
        previous = audit.metrics if audit else {}
        cursor = tuple(previous.get("cursor", [0, 0]))
        if incoming < cursor:
            return view(job_id, audit)  # Durable page replay, no duplicate counters or inserts.
        if incoming != cursor:
            raise ValueError("Matching cursor is ahead of persisted progress")
        products = db.execute(
            select(Product, Criteria)
            .join(Criteria)
            .where(
                Product.active,
                Product.verification_status.in_(
                    ["VERIFIED", "DEMO_FIXTURE"] if settings().demo_mode else ["VERIFIED"]
                ),
            )
            .order_by(Product.id)
        ).all()
        evidence = [
            {
                "product": {
                    key: getattr(p, key)
                    for key in [
                        "id",
                        "lender",
                        "product_name",
                        "source_url",
                        "rate_representation",
                        "criteria_complete",
                        "verification_status",
                    ]
                },
                "criteria": {column.name: getattr(c, column.name) for column in Criteria.__table__.columns},
            }
            for p, c in products
        ]
        fingerprint = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
        if previous and previous.get("product_fingerprint") != fingerprint:
            raise ValueError("Product criteria changed during matching; create a new job")
        sql_started = time.perf_counter()
        candidates = [
            dict(row)
            for row in db.execute(
                text(PAGE_SQL),
                {
                    "job_id": job_id,
                    "demo": settings().demo_mode,
                    "after_user_id": after_user_id,
                    "after_product_id": after_product_id,
                    "page_size": PAGE_SIZE,
                },
            ).mappings()
        ]
        sql_seconds = time.perf_counter() - sql_started
        records = [match_record(job_id, row) for row in candidates]
        expected = {(r["user_id"], r["product_id"]): r["status"] for r in records}
        if proposed != expected:
            raise ValueError("Workflow page disagrees with current criteria")
        if candidates:
            db.execute(insert(Match).values(records).on_conflict_do_nothing())
        users = previous.get("total_users")
        if users is None:
            users = db.scalar(select(func.count()).select_from(User).where(User.job_id == job_id)) or 0
        count = int(previous.get("sql_candidates", 0)) + len(candidates)
        naive = users * len(products)
        elapsed = time.perf_counter() - started
        metrics = {
            "matching_version": VERSION,
            "matching_mode": "keyset-pages",
            "total_users": users,
            "total_active_products": len(products),
            "naive_candidates": naive,
            "sql_candidates": count,
            "advanced_candidates": count,
            "matches_created": count,
            "llm_evaluations": 0,
            "estimated_llm_calls_avoided": naive,
            "reduction_percentage": round(100 * (1 - count / naive), 3) if naive else 0,
            "matching_seconds": float(previous.get("matching_seconds", 0)) + elapsed,
            "candidate_pipeline_seconds": float(previous.get("candidate_pipeline_seconds", 0)) + elapsed,
            "sql_execution_seconds": float(previous.get("sql_execution_seconds", 0)) + sql_seconds,
            "sql_timing_scope": "backend page execute plus fetch; excludes n8n and delivery",
            "sql_prefilter_passes": 2,
            "page_count": int(previous.get("page_count", 0)) + 1,
            "cursor": [candidates[-1]["user_id"], candidates[-1]["product_id"]]
            if candidates
            else list(cursor),
            "product_fingerprint": fingerprint,
            "persisted_by_n8n_execution_id": execution_id,
        }
        status = "PARTITIONING" if len(candidates) == PAGE_SIZE else "PERSISTED"
        if audit:
            audit.metrics, audit.status = metrics, status
        else:
            audit = Audit(job_id=job_id, workflow="B", status=status, metrics=metrics)
            db.add(audit)
        return view(job_id, audit)
