"""Pipeline: detection, normalisation, extraction, provenance, caching."""

from sqlalchemy import select

from app.models import AIArtifact, AIExtractedFact, MedicalRecord
from app.models.enums import AIArtifactStatus, AIOperation
from tests.conftest import API, TAMIL_PROBLEM, create_problem, process_record


def test_full_pipeline_over_tamil_text(client, db, consented_patient):
    record = create_problem(client, consented_patient)
    r = process_record(client, consented_patient, record["id"])
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["status"] == "ok"
    assert body["detected_language"] == "ta"
    assert "headache" in body["normalized_english"]
    assert body["provider"] == "mock" and body["is_external_provider"] is False
    values = {f["value"] for f in body["facts"]}
    assert {"headache", "fever", "2 days"} <= values
    for fact in body["facts"]:
        assert fact["evidence_quote"] in TAMIL_PROBLEM
        assert fact["review_state"] == "pending"  # nothing is trusted yet

    # The original record is untouched.
    stored = db.get(MedicalRecord, __import__("uuid").UUID(record["id"]))
    assert stored.content == TAMIL_PROBLEM
    assert stored.source_language == "ta"
    assert stored.source == "patient"


def test_artifacts_capture_provenance_for_each_operation(client, db, consented_patient):
    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])
    artifacts = list(db.scalars(select(AIArtifact)))
    by_operation = {a.artifact_type: a for a in artifacts}
    assert set(by_operation) == {o.value for o in AIOperation}
    for artifact in artifacts:
        assert artifact.status == AIArtifactStatus.SUCCEEDED
        assert artifact.provider == "mock" and artifact.model
        assert artifact.prompt_version
        assert artifact.latency_ms is not None
        assert artifact.source_hash and artifact.cache_key
        assert artifact.source_references[0]["id"] == record["id"]
    assert by_operation["normalization"].output_language == "en"


def test_second_run_is_served_from_cache(client, db, consented_patient):
    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])
    first = db.scalar(select(AIArtifact).where(AIArtifact.artifact_type == "extraction"))

    again = process_record(client, consented_patient, record["id"]).json()
    assert all(run["cached"] for run in again["runs"])
    assert db.scalar(select(AIArtifact).where(AIArtifact.artifact_type == "extraction").order_by(AIArtifact.created_at)) is first
    assert len(list(db.scalars(select(AIArtifact)))) == 3  # no duplicates written


def test_changed_source_text_is_not_served_from_cache(client, db, consented_patient):
    first = create_problem(client, consented_patient)
    process_record(client, consented_patient, first["id"])
    second = create_problem(client, consented_patient, "मुझे तीन दिन से खांसी है।", "hi")
    body = process_record(client, consented_patient, second["id"]).json()
    assert body["detected_language"] == "hi"
    assert not any(run["cached"] for run in body["runs"])
    assert {f["value"] for f in body["facts"]} >= {"cough", "3 days"}


def test_english_input_keeps_its_own_wording(client, consented_patient):
    record = create_problem(client, consented_patient, "I have had a headache for two days.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    assert body["detected_language"] == "en"
    assert body["normalized_english"] == "I have had a headache for two days."


def test_stored_state_is_readable_without_reprocessing(client, consented_patient):
    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])
    state = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=consented_patient.h).json()
    assert state["status"] == "ok"
    assert state["facts"]


def test_unprocessed_record_reports_not_processed(client, consented_patient):
    record = create_problem(client, consented_patient)
    state = client.get(f"{API}/patients/me/records/{record['id']}/ai", headers=consented_patient.h).json()
    assert state["status"] == "not_processed"
    assert state["facts"] == []


def test_reprocessing_keeps_patient_decisions(client, db, consented_patient):
    record = create_problem(client, consented_patient)
    body = process_record(client, consented_patient, record["id"]).json()
    fact_id = body["facts"][0]["id"]
    client.post(f"{API}/patients/me/ai/facts/{fact_id}", json={"action": "confirm"}, headers=consented_patient.h)

    process_record(client, consented_patient, record["id"])
    kept = db.get(AIExtractedFact, __import__("uuid").UUID(fact_id))
    assert kept is not None and kept.review_state == "confirmed"


def test_reprocessing_does_not_duplicate_decided_facts(client, consented_patient):
    """Found by the live hardening run: a confirmed fact came back as a pending copy."""
    record = create_problem(client, consented_patient)
    body = process_record(client, consented_patient, record["id"]).json()
    first_count = len(body["facts"])
    confirmed = body["facts"][0]
    client.post(
        f"{API}/patients/me/ai/facts/{confirmed['id']}", json={"action": "confirm"}, headers=consented_patient.h
    )

    again = process_record(client, consented_patient, record["id"]).json()

    identities = [(f["category"], f["subject"], f["value"]) for f in again["facts"]]
    assert len(identities) == len(set(identities)), f"duplicate facts after re-processing: {identities}"
    assert len(again["facts"]) == first_count
    assert {f["id"]: f["review_state"] for f in again["facts"]}[confirmed["id"]] == "confirmed"


def test_duplicate_facts_within_one_run_are_collapsed(client, consented_patient, monkeypatch):
    from app.models.enums import FactCategory
    from app.providers.ai.base import Evidence, ExtractedFact
    from tests.ai_stubs import RecordingProvider

    twice = ExtractedFact(category=FactCategory.SYMPTOM, value="headache", evidence=Evidence(quote="headache"))
    provider = RecordingProvider(facts=[twice, twice.model_copy()])
    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: provider)

    record = create_problem(client, consented_patient, "I have a headache.", "en")
    body = process_record(client, consented_patient, record["id"]).json()
    assert [f["value"] for f in body["facts"]] == ["headache"]


def test_empty_record_is_not_processed(client, consented_patient):
    created = client.post(
        f"{API}/patients/me/records",
        json={"type": "condition", "title": "Checkup", "content": "", "source_language": "en"},
        headers=consented_patient.h,
    ).json()
    body = process_record(client, consented_patient, created["id"]).json()
    assert body["status"] == "not_processed"
    assert body["facts"] == []


def test_audit_trail_for_ai_operations(client, db, consented_patient):
    from app.models import AuditEvent

    record = create_problem(client, consented_patient)
    process_record(client, consented_patient, record["id"])
    actions = set(db.scalars(select(AuditEvent.action)))
    assert {"ai.consent_granted", "ai.processing_requested", "ai.processing_completed"} <= actions
