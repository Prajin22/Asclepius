"""The doctor sees original + normalised + structured + evidence + status."""

from tests.conftest import API, create_problem, process_record, request_consultation


def _share_processed_problem(client, case, patient):
    """Patient processes their problem and shares it in a consultation."""
    record = create_problem(client, patient, "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது.", "ta")
    body = process_record(client, patient, record["id"]).json()
    client.post(f"{API}/patients/me/ai/facts/{body['facts'][0]['id']}", json={"action": "confirm"}, headers=patient.h)
    consultation = request_consultation(
        client, case, current_problem_ids=[record["id"]], medical_record_ids=[], document_ids=[]
    ).json()
    return record, body, consultation


def test_case_view_shows_ai_beside_the_original(client, seeded_case):
    case = seeded_case
    from tests.conftest import grant_ai_consent

    grant_ai_consent(client, case.patient)
    record, ai, consultation = _share_processed_problem(client, case, case.patient)

    view = client.get(f"{API}/doctors/me/consultations/{consultation['id']}", headers=case.doctor.h).json()

    # The original is still first-class.
    original = next(p for p in view["current_problems"] if p["id"] == record["id"])
    assert original["content"] == "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது."
    assert original["source_language"] == "ta"

    insight = next(i for i in view["ai_insights"] if i["record_id"] == record["id"])
    assert insight["status"] == "ok"
    assert insight["detected_language"] == "ta"
    assert "headache" in insight["normalized_english"]
    assert insight["provider"] == "mock" and insight["model"]
    values = {f["value"] for f in insight["facts"]}
    assert "headache" in values
    for fact in insight["facts"]:
        assert fact["evidence_quote"] in original["content"]
        assert fact["review_state"] in ("pending", "confirmed", "edited")
    assert any(f["review_state"] == "confirmed" for f in insight["facts"])


def test_rejected_facts_are_not_shown_to_the_doctor(client, seeded_case):
    case = seeded_case
    from tests.conftest import grant_ai_consent

    grant_ai_consent(client, case.patient)
    record, ai, consultation = _share_processed_problem(client, case, case.patient)
    rejected = ai["facts"][-1]
    client.post(
        f"{API}/patients/me/ai/facts/{rejected['id']}", json={"action": "reject"}, headers=case.patient.h
    )

    view = client.get(f"{API}/doctors/me/consultations/{consultation['id']}", headers=case.doctor.h).json()
    insight = next(i for i in view["ai_insights"] if i["record_id"] == record["id"])
    assert all(f["value"] != rejected["value"] or f["review_state"] != "rejected" for f in insight["facts"])


def test_no_ai_insight_for_unprocessed_or_unshared_records(client, seeded_case):
    case = seeded_case
    from tests.conftest import grant_ai_consent

    grant_ai_consent(client, case.patient)
    # Processed but NOT shared.
    private = create_problem(client, case.patient, "I have chest pain.", "en")
    process_record(client, case.patient, private["id"])

    consultation = request_consultation(client, case).json()
    view = client.get(f"{API}/doctors/me/consultations/{consultation['id']}", headers=case.doctor.h).json()
    assert all(i["record_id"] != private["id"] for i in view["ai_insights"])


def test_doctor_cannot_read_patient_ai_artifacts_directly(client, seeded_case):
    case = seeded_case
    from tests.conftest import grant_ai_consent

    grant_ai_consent(client, case.patient)
    record, ai, consultation = _share_processed_problem(client, case, case.patient)
    artifact_id = ai["runs"][0]["artifact_id"]
    assert client.get(f"{API}/patients/me/ai/artifacts/{artifact_id}", headers=case.doctor.h).status_code == 403
