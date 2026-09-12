"""Patient / doctor / admin separation."""

from tests.conftest import API, PASSWORD


def test_patient_cannot_use_doctor_endpoints(client, make_patient):
    p = make_patient()
    assert client.get(f"{API}/doctors/me/consultations", headers=p.h).status_code == 403
    assert client.get(f"{API}/doctors/me/profile", headers=p.h).status_code == 403


def test_doctor_cannot_use_patient_endpoints(client, make_doctor):
    d = make_doctor()
    assert client.get(f"{API}/patients/me/profile", headers=d.h).status_code == 403
    assert client.get(f"{API}/patients/me/records", headers=d.h).status_code == 403
    assert client.get(f"{API}/patients/me/documents", headers=d.h).status_code == 403


def test_doctor_cannot_browse_directory_or_admin(client, make_doctor):
    d = make_doctor()
    assert client.get(f"{API}/doctors", headers=d.h).status_code == 403
    assert client.get(f"{API}/admin/audit-events", headers=d.h).status_code == 403


def test_patient_cannot_create_doctors(client, make_patient):
    p = make_patient()
    r = client.post(
        f"{API}/admin/doctors",
        headers=p.h,
        json={"email": "x@example.com", "password": PASSWORD, "name": "X", "specialization": "Y",
              "qualification": "Z", "registration_identifier": "R"},
    )
    assert r.status_code == 403


def test_admin_creates_doctor_who_can_log_in(client, make_admin):
    a = make_admin()
    r = client.post(
        f"{API}/admin/doctors",
        headers=a.h,
        json={"email": "new.doc@example.com", "password": PASSWORD, "name": "Dr. New", "specialization": "Pediatrics",
              "qualification": "MBBS", "registration_identifier": "DEMO-1", "languages": ["en", "hi"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["languages"] == ["en", "hi"]
    login = client.post(f"{API}/auth/login", json={"email": "new.doc@example.com", "password": PASSWORD})
    assert login.json()["user"]["role"] == "doctor"


def test_admin_has_no_patient_clinical_endpoints(client, make_admin):
    a = make_admin()
    assert client.get(f"{API}/patients/me/records", headers=a.h).status_code == 403
    assert client.get(f"{API}/doctors/me/consultations", headers=a.h).status_code == 403


def test_unauthenticated_requests_rejected(client):
    for path in ("/patients/me/profile", "/doctors/me/consultations", "/doctors", "/admin/audit-events"):
        assert client.get(f"{API}{path}").status_code == 401


def test_directory_filters(client, make_patient, make_doctor):
    p = make_patient()
    make_doctor(email="a@example.com", name="Dr. A", specialization="Cardiology", languages=("en",))
    make_doctor(email="b@example.com", name="Dr. B", specialization="General Medicine", languages=("ta", "en"))
    everyone = client.get(f"{API}/doctors", headers=p.h).json()
    assert {d["name"] for d in everyone} == {"Dr. A", "Dr. B"}
    tamil = client.get(f"{API}/doctors", params={"language": "ta"}, headers=p.h).json()
    assert [d["name"] for d in tamil] == ["Dr. B"]
    cardio = client.get(f"{API}/doctors", params={"q": "cardio"}, headers=p.h).json()
    assert [d["name"] for d in cardio] == ["Dr. A"]
