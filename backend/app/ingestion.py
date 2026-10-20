import hashlib
import io
import logging
import tempfile
from contextlib import closing
from typing import Any
from urllib.parse import unquote_plus

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import IngestionError, Job, Outbox, User, now
from app.storage import s3
from app.validation import rows


def ingest(job_id: str, version: str | None = None) -> dict[str, Any]:
    cfg = settings()
    with Session(engine()) as db, db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job:
            raise ValueError("Unknown job")
        if job.status == "COMPLETED":
            return {"id": job.id, "accepted": job.accepted, "rejected": job.rejected}
        if job.status not in {"UPLOADING", "READY", "RETRY"}:
            raise ValueError("Job is not ingestible")
        job.started_at = now()
        params = {"Bucket": cfg.s3_bucket, "Key": job.file_key}
        selected_version = version or job.object_version
        if selected_version:
            params["VersionId"] = selected_version
        response = s3().get_object(**params)
        if response["ContentLength"] != job.size or job.size > cfg.max_upload_bytes:
            response["Body"].close()
            raise ValueError("Object size mismatch")
        # Bounded memory; spool to disk for a checksum pass and then streaming CSV.
        with tempfile.TemporaryFile() as temp, closing(response["Body"]) as body:
            digest = hashlib.sha256()
            size = 0
            for chunk in body.iter_chunks(chunk_size=65536):
                size += len(chunk)
                if size > cfg.max_upload_bytes:
                    raise ValueError("Upload too large")
                digest.update(chunk)
                temp.write(chunk)
            if digest.hexdigest() != job.checksum:
                raise ValueError("Checksum mismatch")
            temp.seek(0)
            pending: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            accepted = rejected = 0

            def flush() -> None:
                nonlocal accepted, rejected
                if pending:
                    stmt = (
                        insert(User)
                        .values(pending)
                        .on_conflict_do_nothing(index_elements=["job_id", "external_id"])
                        .returning(User.source_row)
                    )
                    inserted_rows = set(db.execute(stmt).scalars())
                    inserted = len(inserted_rows)
                    accepted += inserted
                    rejected += len(pending) - inserted
                    # Duplicate rows are recorded as errors without storing personal values.
                    if inserted != len(pending):
                        errors.extend(
                            {
                                "job_id": job.id,
                                "row_number": item["source_row"],
                                "reason": "Duplicate external ID in this upload",
                            }
                            for item in pending
                            if item["source_row"] not in inserted_rows
                        )
                    pending.clear()
                if errors:
                    db.execute(insert(IngestionError), errors)
                    errors.clear()

            with io.TextIOWrapper(temp, encoding="utf-8-sig", errors="strict", newline="") as text:
                for number, row, error in rows(text):
                    if error:
                        rejected += 1
                        errors.append({"job_id": job.id, "row_number": number, "reason": error})
                    elif row:
                        data = row.model_dump()
                        data["external_id"] = data.pop("user_id")
                        pending.append({**data, "job_id": job.id, "source_row": number})
                    if len(pending) + len(errors) >= cfg.batch_size:
                        flush()
                flush()
        job.accepted, job.rejected = accepted, rejected
        job.status, job.completed_at = "COMPLETED", now()
        job.error_summary = None
        job.object_version = response.get("VersionId")
        db.execute(insert(Outbox).values(job_id=job.id, workflow="B").on_conflict_do_nothing())
        return {"id": job.id, "accepted": accepted, "rejected": rejected}


def process_sqs(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    import json

    failures = []
    for message in event.get("Records", []):
        job_id = None
        try:
            payload = json.loads(message["body"])
            if payload.get("Event") == "s3:TestEvent":
                continue
            for record in payload["Records"]:
                if record["s3"]["bucket"]["name"] != settings().s3_bucket:
                    raise ValueError("Unexpected bucket")
                key = unquote_plus(record["s3"]["object"]["key"])
                with Session(engine()) as db:
                    job_id = db.scalar(select(Job.id).where(Job.file_key == key))
                if not job_id:
                    raise ValueError("Unregistered upload")
                ingest(job_id, record["s3"]["object"].get("versionId"))
        except Exception as exc:
            # The queue owns transient retries and redrive; do not acknowledge failed records.
            logging.getLogger(__name__).warning(
                "SQS ingestion failed message=%s type=%s", message["messageId"], type(exc).__name__
            )
            if job_id:
                try:
                    receives = int(message.get("attributes", {}).get("ApproximateReceiveCount", "1"))
                except (ValueError, TypeError):
                    receives = 1
                try:
                    with Session(engine()) as db, db.begin():
                        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
                        if job and job.status != "COMPLETED":
                            job.attempts += 1
                            job.status = "FAILED" if receives >= 5 else "RETRY"
                            job.error_summary = f"{type(exc).__name__}: SQS ingestion failed; inspect object integrity and DLQ"
                except Exception:
                    # A DB outage must not suppress the original SQS partial failure response.
                    logging.getLogger(__name__).warning("Failure audit unavailable job=%s", job_id)
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}
