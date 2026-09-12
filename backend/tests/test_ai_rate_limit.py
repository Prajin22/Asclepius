"""Per-patient AI budget: bounds abuse and provider spend."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AIArtifact, AuditEvent
from app.models.enums import AIOperation
from app.services.ai_limits import enforce_rate_limit, usage_snapshot
from app.services.errors import AIRateLimited
from tests.conftest import API, create_problem, process_record


def _limits(monkeypatch, **overrides):
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update=overrides)
    monkeypatch.setattr("app.services.ai_pipeline.get_settings", lambda: tuned)
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)
    return tuned


def test_hourly_limit_blocks_further_runs(client, db, consented_patient, monkeypatch):
    _limits(monkeypatch, ai_rate_limit_per_hour=2, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)

    first = create_problem(client, consented_patient, "I have a headache.", "en")
    second = create_problem(client, consented_patient, "I have a cough.", "en")
    third = create_problem(client, consented_patient, "I have a fever.", "en")
    assert process_record(client, consented_patient, first["id"]).status_code == 200
    assert process_record(client, consented_patient, second["id"]).status_code == 200

    blocked = process_record(client, consented_patient, third["id"])
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "ai_rate_limited"
    # Nothing was written for the blocked attempt.
    assert len(list(db.scalars(select(AIArtifact).where(AIArtifact.artifact_type == AIOperation.EXTRACTION.value)))) == 2


def test_blocked_attempt_is_audited(client, db, consented_patient, monkeypatch):
    _limits(monkeypatch, ai_rate_limit_per_hour=1, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    first = create_problem(client, consented_patient, "I have a headache.", "en")
    second = create_problem(client, consented_patient, "I have a cough.", "en")
    process_record(client, consented_patient, first["id"])
    process_record(client, consented_patient, second["id"])
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "ai.rate_limited")) is not None


def test_cache_hits_do_not_consume_budget(client, db, consented_patient, monkeypatch):
    _limits(monkeypatch, ai_rate_limit_per_hour=5, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    record = create_problem(client, consented_patient, "I have a headache.", "en")

    first = process_record(client, consented_patient, record["id"]).json()
    again = process_record(client, consented_patient, record["id"]).json()

    assert all(run["cached"] for run in again["runs"])
    assert first["usage"]["runs_last_hour"] == 1
    assert again["usage"]["runs_last_hour"] == 1  # the cached run cost nothing


def test_daily_cost_limit_blocks(client, db, consented_patient, monkeypatch):
    _limits(monkeypatch, ai_rate_limit_per_hour=0, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0.01)
    record = create_problem(client, consented_patient, "I have a headache.", "en")
    process_record(client, consented_patient, record["id"])

    # Simulate spend from an external provider.
    artifact = db.scalar(select(AIArtifact))
    artifact.estimated_cost_usd = 0.02
    db.commit()

    other = create_problem(client, consented_patient, "I have a cough.", "en")
    blocked = process_record(client, consented_patient, other["id"])
    assert blocked.status_code == 429


def test_limits_can_be_disabled(client, db, consented_patient, monkeypatch):
    _limits(monkeypatch, ai_rate_limit_per_hour=0, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    for text in ("I have a headache.", "I have a cough.", "I have a fever.", "I feel dizzy."):
        record = create_problem(client, consented_patient, text, "en")
        assert process_record(client, consented_patient, record["id"]).status_code == 200


def test_old_runs_fall_out_of_the_window(client, db, consented_patient, monkeypatch):
    tuned = _limits(monkeypatch, ai_rate_limit_per_hour=1, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    record = create_problem(client, consented_patient, "I have a headache.", "en")
    process_record(client, consented_patient, record["id"])

    for artifact in db.scalars(select(AIArtifact)):
        artifact.created_at = datetime.now(UTC) - timedelta(hours=2)
    db.commit()

    other = create_problem(client, consented_patient, "I have a cough.", "en")
    assert process_record(client, consented_patient, other["id"]).status_code == 200
    assert usage_snapshot(db, uuid.UUID(consented_patient.id), tuned)["runs_last_hour"] == 1


def test_limits_are_per_patient(client, db, make_patient, consented_patient, monkeypatch):
    from tests.conftest import grant_ai_consent

    _limits(monkeypatch, ai_rate_limit_per_hour=1, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    mine = create_problem(client, consented_patient, "I have a headache.", "en")
    process_record(client, consented_patient, mine["id"])
    assert process_record(client, consented_patient, mine["id"]).status_code == 429

    other = make_patient(email="other@example.com")
    grant_ai_consent(client, other)
    theirs = create_problem(client, other, "I have a cough.", "en")
    assert process_record(client, other, theirs["id"]).status_code == 200


def test_service_raises_directly(db, consented_patient, monkeypatch):
    tuned = _limits(monkeypatch, ai_rate_limit_per_hour=0, ai_rate_limit_per_day=0, ai_daily_cost_limit_usd=0)
    patient_id = uuid.UUID(consented_patient.id)
    enforce_rate_limit(db, patient_id, tuned)  # disabled: no raise

    strict = tuned.model_copy(update={"ai_rate_limit_per_hour": 1})
    db.add(
        AIArtifact(
            patient_id=patient_id, artifact_type=AIOperation.EXTRACTION.value,
            provider="mock", model="mock-0", content={}, source_references=[],
        )
    )
    db.commit()
    with pytest.raises(AIRateLimited):
        enforce_rate_limit(db, patient_id, strict)
