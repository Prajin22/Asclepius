"""Principle 4: consultations with different doctors stay independent."""

import uuid

from app.models import Prescription
from tests.conftest import API, RX, request_consultation


def _activate(client, case, doctor, **share):
    c = request_consultation(client, case, doctor=doctor, **share).json()
    client.post(f"{API}/doctors/me/consultations/{c['id']}/accept", headers=doctor.h)
    return c


def test_two_doctors_two_independent_consultations(client, db, make_doctor, seeded_case):
    case = seeded_case
    doc_a = case.doctor
    doc_b = make_doctor(email="rajesh@example.com", name="Dr. Rajesh Iyer", specialization="Cardiology")

    ca = _activate(client, case, doc_a)
    cb = _activate(client, case, doc_b, document_ids=[])

    rx_a = client.post(f"{API}/doctors/me/consultations/{ca['id']}/prescriptions", headers=doc_a.h, json=RX).json()
    rx_b_payload = {"items": [{"medication": "Amlodipine 5 mg", "dosage": "1 tablet", "frequency": "Once daily",
                               "duration": "30 days"}]}
    rx_b = client.post(f"{API}/doctors/me/consultations/{cb['id']}/prescriptions", headers=doc_b.h,
                       json=rx_b_payload).json()

    # Each prescription is bound to its own consultation and author.
    assert rx_a["consultation_id"] == ca["id"] and rx_a["authored_by"]["name"] == "Dr. Meera Sharma"
    assert rx_b["consultation_id"] == cb["id"] and rx_b["authored_by"]["name"] == "Dr. Rajesh Iyer"

    # Patient sees both, separately attributed — never merged.
    rxs = client.get(f"{API}/patients/me/prescriptions", headers=case.patient.h).json()
    assert {(r["consultation_id"], r["authored_by"]["name"]) for r in rxs} == {
        (ca["id"], "Dr. Meera Sharma"), (cb["id"], "Dr. Rajesh Iyer"),
    }
    summaries = client.get(f"{API}/patients/me/consultations", headers=case.patient.h).json()
    assert len(summaries) == 2

    # Each doctor sees only their own consultation and prescription.
    a_view = client.get(f"{API}/doctors/me/consultations/{ca['id']}", headers=doc_a.h).json()
    assert [p["id"] for p in a_view["prescriptions"]] == [rx_a["id"]]
    assert a_view["shared_prescriptions"] == [] and a_view["shared_consultations"] == []
    assert client.get(f"{API}/doctors/me/consultations/{cb['id']}", headers=doc_a.h).status_code == 404

    # Doctor A cannot write into Doctor B's consultation.
    r = client.post(f"{API}/doctors/me/consultations/{cb['id']}/prescriptions", headers=doc_a.h, json=RX)
    assert r.status_code == 404

    # patient_id / doctor_id on prescriptions come from the consultation.
    row = db.get(Prescription, uuid.UUID(rx_b["id"]))
    assert str(row.patient_id) == case.patient.id
    assert str(row.doctor_id) == doc_b.id


def test_shared_previous_opinion_keeps_original_attribution(client, make_doctor, seeded_case):
    case = seeded_case
    doc_b = make_doctor(email="rajesh@example.com", name="Dr. Rajesh Iyer", specialization="Cardiology")
    cb = _activate(client, case, doc_b)
    client.put(f"{API}/doctors/me/consultations/{cb['id']}/assessment", headers=doc_b.h,
               json={"doctor_assessment": "Stage 1 hypertension."})
    rx_b = client.post(f"{API}/doctors/me/consultations/{cb['id']}/prescriptions", headers=doc_b.h, json=RX).json()
    client.post(f"{API}/doctors/me/consultations/{cb['id']}/complete", headers=doc_b.h)

    # Patient now consults Doctor A and chooses to share B's consultation and prescription.
    ca = request_consultation(
        client, case, consultation_ids=[cb["id"]], prescription_ids=[rx_b["id"]]
    ).json()
    view = client.get(f"{API}/doctors/me/consultations/{ca['id']}", headers=case.doctor.h).json()
    assert view["shared_consultations"][0]["doctor"]["name"] == "Dr. Rajesh Iyer"
    assert view["shared_consultations"][0]["doctor_assessment"] == "Stage 1 hypertension."
    assert view["shared_prescriptions"][0]["authored_by"]["name"] == "Dr. Rajesh Iyer"
    assert view["prescriptions"] == []  # A's own consultation has no prescriptions yet


def test_unshared_previous_consultation_is_invisible(client, make_doctor, seeded_case):
    case = seeded_case
    doc_b = make_doctor(email="rajesh@example.com", name="Dr. Rajesh Iyer")
    cb = _activate(client, case, doc_b)
    client.post(f"{API}/doctors/me/consultations/{cb['id']}/prescriptions", headers=doc_b.h, json=RX)
    ca = request_consultation(client, case).json()
    view = client.get(f"{API}/doctors/me/consultations/{ca['id']}", headers=case.doctor.h).json()
    assert view["shared_consultations"] == [] and view["shared_prescriptions"] == []
    assert view["own_previous_consultations"] == []
