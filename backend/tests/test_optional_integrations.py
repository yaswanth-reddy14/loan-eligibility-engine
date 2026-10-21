"""Network-free LLM and reserved-event SES transport regressions."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import httpx
import pytest
from app.config import settings
from app.discovery import extract, store_extraction
from app.ingestion import ingest
from app.llm import qualitative_quotes
from app.matching import run_matching
from app.models import Criteria, Notification, Product
from app.n8n_delivery import claim, finish
from app.notifications import notify, seed_events, summarize
from sqlalchemy import select

from backend.tests.test_integration import csv_bytes, product, register
from backend.tests.test_validation import valid_row


@pytest.fixture(autouse=True)
def disabled_optional_defaults(monkeypatch):
    monkeypatch.setenv("N8N_SES_ENABLED", "false")
    monkeypatch.setenv("LLM_ENABLED", "false")
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture
def ses_gate(monkeypatch):
    monkeypatch.setenv("N8N_SES_ENABLED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "test")
    monkeypatch.setenv("SES_SENDER", "verified@example.org")
    settings.cache_clear()
    yield
    settings.cache_clear()


def matched_job(pg, monkeypatch):
    job = register(pg, monkeypatch, csv_bytes([valid_row()]))
    ingest(job.id)
    product(pg)
    run_matching(job.id)
    return job


def test_ses_claim_disabled_without_explicit_gate():
    with pytest.raises(ValueError, match="explicit enablement"):
        claim("unused", "1")


@pytest.mark.parametrize("provider_output,expected", [
    ({"SendEmailResponse": {"SendEmailResult": {"MessageId": "mock-id"}}}, "SENT"),
    ({"error": {"message": "MessageRejected"}}, "UNKNOWN"),
    ({"error": {"message": "Read timeout"}}, "UNKNOWN"),
    ({"ready": True}, "UNKNOWN"),
])
def test_exported_ses_receipt_code_handles_ack_errors_and_disabled_node(provider_output, expected):
    from pathlib import Path

    workflow = json.loads(Path("n8n/workflows/C_user_notification.json").read_text(encoding="utf-8"))
    code = next(n["parameters"]["jsCode"] for n in workflow["nodes"] if n["name"] == "Build SES receipt")
    script = "const $json=" + json.dumps(provider_output) + ";const $execution={id:'123'};const $=()=>({first:()=>({json:{job_id:'test',event_id:'event'}})});const run=()=>{" + code + "};console.log(JSON.stringify(run()[0].json));"
    result = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, check=True)
    receipt = json.loads(result.stdout)
    assert receipt["status"] == expected
    assert (receipt["provider_id"] is not None) == (expected == "SENT")


def test_changed_inbox_requires_reconciliation_before_any_attempt(pg, monkeypatch):
    job = matched_job(pg, monkeypatch)
    seed_events(job.id)
    monkeypatch.setenv("NOTIFICATION_TEST_INBOX", "new-controlled@example.org")
    settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="inbox changed"):
            notify(job.id)
        event = pg.scalar(select(Notification))
        assert event.status == "PENDING" and event.attempts == 0
    finally:
        settings.cache_clear()


def test_ses_reserved_success_and_receipt_replay(pg, monkeypatch, ses_gate):
    job = matched_job(pg, monkeypatch)
    payload = claim(job.id, "123")
    assert payload["ready"] and payload["to"] == settings().notification_test_inbox
    assert "Synthetic" in payload["html"] and "synthetic@example.com" not in str(payload)
    assert claim(job.id, "123")["ready"] is False  # Lost claim response does not resend.
    event = pg.scalar(select(Notification))
    assert event.status == "SENDING" and event.attempts == 1
    with pytest.raises(ValueError, match="does not own"):
        finish(job.id, payload["event_id"], "999", "SENT", "provider-id")
    assert finish(job.id, payload["event_id"], "123", "SENT", "provider-id")["sent"] == 1
    assert finish(job.id, payload["event_id"], "123", "SENT", "provider-id")["sent"] == 0
    assert claim(job.id, "124")["ready"] is False
    pg.expire_all()
    assert pg.scalar(select(Notification)).attempts == 1
    with pytest.raises(ValueError, match="reserved-event"):
        notify(job.id)


@pytest.mark.parametrize("failure", ["rejected", "timeout", "missing_ack"])
def test_ses_failed_or_ambiguous_receipt_stays_terminal(pg, monkeypatch, ses_gate, failure):
    job = matched_job(pg, monkeypatch)
    payload = claim(job.id, "123")
    # The n8n error output and missing-MessageId output both acknowledge UNKNOWN.
    finish(job.id, payload["event_id"], "123", "UNKNOWN")
    finish(job.id, payload["event_id"], "123", "UNKNOWN")
    assert not claim(job.id, "124")["ready"]
    with pytest.raises(ValueError, match="terminal"):
        finish(job.id, payload["event_id"], "123", "SENT", "late-id")
    pg.expire_all()
    event = pg.scalar(select(Notification))
    assert event.status == "UNKNOWN" and event.attempts == 1
    assert summarize(job.id)["sent"] == 0


def test_ses_concurrent_claims_do_not_duplicate_attempt(pg, monkeypatch, ses_gate):
    job = matched_job(pg, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        payloads = list(pool.map(lambda execution: claim(job.id, execution), ["123", "124"]))
    assert sum(payload["ready"] for payload in payloads) == 1
    pg.expire_all()
    assert pg.scalar(select(Notification)).attempts == 1


@pytest.fixture
def llm_gate(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-placeholder")
    monkeypatch.setenv("GEMINI_MODEL", "configured-test-model")
    monkeypatch.setattr("app.llm._calls", 0)
    settings.cache_clear()
    yield
    settings.cache_clear()


def model_response(value):
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://example.org"),
        json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(value)}]}}],
        },
    )


def test_llm_disabled_and_unapproved_sources_never_call_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr("app.llm.httpx.post", post)
    assert qualitative_quotes("Public source", approved=True) == ([], "DISABLED")
    monkeypatch.setenv("LLM_ENABLED", "true")
    settings.cache_clear()
    try:
        assert qualitative_quotes("Public source", approved=False) == ([], "NOT_APPROVED")
        assert qualitative_quotes("Public source", approved=True) == ([], "UNAVAILABLE")
    finally:
        settings.cache_clear()
    post.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        {"quotes": ["Invented condition"]},
        {"quotes": [" "]},
        {"quotes": [], "minimum_credit_score": 700},
        {"quotes": "Not a list"},
    ],
)
def test_llm_rejects_unproven_or_unsupported_output(monkeypatch, llm_gate, value):
    monkeypatch.setattr("app.llm.httpx.post", Mock(return_value=model_response(value)))
    assert qualitative_quotes("Minimum tenure: two years.", approved=True) == ([], "FAILED")


def test_llm_budget_and_timeout_fail_closed(monkeypatch, llm_gate):
    post = Mock(side_effect=httpx.ReadTimeout("No acknowledgement"))
    monkeypatch.setattr("app.llm.httpx.post", post)
    for _ in range(3):
        assert qualitative_quotes("Public source", approved=True) == ([], "FAILED")
    assert qualitative_quotes("Public source", approved=True) == ([], "BUDGET_EXHAUSTED")
    assert post.call_count == 3


def test_fixture_fallback_never_uses_llm_even_when_enabled(monkeypatch, llm_gate):
    from pathlib import Path

    post = Mock()
    monkeypatch.setattr("app.llm.httpx.post", post)
    value = extract(Path("n8n/fixtures/salaried.html").read_text(), {"fixture": True})
    assert value.llm_status == "DISABLED"
    post.assert_not_called()


def test_llm_qualitative_quotes_are_persisted_but_never_verify_eligibility(pg, monkeypatch, llm_gate):
    quote = "Minimum employment tenure: two years."
    post = Mock(return_value=model_response({"quotes": [quote]}))
    monkeypatch.setattr("app.llm.httpx.post", post)
    extracted = extract(
        "<p>" + quote + "</p>",
        {"approved": True, "lender": "Parser test", "url": "https://example.org/public"},
    )
    assert extracted.llm_status == "EXTRACTED" and extracted.qualitative_requirements == [quote]
    assert extracted.minimum_credit_score is None
    stored = store_extraction(extracted)
    assert stored["status"] == "UNVERIFIED"
    assert not pg.get(Product, stored["product_id"]).criteria_complete
    assert quote in pg.get(Criteria, stored["product_id"]).qualitative_requirements
    payload = post.call_args.kwargs["json"]
    assert payload["contents"] == [{"parts": [{"text": quote}]}]
