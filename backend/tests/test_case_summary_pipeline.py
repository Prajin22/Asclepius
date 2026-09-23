"""Phase 4: the summarisation pipeline — caching, staleness, budget, failure, audit.

Stage B has no provider capability yet (that is Stage C), so these drive the
orchestration through the injected `summarize` seam. The gates, the caching, the
persistence and the audit trail are the same either way.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import AIArtifact, AuditEvent, Consultation, ConsultationSummary, DoctorProfile
from app.models.enums import AIArtifactStatus, SummaryStatus
from app.providers.ai.errors import AIProviderUnavailable
from app.schemas.summary import ModelCaseSummary
from app.services import case_summary
from app.services.case_summary import SummarizerResult
from app.services.errors import AIRateLimited
from tests.conftest import API, grant_ai_consent, request_consultation, run_async


class StubSummarizer:
    """Cites whatever the bundle actually contains, and counts its own calls."""

    def __init__(self, sections: int = 1, fail: Exception | None = None, items=None):
        self.calls = 0
        self._fail = fail
        self._sections = sections
        self._items = items

    async def __call__(self, bundle, language):
        self.calls += 1
        if self._fail is not None:
            raise self._fail
        items = self._items
        if items is None:
            problem = next(
                (i for i in bundle.items if i.kind.value == "current_problem"), bundle.items[0]
            )
            items = [
                {
                    "section": "current_problem",
                    "statement": "Reported headache and dizziness",
                    "source_refs": [problem.ref],
                    "is_contradiction": False,
                }
            ][: self._sections]
        return SummarizerResult(
            summary=ModelCaseSummary.model_validate({"items": items}),
            provider="stub",
            model="stub-summary-1",
            prompt_version=None,
            latency_ms=12,
            input_tokens=100,
            output_tokens=40,
            estimated_cost_usd=None,  # unknown pricing stays unknown
        )


@pytest.fixture
def ready_case(client, db, seeded_case):
    """A consented patient, a shared consultation, and the doctor row to act as."""
    grant_ai_consent(client, seeded_case.patient, True)
    c = request_consultation(client, seeded_case).json()
    doctor = db.get(DoctorProfile, uuid.UUID(seeded_case.doctor.id))
    db.expire_all()
    return seeded_case, doctor, uuid.UUID(c["id"])


def _generate(db, doctor, cid, summarize):
    return run_async(case_summary.generate(db, doctor, doctor.user, cid, summarize=summarize))


def _summaries(db, cid):
    return list(
        db.scalars(
            select(ConsultationSummary)
            .where(ConsultationSummary.consultation_id == cid)
            .order_by(ConsultationSummary.created_at)
        )
    )


def _actions(db, cid):
    return [
        e.action
        for e in db.scalars(
            select(AuditEvent).where(AuditEvent.resource_id == str(cid)).order_by(AuditEvent.created_at)
        )
    ]


# ---------- state ----------


def test_state_starts_at_not_generated(db, ready_case):
    _, doctor, cid = ready_case
    state = case_summary.get_state(db, doctor, cid)
    assert state.status == "not_generated"
    assert state.summary is None
    assert len(state.current_bundle_hash) == 64
    assert state.generations_remaining == 10


def test_generation_produces_a_ready_summary(db, ready_case):
    _, doctor, cid = ready_case
    stub = StubSummarizer()
    state = _generate(db, doctor, cid, stub)

    assert stub.calls == 1
    assert state.status == "ready"
    assert state.is_stale is False
    row = state.summary
    assert row.status == SummaryStatus.READY
    assert row.generated_at is not None
    assert row.summary["sections"][0]["items"][0]["statement"] == "Reported headache and dizziness"
    assert row.summary["sections"][0]["items"][0]["origin"] == "patient_provided"
    assert row.dropped_item_count == 0
    # The row records the identity the cache key was built from; the artifact
    # records what actually answered.
    assert (row.provider, row.model) == ("mock", "mock-0")


def test_the_configured_provider_is_used_when_none_is_injected(db, ready_case):
    """With no stub, the configured provider runs. In tests that is the mock."""
    _, doctor, cid = ready_case
    state = run_async(case_summary.generate(db, doctor, doctor.user, cid))

    assert state.status == "ready"
    assert state.summary.provider == "mock"
    assert state.summary.prompt_version == "case_summary_v1"
    sections = {s["kind"] for s in state.summary.summary["sections"]}
    assert "current_problem" in sections
    # Every statement traces to a human, never to the machine that grouped them.
    for section in state.summary.summary["sections"]:
        for item in section["items"]:
            assert item["origin"] in {"patient_provided", "patient_confirmed", "doctor_authored"}
            assert item["sources"]


def test_demo_mode_summaries_are_deterministic(db, ready_case):
    """The public demo must give the same answer every time (D-027)."""
    _, doctor, cid = ready_case
    first = run_async(case_summary.generate(db, doctor, doctor.user, cid))
    payload = first.summary.summary

    # Force a regeneration rather than a cache hit by clearing the stored rows.
    for row in _summaries(db, cid):
        db.delete(row)
    db.commit()

    second = run_async(case_summary.generate(db, doctor, doctor.user, cid))
    assert second.summary.summary == payload


# ---------- artifact ----------


def test_a_successful_run_records_an_artifact(db, ready_case):
    _, doctor, cid = ready_case
    _generate(db, doctor, cid, StubSummarizer())

    artifact = db.scalar(
        select(AIArtifact).where(AIArtifact.artifact_type == case_summary.SUMMARY_OPERATION)
    )
    assert artifact is not None
    assert artifact.consultation_id == cid
    assert artifact.status == AIArtifactStatus.SUCCEEDED
    assert artifact.provider == "stub"
    assert artifact.model == "stub-summary-1"
    assert artifact.latency_ms == 12
    assert artifact.input_tokens == 100
    assert artifact.output_tokens == 40
    assert artifact.estimated_cost_usd is None  # unknown pricing is not invented
    assert len(artifact.source_hash) == 64
    # The artifact is a receipt, not a copy of the summary.
    assert "statement" not in str(artifact.content)


def test_a_failed_run_records_a_failed_artifact(db, ready_case):
    _, doctor, cid = ready_case
    state = _generate(db, doctor, cid, StubSummarizer(fail=AIProviderUnavailable("down")))

    assert state.status == "failed"
    assert state.summary.error_code == "ai_provider_unavailable"
    artifact = db.scalar(
        select(AIArtifact).where(AIArtifact.artifact_type == case_summary.SUMMARY_OPERATION)
    )
    assert artifact.status == AIArtifactStatus.FAILED
    assert artifact.error_code == "ai_provider_unavailable"


def test_everything_dropped_is_a_failure_not_an_empty_summary(db, ready_case):
    """A summary that survived validation empty is not a summary."""
    _, doctor, cid = ready_case
    stub = StubSummarizer(
        items=[{"section": "symptom", "statement": "Chest pain", "source_refs": ["S404"],
                "is_contradiction": False}]
    )
    state = _generate(db, doctor, cid, stub)
    assert state.status == "failed"
    assert state.summary.error_code == "summary_unsupported"
    assert state.summary.dropped_item_count == 1


# ---------- caching ----------


def test_identical_information_reuses_the_stored_summary(db, ready_case):
    _, doctor, cid = ready_case
    stub = StubSummarizer()
    first = _generate(db, doctor, cid, stub)
    second = _generate(db, doctor, cid, stub)

    assert stub.calls == 1, "the second request must not reach the provider"
    assert second.status == "ready"
    assert second.summary.id == first.summary.id
    assert len(_summaries(db, cid)) == 1


def test_a_cache_hit_does_not_consume_the_generation_budget(db, ready_case):
    _, doctor, cid = ready_case
    stub = StubSummarizer()
    _generate(db, doctor, cid, stub)
    before = case_summary.get_state(db, doctor, cid).generations_remaining
    _generate(db, doctor, cid, stub)
    assert case_summary.get_state(db, doctor, cid).generations_remaining == before


# ---------- staleness ----------


def test_editing_shared_information_makes_the_summary_stale(client, db, ready_case):
    case, doctor, cid = ready_case
    _generate(db, doctor, cid, StubSummarizer())
    assert case_summary.get_state(db, doctor, cid).status == "ready"

    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "8 years, worse recently"},
        headers=case.patient.h,
    )
    db.expire_all()

    state = case_summary.get_state(db, doctor, cid)
    assert state.status == "stale"
    assert state.is_stale is True
    # The stored summary is still readable — it is labelled, not deleted.
    assert state.summary.status == SummaryStatus.READY


def test_editing_private_information_does_not_make_it_stale(client, db, ready_case):
    case, doctor, cid = ready_case
    _generate(db, doctor, cid, StubSummarizer())
    client.patch(
        f"{API}/patients/me/records/{case.private_rec['id']}",
        json={"content": "still private"},
        headers=case.patient.h,
    )
    db.expire_all()
    assert case_summary.get_state(db, doctor, cid).status == "ready"


def test_regenerating_after_a_change_adds_a_row_and_calls_the_provider(client, db, ready_case):
    case, doctor, cid = ready_case
    stub = StubSummarizer()
    _generate(db, doctor, cid, stub)

    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "8 years"},
        headers=case.patient.h,
    )
    db.expire_all()
    state = _generate(db, doctor, cid, stub)

    assert stub.calls == 2
    assert state.status == "ready"
    assert state.is_stale is False
    rows = _summaries(db, cid)
    assert len(rows) == 2, "history is kept, not overwritten"
    assert rows[0].source_bundle_hash != rows[1].source_bundle_hash


# ---------- budget ----------


def test_the_per_consultation_cap_bounds_regeneration(client, db, ready_case, monkeypatch):
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update={"summary_per_consultation_limit": 2})
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    case, doctor, cid = ready_case
    stub = StubSummarizer()
    for content in ("v2", "v3"):
        _generate(db, doctor, cid, stub)
        client.patch(
            f"{API}/patients/me/records/{case.shared_rec['id']}",
            json={"content": content},
            headers=case.patient.h,
        )
        db.expire_all()

    assert stub.calls == 2
    with pytest.raises(AIRateLimited):
        _generate(db, doctor, cid, stub)
    assert stub.calls == 2, "the provider must not be called once the cap is reached"
    assert "consultation.summary_rate_limited" in _actions(db, cid)


def test_the_patient_cost_cap_still_applies(db, ready_case, monkeypatch):
    """Summaries spend the patient's money, so the spend cap binds them."""
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update={"ai_daily_cost_limit_usd": 0.0001})
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    _, doctor, cid = ready_case
    db.add(
        AIArtifact(
            patient_id=db.get(Consultation, cid).patient_id,
            artifact_type="extraction", provider="stub", model="stub-1",
            source_references=[], content={}, estimated_cost_usd=0.5,
        )
    )
    db.commit()

    stub = StubSummarizer()
    with pytest.raises(AIRateLimited):
        _generate(db, doctor, cid, stub)
    assert stub.calls == 0


