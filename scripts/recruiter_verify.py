"""Read-only independent pair oracle and retained n8n execution evidence."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from app.config import settings
from app.db import engine
from app.models import Audit, Criteria, Job, Match, Notification, Outbox, Product, User
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id")
    args = parser.parse_args()
    job_id = args.job_id or json.loads(Path("reports/e2e.json").read_text())["job_id"]
    cfg = settings()
    with Session(engine()) as db:
        job = db.get(Job, job_id)
        assert job and job.status == "COMPLETED"
        users = db.scalars(select(User).where(User.job_id == job_id)).all()
        assert len(users) == job.accepted == 10000
        assert len({u.external_id for u in users}) == 10000
        assert job.checksum == hashlib.sha256(Path("users.csv").read_bytes()).hexdigest()
        products = db.execute(
            select(Product, Criteria)
            .join(Criteria)
            .where(
                Product.active,
                Product.verification_status.in_(
                    ["VERIFIED", "DEMO_FIXTURE"] if cfg.demo_mode else ["VERIFIED"]
                ),
            )
        ).all()
        expected = set()
        for user in users:
            for product, criteria in products:
                checks = [
                    (user.monthly_income, criteria.minimum_monthly_income, True),
                    (user.credit_score, criteria.minimum_credit_score, True),
                    (user.age, criteria.age_min, True),
                    (user.age, criteria.age_max, False),
                ]
                if any(
                    bound is not None and (value < bound if lower else value > bound)
                    for value, bound, lower in checks
                ):
                    continue
                if (
                    criteria.employment_requirements is not None
                    and user.employment_status not in criteria.employment_requirements
                ):
                    continue
                unknown = (
                    any(
                        value is None
                        for value in [
                            criteria.minimum_monthly_income,
                            criteria.minimum_credit_score,
                            criteria.age_min,
                            criteria.age_max,
                            criteria.employment_requirements,
                        ]
                    )
                    or bool(criteria.qualitative_requirements)
                    or not product.criteria_complete
                )
                expected.add((user.id, product.id, "REVIEW_REQUIRED" if unknown else "POSSIBLY_ELIGIBLE"))
        matches = db.scalars(select(Match).where(Match.job_id == job_id)).all()
        actual = {(m.user_id, m.product_id, m.status) for m in matches}
        assert actual == expected and len(matches) == len(actual)
        events = db.scalars(select(Notification).where(Notification.job_id == job_id)).all()
        eligible = {u for u, p, s in expected if s == "POSSIBLY_ELIGIBLE"}
        assert {e.user_id for e in events} == eligible
        assert len(events) == len(eligible) and all(e.status == "SENT" for e in events)
        assert {e.destination for e in events} == {cfg.notification_test_inbox}
        assert not db.scalar(
            select(func.count())
            .select_from(User)
            .where(func.lower(User.email) == cfg.notification_test_inbox.lower())
        )
        audits = {a.workflow: a for a in db.scalars(select(Audit).where(Audit.job_id == job_id))}
        assert audits["B"].status == audits["C"].status == "COMPLETED"
        execution_ids = {
            str(audits["B"].metrics["persisted_by_n8n_execution_id"]),
            str(audits["B"].metrics["completed_by_n8n_execution_id"]),
            str(audits["C"].metrics["n8n_execution_id"]),
        }
        outbox = [
            {
                "workflow": e.workflow,
                "status": e.status,
                "attempts": e.attempts,
                "progress_count": e.progress_count,
            }
            for e in db.scalars(select(Outbox).where(Outbox.job_id == job_id))
        ]
        assert len(outbox) == 2 and all(e["status"] == "DELIVERED" for e in outbox)
        report = {
            "job_id": job_id,
            "csv_sha256": job.checksum,
            "users": len(users),
            "distinct_external_ids": len({u.external_id for u in users}),
            "duplicate_match_groups": 0,
            "independent_pair_oracle_equal": True,
            "outcomes": dict(Counter(m.status for m in matches)),
            "products": [
                {
                    "id": p.id,
                    "lender": p.lender,
                    "verification_status": p.verification_status,
                    "source_url": p.source_url,
                    "criteria_complete": p.criteria_complete,
                }
                for p, c in products
            ],
            "per_product_outcomes": [
                {"product_id": p, "status": s, "count": n}
                for (p, s), n in Counter((m.product_id, m.status) for m in matches).items()
            ],
            "notifications_sent": len(events),
            "outbox": outbox,
            "audits": {k: a.metrics for k, a in audits.items()},
            "scope": "Independent Cartesian oracle uses current product criteria; historical comparisons require unchanged criteria or retained match snapshots. No production matching function called.",
        }
    n8n = create_engine(cfg.database_url.rsplit("/", 1)[0] + "/n8n")
    discovery = json.loads(Path("reports/e2e.json").read_text())["discovery"]
    execution_ids.update(item["detail"].rsplit(" ", 1)[1] for item in discovery)
    for _ in range(30):
        with n8n.connect() as db:
            executions = []
            for execution_id in sorted(execution_ids, key=int):
                meta = (
                    db.execute(
                        text(
                            'SELECT id,status,finished,"workflowId" AS workflow_id FROM execution_entity WHERE id=:id'
                        ),
                        {"id": int(execution_id)},
                    )
                    .mappings()
                    .one()
                )
                executions.append(dict(meta))
            if all(e["status"] == "success" and e["finished"] for e in executions):
                for execution in executions:
                    raw = db.execute(
                        text('SELECT data FROM execution_data WHERE "executionId"=:id'),
                        {"id": execution["id"]},
                    ).scalar_one()
                    flat = json.loads(raw)

                    def ref(value, flat=flat):
                        return flat[int(value)] if isinstance(value, str) and value.isdigit() else value

                    runs = ref(ref(flat[0]["resultData"])["runData"])
                    execution["nodes"] = {
                        name: [
                            {
                                "status": ref(ref(item).get("executionStatus")),
                                "milliseconds": ref(item).get("executionTime"),
                            }
                            for item in ref(items)
                        ]
                        for name, items in runs.items()
                    }
                    assert all(
                        r["status"] == "success" for items in execution["nodes"].values() for r in items
                    )
                break
        time.sleep(1)
    else:
        raise RuntimeError("Referenced n8n executions not retained and successfully completed")
    report["n8n_executions"] = executions
    imported = []
    with n8n.connect() as db:
        for path in sorted(Path("n8n/workflows").glob("*.json")):
            export = json.loads(path.read_text(encoding="utf-8"))
            stored = (
                db.execute(
                    text('SELECT nodes,connections,"activeVersionId" FROM workflow_entity WHERE id=:id'),
                    {"id": export["id"]},
                )
                .mappings()
                .one()
            )
            assert stored["nodes"] == export["nodes"] and stored["connections"] == export["connections"]
            assert stored["activeVersionId"]
            imported.append(
                {
                    "workflow_id": export["id"],
                    "file": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "stored_nodes_equal": True,
                    "stored_connections_equal": True,
                    "published_version": stored["activeVersionId"],
                }
            )
    report["imports"] = imported
    Path("reports/workflow-import.json").write_text(json.dumps(imported, indent=2), encoding="utf-8")
    batches = []
    with n8n.connect() as db:
        records = db.execute(
            text(
                'SELECT e.id,e.status,e.finished,d.data FROM execution_entity e JOIN execution_data d ON d."executionId"=e.id WHERE e."workflowId"=\'loan-workflow-c\' AND d.data LIKE :job ORDER BY e.id'
            ),
            {"job": "%" + job_id + "%"},
        ).mappings()
        for record in records:
            assert record["status"] == "success" and record["finished"]
            flat = json.loads(record["data"])

            def ref(value, flat=flat):
                return flat[int(value)] if isinstance(value, str) and value.isdigit() else value

            runs = ref(ref(flat[0]["resultData"])["runData"])
            run = ref(ref(runs["Grouped allowlisted delivery"])[0])
            outputs = ref(ref(run["data"])["main"])
            item = ref(ref(outputs[0])[0])
            payload = ref(item["json"])
            batches.append(
                {"execution_id": record["id"], "sent": payload["sent"], "pending": payload["pending"]}
            )
    assert sum(batch["sent"] for batch in batches) == report["notifications_sent"]
    report["notification_batch_executions"] = batches
    Path("reports/recruiter-verification.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
