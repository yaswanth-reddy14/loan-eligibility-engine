"""Offline validation only: never loads credentials, contacts AWS or imports workflows."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "n8n" / "ses-test"


def restrict_generated_policy(generated: dict[str, Any]) -> dict[str, Any]:
    """Narrow Autopilot's discovered action; never invent an action from source."""
    import copy

    policy = copy.deepcopy(generated["Policies"][0]["Policy"])
    policy.pop("Id", None)
    statements = policy["Statement"]
    assert len(statements) == 1 and statements[0]["Action"] == ["ses:SendEmail"]
    statement = statements[0]
    statement["Sid"] = "OneControlledRecipient"
    statement["Resource"] = ["arn:aws:ses:ap-south-1:ACCOUNT_ID:identity/SENDER_EMAIL"]
    statement["Condition"] = {
        "StringEquals": {"ses:FromAddress": "SENDER_EMAIL", "aws:RequestedRegion": "ap-south-1"},
        "ForAllValues:StringEquals": {"ses:Recipients": ["CONTROLLED_RECIPIENT"]},
        "Null": {"ses:Recipients": "false"},
    }
    return policy


def validate() -> dict[str, Any]:
    plan = json.loads((PREP / "plan.example.json").read_text())
    assert plan["phase"] == "PREPARATION_ONLY" and plan["approved"] is False
    assert plan["max_messages"] == 1 and plan["production_workflow_change_allowed"] is False
    for key in ["account_id", "sender", "recipient", "job_id"]:
        assert plan[key] is None
    for key in ["credential_installed", "sender_verified_in_region", "recipient_verified_in_region"]:
        assert plan[key] is False

    workflow = json.loads((PREP / "C_ses_single_recipient.disabled.json").read_text())
    assert workflow["id"] == "loan-workflow-c-ses-preparation" and workflow["active"] is False
    names = {n["name"]: n for n in workflow["nodes"]}
    assert len(names) == len(workflow["nodes"])
    assert sum(n["type"].endswith("manualTrigger") for n in names.values()) == 1
    assert not any(n["type"].endswith(("webhook", "scheduleTrigger")) for n in names.values())
    assert "Grouped allowlisted delivery" not in names  # No SMTP fallback in this test graph.
    ses = names["AWS SES controlled test"]
    assert ses["disabled"] is True and ses["retryOnFail"] is False
    assert ses["parameters"]["operation"] == "send" and ses["parameters"]["resource"] == "email"
    assert ses["parameters"]["additionalFields"] == {}
    assert ses["parameters"]["toAddresses"] == "={{[$json.to]}}"
    assert names["Reserve SES event"]["retryOnFail"] is False
    pinned = names["Pinned approved test job"]["parameters"]["jsCode"]
    embedded = json.loads(pinned.split("const plan = ", 1)[1].split(";\n", 1)[0])
    assert embedded == plan
    for node in names.values():
        if node["type"].endswith("httpRequest"):
            assert node["parameters"]["url"].lstrip("=").startswith("http://ses-test-api:8000/")
    for source, links in workflow["connections"].items():
        assert source in names
        for output in links["main"]:
            assert all(link["node"] in names for link in output)
    assert workflow["connections"]["Verify reserved single recipient"]["main"][0][0]["node"] == ses["name"]

    service = json.loads((PREP / "compose.preparation.yml").read_text())["services"]["ses-test-api"]
    env = service["environment"]
    assert service["profiles"] == ["ses-preparation"] and "ports" not in service
    assert env["N8N_SES_ENABLED"] == env["LLM_ENABLED"] == "false"
    assert env["EMAIL_DELIVERY_MODE"] == "preview" and env["SMTP_PORT"] == "9"
    assert env["AWS_REGION"] == plan["region"]
    for key in [
        "SES_SENDER",
        "GEMINI_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ]:
        assert env[key] == ""
    generated = json.loads((ROOT / "reports" / "ses-iam-generated-baseline.json").read_text())
    assert json.loads((PREP / "iam-policy.template.json").read_text()) == restrict_generated_policy(generated)
    return {
        "offline_validation": "PASS",
        "live_send_ready": False,
        "candidate_region": plan["region"],
        "missing": [
            "account/identities",
            "regional verification",
            "credential installation approval",
            "pinned fresh job",
            "send approval",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
