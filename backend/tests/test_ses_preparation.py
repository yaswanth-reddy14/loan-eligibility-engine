"""Offline guards for the uninstalled, disabled single-recipient test draft."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.validate_ses_preparation import validate

WORKFLOW = Path("n8n/ses-test/C_ses_single_recipient.disabled.json")


def code(name):
    workflow = json.loads(WORKFLOW.read_text())
    return next(n["parameters"]["jsCode"] for n in workflow["nodes"] if n["name"] == name)


def execute(source, data=None, pinned=None):
    script = (
        "const $json="
        + json.dumps(data or {})
        + ";const pinned="
        + json.dumps(pinned or {})
        + ";const $=()=>({first:()=>({json:pinned})});const $input={all:()=>[{json:$json}]};"
        + "const run=()=>{"
        + source
        + "};console.log(JSON.stringify(run()));"
    )
    return subprocess.run(["node", "-"], input=script, capture_output=True, text=True)


def test_preparation_is_disabled_without_credentials_or_live_identifiers():
    assert validate()["live_send_ready"] is False
    result = execute(code("Pinned approved test job"))
    assert result.returncode != 0 and "approval is absent" in result.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_messages", 2),
        ("region", "us-east-1"),
        ("sandbox_status", "UNVERIFIED"),
        ("credential_installed", False),
        ("sender_verified_in_region", False),
        ("recipient_verified_in_region", False),
        ("account_id", None),
        ("job_id", None),
        ("recipient", "a@invalid,b@invalid"),
    ],
)
def test_pin_guard_rejects_incomplete_or_multi_recipient_approval(field, value):
    source = code("Pinned approved test job")
    original = json.loads(source.split("const plan = ", 1)[1].split(";\n", 1)[0])
    plan = {
        **original,
        "approved": True,
        "sandbox_status": "SANDBOX",
        "credential_installed": True,
        "sender_verified_in_region": True,
        "recipient_verified_in_region": True,
        "account_id": "123456789012",
        "job_id": "11111111-1111-1111-1111-111111111111",
        "sender": "sender@example.invalid",
        "recipient": "recipient@example.invalid",
    }
    plan[field] = value
    source = source.replace(json.dumps(original, separators=(",", ":")), json.dumps(plan))
    assert execute(source).returncode != 0


@pytest.mark.parametrize(
    "accepted,status,job", [(2, "COMPLETED", "test"), (1, "READY", "test"), (1, "COMPLETED", "another")]
)
def test_guard_rejects_multi_user_incomplete_or_unpinned_job(accepted, status, job):
    result = execute(
        code("Require one completed synthetic user"),
        {"id": job, "status": status, "accepted": accepted, "rejected": 0},
        {"job_id": "test"},
    )
    assert result.returncode != 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("to", "other@example.invalid"),
        ("from", "other@example.invalid"),
        ("job_id", "other"),
        ("ready", False),
    ],
)
def test_reserved_event_must_match_exact_approved_job_sender_and_recipient(field, value):
    pinned = {"job_id": "test", "sender": "sender@example.invalid", "recipient": "recipient@example.invalid"}
    data = {
        "job_id": "test",
        "from": pinned["sender"],
        "to": pinned["recipient"],
        "event_id": "event",
        "ready": True,
    }
    data[field] = value
    assert execute(code("Verify reserved single recipient"), data, pinned).returncode != 0


def test_reservation_payload_passes_only_when_it_matches_and_preview_has_no_fallback():
    pinned = {"job_id": "test", "sender": "sender@example.invalid", "recipient": "recipient@example.invalid"}
    data = {
        "job_id": "test",
        "from": pinned["sender"],
        "to": pinned["recipient"],
        "event_id": "event",
        "ready": True,
    }
    assert execute(code("Verify reserved single recipient"), data, pinned).returncode == 0
    assert (
        execute(
            code("Require explicit SES transport"), {"job_id": "test", "n8n_ses": False}, pinned
        ).returncode
        != 0
    )


def test_iam_template_is_sender_identity_scoped_and_requires_recipient_presence():
    policy = json.loads(Path("n8n/ses-test/iam-policy.template.json").read_text())
    (statement,) = policy["Statement"]
    assert statement["Action"] == ["ses:SendEmail"]
    assert statement["Resource"] == ["arn:aws:ses:ap-south-1:ACCOUNT_ID:identity/SENDER_EMAIL"]
    assert statement["Condition"]["ForAllValues:StringEquals"]["ses:Recipients"] == ["CONTROLLED_RECIPIENT"]
    assert statement["Condition"]["Null"] == {"ses:Recipients": "false"}
