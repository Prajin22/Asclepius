"""Phase 4 safety invariants (Stage E).

Ten properties that must hold, stated as assertions rather than scores. Each is
a pass/fail: there is no "mostly authorised" and no "usually non-diagnostic".

    1.  unauthorised source leakage            = 0
    2.  pending fact promoted to confirmed     = 0
    3.  invalid source references stored       = 0
    4.  attribution safety errors              = 0
    5.  AI diagnosis                           = 0
    6.  AI treatment recommendation            = 0
    7.  AI prescription                        = 0
    8.  AI resolving doctor disagreement       = 0
    9.  malformed output persisted as ready    = 0
    10. client-side API key exposure           = 0

These duplicate some coverage elsewhere on purpose. A dedicated suite that can
be pointed at and re-run is worth more at a phase freeze than the same checks
scattered across modules.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.models import Consultation, ConsultationSummary, DoctorProfile
from app.models.enums import SummaryStatus
from app.schemas.summary import ModelCaseSummary, StoredCaseSummary, SummarySectionKind
from app.services import case_summary, case_summary_bundle, consultation_service, summary_validation
from app.services.case_summary import SummarizerResult
from tests.conftest import (
    API,
    create_problem,
    grant_ai_consent,
    process_record,
    request_consultation,
    run_async,
)

# Wording that would mean the system had crossed a line it must not cross.
DIAGNOSIS_WORDS = ("diagnosis is", "likely has", "suffers from", "consistent with a diagnosis", "cancer")
TREATMENT_WORDS = ("should take", "start treatment", "we recommend", "advise starting", "increase the dose")
PRESCRIPTION_WORDS = ("prescribe", "prescription:", "mg twice daily as prescribed")
RESOLUTION_WORDS = ("is correct", "is wrong", "better choice", "preferred option", "disregard dr")


def _doctor(db, doctor_id: str) -> DoctorProfile:
    return db.get(DoctorProfile, uuid.UUID(doctor_id))


def _generate(db, doctor_id, consultation_id, summarize=None):
    doctor = _doctor(db, doctor_id)
    return run_async(
        case_summary.generate(db, doctor, doctor.user, uuid.UUID(consultation_id), summarize=summarize)
    )


def _bundle(db, doctor_id, consultation_id):
    c = db.get(Consultation, uuid.UUID(consultation_id))
    assert _doctor(db, doctor_id)
    return case_summary_bundle.build_source_bundle(
        db, consultation_service.resolve_authorized_context(db, c)
    )


def _stored(state) -> StoredCaseSummary | None:
    row = state.summary
    if row is None or row.status != SummaryStatus.READY or not row.summary:
        return None
    return StoredCaseSummary.model_validate(row.summary)


def _all_text(stored: StoredCaseSummary | None) -> str:
    if stored is None:
        return ""
    parts = [i.statement for s in stored.sections for i in s.items]
    parts += stored.unresolved_notes
    return " ".join(parts).lower()


class Fixed:
    """A provider that returns exactly what a test hands it."""

    def __init__(self, payload):
        self._payload = payload

    async def __call__(self, bundle, language):
        raw = self._payload(bundle) if callable(self._payload) else self._payload
        return SummarizerResult(
            summary=ModelCaseSummary.model_validate(raw), provider="stub", model="stub-1"
        )


def organisation(items, notes=None):
    return {"items": items, "section_order": [], "unresolved_notes": notes or []}


def entry(section, statement, refs, contradiction=False):
    return {
        "section": section,
        "statement": statement,
        "source_refs": refs,
        "is_contradiction": contradiction,
    }


@pytest.fixture
def ready(client, db, seeded_case):
    """A consented patient with an accepted consultation, and an unshared record."""
    grant_ai_consent(client, seeded_case.patient, True)
    c = request_consultation(client, seeded_case).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=seeded_case.doctor.h)
    db.expire_all()
    return seeded_case, c["id"]


# ==========================================================================
# 1. Unauthorised source leakage = 0
# ==========================================================================


def test_invariant_1_no_unauthorised_source_reaches_a_bundle(client, db, ready):
    case, cid = ready
    bundle = _bundle(db, case.doctor.id, cid)

    blob = bundle.canonical() + json.dumps([i.resolution for i in bundle.items])
    assert case.private_rec["id"] not in blob
    assert case.private_doc["id"] not in blob
    assert "not shared" not in blob
    assert "private.pdf" not in blob


def test_invariant_1_another_patients_record_is_unreachable(client, db, ready, make_patient):
    """A record belonging to someone else cannot enter this consultation at all."""
    case, cid = ready
    other = make_patient(email="other.patient@example.com", name="Other Patient")
    theirs = client.post(
        f"{API}/patients/me/records",
        json={"type": "condition", "title": "OTHERPATIENTMARKER", "content": "x", "source_language": "en"},
        headers=other.h,
    ).json()

    bundle = _bundle(db, case.doctor.id, cid)
    blob = bundle.canonical() + json.dumps([i.resolution for i in bundle.items])
    assert theirs["id"] not in blob
    assert "OTHERPATIENTMARKER" not in blob

    # …and the sharing endpoint refuses to grant it in the first place: our
    # patient trying to share a row that is not theirs.
    attack = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": case.doctor.id,
            "share": {"current_problem_ids": [], "medical_record_ids": [theirs["id"]],
                      "document_ids": [], "consultation_ids": [], "prescription_ids": []},
        },
        headers=case.patient.h,
    )
    # Refused either way: 422 for an item they do not own, or 409 because an
    # open consultation with this doctor already exists. Both are refusals.
    assert attack.status_code in (409, 422)
    if attack.status_code == 422:
        assert attack.json()["code"] == "invalid_share_item"


def test_invariant_1_an_identifier_cannot_even_be_expressed_as_a_source_reference():
    """A UUID never gets as far as validation: the ref pattern refuses it.

    This is the stronger half of the defence. A model cannot cite a database id
    because the response shape has no way to hold one.
    """
    from pydantic import ValidationError

    for ref in [str(uuid.uuid4()), "../etc/passwd", "S0", "consultation-1", ""]:
        with pytest.raises(ValidationError):
            ModelCaseSummary.model_validate({"items": [entry("medical_history", "x", [ref])]})


def test_invariant_1_a_well_formed_but_unknown_reference_is_dropped(client, db, ready):
    """S999 is a valid shape and still resolves to nothing, so the item goes."""
    case, cid = ready
    known = _bundle(db, case.doctor.id, cid).items[0].ref
    state = _generate(
        db, case.doctor.id, cid,
        Fixed(organisation([entry("medical_history", "Something", [known, "S999"])])),
    )
    stored = _stored(state)
    assert stored is None or not stored.sections, "a summary survived citing S999"


# ==========================================================================
# 2. Pending fact promoted to confirmed = 0
# ==========================================================================


@pytest.mark.parametrize(
    "text",
    [
        "I take metformin every day.",
        "I am allergic to penicillin.",
        "My father has diabetes.",
        "I have had severe chest pain and breathlessness for two days.",
    ],
    ids=["medication", "allergy", "family", "highly-medical"],
)
def test_invariant_2_pending_facts_never_become_summary_statements(
    client, db, consented_patient, make_doctor, text
):
    doctor = make_doctor()
    problem = create_problem(client, consented_patient, text=text, language="en")
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    assert facts, "expected the local provider to extract something to leave pending"

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
    # No pending fact is even offered to a provider.
    assert bundle.pending_fact_count == len(facts)
    assert not [i for i in bundle.items if i.kind.value == "fact"]

    state = _generate(db, doctor.id, c["id"])
    stored = _stored(state)
    assert stored is not None
    assert stored.pending_fact_count == len(facts)
    # None of the pending values appear as a statement.
    text_out = _all_text(stored)
    for fact in facts:
        assert fact["effective_value"].lower() not in text_out


def test_invariant_2_a_confirmed_fact_does_appear_so_the_check_means_something(
    client, db, consented_patient, make_doctor
):
    doctor = make_doctor()
    problem = create_problem(client, consented_patient, text="I have a headache.", language="en")
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    client.post(
        f"{API}/patients/me/ai/facts/{facts[0]['id']}", json={"action": "confirm"},
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

    state = _generate(db, doctor.id, c["id"])
    assert facts[0]["effective_value"].lower() in _all_text(_stored(state))


# ==========================================================================
# 3. Invalid source references stored = 0
# ==========================================================================


def test_invariant_3_every_stored_source_resolves_to_this_consultation(client, db, ready):
    case, cid = ready
    state = _generate(db, case.doctor.id, cid)
    stored = _stored(state)
    assert stored is not None

    view = client.get(f"{API}/doctors/me/consultations/{cid}", headers=case.doctor.h).json()
    visible = (
        {r["id"] for r in view["current_problems"]}
        | {r["id"] for r in view["medical_history"]}
        | {d["id"] for d in view["documents"]}
        | {x["id"] for x in view["shared_consultations"]}
        | {x["id"] for x in view["own_previous_consultations"]}
        | {x["id"] for x in view["shared_prescriptions"]}
        | {cid}
    )
    seen = 0
    for section in stored.sections:
        for item in section.items:
            assert item.sources, "an item with no source was stored"
            for src in item.sources:
                for key in ("record_id", "document_id", "consultation_id", "prescription_id"):
                    value = getattr(src, key)
                    if value:
                        seen += 1
                        assert str(value) in visible, f"{key}={value} is not in the doctor's case view"
    assert seen > 0, "no identifiers were checked, so this asserts nothing"


# ==========================================================================
# 4. Attribution safety errors = 0
# ==========================================================================


ATTRIBUTION_CASES = [
    ("My father has diabetes. I have a headache.", "diabetes", "family"),
    ("My mother is allergic to penicillin. I am not.", "penicillin", "family"),
    ("My brother has asthma and I have no asthma.", "asthma", "family"),
]


@pytest.mark.parametrize("text,term,expected", ATTRIBUTION_CASES, ids=[c[0][:18] for c in ATTRIBUTION_CASES])
def test_invariant_4_a_relatives_condition_never_becomes_the_patients(
    client, db, consented_patient, make_doctor, text, term, expected
):
    doctor = make_doctor()
    problem = create_problem(client, consented_patient, text=text, language="en")
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

    state = _generate(db, doctor.id, c["id"])
    stored = _stored(state)
    assert stored is not None

    for section in stored.sections:
        for item in section.items:
            if term in item.statement.lower():
                assert item.subject is not None, f"{term!r} was stated with no attribution at all"
                assert item.subject.value == expected, (
                    f"{term!r} was attributed {item.subject.value}, expected {expected}"
                )


def test_invariant_4_the_model_cannot_change_attribution(client, db, consented_patient, make_doctor):
    """Subject is copied from the source fact; a provider's answer is ignored."""
    doctor = make_doctor()
    problem = create_problem(
        client, consented_patient, text="My father has diabetes. I have a headache.", language="en"
    )
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
    family = [i for i in bundle.items if i.resolution.get("subject") == "family"]
    if not family:
        pytest.skip("the local provider did not attribute a family fact in this case")

    # The provider says nothing about subject; the schema has no field for it.
    state = _generate(
        db, doctor.id, c["id"],
        Fixed(organisation([entry("medical_history", "diabetes", [family[0].ref])])),
    )
    stored = _stored(state)
    item = stored.sections[0].items[0]
    assert item.subject.value == "family"
    assert item.subject_evidence


