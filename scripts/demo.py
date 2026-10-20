"""Real n8n A/B/C local run; verifies this job's Mailpit Message-IDs."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import httpx
from app.config import settings
from app.db import engine
from app.models import CrawlRun, Job, Notification
from sqlalchemy import select
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--job-id", help="Observe an existing dashboard upload instead of uploading again")
    args = parser.parse_args()
    cfg = settings()
    if cfg.email_delivery_mode != "preview":
        raise SystemExit("This automated demonstration requires Mailpit preview mode")
    headers = {"Authorization": "Bearer " + cfg.api_token}
    started = time.monotonic()
    with httpx.Client(base_url="http://127.0.0.1:8000", headers=headers, timeout=60) as client:
        with Session(engine()) as db:
            previous = set(db.scalars(select(CrawlRun.id)))
        client.post("/api/discovery/demo").raise_for_status()
        for _ in range(60):
            with Session(engine()) as db:
                crawls = db.scalars(select(CrawlRun).where(CrawlRun.status == "FIXTURE")).all()
                fresh = [r for r in crawls if r.id not in previous and "n8n execution" in r.detail]
                if len({r.source_url for r in fresh}) == 3:
                    discovery = [{"source_url": r.source_url, "detail": r.detail} for r in fresh]
                    break
            time.sleep(1)
        else:
            raise RuntimeError("n8n A did not fetch, extract and upsert all three fixtures")
        job_id = args.job_id
        if not job_id:
            data = Path("users.csv").read_bytes()
            response = client.post(
                "/api/uploads",
                json={
                    "filename": "users.csv",
                    "size": len(data),
                    "checksum": hashlib.sha256(data).hexdigest(),
                },
            )
            response.raise_for_status()
            upload = response.json()
            httpx.put(upload["url"], content=data, headers=upload["headers"], timeout=60).raise_for_status()
            job_id = upload["job_id"]
            client.post(f"/api/uploads/{job_id}/complete").raise_for_status()
            print("Uploaded job " + job_id, flush=True)
        while time.monotonic() - started < args.timeout:
            try:
                response = client.get("/api/dashboard", params={"job_id": job_id})
            except httpx.TransportError as exc:
                print(f"Observation interrupted ({type(exc).__name__}); retrying read only", flush=True)
                time.sleep(3)
                continue
            response.raise_for_status()
            state = response.json()
            job = state["jobs"][0]
            if job["status"] == "FAILED":
                raise RuntimeError(job["error_summary"])
            audits = {a["workflow"]: a for a in state["workflows"]}
            if all(audits.get(k, {}).get("status") == "COMPLETED" for k in ["B", "C"]):
                break
            time.sleep(3)
        else:
            raise TimeoutError(
                "Inspect n8n executions and outbox; no completion inferred from HTTP acceptance"
            )
    with Session(engine()) as db:
        events = db.scalars(select(Notification).where(Notification.job_id == job_id)).all()
        assert events and all(e.status == "SENT" and e.provider_id for e in events)
        expected = {e.provider_id.strip("<>") for e in events}
        assert len(expected) == len(events)
        assert {e.destination for e in events} == {cfg.notification_test_inbox}
        persisted_job = db.get(Job, job_id)
        assert persisted_job is not None
        pipeline_seconds = (max(e.updated_at for e in events) - persisted_job.created_at).total_seconds()
    captured = {}
    with httpx.Client(base_url="http://127.0.0.1:8025", timeout=30) as mail:
        response = mail.get("/api/v1/messages", params={"limit": 100})
        response.raise_for_status()
        total = response.json()["total"]
        for offset in range(0, total, 100):
            page = mail.get("/api/v1/messages", params={"start": offset, "limit": 100})
            page.raise_for_status()
            for message in page.json()["messages"]:
                message_id = message.get("MessageID", "").strip("<>")
                if message_id in expected:
                    assert {r["Address"] for r in message["To"]} == {cfg.notification_test_inbox}
                    captured[message_id] = message["ID"]
        assert expected == set(captured), f"Missing {len(expected - set(captured))} job-specific messages"
        sample = mail.get("/api/v1/message/" + next(iter(captured.values())))
        sample.raise_for_status()
        body = sample.json()
        assert body["HTML"] and body["Text"] and "preliminary" in body["Text"].lower()
    report = {
        "job_id": job_id,
        "ingestion": job,
        "audits": audits,
        "discovery": discovery,
        "mailpit_total": total,
        "job_messages_verified": len(captured),
        "sample_mailpit_id": body["ID"],
        "recipient_allowlist_verified": True,
        "elapsed_seconds": time.monotonic() - started,
        "elapsed_scope": "This observer invocation, including any repeated A discovery; not original upload duration",
        "upload_to_last_sent_seconds": pipeline_seconds,
        "delivery": "Mailpit SMTP capture; AWS SES NOT tested",
        "upload_surface": "existing job" if args.job_id else "HTTP API (browser interaction not tested)",
    }
    Path("reports/e2e.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
