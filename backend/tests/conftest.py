import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

config = dotenv_values(".env")
os.environ.setdefault("API_TOKEN", "unit-test-token-only-0000000000")
os.environ.setdefault("WORKFLOW_SECRET", "unit-test-secret-only-0000000000")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local-test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local-test-secret")


@pytest.fixture
def pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    from app.config import settings
    from app.db import engine
    from app.models import Base

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an explicitly disposable PostgreSQL database")
    # Unique schema per test; never drops a database or existing schema.
    test_engine = create_engine(url)
    schema = "test_" + uuid.uuid4().hex
    with test_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(scoped)
    monkeypatch.setattr("app.db.engine", lambda: scoped)
    for module in [
        "app.ingestion",
        "app.matching",
        "app.notifications",
        "app.worker",
        "app.discovery",
        "app.n8n_delivery",
        "app.matching_pages",
    ]:
        monkeypatch.setattr(module + ".engine", lambda: scoped)
    with Session(scoped) as db:
        yield db
    scoped.dispose()
    with test_engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    test_engine.dispose()
    engine.cache_clear()
    settings.cache_clear()


@pytest.fixture
def input_csv() -> Path:
    path = Path("users.csv")
    if not path.exists():
        pytest.skip("Supplied users.csv is not available; never fabricate assignment data")
    return path
