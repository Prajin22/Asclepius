"""Patient confirmation: AI output becomes trusted only when the patient says so."""

import uuid

from sqlalchemy import select

from app.models import AIExtractedFact, AuditEvent, MedicalRecord
from app.models.enums import RecordSource
from tests.conftest import API, create_problem, process_record


def facts_of(body, category=None):
    return [f for f in body["facts"] if category is None or f["category"] == category]


def act(client, patient, fact_id, action, value=None):
    payload = {"action": action} | ({"value": value} if value else {})
    return client.post(f"{API}/patients/me/ai/facts/{fact_id}", json=payload, headers=patient.h)


def test_facts_start_pending_and_are_not_health_records(client, db, patient_with_ai):
    assert all(f["review_state"] == "pending" for f in patient_with_ai.ai["facts"])
    assert db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED)) is None


def test_confirm_marks_the_fact_and_keeps_attribution(client, db, patient_with_ai):
    fact = patient_with_ai.ai["facts"][0]
    r = act(client, patient_with_ai.patient, fact["id"], "confirm")
    assert r.status_code == 200
    assert r.json()["review_state"] == "confirmed"
    assert r.json()["effective_value"] == fact["value"]


def test_confirming_an_allergy_creates_an_ai_extracted_record(client, db, consented_patient):
    record = create_problem(client, consented_patient, "I am allergic to penicillin.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    allergy = facts_of(body, "allergy")[0]

    act(client, consented_patient, allergy["id"], "confirm")
    created = db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED))
    assert created is not None
    assert "penicillin" in created.title.lower()
    assert created.content == "allergic to penicillin"  # the patient's own words
    assert created.type == "allergy"


def test_symptoms_do_not_become_records_on_confirmation(client, db, patient_with_ai):
    symptom = facts_of(patient_with_ai.ai, "symptom")[0]
    act(client, patient_with_ai.patient, symptom["id"], "confirm")
    assert db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED)) is None


def test_edit_replaces_the_value_but_keeps_the_ai_original(client, db, patient_with_ai):
    fact = patient_with_ai.ai["facts"][0]
    r = act(client, patient_with_ai.patient, fact["id"], "edit", "severe headache")
    body = r.json()
    assert body["review_state"] == "edited"
    assert body["edited_value"] == "severe headache"
    assert body["value"] == fact["value"]  # what the AI said is preserved
    assert body["effective_value"] == "severe headache"


def test_edit_requires_a_value(client, patient_with_ai):
    fact = patient_with_ai.ai["facts"][0]
    assert act(client, patient_with_ai.patient, fact["id"], "edit").status_code == 422


def test_reject_removes_any_record_created_earlier(client, db, consented_patient):
    record = create_problem(client, consented_patient, "I take metformin 500 mg daily.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    medication = facts_of(body, "medication")[0]

    act(client, consented_patient, medication["id"], "confirm")
    assert db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED)) is not None

    r = act(client, consented_patient, medication["id"], "reject")
    assert r.json()["review_state"] == "rejected"
    assert db.scalar(select(MedicalRecord).where(MedicalRecord.source == RecordSource.AI_EXTRACTED)) is None


def test_confirmation_state_persists(client, consented_patient):
    record = create_problem(client, consented_patient)
    body = process_record(client, consented_patient, record["id"]).json()
    act(client, consented_patient, body["facts"][0]["id"], "confirm")

    reloaded = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=consented_patient.h).json()
    states = {f["id"]: f["review_state"] for f in reloaded["facts"]}
    assert states[body["facts"][0]["id"]] == "confirmed"


def test_unknown_action_is_rejected(client, patient_with_ai):
    fact = patient_with_ai.ai["facts"][0]
    assert act(client, patient_with_ai.patient, fact["id"], "approve").status_code == 422


def test_another_patient_cannot_review_your_facts(client, make_patient, patient_with_ai):
    intruder = make_patient(email="intruder@example.com")
    fact = patient_with_ai.ai["facts"][0]
    assert act(client, intruder, fact["id"], "confirm").status_code == 404


def test_review_actions_are_audited(client, db, patient_with_ai):
    fact = patient_with_ai.ai["facts"][0]
    act(client, patient_with_ai.patient, fact["id"], "confirm")
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "ai.fact_confirmed")) is not None


def test_missing_fact_is_not_found(client, patient_with_ai):
    assert act(client, patient_with_ai.patient, str(uuid.uuid4()), "confirm").status_code == 404
