import json
import time
from pathlib import Path

import httpx
from app.config import settings
from app.db import engine
from sqlalchemy import create_engine, text


def main() -> None:
    cfg = settings()
    job_id = json.loads(Path("reports/e2e.json").read_text())["job_id"]
    n8n_db = create_engine(cfg.database_url.rsplit("/", 1)[0] + "/n8n", connect_args={"connect_timeout": 5})
    with engine().connect() as db:
        before = db.execute(text("SELECT count(*) FROM notification_events WHERE status='SENT'")).scalar_one()
    with n8n_db.connect() as db:
        previous = db.execute(text("SELECT coalesce(max(id),0) FROM execution_entity")).scalar_one()
    with httpx.Client(base_url="http://127.0.0.1:5678", timeout=30) as client:
        for _ in range(30):
            try:
                if client.get("/healthz").is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        rejected = client.post("/webhook/loan-b", json={"job_id": job_id})
        assert rejected.status_code in {401, 403}, rejected.status_code
        for letter in ["b", "c"]:
            response = client.post(
                "/webhook/loan-" + letter,
                json={"job_id": job_id},
                headers={"X-Workflow-Secret": cfg.workflow_secret},
            )
            response.raise_for_status()
    for _ in range(60):
        with n8n_db.connect() as db:
            results = [
                dict(row)
                for row in db.execute(
                    text(
                        'SELECT id,status,finished,"workflowId" AS workflow_id,"startedAt" AS started_at,"stoppedAt" AS stopped_at FROM execution_entity WHERE id > :previous ORDER BY id'
                    ),
                    {"previous": previous},
                ).mappings()
            ]
        if len(results) >= 2 and all(row["status"] == "success" and row["finished"] for row in results):
            with engine().connect() as db:
                after = db.execute(
                    text("SELECT count(*) FROM notification_events WHERE status='SENT'")
                ).scalar_one()
            assert before == after
            for execution in results:
                with n8n_db.connect() as db:
                    raw = db.execute(
                        text('SELECT data FROM execution_data WHERE "executionId"=:id'),
                        {"id": execution["id"]},
                    ).scalar_one()
                flattened = json.loads(raw)

                def ref(value, values=flattened):
                    return values[int(value)] if isinstance(value, str) and value.isdigit() else value

                run_data = ref(ref(flattened[0]["resultData"])["runData"])
                execution["nodes"] = {
                    name: [
                        {
                            "status": ref(ref(item).get("executionStatus")),
                            "milliseconds": ref(item).get("executionTime"),
                        }
                        for item in ref(runs)
                    ]
                    for name, runs in run_data.items()
                }
                assert all(
                    item["status"] == "success" for runs in execution["nodes"].values() for item in runs
                )
            report = {
                "unauthenticated_webhook_status": rejected.status_code,
                "job_id": job_id,
                "executions": results,
                "sent_before": before,
                "sent_after": after,
                "idempotent": True,
            }
            Path("reports/n8n-replay.json").write_text(json.dumps(report, indent=2, default=str))
            print(json.dumps(report, indent=2, default=str))
            return
        time.sleep(1)
    raise RuntimeError("n8n replay did not produce completed success execution metadata")


if __name__ == "__main__":
    main()
