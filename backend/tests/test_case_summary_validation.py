"""Phase 4: application-side validation of a model's summary.

Every test here feeds a hand-written `ModelCaseSummary` — what a provider might
return, including what a badly behaved one might return — through the validator
against a real bundle, and asserts that the item survives or is dropped.

Nothing is ever repaired. A failing item is dropped and counted.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.models import Consultation, DoctorProfile
from app.models.enums import (
    BundleItemKind,
    FactSubject,
    SummaryItemOrigin,
    SummarySectionKind,
)
from app.schemas.summary import ModelCaseSummary
from app.services import case_summary_bundle, consultation_service, summary_validation
from tests.conftest import API, create_problem, process_record, request_consultation


def _bundle(db, doctor_id, consultation_id):
    doctor = db.get(DoctorProfile, uuid.UUID(doctor_id))
    c = db.get(Consultation, uuid.UUID(consultation_id))
    assert doctor
    return case_summary_bundle.build_source_bundle(
        db, consultation_service.resolve_authorized_context(db, c)
    )


def _model(items, **kw):
    return ModelCaseSummary(items=items, **kw)


def _item(section, statement, refs, contradiction=False):
    return {
        "section": section,
        "statement": statement,
        "source_refs": refs,
        "is_contradiction": contradiction,
    }


@pytest.fixture
def case(client, db, seeded_case):
    """A consultation whose bundle has a patient statement, a problem and a record."""
    c = request_consultation(client, seeded_case).json()
    return _bundle(db, seeded_case.doctor.id, c["id"])


@pytest.fixture
def fact_case(client, db, consented_patient, make_doctor):
    """A bundle whose facts the patient has confirmed, plus the record they came from."""
    doctor = make_doctor()
    problem = create_problem(client, consented_patient)
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    for fact in facts:
        client.post(
            f"{API}/patients/me/ai/facts/{fact['id']}", json={"action": "confirm"},
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
    return _bundle(db, doctor.id, c["id"])


# ---------- the schema layer ----------


def test_schema_rejects_a_diagnosis_field():
    with pytest.raises(ValidationError):
        ModelCaseSummary.model_validate(
            {"items": [{**_item("symptom", "Headache", ["S1"]), "diagnosis": "migraine"}]}
        )


def test_schema_rejects_an_unknown_section():
    for forbidden in ("diagnosis", "differential", "triage", "risk_score", "treatment", "prognosis"):
        with pytest.raises(ValidationError):
            ModelCaseSummary.model_validate({"items": [_item(forbidden, "x", ["S1"])]})


def test_schema_rejects_an_uncited_item():
    with pytest.raises(ValidationError):
        ModelCaseSummary.model_validate({"items": [_item("symptom", "Headache", [])]})


def test_schema_rejects_a_statement_long_enough_to_hide_prose():
    with pytest.raises(ValidationError):
        ModelCaseSummary.model_validate({"items": [_item("symptom", "x" * 201, ["S1"])]})


# ---------- reference resolution ----------


def test_unknown_reference_is_dropped(case):
    outcome = summary_validation.validate_summary(
        _model([_item("patient_statement", "Patient asked for a review", ["S999"])]), case
    )
    assert outcome.items == []
    assert outcome.dropped == 1
    assert "unknown_source_reference" in outcome.warnings


def test_a_real_reference_resolves_to_real_identifiers(case):
    statement = next(i for i in case.items if i.kind == BundleItemKind.PATIENT_STATEMENT)
    outcome = summary_validation.validate_summary(
        _model([_item("patient_statement", "Patient asked for a review", [statement.ref])]), case
    )
    assert len(outcome.items) == 1
    source = outcome.items[0].sources[0]
    assert source.ref == statement.ref
    assert str(source.consultation_id) == statement.resolution["consultation_id"]
    assert outcome.dropped == 0


def test_partially_valid_citation_drops_the_whole_item(case):
    """One bad reference poisons the item. Half-resolving it would be guessing."""
    good = case.items[0].ref
    outcome = summary_validation.validate_summary(
        _model([_item("patient_statement", "Mixed", [good, "S998"])]), case
    )
    assert outcome.items == []
    assert outcome.dropped == 1


# ---------- provenance the model cannot set ----------


def test_origin_is_derived_from_the_source(case):
    problem = next(i for i in case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    outcome = summary_validation.validate_summary(
        _model([_item("current_problem", "Reported headache and dizziness", [problem.ref])]), case
    )
    assert outcome.items[0].origin == SummaryItemOrigin.PATIENT_PROVIDED


def test_doctor_authored_cannot_be_recast_as_a_patient_claim(client, db, seeded_case):
    """§14 — a doctor's assessment must never reappear as a confirmed symptom."""
    first = request_consultation(client, seeded_case).json()
    client.post(f"{API}/doctors/me/consultations/{first['id']}/accept", headers=seeded_case.doctor.h)
    client.put(
        f"{API}/doctors/me/consultations/{first['id']}/assessment",
        json={"doctor_assessment": "Reviewed and advised rest."},
        headers=seeded_case.doctor.h,
    )
    client.post(f"{API}/doctors/me/consultations/{first['id']}/complete", headers=seeded_case.doctor.h)
    second = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, second["id"])
    prior = next(i for i in bundle.items if i.kind == BundleItemKind.PRIOR_CONSULTATION)

    # Cited into a patient-claim section: dropped.
    recast = summary_validation.validate_summary(
        _model([_item("symptom", "Rest advised", [prior.ref])]), bundle
    )
    assert recast.items == []
    assert "doctor_authored_recast_as_patient_claim" in recast.warnings

    # Cited into a doctor section: kept, and attributed to the doctor.
    kept = summary_validation.validate_summary(
        _model([_item("prior_consultation", "Previous assessment on file", [prior.ref])]), bundle
    )
    assert len(kept.items) == 1
    assert kept.items[0].origin == SummaryItemOrigin.DOCTOR_AUTHORED
    assert kept.items[0].sources[0].doctor_name == "Dr. Meera Sharma"


