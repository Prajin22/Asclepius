"""Consultation lifecycle + patient-controlled sharing."""

from sqlalchemy import select

from app.models import AuditEvent, Consultation
from tests.conftest import API, RX, request_consultation, upload


def test_full_vertical_slice(client, seeded_case):
    case = seeded_case
    r = request_consultation(client, case)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["status"] == "requested"
    assert set(c["shared_categories"]) == {"current_problem", "medical_history", "documents"}

    # Doctor sees the request in the incoming queue with the patient's own words.
    queue = client.get(f"{API}/doctors/me/consultations", params={"status": "requested"}, headers=case.doctor.h).json()
    assert [q["id"] for q in queue] == [c["id"]]
    assert queue[0]["current_problem_excerpt"].startswith("மூன்று")
    assert queue[0]["patient"]["display_name"] == "Arun Kumar"

    # Doctor opens the case before accepting.
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h).json()
    assert [x["id"] for x in view["current_problems"]] == [case.problem["id"]]
    assert view["current_problems"][0]["source_language"] == "ta"
    assert [x["id"] for x in view["medical_history"]] == [case.shared_rec["id"]]
    assert [x["id"] for x in view["documents"]] == [case.shared_doc["id"]]

    # Accept → active, visible to the patient.
    acc = client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=case.doctor.h)
    assert acc.status_code == 200 and acc.json()["status"] == "active"
    mine = client.get(f"{API}/patients/me/consultations/{c['id']}", headers=case.patient.h).json()
    assert mine["status"] == "active"

    # Text communication both ways, original language preserved.
    m1 = client.post(f"{API}/consultations/{c['id']}/messages", headers=case.patient.h,
                     json={"body": "வணக்கம் டாக்டர்", "language": "ta"})
    m2 = client.post(f"{API}/consultations/{c['id']}/messages", headers=case.doctor.h,
                     json={"body": "Hello, how long have you had the headache?", "language": "en"})
    assert m1.status_code == m2.status_code == 201
    msgs = client.get(f"{API}/consultations/{c['id']}/messages", headers=case.doctor.h).json()
    assert [m["sender_role"] for m in msgs] == ["patient", "doctor"]
    assert msgs[0]["body"] == "வணக்கம் டாக்டர்"

    # Doctor notes + prescription.
    client.put(f"{API}/doctors/me/consultations/{c['id']}/assessment", headers=case.doctor.h,
               json={"doctor_assessment": "Tension-type headache suspected."})
    rx = client.post(f"{API}/doctors/me/consultations/{c['id']}/prescriptions", headers=case.doctor.h, json=RX)
    assert rx.status_code == 201, rx.text
    rx_body = rx.json()
    assert rx_body["authorship"] == "doctor"
    assert rx_body["authored_by"]["name"] == "Dr. Meera Sharma"

    # Patient sees the prescription with attribution.
    rxs = client.get(f"{API}/patients/me/prescriptions", headers=case.patient.h).json()
    assert len(rxs) == 1
    assert rxs[0]["items"][0]["medication"] == "Paracetamol 500 mg"
    assert rxs[0]["consultation_id"] == c["id"]
    detail = client.get(f"{API}/patients/me/consultations/{c['id']}", headers=case.patient.h).json()
    assert detail["doctor_assessment"] == "Tension-type headache suspected."
    assert len(detail["prescriptions"]) == 1

    # Complete.
    done = client.post(f"{API}/doctors/me/consultations/{c['id']}/complete", headers=case.doctor.h)
    assert done.json()["status"] == "completed"


def test_doctor_sees_only_shared_items(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h).json()
    all_ids = {x["id"] for x in view["medical_history"] + view["current_problems"] + view["documents"]}
    assert case.private_rec["id"] not in all_ids
    assert case.private_doc["id"] not in all_ids

    base = f"{API}/doctors/me/consultations/{c['id']}/documents"
    assert client.get(f"{base}/{case.shared_doc['id']}/file", headers=case.doctor.h).status_code == 200
    assert client.get(f"{base}/{case.private_doc['id']}/file", headers=case.doctor.h).status_code == 404


def test_patient_profile_details_not_exposed_to_doctor(client, seeded_case):
    case = seeded_case
    client.put(f"{API}/patients/me/profile", headers=case.patient.h,
               json={"phone": "+91 90000 00001", "emergency_contact_name": "Lakshmi"})
    c = request_consultation(client, case).json()
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h).json()
    assert set(view["patient"]) == {"id", "display_name", "age", "sex", "preferred_language"}


def test_sharing_nothing_optional_is_respected(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case, medical_record_ids=[], document_ids=[]).json()
    assert c["shared_categories"] == ["current_problem"]
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h).json()
    assert view["medical_history"] == [] and view["documents"] == []


