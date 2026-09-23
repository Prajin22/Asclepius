"""Phase 4: the two doctor endpoints.

Authorization is checked server-side on every call; a patient must never reach
doctor-only information through them, and a stale summary must never be served
as a current one.
"""

from tests.conftest import API, grant_ai_consent, request_consultation

SUMMARY = "/doctors/me/consultations/{cid}/summary"


def _url(cid: str) -> str:
    return f"{API}{SUMMARY.format(cid=cid)}"


def _ready(client, case):
    grant_ai_consent(client, case.patient, True)
    c = request_consultation(client, case).json()
    return c["id"]


# ---------- the happy path ----------


def test_generate_then_read(client, seeded_case):
    cid = _ready(client, seeded_case)

    before = client.get(_url(cid), headers=seeded_case.doctor.h)
    assert before.status_code == 200
    assert before.json()["status"] == "not_generated"
    assert before.json()["summary"] is None

    created = client.post(_url(cid), headers=seeded_case.doctor.h)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "ready"
    assert body["is_stale"] is False
    assert body["provider"] == "mock"
    assert body["prompt_version"] == "case_summary_v1"
    assert body["is_external_provider"] is False  # DEMO_MODE stays local
    assert body["generations_remaining"] == 9
    assert body["summary"]["sections"]

    read = client.get(_url(cid), headers=seeded_case.doctor.h)
    assert read.status_code == 200
    assert read.json()["status"] == "ready"
    assert read.json()["summary"] == body["summary"]


def test_every_item_carries_resolved_provenance(client, seeded_case):
    cid = _ready(client, seeded_case)
    body = client.post(_url(cid), headers=seeded_case.doctor.h).json()

    for section in body["summary"]["sections"]:
        for item in section["items"]:
            assert item["origin"] in {"patient_provided", "patient_confirmed", "doctor_authored"}
            assert item["sources"], "every item must point back at a source"
            for source in item["sources"]:
                assert source["ref"].startswith("S")
                assert source["authorization_basis"] in {"patient_grant", "own_prior_consultation"}
                # At least one real identifier, resolved by the application.
                assert any(
                    source[k]
                    for k in ("record_id", "document_id", "consultation_id", "prescription_id", "fact_id")
                )


def test_a_second_post_reuses_the_stored_summary(client, seeded_case):
    cid = _ready(client, seeded_case)
    first = client.post(_url(cid), headers=seeded_case.doctor.h).json()
    second = client.post(_url(cid), headers=seeded_case.doctor.h).json()
    assert second["generations_remaining"] == first["generations_remaining"]
    assert second["summary"] == first["summary"]


# ---------- staleness ----------


def test_editing_shared_information_reports_stale(client, seeded_case):
    cid = _ready(client, seeded_case)
    client.post(_url(cid), headers=seeded_case.doctor.h)

    client.patch(
        f"{API}/patients/me/records/{seeded_case.shared_rec['id']}",
        json={"content": "8 years, worse recently"},
        headers=seeded_case.patient.h,
    )

    read = client.get(_url(cid), headers=seeded_case.doctor.h).json()
    assert read["status"] == "stale"
    assert read["is_stale"] is True
    # Still readable — labelled, not withdrawn.
    assert read["summary"] is not None


# ---------- authorization ----------


def test_another_doctor_gets_not_found(client, seeded_case, make_doctor):
    other = make_doctor(email="other@example.com", name="Dr. Other")
    cid = _ready(client, seeded_case)
    client.post(_url(cid), headers=seeded_case.doctor.h)

    for call in (client.get, client.post):
        r = call(_url(cid), headers=other.h)
        assert r.status_code == 404
        assert r.json()["code"] == "not_found"


def test_a_patient_cannot_reach_the_doctor_summary(client, seeded_case):
    cid = _ready(client, seeded_case)
    client.post(_url(cid), headers=seeded_case.doctor.h)

    for call in (client.get, client.post):
        r = call(_url(cid), headers=seeded_case.patient.h)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not permitted for this role"


def test_anonymous_access_is_refused(client, seeded_case):
    cid = _ready(client, seeded_case)
    assert client.get(_url(cid)).status_code == 401
    assert client.post(_url(cid)).status_code == 401


def test_an_unapproved_doctor_is_refused(client, db, seeded_case, make_doctor):
    import uuid

    from app.models import DoctorProfile
    from app.models.enums import DoctorApproval

    pending = make_doctor(email="pending@example.com", name="Dr. Pending")
    cid = _ready(client, seeded_case)
    db.expire_all()
    db.get(DoctorProfile, uuid.UUID(pending.id)).approval_status = DoctorApproval.PENDING
    db.commit()

    r = client.post(_url(cid), headers=pending.h)
    assert r.status_code == 403
    assert r.json()["code"] == "doctor_not_approved"


def test_without_ai_consent_the_summary_is_refused(client, seeded_case):
    """D-020. The case view keeps working; only the summary is unavailable."""
    c = request_consultation(client, seeded_case).json()  # no consent granted

    r = client.post(_url(c["id"]), headers=seeded_case.doctor.h)
    assert r.status_code == 403
    assert r.json()["code"] == "ai_consent_required"

    # The doctor can still read everything the patient shared.
    assert client.get(
        f"{API}/doctors/me/consultations/{c['id']}", headers=seeded_case.doctor.h
    ).status_code == 200


def test_a_cancelled_consultation_is_no_longer_summarisable(client, seeded_case):
    cid = _ready(client, seeded_case)
    client.post(f"{API}/patients/me/consultations/{cid}/cancel", headers=seeded_case.patient.h)

    r = client.post(_url(cid), headers=seeded_case.doctor.h)
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


# ---------- budget ----------


def test_the_generation_cap_returns_a_stable_error_code(client, db, seeded_case, monkeypatch):
    from app.core.config import get_settings

    tuned = get_settings().model_copy(update={"summary_per_consultation_limit": 1})
    monkeypatch.setattr("app.services.ai_limits.get_settings", lambda: tuned)

    cid = _ready(client, seeded_case)
    assert client.post(_url(cid), headers=seeded_case.doctor.h).status_code == 200

    client.patch(
        f"{API}/patients/me/records/{seeded_case.shared_rec['id']}",
        json={"content": "changed"},
        headers=seeded_case.patient.h,
    )
    r = client.post(_url(cid), headers=seeded_case.doctor.h)
    assert r.status_code == 429
    assert r.json()["code"] == "ai_rate_limited"
