import hashlib
import io
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from app.config import settings
from app.ingestion import ingest, process_sqs
from app.main import app
from app.matching import naive_pairs, run_matching
from app.models import Criteria, Job, Match, Notification, Outbox, Product, User, uid
from app.notifications import notify
from app.validation import HEADERS
from botocore.response import StreamingBody
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.tests.test_validation import valid_row

pytestmark = pytest.mark.integration


def register(db, monkeypatch, data):
    job = Job(
        id=uid(),
        file_key="uploads/" + uid() + "/users.csv",
        checksum=hashlib.sha256(data).hexdigest(),
        size=len(data),
        status="READY",
    )
    db.add(job)
    db.commit()
    storage = Mock()
    storage.get_object.side_effect = lambda **kw: {
        "ContentLength": len(data),
        "Body": StreamingBody(io.BytesIO(data), len(data)),
        "VersionId": "v1",
    }
    monkeypatch.setattr("app.ingestion.s3", lambda: storage)
    return job


def csv_bytes(records):
    import csv

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode()


def product(db, **changes):
    value = Product(
        lender="Fictional",
        product_name="DEMO",
        source_url="https://example.org/" + uid(),
        verification_status="DEMO_FIXTURE",
        criteria_complete=True,
    )
    db.add(value)
    db.flush()
    criteria = Criteria(
        product_id=value.id,
        minimum_monthly_income=Decimal("30000"),
        minimum_credit_score=700,
        age_min=21,
        age_max=60,
        employment_requirements=["SALARIED"],
        qualitative_requirements=[],
    )
    for key, val in changes.items():
        setattr(criteria, key, val)
    db.add(criteria)
    db.commit()
    return value


def test_10000_ingestion_and_idempotency(pg, monkeypatch, input_csv):
    job = register(pg, monkeypatch, input_csv.read_bytes())
    first = ingest(job.id)
    assert first["accepted"] == 10000
    assert ingest(job.id) == first
    assert pg.scalar(select(func.count()).select_from(User)) == 10000
    assert pg.scalar(select(func.count()).select_from(Outbox)) == 1


def test_duplicate_upload_preserves_history(pg, monkeypatch):
    data = csv_bytes([valid_row()])
    first = register(pg, monkeypatch, data)
    ingest(first.id)
    second = register(pg, monkeypatch, data)
    ingest(second.id)
    assert pg.scalar(select(func.count()).select_from(User)) == 2


def test_duplicate_ids_invalid_rows(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row(), valid_row(), valid_row(user_id="bad", age="-1")]))
    result = ingest(job.id)
    assert result["accepted"] == 1 and result["rejected"] == 2


def test_atomic_bad_encoding_and_checksum(pg, monkeypatch):
    for data in [b"invalid,headers\n", b"\xff\xfe"]:
        job = register(pg, monkeypatch, data)
        with pytest.raises((ValueError, UnicodeError)):
            ingest(job.id)
    assert pg.scalar(select(func.count()).select_from(User)) == 0
    assert pg.scalar(select(func.count()).select_from(Outbox)) == 0


def test_worker_retry_records_failure_without_detached_access(pg, monkeypatch):
    from app.worker import ingestion_tick

    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    monkeypatch.setattr("app.worker.ingest", Mock(side_effect=ConnectionError))
    pause = Mock()
    monkeypatch.setattr("app.worker.stopping.wait", pause)
    assert ingestion_tick()
    pg.expire_all()
    saved = pg.get(Job, job.id)
    assert saved.status == "RETRY" and saved.attempts == 1
    pause.assert_called_once_with(2)


