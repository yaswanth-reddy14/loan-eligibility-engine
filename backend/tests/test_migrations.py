"""Exercise immutable initial schema and the follow-up migration in an empty isolated schema."""

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
def test_cold_migration_upgrade_downgrade_and_reupgrade(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly disposable PostgreSQL test database")
    schema = "migration_test_" + uuid.uuid4().hex
    admin = create_engine(url)
    scoped = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        monkeypatch.setattr("app.db.engine", lambda: scoped)
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        tables = set(inspect(scoped).get_table_names(schema=schema))
        assert len(tables) == 11 and "alembic_version" in tables
        assert "progress_count" in {
            c["name"] for c in inspect(scoped).get_columns("workflow_outbox", schema=schema)
        }
        command.downgrade(cfg, "0001")
        assert "progress_count" not in {
            c["name"] for c in inspect(scoped).get_columns("workflow_outbox", schema=schema)
        }
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        scoped.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
