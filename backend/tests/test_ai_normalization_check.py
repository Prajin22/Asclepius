"""The three layers must keep saying the same thing."""

from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactSubject
from app.providers.ai.base import (
    AIUsage,
    Evidence,
    ExtractedFact,
    ExtractionResult,
    NormalizationResult,
)
from app.services.normalization_check import check_normalization
from tests.ai_stubs import RecordingProvider
from tests.conftest import API, create_problem, process_record

SOURCE_TA = "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது."


def fact(value: str, category=FactCategory.SYMPTOM, quote="தலைவலி", subject=FactSubject.SELF):
    return ExtractedFact(category=category, value=value, evidence=Evidence(quote=quote), subject=subject)


def test_faithful_normalisation_passes():
    check = check_normalization(SOURCE_TA, "Patient reports headache. Reported duration: 2 days.", [fact("headache")])
    assert check.status == "ok"
    assert check.added_terms == [] and check.dropped_facts == []


def test_added_medical_term_is_flagged():
    """The English asserts diabetes; neither the source nor any fact supports it."""
    check = check_normalization(SOURCE_TA, "Patient reports headache and has diabetes.", [fact("headache")])
    assert check.status == "review"
    assert "diabetes" in check.added_terms


def test_dropped_fact_is_flagged():
    check = check_normalization("I have a headache and a cough.", "Patient reports headache.",
                                [fact("headache"), fact("cough", quote="cough")])
    assert check.status == "review"
    assert "cough" in check.dropped_facts


def test_lost_attribution_is_flagged():
    check = check_normalization(
        "My father has diabetes.",
        "Patient reports diabetes.",
        [fact("diabetes", FactCategory.MEDICAL_HISTORY, quote="diabetes", subject=FactSubject.FAMILY)],
    )
    assert check.status == "review"
    assert "attribution_lost" in check.notes


def test_no_normalisation_is_not_a_failure():
    assert check_normalization(SOURCE_TA, None, []).status == "ok"


def test_mock_pipeline_reports_a_clean_check(client, consented_patient):
    record = create_problem(client, consented_patient, SOURCE_TA, "ta")
    body = process_record(client, consented_patient, record["id"]).json()
    assert body["normalization_check"]["status"] == "ok"
    # All three layers are inspectable together.
    assert body["original_text"] == SOURCE_TA
    assert body["normalized_english"]
    assert body["facts"]


def test_drifting_provider_is_flagged_to_the_patient(client, consented_patient, monkeypatch):
    class DriftingProvider(RecordingProvider):
        name = "drifting"

        async def normalize_to_english(self, text, source_language):
            self.calls.append("normalize")
            return NormalizationResult(
                provider=self.name, model=self.model, original_text=text, source_language=source_language,
                # Invents a diagnosis the patient never mentioned.
                normalized_text_en="Patient reports headache caused by diabetes.", usage=AIUsage(),
            )

        async def extract_medical_information(self, text, language):
            self.calls.append("extract")
            return ExtractionResult(
                provider=self.name, model=self.model, usage=AIUsage(),
                facts=[ExtractedFact(category=FactCategory.SYMPTOM, value="headache",
                                     evidence=Evidence(quote="headache"))],
            )

    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: DriftingProvider())
    record = create_problem(client, consented_patient, "I have a headache.", "en")
    body = process_record(client, consented_patient, record["id"]).json()

    assert body["normalization_check"]["status"] == "review"
    assert "diabetes" in body["normalization_check"]["added_terms"]
    # The invented term never became a fact.
    assert all(f["value"] != "diabetes" for f in body["facts"])


def test_check_is_stored_and_returned_later(client, consented_patient):
    record = create_problem(client, consented_patient, SOURCE_TA, "ta")
    process_record(client, consented_patient, record["id"])
    stored = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=consented_patient.h).json()
    assert stored["normalization_check"]["status"] == "ok"
    assert stored["original_text"] == SOURCE_TA


def test_doctor_view_carries_all_three_layers(client, seeded_case):
    from tests.conftest import grant_ai_consent, request_consultation

    case = seeded_case
    grant_ai_consent(client, case.patient)
    record = create_problem(client, case.patient, SOURCE_TA, "ta")
    process_record(client, case.patient, record["id"])
    consultation = request_consultation(
        client, case, current_problem_ids=[record["id"]], medical_record_ids=[], document_ids=[]
    ).json()

    view = client.get(f"{API}/doctors/me/consultations/{consultation['id']}", headers=case.doctor.h).json()
    insight = next(i for i in view["ai_insights"] if i["record_id"] == record["id"])
    assert insight["original_text"] == SOURCE_TA
    assert insight["normalized_english"]
    assert insight["facts"]
    assert insight["normalization_check"]["status"] == "ok"