def test_sqs_retry_partial_failure(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    payload = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": settings().s3_bucket},
                    "object": {"key": job.file_key, "versionId": "v1"},
                }
            }
        ]
    }
    event = {
        "Records": [
            {"messageId": "good", "body": json.dumps(payload)},
            {"messageId": "bad", "body": "invalid"},
        ]
    }
    assert process_sqs(event) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert process_sqs(event) == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert pg.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("age", "20", 0),
        ("age", "21", 1),
        ("age", "60", 1),
        ("age", "61", 0),
        ("credit_score", "699", 0),
        ("credit_score", "700", 1),
        ("monthly_income", "29999.99", 0),
        ("monthly_income", "30000", 1),
        ("employment_status", "Self-Employed", 0),
    ],
)
def test_matching_boundaries_equivalence_idempotency(pg, monkeypatch, field, value, expected):
    job = register(pg, monkeypatch, csv_bytes([valid_row(**{field: value})]))
    ingest(job.id)
    product(pg)
    oracle = naive_pairs(pg, job.id)
    metrics = run_matching(job.id)
    assert metrics["matches_created"] == expected
    assert run_matching(job.id) == metrics
    actual = {(row.user_id, row.product_id, row.status) for row in pg.scalars(select(Match)).all()}
    assert actual == oracle


def test_unknown_criteria_review_and_no_email(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    product(pg, minimum_credit_score=None)
    run_matching(job.id)
    assert pg.scalar(select(Match.status)) == "REVIEW_REQUIRED"
    assert notify(job.id)["sent"] == 0


def test_unknown_employment_remains_review_candidate(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    product(pg, employment_requirements=None)
    assert run_matching(job.id)["matches_created"] == 1
    assert pg.scalar(select(Match.status)) == "REVIEW_REQUIRED"


def test_workflow_evaluation_cannot_override_rules(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    value = product(pg, minimum_credit_score=None)
    user_id = pg.scalar(select(User.id))
    with pytest.raises(ValueError, match="disagrees"):
        run_matching(job.id, [{"user_id": user_id, "product_id": value.id, "status": "POSSIBLY_ELIGIBLE"}])
    assert pg.scalar(select(func.count()).select_from(Match)) == 0


def test_notifications_deduplicate_and_never_sample_destination(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row(email="original@example.com")]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    delivered = []

    def deliver(event_id, first_name, products):
        from app.notifications import destination

        delivered.append(destination())
        return "captured"

    monkeypatch.setattr("app.notifications.deliver", deliver)
    assert notify(job.id)["sent"] == 1
    assert notify(job.id)["sent"] == 0
    assert delivered == [settings().notification_test_inbox]
    assert "original@example.com" not in delivered
    assert pg.scalar(select(Notification.status)) == "SENT"


def test_ambiguous_send_not_retried(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    monkeypatch.setattr("app.notifications.deliver", Mock(side_effect=TimeoutError))
    with pytest.raises(TimeoutError):
        notify(job.id)
    assert notify(job.id)["sent"] == 0
    assert pg.scalar(select(Notification.status)) == "UNKNOWN"


def test_allowlist_collision_with_source_is_rejected(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row(email="collision@example.com")]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    monkeypatch.setenv("NOTIFICATION_TEST_INBOX", "collision@example.com")
    settings.cache_clear()
    with pytest.raises(ValueError, match="collides"):
        notify(job.id)
    assert pg.scalar(select(func.count()).select_from(Notification)) == 0


def test_api_auth_and_dashboard(pg):
    client = TestClient(app)
    assert client.get("/api/dashboard").status_code == 401
    assert client.post("/internal/matching/invalid").status_code == 401
    assert client.get("/health").status_code == 200
    assert (
        client.get("/api/dashboard", headers={"Authorization": "Bearer " + settings().api_token}).status_code
        == 200
    )
    assert client.get("/").status_code == 200


def test_migration_schema_tables(pg):
    tables = set(
        pg.execute(text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")).scalars()
    )
    assert {
        "users",
        "ingestion_jobs",
        "ingestion_errors",
        "loan_products",
        "product_criteria",
        "matches",
        "notification_events",
        "workflow_outbox",
        "crawler_runs",
        "workflow_run_audit",
    } <= tables