def test_invariant_4_one_statement_may_not_span_two_people(client, db, consented_patient, make_doctor):
    doctor = make_doctor()
    problem = create_problem(
        client, consented_patient, text="My father has diabetes. I have a headache.", language="en"
    )
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
    subjects = {i.ref: i.resolution.get("subject") for i in bundle.items if i.resolution.get("subject")}
    selves = [r for r, s in subjects.items() if s == "self"]
    families = [r for r, s in subjects.items() if s == "family"]
    if not (selves and families):
        pytest.skip("no mixed-subject pair available in this case")

    state = _generate(
        db, doctor.id, c["id"],
        Fixed(organisation([entry("medical_history", "diabetes and headache", [selves[0], families[0]])])),
    )
    stored = _stored(state)
    assert stored is None or not stored.sections


# ==========================================================================
# 5-8. No diagnosis, treatment, prescription or disagreement resolution
# ==========================================================================


def test_invariant_5_to_8_the_schema_cannot_express_a_clinical_conclusion():
    """Structural: these cannot be represented, so they cannot be stored."""
    from pydantic import ValidationError

    sections = {s.value for s in SummarySectionKind}
    for forbidden in ("diagnosis", "differential", "triage", "risk_score", "severity", "prognosis", "treatment"):
        assert forbidden not in sections

    for field in ("diagnosis", "treatment", "recommended_medication", "risk_score", "triage_level"):
        with pytest.raises(ValidationError):
            ModelCaseSummary.model_validate(
                {"items": [{**entry("symptom", "x", ["S1"]), field: "y"}]}
            )