def test_prior_consultation_section_needs_a_doctor_source(case):
    problem = next(i for i in case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    outcome = summary_validation.validate_summary(
        _model([_item("prior_consultation", "Seen before", [problem.ref])]), case
    )
    assert outcome.items == []
    assert "prior_consultation_without_doctor_source" in outcome.warnings


# ---------- attribution ----------


def _family_bundle(client, db, consented_patient, make_doctor):
    doctor = make_doctor()
    problem = create_problem(
        client, consented_patient, text="My father has diabetes. I have a headache.", language="en"
    )
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    for fact in facts:
        client.post(
            f"{API}/patients/me/ai/facts/{fact['id']}", json={"action": "confirm"},
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
    return _bundle(db, doctor.id, c["id"]), facts


def test_subject_is_copied_from_the_source_fact(client, db, consented_patient, make_doctor):
    bundle, _ = _family_bundle(client, db, consented_patient, make_doctor)
    family = [i for i in bundle.items if i.resolution.get("subject") == FactSubject.FAMILY.value]
    if not family:
        pytest.skip("the local provider did not attribute a family fact in this case")

    outcome = summary_validation.validate_summary(
        _model([_item("medical_history", "Diabetes", [family[0].ref])]), bundle
    )
    assert len(outcome.items) == 1
    assert outcome.items[0].subject == FactSubject.FAMILY
    assert outcome.items[0].subject_evidence


def test_one_statement_may_not_cover_two_peoples_health(client, db, consented_patient, make_doctor):
    bundle, _ = _family_bundle(client, db, consented_patient, make_doctor)
    subjects = {i.ref: i.resolution.get("subject") for i in bundle.items if i.resolution.get("subject")}
    selves = [ref for ref, s in subjects.items() if s == FactSubject.SELF.value]
    families = [ref for ref, s in subjects.items() if s == FactSubject.FAMILY.value]
    if not (selves and families):
        pytest.skip("this case has no mixed-subject pair to merge")

    outcome = summary_validation.validate_summary(
        _model([_item("medical_history", "Diabetes and headache", [selves[0], families[0]])]), bundle
    )
    assert outcome.items == []
    assert "mixed_subject_attribution" in outcome.warnings


# ---------- unsupported content ----------


def test_a_health_claim_needs_a_confirmed_source(case):
    """Free text can support a pointer, never a claim about the patient's health.

    Turning free text into a health claim is extraction, and extraction goes
    through the patient (Phase 2). This is the check that does not depend on a
    word list, so an invented condition is dropped whether or not the lexicon
    happens to know it.
    """
    problem = next(i for i in case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    outcome = summary_validation.validate_summary(
        _model([_item("medical_history", "Patient has cancer", [problem.ref])]), case
    )
    assert outcome.items == []
    assert "health_claim_without_confirmed_source" in outcome.warnings


def test_a_pointer_section_may_rest_on_free_text(case):
    """The same source is fine under current_problem, which points rather than claims."""
    problem = next(i for i in case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    outcome = summary_validation.validate_summary(
        _model([_item("current_problem", "Current problem recorded, 2026-09-23", [problem.ref])]), case
    )
    assert len(outcome.items) == 1


LONG_TEXT = (
    "I have had a headache every morning for the past three days and it gets worse "
    "when I stand up quickly, and I also feel unsteady on the stairs at home."
)


def test_a_statement_that_copies_source_text_is_dropped(client, db, seeded_case):
    """A long verbatim span of free text is a copy, not an organising line.

    This is what stops a real provider doing what an early version of the local
    one did: lifting a whole record into a statement, so that anything written
    inside it reads as the summary's own line.
    """
    problem = client.post(
        f"{API}/patients/me/current-problems",
        json={"text": LONG_TEXT, "language": "en"},
        headers=seeded_case.patient.h,
    ).json()
    c = request_consultation(client, seeded_case, current_problem_ids=[problem["id"]]).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])
    item = next(i for i in bundle.items if i.kind == BundleItemKind.CURRENT_PROBLEM)

    copied = LONG_TEXT[:190]
    assert len(copied) >= 80
    outcome = summary_validation.validate_summary(
        _model([_item("current_problem", copied, [item.ref])]), bundle
    )
    assert outcome.items == []
    assert "statement_copies_source_text" in outcome.warnings

    # A short organising line over the same source is fine.
    ok = summary_validation.validate_summary(
        _model([_item("current_problem", "Current problem recorded, 2026-09-23", [item.ref])]), bundle
    )
    assert len(ok.items) == 1


def test_an_unsupported_medical_term_is_dropped(fact_case):
    fact = next(i for i in fact_case.items if i.kind == BundleItemKind.FACT)
    outcome = summary_validation.validate_summary(
        _model([_item("symptom", "Chest pain", [fact.ref])]), fact_case
    )
    assert outcome.items == []
    assert "unsupported_medical_term" in outcome.warnings


def test_an_unstated_absence_is_dropped(fact_case):
    fact = next(i for i in fact_case.items if i.kind == BundleItemKind.FACT)
    outcome = summary_validation.validate_summary(
        _model([_item("allergy", "No known allergies", [fact.ref])]), fact_case
    )
    assert outcome.items == []
    assert "unstated_absence" in outcome.warnings


def test_a_quote_that_is_not_in_the_source_is_dropped(client, db, consented_patient, make_doctor):
    doctor = make_doctor()
    problem = create_problem(client, consented_patient)
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
    bundle = _bundle(db, doctor.id, c["id"])
    fact_item = next(i for i in bundle.items if i.kind == BundleItemKind.FACT)

    # Corrupt the stored quote so it no longer appears in the source text.
    fact_item.resolution["quote"] = "a quote that was never written anywhere"
    outcome = summary_validation.validate_summary(
        _model([_item("symptom", fact_item.payload["value"], [fact_item.ref])]), bundle
    )
    assert outcome.items == []
    assert "quote_not_found_in_source" in outcome.warnings


# ---------- assembly ----------


def test_contradictions_are_preserved_not_resolved(fact_case):
    """The record that denies and the fact that reports both survive, side by side."""
    fact = next(i for i in fact_case.items if i.kind == BundleItemKind.FACT)
    problem = next(i for i in fact_case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    outcome = summary_validation.validate_summary(
        _model(
            [_item("symptom", "Records differ about this symptom", [problem.ref, fact.ref], True)]
        ),
        fact_case,
    )
    assert len(outcome.items) == 1
    assert outcome.items[0].is_contradiction is True
    # Both sides survive; nothing picked a winner.
    assert {s.ref for s in outcome.items[0].sources} == {problem.ref, fact.ref}


def test_sections_follow_the_canonical_order(case):
    problem = next(i for i in case.items if i.kind == BundleItemKind.CURRENT_PROBLEM)
    statement = next(i for i in case.items if i.kind == BundleItemKind.PATIENT_STATEMENT)
    model = _model(
        [
            _item("patient_statement", "Asked for a review", [statement.ref]),
            _item("current_problem", "Reported headache and dizziness", [problem.ref]),
        ],
        section_order=[SummarySectionKind.PATIENT_STATEMENT],
    )
    outcome = summary_validation.validate_summary(model, case)
    stored = summary_validation.assemble(model, case, outcome)
    assert [s.kind for s in stored.sections] == [
        SummarySectionKind.PATIENT_STATEMENT,
        SummarySectionKind.CURRENT_PROBLEM,
    ]


def test_assembly_carries_pending_count_and_truncation(case):
    model = _model([])
    stored = summary_validation.assemble(model, case, summary_validation.validate_summary(model, case))
    assert stored.pending_fact_count == case.pending_fact_count
    assert stored.truncated == case.truncated
    assert stored.version == 1
