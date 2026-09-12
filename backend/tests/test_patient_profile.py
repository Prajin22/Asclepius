import uuid
from datetime import date

from app.models import MedicalRecord
from app.models.enums import RecordSource, RecordType
from tests.conftest import API


def test_profile_get_and_update(client, make_patient):
    p = make_patient()
    r = client.put(
        f"{API}/patients/me/profile",
        headers=p.h,
        json={"date_of_birth": "1980-03-15", "sex": "male", "phone": "+91 90000 00001",
              "emergency_contact_name": "Lakshmi", "preferred_language": "ta"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    today = date.today()
    expected_age = today.year - 1980 - ((today.month, today.day) < (3, 15))
    assert body["age"] == expected_age
    assert body["emergency_contact_name"] == "Lakshmi"
    assert body["preferred_language"] == "ta"


def test_profile_rejects_invalid_values(client, make_patient):
    p = make_patient()
    assert client.put(f"{API}/patients/me/profile", headers=p.h, json={"preferred_language": "xx"}).status_code == 422
    assert client.put(f"{API}/patients/me/profile", headers=p.h, json={"date_of_birth": "2999-01-01"}).status_code == 422
    assert client.put(f"{API}/patients/me/profile", headers=p.h, json={"display_name": None}).status_code == 422


def test_record_crud_and_source_is_patient(client, make_patient):
    p = make_patient()
    created = client.post(
        f"{API}/patients/me/records",
        headers=p.h,
        json={"type": "allergy", "title": "Penicillin", "content": "rash", "source_language": "en"},
    )
    assert created.status_code == 201
    rec = created.json()
    assert rec["source"] == "patient"

    upd = client.patch(f"{API}/patients/me/records/{rec['id']}", headers=p.h, json={"status": "resolved"})
    assert upd.json()["status"] == "resolved"

    listed = client.get(f"{API}/patients/me/records", params={"type": "allergy"}, headers=p.h).json()
    assert [x["id"] for x in listed] == [rec["id"]]

    assert client.delete(f"{API}/patients/me/records/{rec['id']}", headers=p.h).status_code == 204
    assert client.get(f"{API}/patients/me/records", headers=p.h).json() == []


def test_client_cannot_claim_doctor_source(client, make_patient):
    p = make_patient()
    r = client.post(
        f"{API}/patients/me/records",
        headers=p.h,
        json={"type": "condition", "title": "X", "source": "doctor", "source_language": "en"},
    )
    assert r.status_code == 201
    assert r.json()["source"] == "patient"


def test_patient_cannot_edit_doctor_provided_record(client, db, make_patient):
    p = make_patient()
    rec = MedicalRecord(
        patient_id=uuid.UUID(p.id), type=RecordType.CONDITION, title="Stage 1 hypertension", content="by doctor",
        source=RecordSource.DOCTOR, source_language="en",
    )
    db.add(rec)
    db.commit()
    assert client.patch(f"{API}/patients/me/records/{rec.id}", headers=p.h, json={"title": "x"}).status_code == 403
    assert client.delete(f"{API}/patients/me/records/{rec.id}", headers=p.h).status_code == 403


def test_patient_cannot_touch_another_patients_record(client, make_patient):
    a = make_patient(email="a@example.com")
    b = make_patient(email="b@example.com")
    rec = client.post(
        f"{API}/patients/me/records", headers=a.h,
        json={"type": "condition", "title": "Asthma", "source_language": "en"},
    ).json()
    assert client.patch(f"{API}/patients/me/records/{rec['id']}", headers=b.h, json={"title": "x"}).status_code == 404
    assert client.delete(f"{API}/patients/me/records/{rec['id']}", headers=b.h).status_code == 404


def test_current_problem_preserves_original_language(client, make_patient):
    p = make_patient()
    text = "எனக்கு மூன்று நாட்களாக காய்ச்சல் இருக்கிறது"
    r = client.post(f"{API}/patients/me/current-problems", headers=p.h, json={"text": text, "language": "ta"})
    assert r.status_code == 201
    body = r.json()
    assert body["content"] == text  # verbatim, no normalisation
    assert body["source_language"] == "ta"
    assert body["type"] == "current_problem"
    dash = client.get(f"{API}/patients/me/dashboard", headers=p.h).json()
    assert dash["latest_current_problem"]["content"] == text


def test_non_problem_records_need_title(client, make_patient):
    p = make_patient()
    r = client.post(f"{API}/patients/me/records", headers=p.h, json={"type": "condition", "source_language": "en"})
    assert r.status_code == 422
