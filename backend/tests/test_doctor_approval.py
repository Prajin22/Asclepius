"""Doctor sign-up and admin approval.

A doctor account an admin has not approved can sign in and see its own
application, and nothing else: no directory listing, no consultations, no
patient information.
"""

import uuid
from types import SimpleNamespace

from tests.conftest import API, PASSWORD, auth, request_consultation

APPLICATION = {
    "email": "kavya@example.com",
    "password": PASSWORD,
    "name": "Dr. Kavya Iyer",
    "specialization": "Dermatology",
    "qualification": "MBBS, MD",
    "registration_identifier": "TN-DEMO-4471",
    "languages": ["en", "ta"],
}
DETAILS = {k: v for k, v in APPLICATION.items() if k not in ("email", "password")}


def _apply(client, **overrides) -> SimpleNamespace:
    r = client.post(f"{API}/auth/register-doctor", json={**APPLICATION, **overrides})
    assert r.status_code == 201, r.text
    h = auth(r.json()["access_token"])
    me = client.get(f"{API}/auth/me", headers=h).json()
    return SimpleNamespace(h=h, id=me["profile_id"], me=me)


def test_applicant_starts_pending_and_reaches_only_their_application(client):
    d = _apply(client)
    assert d.me["user"]["role"] == "doctor"
    assert d.me["doctor_approval"] == "pending"

    mine = client.get(f"{API}/doctors/me/profile", headers=d.h)
    assert mine.status_code == 200
    assert mine.json()["approval_status"] == "pending"
    assert mine.json()["registration_identifier"] == "TN-DEMO-4471"

    for path in ("/doctors/me/consultations", f"/doctors/me/consultations/{uuid.uuid4()}"):
        r = client.get(f"{API}{path}", headers=d.h)
        assert r.status_code == 403
        assert r.json()["code"] == "doctor_not_approved"
    r = client.put(f"{API}/doctors/me/profile", json={"is_accepting_consultations": True}, headers=d.h)
    assert r.status_code == 403


def test_pending_doctor_is_invisible_to_patients(client, seeded_case):
    applicant = _apply(client)
    listed = client.get(f"{API}/doctors", headers=seeded_case.patient.h).json()
    assert [x["name"] for x in listed] == ["Dr. Meera Sharma"]
    assert client.get(f"{API}/doctors/{applicant.id}", headers=seeded_case.patient.h).status_code == 404
    r = request_consultation(client, seeded_case, doctor=applicant)
    assert r.status_code == 404


def test_admin_approves_and_the_doctor_gets_access(client, make_admin, make_patient):
    a, p, d = make_admin(), make_patient(), _apply(client)

    pending = client.get(f"{API}/admin/doctors", params={"status": "pending"}, headers=a.h).json()
    assert [x["email"] for x in pending] == ["kavya@example.com"]
    assert pending[0]["registration_conflict"] is False

    r = client.post(f"{API}/admin/doctors/{d.id}/approve", headers=a.h)
    assert r.status_code == 200, r.text
    assert r.json()["approval_status"] == "approved"
    assert r.json()["reviewed_at"]

    assert client.get(f"{API}/admin/doctors", params={"status": "pending"}, headers=a.h).json() == []
    # The token issued at sign-up works as soon as the account is approved.
    assert client.get(f"{API}/doctors/me/consultations", headers=d.h).status_code == 200
    assert [x["name"] for x in client.get(f"{API}/doctors", headers=p.h).json()] == ["Dr. Kavya Iyer"]
    events = client.get(f"{API}/admin/audit-events", params={"action": "doctor.approved"}, headers=a.h).json()
    assert [(e["resource_id"], e["details"]) for e in events] == [(d.id, {"from": "pending"})]