def test_sharing_decision_is_recorded(client, db, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    row = db.get(Consultation, __import__("uuid").UUID(c["id"]))
    cats = row.patient_shared_context["categories"]
    assert cats["current_problem"]["shared"] is True
    assert cats["previous_prescriptions"] == {"shared": False, "item_ids": []}
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "consultation.sharing_decided")) is not None


def test_cannot_share_another_patients_items(client, make_patient, seeded_case):
    case = seeded_case
    other = make_patient(email="other@example.com")
    foreign_doc = upload(client, other).json()
    r = request_consultation(client, case, document_ids=[foreign_doc["id"]])
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_share_item"


def test_current_problem_ids_must_be_current_problems(client, seeded_case):
    case = seeded_case
    r = request_consultation(client, case, current_problem_ids=[case.shared_rec["id"]])
    assert r.status_code == 422


def test_duplicate_open_request_rejected(client, seeded_case):
    case = seeded_case
    assert request_consultation(client, case).status_code == 201
    r = request_consultation(client, case)
    assert r.status_code == 409


def test_other_doctor_cannot_see_consultation(client, make_doctor, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    intruder = make_doctor(email="intruder@example.com", name="Dr. Intruder")
    assert client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=intruder.h).status_code == 404
    assert client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=intruder.h).status_code == 404
    assert client.get(f"{API}/consultations/{c['id']}/messages", headers=intruder.h).status_code == 404
    assert client.get(f"{API}/doctors/me/consultations", headers=intruder.h).json() == []


def test_other_patient_cannot_see_consultation(client, make_patient, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    other = make_patient(email="other@example.com")
    assert client.get(f"{API}/patients/me/consultations/{c['id']}", headers=other.h).status_code == 404
    assert client.get(f"{API}/consultations/{c['id']}/messages", headers=other.h).status_code == 404


def test_decline_revokes_doctor_access(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    r = client.post(f"{API}/doctors/me/consultations/{c['id']}/decline", headers=case.doctor.h,
                    json={"reason": "Outside my specialty"})
    assert r.json()["status"] == "cancelled"
    assert client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h).status_code == 403
    doc_url = f"{API}/doctors/me/consultations/{c['id']}/documents/{case.shared_doc['id']}/file"
    assert client.get(doc_url, headers=case.doctor.h).status_code == 403


def test_patient_can_cancel_request(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    r = client.post(f"{API}/patients/me/consultations/{c['id']}/cancel", headers=case.patient.h)
    assert r.json()["status"] == "cancelled"
    # A new request to the same doctor is now allowed.
    assert request_consultation(client, case).status_code == 201


def test_invalid_transitions(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    base = f"{API}/doctors/me/consultations/{c['id']}"
    # Not active yet: no prescription, no messages, no complete.
    assert client.post(f"{base}/prescriptions", headers=case.doctor.h, json=RX).status_code == 409
    assert client.post(f"{API}/consultations/{c['id']}/messages", headers=case.patient.h,
                       json={"body": "hi"}).status_code == 409
    client.post(f"{base}/accept", headers=case.doctor.h)
    assert client.post(f"{base}/accept", headers=case.doctor.h).status_code == 409
    client.post(f"{base}/complete", headers=case.doctor.h)
    assert client.post(f"{base}/prescriptions", headers=case.doctor.h, json=RX).status_code == 409
    assert client.post(f"{API}/patients/me/consultations/{c['id']}/cancel", headers=case.patient.h).status_code == 409


def test_case_view_and_document_access_are_audited(client, db, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=case.doctor.h)
    client.get(f"{API}/doctors/me/consultations/{c['id']}/documents/{case.shared_doc['id']}/file", headers=case.doctor.h)
    actions = set(db.scalars(select(AuditEvent.action)))
    assert {"consultation.case_viewed", "document.viewed_by_doctor", "consultation.requested"} <= actions


def test_unavailable_doctor(client, seeded_case):
    case = seeded_case
    client.put(f"{API}/doctors/me/profile", headers=case.doctor.h, json={"is_accepting_consultations": False})
    r = request_consultation(client, case)
    assert r.status_code == 409


def test_prescription_validation(client, seeded_case):
    case = seeded_case
    c = request_consultation(client, case).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=case.doctor.h)
    url = f"{API}/doctors/me/consultations/{c['id']}/prescriptions"
    assert client.post(url, headers=case.doctor.h, json={"items": []}).status_code == 422
    bad_item = {"items": [{"medication": "", "dosage": "1", "frequency": "1", "duration": "1"}]}
    assert client.post(url, headers=case.doctor.h, json=bad_item).status_code == 422
    # Patients cannot write prescriptions at all.
    assert client.post(url, headers=case.patient.h, json=RX).status_code == 403