def test_summaries_do_not_consume_the_patient_run_allowance(db, ready_case, monkeypatch):
    """Stage A decision 3 — run caps stay reserved for patient-initiated work."""
    from app.core.config import get_settings
    from app.services import ai_limits

    tuned = get_settings().model_copy(
        update={"ai_rate_limit_per_hour": 1, "ai_rate_limit_per_day": 1, "ai_daily_cost_limit_usd": 0}
    )
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    _, doctor, cid = ready_case
    patient_id = db.get(Consultation, cid).patient_id
    _generate(db, doctor, cid, StubSummarizer())

    # The patient's own hourly allowance is untouched by the doctor's summary.
    ai_limits.enforce_rate_limit(db, patient_id, tuned)


# ---------- audit ----------


def test_the_audit_trail_covers_request_generate_and_view(db, ready_case):
    _, doctor, cid = ready_case
    state = _generate(db, doctor, cid, StubSummarizer())
    case_summary.record_view(db, doctor.user, db.get(Consultation, cid), state.summary)

    actions = _actions(db, cid)
    assert "consultation.summary_requested" in actions
    assert "consultation.summary_generated" in actions
    assert "consultation.summary_viewed" in actions

    event = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "consultation.summary_generated")
    )
    # Ids and counts only — never the clinical text itself.
    assert set(event.details) == {
        "summary_id", "provider", "model", "sections", "items", "dropped", "pending_facts"
    }
    assert "headache" not in str(event.details).lower()


