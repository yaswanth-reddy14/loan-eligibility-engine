import argparse
import logging
import signal
import threading
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.ingestion import ingest
from app.models import Audit, Job, Outbox, now

log = logging.getLogger(__name__)
stopping = threading.Event()


def ingestion_tick() -> bool:
    with Session(engine()) as db:
        job_id = db.scalar(
            select(Job.id).where(Job.status.in_(["READY", "RETRY"])).order_by(Job.created_at).limit(1)
        )
    if not job_id:
        return False
    try:
        ingest(job_id)
    except Exception as exc:
        with Session(engine()) as db, db.begin():
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            # Another worker may have completed (or exhausted) this job after our
            # ingestion transaction rolled back, before this error audit got the lock.
            if job is None or job.status not in {"READY", "RETRY"}:
                return True
            job.attempts += 1
            job.status = "FAILED" if job.attempts >= 5 else "RETRY"
            job.error_summary = (
                type(exc).__name__ + ": ingestion failed; inspect validation and object integrity"
            )
            attempts = job.attempts
        log.warning("Ingestion failed job=%s type=%s", job_id, type(exc).__name__)
        stopping.wait(min(2**attempts, 30))
    return True


def dispatch_tick() -> bool:
    # Hold row lock while making bounded HTTP request. Multiple dispatchers skip locked rows.
    with Session(engine()) as db, db.begin():
        event = db.scalar(
            select(Outbox)
            .where(Outbox.status == "PENDING", Outbox.next_attempt_at <= now())
            .order_by(Outbox.next_attempt_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not event:
            return False
        audit = db.scalar(select(Audit).where(Audit.job_id == event.job_id, Audit.workflow == event.workflow))
        if audit and audit.status in {"COMPLETED", "REVIEW_REQUIRED"}:
            event.status = "DELIVERED"
            return True
        try:
            response = httpx.post(
                f"{settings().n8n_url}/webhook/loan-{event.workflow.lower()}",
                json={"job_id": event.job_id, "event_id": event.id},
                headers={"X-Workflow-Secret": settings().workflow_secret},
                timeout=30,
            )
            response.raise_for_status()
            # Webhook acceptance is not completion. Audit callback is the acknowledgement.
            event.next_attempt_at = now() + timedelta(
                seconds=5 if audit and audit.status == "RUNNING" else 20
            )
            event.attempts += 1
            progress = int(audit.metrics.get("sent_total", 0)) if audit else 0
            if progress > event.progress_count:
                event.progress_count = progress
                event.attempts = 0  # Reset only on newly observed delivery progress, never stale RUNNING.
            if event.attempts >= 20:
                event.status = "DEAD"
                event.last_error = "No completion audit after 20 dispatches; operator review required"
        except httpx.HTTPError as exc:
            event.attempts += 1
            event.last_error = type(exc).__name__
            event.status = "DEAD" if event.attempts >= 20 else "PENDING"
            event.next_attempt_at = now() + timedelta(seconds=min(2**event.attempts, 300))
    return True


def request_stop(*_: Any) -> None:
    stopping.set()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["ingestion", "dispatcher"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    tick = ingestion_tick if args.mode == "ingestion" else dispatch_tick
    while not stopping.is_set():
        try:
            if not tick():
                stopping.wait(2)
        except Exception:
            log.exception("Worker tick failed")
            stopping.wait(5)


if __name__ == "__main__":
    main()