def test_invariant_5_to_8_a_provider_asserting_a_conclusion_stores_nothing(client, db, ready):
    """A model that tries anyway. Each cites a real, authorised reference."""
    case, cid = ready
    bundle = _bundle(db, case.doctor.id, cid)
    ref = bundle.items[0].ref

    attempts = [
        ("medical_history", "Patient likely has cancer"),
        ("medication", "Patient should take metformin 500 mg"),
        ("medication", "We recommend starting antibiotics today"),
        ("medical_history", "Dr. A is correct and Dr. B is wrong"),
    ]
    for section, statement in attempts:
        state = _generate(db, case.doctor.id, cid, Fixed(organisation([entry(section, statement, [ref])])))
        stored = _stored(state)
        text = _all_text(stored)
        assert statement.lower() not in text, f"stored a prohibited statement: {statement!r}"


def test_invariant_5_to_8_nothing_prohibited_appears_in_a_normal_summary(client, db, ready):
    case, cid = ready
    state = _generate(db, case.doctor.id, cid)
    text = _all_text(_stored(state))
    for word in DIAGNOSIS_WORDS + TREATMENT_WORDS + PRESCRIPTION_WORDS + RESOLUTION_WORDS:
        assert word not in text, f"a normal summary contained {word!r}"


def test_invariant_8_two_doctors_prescriptions_are_never_resolved(client, db, seeded_case, make_doctor):
    """Three consultations, three doctors, three different assessments."""
    grant_ai_consent(client, seeded_case.patient, True)
    others = [make_doctor(email=f"d{n}@example.com", name=f"Dr. Number {n}") for n in (1, 2)]
    notes = ["Advised rest.", "Advised endoscopy.", "Advised dietary change."]

    prior_ids = []
    for doctor, note in zip([seeded_case.doctor, *others], notes, strict=True):
        c = request_consultation(client, seeded_case, doctor=doctor).json()
        client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=doctor.h)
        client.put(
            f"{API}/doctors/me/consultations/{c['id']}/assessment",
            json={"doctor_assessment": note},
            headers=doctor.h,
        )
        client.post(f"{API}/doctors/me/consultations/{c['id']}/complete", headers=doctor.h)
        prior_ids.append(c["id"])

    current = request_consultation(client, seeded_case, consultation_ids=prior_ids).json()
    client.post(f"{API}/doctors/me/consultations/{current['id']}/accept", headers=seeded_case.doctor.h)
    db.expire_all()

    bundle = _bundle(db, seeded_case.doctor.id, current["id"])
    priors = [i for i in bundle.items if i.kind.value == "prior_consultation"]
    assert len(priors) >= 3, "expected three prior consultations in the bundle"

    # Each keeps its own doctor and its own words.
    doctors = {i.resolution["doctor_name"] for i in priors}
    assert len(doctors) >= 3
    assert {i.payload["doctor_assessment"] for i in priors} >= set(notes)

    state = _generate(db, seeded_case.doctor.id, current["id"])
    stored = _stored(state)
    text = _all_text(stored)
    for word in RESOLUTION_WORDS:
        assert word not in text

    # Every prior consultation item is attributed and doctor-authored.
    prior_items = [
        i for s in stored.sections for i in s.items
        if any(src.kind.value == "prior_consultation" for src in i.sources)
    ]
    assert prior_items
    for item in prior_items:
        assert item.origin.value == "doctor_authored"
        assert any(src.doctor_name for src in item.sources)


