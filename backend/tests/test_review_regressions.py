from unittest.mock import Mock

import httpx
import pytest
from app.config import settings
from app.ingestion import ingest
from app.main import app
from app.matching import complete_matching, run_matching
from app.models import Audit, IngestionError, Match, Notification, Outbox, User
from app.notifications import notify
from app.worker import dispatch_tick
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.tests.test_integration import csv_bytes, product, register
from backend.tests.test_validation import valid_row

pytestmark = pytest.mark.integration


def test_c_not_queued_until_final_b_ack(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    p = product(pg)
    user_id = pg.scalar(select(User.id))
    run_matching(job.id, [{"user_id": user_id, "product_id": p.id, "status": "POSSIBLY_ELIGIBLE"}], "123")
    assert pg.scalar(select(Audit.status).where(Audit.workflow == "B")) == "PERSISTED"
    assert not pg.scalar(select(Outbox.id).where(Outbox.workflow == "C"))
    with pytest.raises(ValueError, match="complete"):
        notify(job.id)
    assert complete_matching(job.id, "123")["status"] == "COMPLETED"
    complete_matching(job.id, "124")
    assert pg.scalar(select(func.count()).select_from(Outbox).where(Outbox.workflow == "C")) == 1


def test_http_matching_requires_orchestrated_payload(pg):
    client = TestClient(app)
    headers = {"X-Workflow-Secret": settings().workflow_secret}
    assert client.post("/internal/matching/example", headers=headers).status_code == 422
    assert (
        client.post("/internal/matching/example", headers=headers, json={"execution_id": "12"}).status_code
        == 422
    )
    assert client.post("/internal/notifications/example", headers=headers).status_code == 422


def test_stale_running_audit_cannot_reset_retry_budget(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    pg.add(
        Audit(
            job_id=job.id, workflow="C", status="RUNNING", metrics={"sent_total": 0, "last_batch_sent": 100}
        )
    )
    event = Outbox(job_id=job.id, workflow="C", attempts=19, progress_count=0)
    pg.add(event)
    pg.commit()
    monkeypatch.setattr(
        "app.worker.httpx.post",
        Mock(return_value=httpx.Response(200, request=httpx.Request("POST", "http://n8n.test"))),
    )
    assert dispatch_tick()
    pg.expire_all()
    assert pg.get(Outbox, event.id).status == "DEAD"


def test_real_new_progress_resets_retry_budget(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    pg.add(Audit(job_id=job.id, workflow="C", status="RUNNING", metrics={"sent_total": 200}))
    event = Outbox(job_id=job.id, workflow="C", attempts=19, progress_count=100)
    pg.add(event)
    pg.commit()
    monkeypatch.setattr(
        "app.worker.httpx.post",
        Mock(return_value=httpx.Response(200, request=httpx.Request("POST", "http://n8n.test"))),
    )
    dispatch_tick()
    pg.expire_all()
    saved = pg.get(Outbox, event.id)
    assert (saved.status, saved.attempts, saved.progress_count) == ("PENDING", 0, 200)


def test_notification_uses_matched_product_snapshot(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    p = product(pg)
    p.rate_representation = "Fictional starting from 12.5%"
    pg.commit()
    run_matching(job.id)
    p.rate_representation = "Changed after matching"
    pg.commit()
    capture = Mock(return_value="preview-provider-id")
    monkeypatch.setattr("app.notifications.deliver", capture)
    notify(job.id)
    assert capture.call_args.args[2][0]["rate_representation"] == "Fictional starting from 12.5%"


def test_actual_checksum_mismatch_rolls_back(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    job.checksum = "0" * 64
    pg.commit()
    with pytest.raises(ValueError, match="Checksum"):
        ingest(job.id)
    assert pg.scalar(select(func.count()).select_from(User)) == 0
    assert pg.scalar(select(func.count()).select_from(Match)) == 0


def test_duplicate_row_error_has_exact_source_line(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row(), valid_row(), valid_row(user_id="bad", age="-1")]))
    ingest(job.id)
    assert pg.scalars(select(IngestionError.row_number).order_by(IngestionError.row_number)).all() == [3, 4]


def test_concurrent_notification_batches_finish_consistently(pg, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    job = register(pg, monkeypatch, csv_bytes([valid_row(user_id="one"), valid_row(user_id="two")]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    barrier = Barrier(2)

    def capture(*args):
        barrier.wait(timeout=10)
        return "preview-provider-id"

    monkeypatch.setattr("app.notifications.deliver", capture)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(notify, job.id, 1) for _ in range(2)]
        assert sum(f.result(timeout=20)["sent"] for f in futures) == 2
    assert pg.scalar(select(func.count()).select_from(Notification).where(Notification.status == "SENT")) == 2
    audit = pg.scalar(select(Audit).where(Audit.workflow == "C"))
    assert audit.status == "COMPLETED"
    assert audit.metrics["sent_total"] == 2


def test_upload_csp_uses_configured_object_storage_origin(monkeypatch):
    monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "https://storage.example.org/prefix")
    settings.cache_clear()
    try:
        response = TestClient(app).get("/")
        policy = response.headers["Content-Security-Policy"]
        assert "connect-src 'self' https://storage.example.org;" in policy
        assert "localhost:9000" not in policy
        monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "")
        monkeypatch.setenv("S3_ENDPOINT", "")
        settings.cache_clear()
        response = TestClient(app).get("/")
        assert (
            f"https://{settings().s3_bucket}.s3.{settings().aws_region}.amazonaws.com"
            in response.headers["Content-Security-Policy"]
        )
        from urllib.parse import urlsplit

        from app.storage import s3

        s3.cache_clear()
        signed = s3(public=True).generate_presigned_url(
            "put_object", Params={"Bucket": settings().s3_bucket, "Key": "uploads/synthetic.csv"}
        )
        parsed = urlsplit(signed)
        assert f"{parsed.scheme}://{parsed.netloc}" in response.headers["Content-Security-Policy"]
        s3.cache_clear()
    finally:
        settings.cache_clear()


def test_sqs_failure_state_and_successful_recovery(pg, monkeypatch):
    import json

    from app.ingestion import process_sqs
    from app.models import Job

    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    message = {
        "messageId": "synthetic-sqs",
        "attributes": {"ApproximateReceiveCount": "1"},
        "body": json.dumps(
            {"Records": [{"s3": {"bucket": {"name": settings().s3_bucket}, "object": {"key": job.file_key}}}]}
        ),
    }
    from app.ingestion import s3

    storage = s3()
    original = storage.get_object.side_effect
    storage.get_object.side_effect = RuntimeError("private-detail@example.org")
    assert process_sqs({"Records": [message]}) == {"batchItemFailures": [{"itemIdentifier": "synthetic-sqs"}]}
    pg.expire_all()
    failed = pg.get(Job, job.id)
    assert failed.status == "RETRY" and failed.attempts == 1
    assert "private-detail" not in failed.error_summary
    storage.get_object.side_effect = original
    assert process_sqs({"Records": [message]}) == {"batchItemFailures": []}
    pg.expire_all()
    assert pg.get(Job, job.id).status == "COMPLETED" and pg.get(Job, job.id).error_summary is None


def test_sqs_final_receive_marks_registered_job_failed(pg, monkeypatch):
    import json

    from app.ingestion import process_sqs
    from app.models import Job

    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    from app.ingestion import s3

    s3().get_object.side_effect = RuntimeError("synthetic storage outage")
    message = {
        "messageId": "synthetic-final",
        "attributes": {"ApproximateReceiveCount": "5"},
        "body": json.dumps(
            {"Records": [{"s3": {"bucket": {"name": settings().s3_bucket}, "object": {"key": job.file_key}}}]}
        ),
    }
    assert process_sqs({"Records": [message]}) == {
        "batchItemFailures": [{"itemIdentifier": "synthetic-final"}]
    }
    pg.expire_all()
    assert pg.get(Job, job.id).status == "FAILED" and pg.get(Job, job.id).attempts == 1
