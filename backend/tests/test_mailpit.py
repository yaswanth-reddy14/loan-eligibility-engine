import os
import uuid

import httpx
import pytest


@pytest.mark.e2e
def test_actual_mailpit_preview(monkeypatch):
    if os.environ.get("RUN_MAILPIT_TEST") != "1":
        pytest.skip("Opt in to the local-only Mailpit service check with RUN_MAILPIT_TEST=1")
    from app.config import settings
    from app.notifications import deliver

    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "preview")
    settings.cache_clear()
    identifier = str(uuid.uuid4())
    provider_id = deliver(
        identifier,
        "Synthetic",
        [
            {
                "lender": "Fictional QA",
                "product_name": "Synthetic test",
                "source_url": "https://example.org/demo",
                "rate_representation": "Demo only",
            }
        ],
    )
    assert identifier in provider_id
    response = httpx.get(
        "http://127.0.0.1:8025/api/v1/search",
        params={"query": "message-id:" + identifier + "@loan.test"},
        timeout=10,
    )
    response.raise_for_status()
    messages = response.json()["messages"]
    assert len(messages) == 1
    assert [value["Address"] for value in messages[0]["To"]] == [settings().notification_test_inbox]
    settings.cache_clear()