def test_regeneration_is_audited_distinctly(client, db, ready_case):
    case, doctor, cid = ready_case
    stub = StubSummarizer()
    _generate(db, doctor, cid, stub)
    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "changed"},
        headers=case.patient.h,
    )
    db.expire_all()
    _generate(db, doctor, cid, stub)

    actions = _actions(db, cid)
    assert "consultation.summary_generated" in actions
    assert "consultation.summary_regenerated" in actions


def test_failure_is_audited(db, ready_case):
    _, doctor, cid = ready_case
    _generate(db, doctor, cid, StubSummarizer(fail=AIProviderUnavailable("down")))
    assert "consultation.summary_failed" in _actions(db, cid)


# ---------- presentation ----------


def test_present_hides_the_payload_unless_ready(db, ready_case):
    _, doctor, cid = ready_case
    failed = _generate(db, doctor, cid, StubSummarizer(fail=AIProviderUnavailable("down")))
    out = case_summary.present(failed)
    assert out.status == "failed"
    assert out.summary is None
    assert out.error_code == "ai_provider_unavailable"

    ready = _generate(db, doctor, cid, StubSummarizer())
    out = case_summary.present(ready)
    assert out.status == "ready"
    assert out.summary is not None
    assert out.summary.sections[0].items[0].sources[0].ref.startswith("S")