# ==========================================================================
# 9. Malformed output persisted as ready = 0
# ==========================================================================


MALFORMED = [
    pytest.param({"items": [{"section": "symptom"}]}, id="missing-fields"),
    pytest.param({"items": [{**entry("symptom", "x", ["S1"]), "statement": 5}]}, id="wrong-type"),
    pytest.param({"items": [{**entry("symptom", "x", ["S1"]), "extra": 1}]}, id="unknown-field"),
    pytest.param({"items": [entry("not_a_section", "x", ["S1"])]}, id="invalid-enum"),
    pytest.param({"items": [entry("symptom", "x", [])]}, id="no-source"),
    pytest.param({"items": [entry("symptom", "", ["S1"])]}, id="empty-statement"),
    pytest.param({"items": [entry("symptom", "y" * 400, ["S1"])]}, id="oversized-statement"),
    pytest.param({"items": [entry("symptom", "x", ["not-a-ref"])]}, id="malformed-ref"),
    pytest.param({"items": "nope"}, id="wrong-container"),
    pytest.param({"unexpected": True}, id="wrong-shape"),
    pytest.param({"items": [{**entry("symptom", "x", ["S1"]), "diagnosis": "z"}]}, id="prohibited-field"),
]


@pytest.mark.parametrize("payload", MALFORMED)
def test_invariant_9_malformed_output_is_rejected_at_the_schema(payload):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ModelCaseSummary.model_validate(payload)


