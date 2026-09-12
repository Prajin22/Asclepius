"""Failure handling: degrade to the original information, never fabricate."""

import asyncio

import pytest
from sqlalchemy import select

from app.models import AIArtifact, AuditEvent, MedicalRecord
from app.models.enums import AIArtifactStatus
from app.providers.ai.errors import (
    AICircuitOpen,
    AIMalformedOutput,
    AIProviderUnavailable,
    AITimeout,
)
from app.providers.ai.runtime import CircuitBreaker, call_with_resilience
from tests.ai_stubs import FailingProvider, MalformedProvider, SlowProvider
from tests.conftest import API, TAMIL_PROBLEM, create_problem, process_record, run_async


def _use(monkeypatch, provider):
    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: provider)
    return provider


def _short_timeout(monkeypatch, seconds: float = 0.05):
    """Make the pipeline's own timeout tiny for the slow-provider test."""
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update={"ai_timeout_seconds": seconds, "ai_max_attempts": 1})
    monkeypatch.setattr("app.services.ai_pipeline.get_settings", lambda: tuned)


@pytest.mark.parametrize("provider_factory", [FailingProvider, MalformedProvider, SlowProvider])
def test_provider_failures_degrade_to_the_original_text(client, db, consented_patient, monkeypatch, provider_factory):
    _short_timeout(monkeypatch)
    _use(monkeypatch, provider_factory())

    record = create_problem(client, consented_patient)
    r = process_record(client, consented_patient, record["id"])

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unavailable"
    assert body["error_code"]
    # No facts are invented. Output from steps that did succeed (e.g. a
    # normalisation before extraction failed) is real and may be shown.
    assert body["facts"] == []

    stored = db.get(MedicalRecord, __import__("uuid").UUID(record["id"]))
    assert stored.content == TAMIL_PROBLEM  # the patient's information is untouched


def test_failure_is_recorded_as_a_failed_artifact_and_audited(client, db, consented_patient, monkeypatch):
    _use(monkeypatch, FailingProvider())
    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])

    artifact = db.scalar(select(AIArtifact))
    assert artifact is not None and artifact.status == AIArtifactStatus.FAILED
    assert artifact.error_code == "ai_provider_unavailable"
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "ai.processing_failed")) is not None


def test_stored_state_after_failure_reports_unavailable(client, consented_patient, monkeypatch):
    _use(monkeypatch, FailingProvider())
    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])
    state = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=consented_patient.h).json()
    assert state["status"] == "unavailable"


# ---------- runtime primitives ----------


def test_retry_then_success():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise AIProviderUnavailable("first try fails")
        return "ok"

    assert run_async(call_with_resilience(flaky, timeout_seconds=1, max_attempts=2)) == "ok"
    assert attempts["n"] == 2


def test_malformed_output_is_not_retried():
    attempts = {"n": 0}

    async def bad():
        attempts["n"] += 1
        raise AIMalformedOutput("nope")

    with pytest.raises(AIMalformedOutput):
        run_async(call_with_resilience(bad, timeout_seconds=1, max_attempts=3))
    assert attempts["n"] == 1  # retrying a schema violation is pointless


def test_timeout_is_enforced():
    async def slow():
        await asyncio.sleep(1)

    with pytest.raises(AITimeout):
        run_async(call_with_resilience(slow, timeout_seconds=0.05, max_attempts=1))


def test_circuit_opens_after_repeated_failures_and_recovers():
    breaker = CircuitBreaker(threshold=2, reset_seconds=0.2)

    async def always_fails():
        raise AIProviderUnavailable("down")

    for _ in range(2):
        with pytest.raises(AIProviderUnavailable):
            run_async(call_with_resilience(always_fails, timeout_seconds=1, max_attempts=1, breaker=breaker))

    with pytest.raises(AICircuitOpen):
        run_async(call_with_resilience(always_fails, timeout_seconds=1, max_attempts=1, breaker=breaker))

    breaker.reset()

    async def works():
        return "ok"

    assert run_async(call_with_resilience(works, timeout_seconds=1, max_attempts=1, breaker=breaker)) == "ok"
