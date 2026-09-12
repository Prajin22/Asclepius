"""Migrations apply cleanly and match the ORM models (PostgreSQL only).

Set MIGRATION_TEST_DATABASE_URL to an empty PostgreSQL database whose name
contains "test", e.g. .../carebridge_migrations_test
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="MIGRATION_TEST_DATABASE_URL not set")

BACKEND = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["database_url"] = URL
    return cfg


def test_upgrade_check_downgrade():
    assert URL and "test" in URL.rsplit("/", 1)[-1]
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "patient_profiles", "consultations", "consultation_shares", "prescriptions",
            "ai_artifacts", "audit_events"} <= tables
    command.check(cfg)  # raises if models and migrations have drifted
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