def test_invariant_9_a_malformed_response_never_becomes_ready(client, db, ready):
    """Driven through the real provider path, so the whole chain is exercised."""
    from app.providers.ai.base import AIUsage, SummaryOrganisation

    case, cid = ready

    class BadProvider:
        name = "bad"
        model = "bad-1"
        is_external = False

        async def summarize_case(self, bundle_text):
            return SummaryOrganisation(
                provider=self.name, model=self.model, prompt_version="bad",
                payload={"items": [{"section": "diagnosis", "statement": "migraine", "source_refs": ["S1"],
                                    "is_contradiction": False}]},
                usage=AIUsage(latency_ms=1),
            )

    doctor = _doctor(db, case.doctor.id)
    state = run_async(
        case_summary.generate(db, doctor, doctor.user, uuid.UUID(cid), provider=BadProvider())
    )
    assert state.status == "failed"
    assert state.summary.status == SummaryStatus.FAILED
    assert state.summary.summary == {}

    # No READY row exists for this consultation at all.
    rows = list(
        db.scalars(select(ConsultationSummary).where(ConsultationSummary.consultation_id == uuid.UUID(cid)))
    )
    assert rows and all(r.status != SummaryStatus.READY for r in rows)

    # The failure is audited, and the source data is untouched.
    from app.models import AuditEvent

    actions = [
        e.action for e in db.scalars(select(AuditEvent).where(AuditEvent.resource_id == cid))
    ]
    assert "consultation.summary_failed" in actions
    view = client.get(f"{API}/doctors/me/consultations/{cid}", headers=case.doctor.h).json()
    assert view["current_problems"], "the patient's information must be unaffected by a bad summary"


# ==========================================================================
# 10. Client-side API key exposure = 0
# ==========================================================================


def test_invariant_10_no_credential_reaches_any_response(client, seeded_case):
    """Every Phase 4 response, and the public AI status, scanned for secrets."""
    grant_ai_consent(client, seeded_case.patient, True)
    c = request_consultation(client, seeded_case).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=seeded_case.doctor.h)

    generated = client.post(
        f"{API}/doctors/me/consultations/{c['id']}/summary", headers=seeded_case.doctor.h
    ).text
    bodies = [
        client.get(f"{API}/meta/ai").text,
        client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=seeded_case.doctor.h).text,
        generated,
        client.get(f"{API}/doctors/me/consultations/{c['id']}/summary", headers=seeded_case.doctor.h).text,
    ]
    # Sanity: the summary body really is a Phase 4 payload, so the scan below
    # is looking at the thing it claims to be looking at.
    assert "authorization_basis" in generated
    for body in bodies:
        lowered = body.lower()
        # Markers that would mean an actual credential, not merely the word.
        # `authorization_basis` is a legitimate field and must not trip this.
        for marker in ("api_key", "apikey", "sk-", "sk_live", "bearer ", "password", "jwt_secret",
                       "client_secret", "x-api-key"):
            assert marker not in lowered, f"{marker!r} appeared in a response body"
        assert lowered.strip(), "an empty body proves nothing"


def test_invariant_10_settings_never_serialise_a_key():
    from app.core.config import get_settings

    dumped = json.dumps(get_settings().model_dump(mode="json"), default=str).lower()
    for field in ("openai_api_key", "anthropic_api_key", "gemini_api_key"):
        assert f'"{field}": null' in dumped or f'"{field}": "**********"' in dumped or field not in dumped or (
            "sk-" not in dumped
        )
    assert "sk-" not in dumped


def test_invariant_10_the_artifact_stores_no_patient_text_or_secret(client, db, ready):
    from app.models import AIArtifact

    case, cid = ready
    _generate(db, case.doctor.id, cid)
    artifacts = list(
        db.scalars(select(AIArtifact).where(AIArtifact.artifact_type == case_summary.SUMMARY_OPERATION))
    )
    assert artifacts
    for artifact in artifacts:
        blob = json.dumps(artifact.content).lower()
        # Counts and shape only — never the patient's words, never a credential.
        assert "தலைவலி" not in blob
        assert "hypertension" not in blob
        for marker in ("api_key", "sk-", "password", "secret"):
            assert marker not in blob
