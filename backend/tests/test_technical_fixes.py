"""Small isolated regressions; no supplied-data ingestion or external email."""

import copy
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from app.config import Settings, settings
from app.ingestion import ingest
from app.main import app
from app.matching import run_matching
from app.models import Job, Notification, User, now, uid
from app.notifications import deliver, notify
from app.worker import ingestion_tick
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.tests.test_integration import csv_bytes, product, register
from backend.tests.test_validation import valid_row
from scripts.validate_config import CloudLoader, validate


def test_setup_builds_all_images_without_overwriting_environment(tmp_path):
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell is needed for the Windows startup harness")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile("scripts/setup.ps1", scripts / "setup.ps1")
    (tmp_path / ".env").write_text("PRIVATE_SENTINEL=unchanged\n")
    code = """
function docker {
    if ($args[0] -ne 'compose') { throw 'Unexpected command' }
    if ($args[1] -eq 'build') {
        $script:built = if ($args.Count -eq 2) { @('api','minio') } else { @($args[2..($args.Count-1)]) }
    } elseif ($args[1] -eq 'up') {
        if ('api' -notin $script:built -or 'minio' -notin $script:built) { throw 'Missing clean-machine image' }
        if ('--no-build' -notin $args) { throw 'Unexpected startup mode' }
    } else { throw 'Unexpected operation' }
    $global:LASTEXITCODE = 0
}
& './scripts/setup.ps1'
"""
    result = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".env").read_text() == "PRIVATE_SENTINEL=unchanged\n"


@pytest.mark.parametrize("scope", ["provider", "function"])
@pytest.mark.parametrize("key", ["AWS_DEFAULT_REGION", "AWS_REGION", "AWS_ACCESS_KEY_ID", "_HANDLER"])
def test_reserved_lambda_environment_rejected(scope, key):
    value = yaml.load(Path("serverless.yml").read_text(), Loader=CloudLoader)
    changed = copy.deepcopy(value)
    target = changed["provider"] if scope == "provider" else changed["functions"]["uploadApi"]
    target.setdefault("environment", {})[key] = "invalid"
    with pytest.raises(ValueError, match="Reserved Lambda"):
        validate(changed)
    validate(value)


def test_lambda_runtime_region_wins_over_local_default(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    cfg = Settings(
        _env_file=None, api_token="test-token-0000000000000000", workflow_secret="test-secret-000000000000000"
    )
    assert cfg.aws_region == "eu-west-1"


@pytest.mark.parametrize(
    "status,attempts,expected", [("READY", 0, "RETRY"), ("RETRY", 4, "FAILED"), ("FAILED", 5, "FAILED")]
)
def test_worker_error_preserves_terminal_states_and_retries(pg, monkeypatch, status, attempts, expected):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    monkeypatch.setattr("app.worker.stopping.wait", Mock())

    def fail(_):
        with Session(pg.bind) as other, other.begin():
            saved = other.get(Job, job.id)
            saved.status, saved.attempts = status, attempts
        raise ConnectionError()

    monkeypatch.setattr("app.worker.ingest", fail)
    assert ingestion_tick()
    pg.expire_all()
    assert pg.get(Job, job.id).status == expected


def test_concurrent_completion_not_overwritten_by_error_audit(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))

    def complete_elsewhere():
        with Session(pg.bind) as other, other.begin():
            other.get(Job, job.id).status = "COMPLETED"

    def fail_after_completion(_):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(complete_elsewhere).result(timeout=10)
        raise ConnectionError()

    pause = Mock()
    monkeypatch.setattr("app.worker.ingest", fail_after_completion)
    monkeypatch.setattr("app.worker.stopping.wait", pause)
    assert ingestion_tick()
    pg.expire_all()
    saved = pg.get(Job, job.id)
    assert saved.status == "COMPLETED" and saved.attempts == 0 and saved.error_summary is None
    pause.assert_not_called()


def test_duplicate_workers_and_replay_are_idempotent(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ingest, [job.id, job.id]))
    assert results[0] == results[1]
    assert pg.scalar(select(func.count()).select_from(User)) == 1
    assert not ingestion_tick()  # Completed jobs are not picked up again.


def test_historical_dashboard_selection_outside_recent_window(pg):
    historical_id = uid()
    for i in range(22):
        pg.add(
            Job(
                id=historical_id if i == 0 else uid(),
                file_key="uploads/" + uid(),
                checksum="0" * 64,
                size=1,
                status="COMPLETED",
                created_at=now() + timedelta(seconds=i),
            )
        )
    pg.commit()
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + settings().api_token}
    recent = client.get("/api/dashboard", headers=headers).json()
    assert len(recent["jobs"]) == 20 and historical_id not in {j["id"] for j in recent["jobs"]}
    selected = client.get("/api/dashboard", params={"job_id": historical_id}, headers=headers).json()
    assert [j["id"] for j in selected["jobs"]] == [historical_id]
    assert len(selected["available_jobs"]) == 21
    assert historical_id in {j["id"] for j in selected["available_jobs"]}


@pytest.mark.parametrize(
    "error",
    [
        None,
        TimeoutError(),
        ClientError({"Error": {"Code": "MessageRejected", "Message": "test"}}, "SendEmail"),
    ],
)
def test_ses_one_sdk_attempt_and_ambiguous_outcomes_not_resent(pg, monkeypatch, error):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "test")
    monkeypatch.setenv("N8N_SES_ENABLED", "false")
    monkeypatch.setenv("SES_SENDER", "verified@example.org")
    settings.cache_clear()
    client = Mock()
    client.send_email.return_value = {"MessageId": "mock-ses-id"}
    client.send_email.side_effect = error
    factory = Mock(return_value=client)
    monkeypatch.setattr("app.notifications.boto3.client", factory)
    if error:
        with pytest.raises(type(error)):
            notify(job.id)
    else:
        assert notify(job.id)["sent"] == 1
    assert notify(job.id)["sent"] == 0
    event = pg.scalar(select(Notification))
    assert event.status == ("UNKNOWN" if error else "SENT")
    assert event.attempts == 1 and client.send_email.call_count == 1
    assert factory.call_args.kwargs["config"].retries["total_max_attempts"] == 1
    assert client.send_email.call_args.kwargs["Destination"] == {
        "ToAddresses": [settings().notification_test_inbox]
    }
    assert callable(deliver)
