"""Subject attribution: a relative's condition is never the patient's."""

import pytest
from sqlalchemy import select

from app.core.languages import LanguageCode
from app.models import AIExtractedFact, MedicalRecord
from app.models.enums import FactCategory, FactSubject, RecordSource, RecordType
from app.providers.ai import MockAIProvider
from app.services.ai_facts import record_type_for
from tests.conftest import API, create_problem, process_record, run_async


def extract(text: str, language: LanguageCode = LanguageCode.EN):
    return run_async(MockAIProvider().extract_medical_information(text, language))


def subjects(result) -> dict[str, FactSubject]:
    return {f.value: f.subject for f in result.facts}


# ---------- extraction ----------


def test_first_person_statement_is_the_patient():
    result = extract("I have diabetes and I take metformin.")
    assert subjects(result)["diabetes"] == FactSubject.SELF
    assert all(f.subject_evidence is None for f in result.facts)


@pytest.mark.parametrize(
    ("text", "language", "cue"),
    [
        ("My father has diabetes.", LanguageCode.EN, "my father"),
        ("என் அம்மாவுக்கு நீரிழிவு உள்ளது.", LanguageCode.TA, "அம்மா"),
        ("मेरे पिताजी को दमा है।", LanguageCode.HI, "मेरे पिता"),
    ],
)
def test_relatives_condition_is_attributed_to_family(text, language, cue):
    result = extract(text, language)
    assert result.facts, "expected the condition to be extracted"
    fact = result.facts[0]
    assert fact.subject == FactSubject.FAMILY
    assert cue in fact.subject_evidence.casefold() or cue in fact.subject_evidence


def test_attribution_does_not_leak_across_clauses():
    """The father's diabetes must not make the patient's own clause 'family'."""
    result = extract("My father has diabetes. I have a headache.")
    by_value = {f.value: f for f in result.facts}
    assert by_value["diabetes"].subject == FactSubject.FAMILY
    assert by_value["headache"].subject == FactSubject.SELF


def test_family_allergy_is_not_the_patients_allergy():
    result = extract("My mother is allergic to penicillin.")
    allergy = next(f for f in result.facts if f.category == FactCategory.ALLERGY)
    assert allergy.subject == FactSubject.FAMILY


def test_normalisation_reports_family_separately():
    result = run_async(
        MockAIProvider().normalize_to_english("என் அம்மாவுக்கு நீரிழிவு உள்ளது.", LanguageCode.TA)
    )
    assert "family member" in result.normalized_text_en.lower()
    assert not result.normalized_text_en.lower().startswith("patient reports diabetes")


# ---------- record mapping ----------


def test_record_type_mapping_by_subject(db, make_patient):
    def fact(category: FactCategory, subject: FactSubject) -> AIExtractedFact:
        return AIExtractedFact(
            category=category, subject=subject, value="x", evidence_quote="x",
            source_type="medical_record", source_id=__import__("uuid").uuid4(),
            patient_id=__import__("uuid").uuid4(), artifact_id=__import__("uuid").uuid4(),
        )

    assert record_type_for(fact(FactCategory.ALLERGY, FactSubject.SELF)) == RecordType.ALLERGY
    assert record_type_for(fact(FactCategory.MEDICATION, FactSubject.SELF)) == RecordType.MEDICATION
    assert record_type_for(fact(FactCategory.ALLERGY, FactSubject.FAMILY)) == RecordType.FAMILY_HISTORY
    assert record_type_for(fact(FactCategory.MEDICATION, FactSubject.FAMILY)) == RecordType.FAMILY_HISTORY
    assert record_type_for(fact(FactCategory.SYMPTOM, FactSubject.SELF)) is None
    assert record_type_for(fact(FactCategory.ALLERGY, FactSubject.UNKNOWN)) is None
    assert record_type_for(fact(FactCategory.ALLERGY, FactSubject.OTHER)) is None


# ---------- pipeline + confirmation ----------


def test_pipeline_stores_attribution(client, db, consented_patient):
    record = create_problem(client, consented_patient, "My father has diabetes. I have a headache.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    by_value = {f["value"]: f for f in body["facts"]}
    assert by_value["diabetes"]["subject"] == "family"
    assert by_value["diabetes"]["subject_evidence"]
    assert by_value["headache"]["subject"] == "self"


def test_confirming_a_family_allergy_never_creates_a_patient_allergy(client, db, consented_patient):
    """The safety case: a father's penicillin allergy is not the patient's."""
    record = create_problem(client, consented_patient, "My father is allergic to penicillin.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    allergy = next(f for f in body["facts"] if f["category"] == "allergy")
    assert allergy["subject"] == "family"

    client.post(f"{API}/patients/me/ai/facts/{allergy['id']}", json={"action": "confirm"},
                headers=consented_patient.h)

    created = list(db.scalars(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED)))
    assert len(created) == 1
    assert created[0].type == RecordType.FAMILY_HISTORY
    assert created[0].type != RecordType.ALLERGY
    assert "father" in created[0].title.lower()


def test_confirming_own_allergy_still_creates_an_allergy_record(client, db, consented_patient):
    record = create_problem(client, consented_patient, "I am allergic to penicillin.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    allergy = next(f for f in body["facts"] if f["category"] == "allergy")
    client.post(f"{API}/patients/me/ai/facts/{allergy['id']}", json={"action": "confirm"},
                headers=consented_patient.h)
    created = db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED))
    assert created.type == RecordType.ALLERGY


def test_doctor_sees_attribution(client, seeded_case):
    from tests.conftest import grant_ai_consent, request_consultation

    case = seeded_case
    grant_ai_consent(client, case.patient)
    record = create_problem(client, case.patient, "My father has diabetes. I have a headache.", "en")
    process_record(client, case.patient, record["id"])
    consultation = request_consultation(
        client, case, current_problem_ids=[record["id"]], medical_record_ids=[], document_ids=[]
    ).json()

    view = client.get(f"{API}/doctors/me/consultations/{consultation['id']}", headers=case.doctor.h).json()
    insight = next(i for i in view["ai_insights"] if i["record_id"] == record["id"])
    by_value = {f["value"]: f for f in insight["facts"]}
    assert by_value["diabetes"]["subject"] == "family"
    assert by_value["headache"]["subject"] == "self"