def test_rejection_needs_a_reason_and_the_applicant_can_resubmit(client, make_admin):
    a, d = make_admin(), _apply(client)
    assert client.post(f"{API}/admin/doctors/{d.id}/reject", headers=a.h).status_code == 422
    assert client.post(f"{API}/admin/doctors/{d.id}/reject", json={"reason": "  "}, headers=a.h).status_code == 422

    reason = "Registration number not found on the register"
    r = client.post(f"{API}/admin/doctors/{d.id}/reject", json={"reason": reason}, headers=a.h)
    assert r.status_code == 200, r.text
    mine = client.get(f"{API}/doctors/me/profile", headers=d.h).json()
    assert (mine["approval_status"], mine["approval_note"]) == ("rejected", reason)
    assert client.get(f"{API}/doctors/me/consultations", headers=d.h).json()["code"] == "doctor_not_approved"

    r = client.put(f"{API}/doctors/me/application", json={**DETAILS, "registration_identifier": "TN-DEMO-4472"},
                   headers=d.h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["approval_status"], body["approval_note"], body["reviewed_at"]) == ("pending", None, None)
    assert body["registration_identifier"] == "TN-DEMO-4472"
    assert client.post(f"{API}/admin/doctors/{d.id}/approve", headers=a.h).status_code == 200


def test_rejecting_an_approved_doctor_revokes_access(client, make_admin, seeded_case):
    a, case = make_admin(), seeded_case
    created = request_consultation(client, case)
    assert created.status_code == 201, created.text
    queue = client.get(f"{API}/doctors/me/consultations", headers=case.doctor.h).json()
    assert [c["id"] for c in queue] == [created.json()["id"]]

    r = client.post(f"{API}/admin/doctors/{case.doctor.id}/reject", json={"reason": "Registration lapsed"},
                    headers=a.h)
    assert r.status_code == 200, r.text
    for path in ("/doctors/me/consultations", f"/doctors/me/consultations/{created.json()['id']}"):
        blocked = client.get(f"{API}{path}", headers=case.doctor.h)
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "doctor_not_approved"
    assert client.get(f"{API}/doctors", headers=case.patient.h).json() == []


def test_review_transitions_are_explicit(client, make_admin, make_doctor):
    a, d = make_admin(), make_doctor()
    r = client.post(f"{API}/admin/doctors/{d.id}/approve", headers=a.h)
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert client.post(f"{API}/admin/doctors/{uuid.uuid4()}/approve", headers=a.h).status_code == 404
    r = client.put(f"{API}/doctors/me/application", json=DETAILS, headers=d.h)
    assert r.status_code == 409 and r.json()["code"] == "application_closed"


def test_registration_number_held_by_an_approved_doctor_blocks_approval(client, make_admin, make_doctor):
    a = make_admin()
    make_doctor(email="meera@example.com")  # registration TEST-meera@example.com
    d = _apply(client, registration_identifier="test meera@example.com")

    listed = client.get(f"{API}/admin/doctors", params={"status": "pending"}, headers=a.h).json()
    assert listed[0]["registration_conflict"] is True
    r = client.post(f"{API}/admin/doctors/{d.id}/approve", headers=a.h)
    assert r.status_code == 409 and r.json()["code"] == "registration_in_use"


def test_only_admins_review_doctors(client, make_patient, make_doctor):
    p, approved, applicant = make_patient(), make_doctor(), _apply(client)
    for h in (p.h, approved.h, applicant.h):
        assert client.get(f"{API}/admin/doctors", headers=h).status_code == 403
        assert client.post(f"{API}/admin/doctors/{applicant.id}/approve", headers=h).status_code == 403
    assert client.post(f"{API}/admin/doctors/{applicant.id}/approve").status_code == 401


def test_doctor_sign_up_validation(client, make_patient):
    make_patient(email="arun@example.com")
    r = client.post(f"{API}/auth/register-doctor", json={**APPLICATION, "email": "ARUN@example.com"})
    assert r.status_code == 409 and r.json()["code"] == "email_taken"
    for bad in ({"registration_identifier": " "}, {"registration_identifier": "X" * 65}, {"languages": []},
                {"password": "short"}, {"name": "D" * 121}):
        assert client.post(f"{API}/auth/register-doctor", json={**APPLICATION, **bad}).status_code == 422, bad


def test_admin_created_and_patient_accounts(client, make_doctor, make_patient):
    d, p = make_doctor(), make_patient()
    assert client.get(f"{API}/auth/me", headers=d.h).json()["doctor_approval"] == "approved"
    assert client.get(f"{API}/auth/me", headers=p.h).json()["doctor_approval"] is None
