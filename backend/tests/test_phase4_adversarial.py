"""Phase 4 adversarial validation (Stage E).

Attacks on the parts that are easy to get quietly wrong: cache invalidation,
budget accounting, document provenance, multilingual attribution, provider
failure, and the append-only history.

Where a test asserts "nothing happened", it also asserts that the positive case
does happen — otherwise a broken fixture would look like a pass.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import AIArtifact, AuditEvent, Consultation, ConsultationShare, ConsultationSummary, DoctorProfile
from app.models.enums import AIArtifactStatus, SummaryStatus
from app.providers.ai.errors import (
    AICredentialsMissing,
    AIMalformedOutput,
    AIProviderUnavailable,
    AITimeout,
)
from app.schemas.summary import ModelCaseSummary
from app.services import ai_limits, case_summary, case_summary_bundle, consultation_service
from app.services.case_summary import SummarizerResult
from app.services.errors import AIRateLimited
from tests.conftest import (
    API,
    create_problem,
    grant_ai_consent,
    process_record,
    request_consultation,
    run_async,
    upload,
)


def _doctor(db, doctor_id):
    return db.get(DoctorProfile, uuid.UUID(doctor_id))


def _generate(db, doctor_id, cid, summarize=None, provider=None):
    doctor = _doctor(db, doctor_id)
    return run_async(
        case_summary.generate(
            db, doctor, doctor.user, uuid.UUID(cid), summarize=summarize, provider=provider
        )
    )


def _bundle(db, doctor_id, cid):
    c = db.get(Consultation, uuid.UUID(cid))
    assert _doctor(db, doctor_id)
    return case_summary_bundle.build_source_bundle(
        db, consultation_service.resolve_authorized_context(db, c)
    )


def _rows(db, cid):
    return list(
        db.scalars(
            select(ConsultationSummary)
            .where(ConsultationSummary.consultation_id == uuid.UUID(cid))
            .order_by(ConsultationSummary.created_at)
        )
    )


class Counting:
    """Counts calls, so "did not reach the provider" is measurable."""

    def __init__(self, raises=None):
        self.calls = 0
        self._raises = raises

    async def __call__(self, bundle, language):
        self.calls += 1
        if self._raises:
            raise self._raises
        item = {
            "section": "current_problem",
            "statement": "Current problem recorded",
            "source_refs": [bundle.items[0].ref],
            "is_contradiction": False,
        }
        return SummarizerResult(
            summary=ModelCaseSummary.model_validate({"items": [item]}),
            provider="stub", model="stub-1", prompt_version=None,
        )


@pytest.fixture
def ready(client, db, seeded_case):
    grant_ai_consent(client, seeded_case.patient, True)
    c = request_consultation(client, seeded_case).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=seeded_case.doctor.h)
    db.expire_all()
    return seeded_case, c["id"]


# ==========================================================================
# Cache invalidation
# ==========================================================================


def test_cache_hits_on_identical_authorised_state(db, ready):
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)
    _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 1
    assert len(_rows(db, cid)) == 1


def test_editing_a_shared_source_invalidates_the_cache(client, db, ready):
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)
    before = _bundle(db, case.doctor.id, cid).hash()

    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "8 years, worse recently"},
        headers=case.patient.h,
    )
    db.expire_all()

    assert _bundle(db, case.doctor.id, cid).hash() != before
    _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 2
    assert len(_rows(db, cid)) == 2


def test_editing_an_unshared_source_does_not_invalidate_the_cache(client, db, ready):
    """A private edit is invisible to the doctor, so it cannot make their summary stale."""
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)
    before = _bundle(db, case.doctor.id, cid).hash()

    client.patch(
        f"{API}/patients/me/records/{case.private_rec['id']}",
        json={"content": "still private, now much longer than before"},
        headers=case.patient.h,
    )
    db.expire_all()

    assert _bundle(db, case.doctor.id, cid).hash() == before
    _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 1, "a private edit must not cost a provider call"


def test_a_different_provider_or_model_misses_the_cache(db, ready):
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)

    class OtherProvider:
        name = "other"
        model = "other-1"
        is_external = False

    _generate(db, case.doctor.id, cid, stub, provider=OtherProvider())
    assert stub.calls == 2, "a different provider identity must not reuse a stored summary"


def test_a_changed_prompt_version_misses_the_cache(db, ready, monkeypatch):
    """Bumping a prompt must make every summary produced by the old wording unreachable."""
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)

    monkeypatch.setattr(case_summary, "_prompt_version", lambda: "case_summary_v2")
    _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 2


def test_revoking_a_share_changes_the_bundle_and_the_cache(db, ready):
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)
    before = _bundle(db, case.doctor.id, cid).hash()

    from datetime import UTC, datetime

    share = db.scalar(
        select(ConsultationShare).where(
            ConsultationShare.consultation_id == uuid.UUID(cid),
            ConsultationShare.item_id == uuid.UUID(case.shared_rec["id"]),
        )
    )
    share.revoked_at = datetime.now(UTC)
    db.commit()
    db.expire_all()

    after_bundle = _bundle(db, case.doctor.id, cid)
    assert after_bundle.hash() != before
    assert "Hypertension" not in after_bundle.canonical()
    _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 2


# ==========================================================================
# Append-only history
# ==========================================================================


def test_regeneration_appends_and_never_overwrites(client, db, ready):
    case, cid = ready
    stub = Counting()
    first = _generate(db, case.doctor.id, cid, stub)
    first_id, first_hash, first_at = first.summary.id, first.summary.source_bundle_hash, first.summary.created_at

    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "changed"},
        headers=case.patient.h,
    )
    db.expire_all()
    second = _generate(db, case.doctor.id, cid, stub)

    rows = _rows(db, cid)
    assert len(rows) == 2
    kept = db.get(ConsultationSummary, first_id)
    assert kept is not None, "the earlier summary was overwritten"
    assert kept.source_bundle_hash == first_hash
    assert kept.status == SummaryStatus.READY
    assert second.summary.id != first_id
    assert second.summary.source_bundle_hash != first_hash
    assert second.summary.created_at >= first_at

    # Both remain associated with audit events for this consultation.
    actions = [e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == cid))]
    assert "consultation.summary_generated" in actions
    assert "consultation.summary_regenerated" in actions


def test_a_failed_regeneration_leaves_the_earlier_summary_intact(client, db, ready):
    case, cid = ready
    stub = Counting()
    first = _generate(db, case.doctor.id, cid, stub)
    assert first.status == "ready"

    client.patch(
        f"{API}/patients/me/records/{case.shared_rec['id']}",
        json={"content": "changed"},
        headers=case.patient.h,
    )
    db.expire_all()
    failed = _generate(db, case.doctor.id, cid, Counting(raises=AIProviderUnavailable("down")))
    assert failed.status == "failed"

    kept = db.get(ConsultationSummary, first.summary.id)
    assert kept.status == SummaryStatus.READY
    assert kept.summary["sections"], "the earlier summary's content must survive a later failure"


# ==========================================================================
# Provider failure modes
# ==========================================================================


@pytest.mark.parametrize(
    "error",
    [
        AITimeout("timed out"),
        AIProviderUnavailable("connection refused"),
        AIProviderUnavailable("AI provider returned 429"),
        AIProviderUnavailable("AI provider returned 500"),
        AIMalformedOutput("not json"),
        AICredentialsMissing("no key"),
    ],
    ids=["timeout", "connection", "429", "500", "malformed", "credentials"],
)
def test_every_provider_failure_degrades_safely(client, db, ready, error):
    case, cid = ready
    state = _generate(db, case.doctor.id, cid, Counting(raises=error))

    assert state.status == "failed"
    assert state.summary.status == SummaryStatus.FAILED
    assert state.summary.summary == {}
    assert state.summary.error_code == error.code

    # A failure artifact exists and carries the error code.
    artifact = db.scalar(
        select(AIArtifact).where(AIArtifact.artifact_type == case_summary.SUMMARY_OPERATION)
    )
    assert artifact.status == AIArtifactStatus.FAILED
    assert artifact.error_code == error.code

    # No READY row for this consultation.
    assert all(r.status != SummaryStatus.READY for r in _rows(db, cid))

    # The patient's information is untouched and still visible to the doctor.
    view = client.get(f"{API}/doctors/me/consultations/{cid}", headers=case.doctor.h).json()
    assert view["current_problems"]


def test_an_empty_result_after_validation_is_a_failure_not_an_empty_summary(db, ready):
    case, cid = ready

    class AllDropped:
        async def __call__(self, bundle, language):
            return SummarizerResult(
                summary=ModelCaseSummary.model_validate(
                    {"items": [{"section": "symptom", "statement": "Chest pain",
                                "source_refs": ["S999"], "is_contradiction": False}]}
                ),
                provider="stub", model="stub-1",
            )

    state = _generate(db, case.doctor.id, cid, AllDropped())
    assert state.status == "failed"
    assert state.summary.error_code == "summary_unsupported"
    assert state.summary.warnings, "the reason items were dropped must be recorded"


# ==========================================================================
# Budget
# ==========================================================================


def test_a_summary_does_not_consume_the_patients_run_allowance(db, ready, monkeypatch):
    from app.core.config import get_settings

    tuned = get_settings().model_copy(
        update={"ai_rate_limit_per_hour": 1, "ai_rate_limit_per_day": 1, "ai_daily_cost_limit_usd": 0}
    )
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    case, cid = ready
    patient_id = db.get(Consultation, uuid.UUID(cid)).patient_id
    _generate(db, case.doctor.id, cid, Counting())
    # Still affordable for the patient's own work.
    ai_limits.enforce_rate_limit(db, patient_id, tuned)


def test_a_cache_hit_costs_nothing_against_the_consultation_cap(db, ready):
    case, cid = ready
    stub = Counting()
    _generate(db, case.doctor.id, cid, stub)
    before = ai_limits.summary_generations_remaining(db, uuid.UUID(cid))
    _generate(db, case.doctor.id, cid, stub)
    assert ai_limits.summary_generations_remaining(db, uuid.UUID(cid)) == before


def test_a_failure_does_count_against_the_cap(client, db, ready, monkeypatch):
    """It spent a provider call; a failing provider must not be unlimited."""
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update={"summary_per_consultation_limit": 2})
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    case, cid = ready
    _generate(db, case.doctor.id, cid, Counting(raises=AIProviderUnavailable("down")))
    assert ai_limits.summary_generations_remaining(db, uuid.UUID(cid)) == 1


def test_zero_disables_only_the_consultation_cap(db, ready, monkeypatch):
    from app.core.config import get_settings

    tuned = get_settings().model_copy(
        update={"summary_per_consultation_limit": 0, "ai_daily_cost_limit_usd": 0.0001}
    )
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    case, cid = ready
    assert ai_limits.summary_generations_remaining(db, uuid.UUID(cid)) is None

    # The patient's cost cap still binds.
    db.add(
        AIArtifact(
            patient_id=db.get(Consultation, uuid.UUID(cid)).patient_id,
            artifact_type="extraction", provider="stub", model="stub-1",
            source_references=[], content={}, estimated_cost_usd=0.5,
        )
    )
    db.commit()
    stub = Counting()
    with pytest.raises(AIRateLimited):
        _generate(db, case.doctor.id, cid, stub)
    assert stub.calls == 0


def test_phase_2_limits_are_untouched(client, db, consented_patient, monkeypatch):
    """The existing per-patient extraction budget behaves exactly as before."""
    from app.core.config import get_settings

    tuned = get_settings().model_copy(
        update={"ai_rate_limit_per_hour": 1, "ai_rate_limit_per_day": 0, "ai_daily_cost_limit_usd": 0}
    )
    monkeypatch.setattr("app.services.ai_pipeline.get_settings", lambda: tuned)
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    first = create_problem(client, consented_patient, text="I have a headache.", language="en")
    assert process_record(client, consented_patient, first["id"]).status_code == 200
    second = create_problem(client, consented_patient, text="I have a cough.", language="en")
    blocked = process_record(client, consented_patient, second["id"])
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "ai_rate_limited"


# ==========================================================================
# Document provenance
# ==========================================================================


def test_document_facts_keep_their_page_and_the_file_is_unchanged(client, db, consented_patient, make_doctor):
    from app.synthetic_documents import text_pdf

    doctor = make_doctor()
    pdf = text_pdf([["Lab report", "Glucose: 126 mg/dL", "Haemoglobin: 12.4 g/dL"]])
    doc = upload(client, consented_patient, content=pdf, name="labs.pdf").json()
    processed = client.post(
        f"{API}/patients/me/documents/{doc['id']}/process", headers=consented_patient.h
    ).json()

    facts = [f for page in processed["pages"] for f in page["facts"]]
    if not facts:
        pytest.skip("the local reader extracted nothing from this synthetic report")
    for f in facts:
        client.post(
            f"{API}/patients/me/ai/facts/{f['id']}", json={"action": "confirm"},
            headers=consented_patient.h,
        )

    c = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [], "medical_record_ids": [],
                      "document_ids": [doc["id"]], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    ).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=doctor.h)
    db.expire_all()

    bundle = _bundle(db, doctor.id, c["id"])
    doc_facts = [i for i in bundle.items if i.kind.value == "fact" and i.resolution.get("page_number")]
    assert doc_facts, "a document-derived fact should carry its page"
    for item in doc_facts:
        assert item.resolution["document_id"] == doc["id"]
        assert item.resolution["page_number"] >= 1

    state = _generate(db, doctor.id, c["id"])
    stored = state.summary.summary
    text = " ".join(
        i["statement"] for s in stored["sections"] for i in s["items"]
    ).lower()
    # A value is carried, never interpreted.
    for interpretation in ("high glucose", "elevated", "abnormal", "low haemoglobin", "within range"):
        assert interpretation not in text

    # The stored file still matches the bytes that were uploaded.
    fetched = client.get(f"{API}/patients/me/documents/{doc['id']}/file", headers=consented_patient.h)
    assert fetched.content == pdf


def test_an_unshared_document_never_reaches_the_bundle(client, db, consented_patient, make_doctor):
    from app.synthetic_documents import text_pdf

    doctor = make_doctor()
    shared = upload(client, consented_patient, content=text_pdf([["Shared report", "Value: 1"]]),
                    name="shared.pdf").json()
    private = upload(client, consented_patient, content=text_pdf([["PRIVATEDOCMARKER", "Value: 2"]]),
                     name="private.pdf").json()
    for d in (shared, private):
        client.post(f"{API}/patients/me/documents/{d['id']}/process", headers=consented_patient.h)

    c = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [], "medical_record_ids": [],
                      "document_ids": [shared["id"]], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    ).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=doctor.h)
    db.expire_all()

    bundle = _bundle(db, doctor.id, c["id"])
    blob = bundle.canonical() + str([i.resolution for i in bundle.items])
    assert private["id"] not in blob
    assert "PRIVATEDOCMARKER" not in blob
    assert shared["id"] in str([i.resolution for i in bundle.items])


# ==========================================================================
# Multilingual
# ==========================================================================


MULTILINGUAL = [
    ("ta", "எனக்கு மூன்று நாட்களாக தலைவலி உள்ளது."),
    ("hi", "मुझे दो दिन से बुखार है।"),
    ("en", "I have had a headache for three days."),
]


@pytest.mark.parametrize("language,text", MULTILINGUAL, ids=[m[0] for m in MULTILINGUAL])
def test_the_original_survives_and_english_is_never_the_authority(
    client, db, consented_patient, make_doctor, language, text
):
    doctor = make_doctor()
    problem = create_problem(client, consented_patient, text=text, language=language)
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    for f in facts:
        client.post(
            f"{API}/patients/me/ai/facts/{f['id']}", json={"action": "confirm"},
            headers=consented_patient.h,
        )
    c = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [problem["id"]], "medical_record_ids": [],
                      "document_ids": [], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    ).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=doctor.h)
    db.expire_all()

    bundle = _bundle(db, doctor.id, c["id"])
    problem_item = next(i for i in bundle.items if i.kind.value == "current_problem")
    # The patient's own words travel, and are marked with their language.
    assert problem_item.payload["text"] == text
    assert problem_item.payload["language"] == language
    assert problem_item.resolution["original_text"] == text

    state = _generate(db, doctor.id, c["id"])
    # Every source keeps the original wording and its language for the reader.
    sources = [
        src for s in state.summary.summary["sections"] for i in s["items"] for src in i["sources"]
    ]
    originals = [src for src in sources if src.get("original_text")]
    assert originals, "no source carried the patient's own words"
    if language != "en":
        assert any(src["language"] == language for src in sources)
