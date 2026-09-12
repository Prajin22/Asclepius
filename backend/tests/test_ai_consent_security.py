"""Consent enforcement and access control around AI data."""

import uuid

from sqlalchemy import select

from app.models import AIArtifact, AuditEvent
from tests.ai_stubs import RecordingProvider
from tests.conftest import API, create_problem, grant_ai_consent, process_record


def test_processing_is_refused_without_consent_and_no_provider_is_called(client, db, make_patient, monkeypatch):
    patient = make_patient()
    provider = RecordingProvider()
    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: provider)

    record = create_problem(client, patient)
    r = process_record(client, patient, record["id"])

    assert r.status_code == 403
    assert r.json()["code"] == "ai_consent_required"
    assert provider.calls == []  # nothing was sent anywhere
    assert db.scalar(select(AIArtifact)) is None


def test_patient_information_still_works_without_consent(client, make_patient):
    patient = make_patient()
    record = create_problem(client, patient)
    assert client.get(f"{API}/patients/me/records", headers=patient.h).status_code == 200
    state = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=patient.h).json()
    assert state["status"] == "not_processed"


def test_consent_is_off_by_default_and_recorded_when_changed(client, db, make_patient):
    patient = make_patient()
    profile = client.get(f"{API}/patients/me/profile", headers=patient.h).json()
    assert profile["ai_processing_consent"] is False

    granted = grant_ai_consent(client, patient).json()
    assert granted["ai_processing_consent"] is True
    assert granted["ai_consent_updated_at"] is not None

    withdrawn = grant_ai_consent(client, patient, granted=False).json()
    assert withdrawn["ai_processing_consent"] is False
    actions = set(db.scalars(select(AuditEvent.action)))
    assert {"ai.consent_granted", "ai.consent_withdrawn"} <= actions


def test_withdrawing_consent_blocks_further_processing(client, consented_patient):
    record = create_problem(client, consented_patient)
    assert process_record(client, consented_patient, record["id"]).status_code == 200
    grant_ai_consent(client, consented_patient, granted=False)
    assert process_record(client, consented_patient, record["id"]).status_code == 403


def test_another_patient_cannot_read_your_ai_artifacts(client, make_patient, patient_with_ai):
    intruder = make_patient(email="intruder@example.com")
    artifact_id = patient_with_ai.ai["runs"][0]["artifact_id"]
    assert client.get(f"{API}/patients/me/ai/artifacts/{artifact_id}", headers=intruder.h).status_code == 404
    assert (
        client.get(f"{API}/patients/me/records/{patient_with_ai.record['id']}/ai", headers=intruder.h).status_code
        == 404
    )


def test_owner_can_read_their_artifact(client, patient_with_ai):
    artifact_id = patient_with_ai.ai["runs"][0]["artifact_id"]
    body = client.get(f"{API}/patients/me/ai/artifacts/{artifact_id}", headers=patient_with_ai.patient.h).json()
    assert body["provider"] == "mock"
    assert body["prompt_version"]
    assert "api_key" not in str(body).lower()


def test_doctor_cannot_use_patient_ai_endpoints(client, make_doctor, patient_with_ai):
    doctor = make_doctor()
    assert process_record(client, doctor, patient_with_ai.record["id"]).status_code == 403
    assert client.put(f"{API}/patients/me/ai-consent", json={"granted": True}, headers=doctor.h).status_code == 403


def test_unauthenticated_ai_requests_are_rejected(client, patient_with_ai):
    assert client.post(f"{API}/patients/me/records/{patient_with_ai.record['id']}/ai-process").status_code == 401
    assert client.get(f"{API}/patients/me/ai/artifacts/{uuid.uuid4()}").status_code == 401


def test_api_never_returns_provider_credentials(client, patient_with_ai, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-appear")
    for path in ("/meta/ai", f"/patients/me/records/{patient_with_ai.record['id']}/ai"):
        body = client.get(f"{API}{path}", headers=patient_with_ai.patient.h).text.lower()
        assert "sk-should-never-appear" not in body
        assert "api_key" not in body
