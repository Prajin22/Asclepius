"""Phase 4: one authorization boundary, shared by the case view and the bundle.

The point of the Stage B extraction is that a doctor's case view and the source
bundle a provider is shown can never drift apart. These tests hold them against
each other, and check every gate that stands in front of generation.
"""

import uuid

import pytest

from app.models import Consultation, DoctorProfile
from app.services import case_summary, case_summary_bundle, consultation_service
from app.services.errors import AIConsentRequired, Forbidden, NotFound
from tests.conftest import API, request_consultation, run_async


def _ctx(db, doctor_id, consultation_id):
    doctor = db.get(DoctorProfile, uuid.UUID(doctor_id))
    c = db.get(Consultation, uuid.UUID(consultation_id))
    return doctor, c, consultation_service.resolve_authorized_context(db, c)


def test_resolver_and_case_view_agree(client, db, seeded_case):
    """Whatever the case view shows, the resolver resolved — and nothing more."""
    c = request_consultation(client, seeded_case).json()
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=seeded_case.doctor.h).json()
    _, consultation, context = _ctx(db, seeded_case.doctor.id, c["id"])

    view_records = {r["id"] for r in view["current_problems"]} | {r["id"] for r in view["medical_history"]}
    assert {str(r.id) for r in context.records} == view_records
    assert {str(d.id) for d in context.documents} == {d["id"] for d in view["documents"]}
    assert {str(x.id) for x in context.shared_consultations} == {
        x["id"] for x in view["shared_consultations"]
    }
    assert {str(x.id) for x in context.shared_prescriptions} == {
        x["id"] for x in view["shared_prescriptions"]
    }
    assert {str(x.id) for x in context.own_previous_consultations} == {
        x["id"] for x in view["own_previous_consultations"]
    }


def test_bundle_never_exceeds_the_case_view(client, db, seeded_case):
    """Every identifier the bundle can resolve is one the case view already showed."""
    c = request_consultation(client, seeded_case).json()
    view = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=seeded_case.doctor.h).json()
    _, _, context = _ctx(db, seeded_case.doctor.id, c["id"])
    bundle = case_summary_bundle.build_source_bundle(db, context)

    visible = (
        {r["id"] for r in view["current_problems"]}
        | {r["id"] for r in view["medical_history"]}
        | {d["id"] for d in view["documents"]}
        | {x["id"] for x in view["shared_consultations"]}
        | {x["id"] for x in view["own_previous_consultations"]}
        | {x["id"] for x in view["shared_prescriptions"]}
        | {c["id"]}
    )
    for item in bundle.items:
        for key in ("record_id", "document_id", "consultation_id", "prescription_id"):
            value = item.resolution.get(key)
            if value:
                assert value in visible, f"{key}={value} is in the bundle but not in the case view"


def test_another_doctor_cannot_resolve_the_consultation(client, db, seeded_case, make_doctor):
    other = make_doctor(email="other@example.com", name="Dr. Other")
    c = request_consultation(client, seeded_case).json()
    doctor = db.get(DoctorProfile, uuid.UUID(other.id))

    with pytest.raises(NotFound):
        consultation_service.get_doctor_consultation(db, doctor, uuid.UUID(c["id"]))
    with pytest.raises(NotFound):
        run_async(case_summary.generate(db, doctor, doctor.user, uuid.UUID(c["id"])))


def test_cancelled_consultation_is_not_resolvable(client, db, seeded_case):
    c = request_consultation(client, seeded_case).json()
    assert client.post(
        f"{API}/patients/me/consultations/{c['id']}/cancel", headers=seeded_case.patient.h
    ).status_code == 200
    db.expire_all()

    doctor = db.get(DoctorProfile, uuid.UUID(seeded_case.doctor.id))
    consultation = db.get(Consultation, uuid.UUID(c["id"]))
    with pytest.raises(Forbidden):
        consultation_service.resolve_authorized_context(db, consultation)


def test_generation_requires_patient_ai_consent(client, db, seeded_case):
    """D-020 — consent covers all AI processing, including a doctor's request."""
    c = request_consultation(client, seeded_case).json()
    doctor = db.get(DoctorProfile, uuid.UUID(seeded_case.doctor.id))
    with pytest.raises(AIConsentRequired):
        run_async(case_summary.generate(db, doctor, doctor.user, uuid.UUID(c["id"])))


def test_consent_withdrawn_after_sharing_blocks_generation(client, db, seeded_case):
    from tests.conftest import grant_ai_consent

    grant_ai_consent(client, seeded_case.patient, True)
    c = request_consultation(client, seeded_case).json()
    grant_ai_consent(client, seeded_case.patient, False)
    db.expire_all()

    doctor = db.get(DoctorProfile, uuid.UUID(seeded_case.doctor.id))
    with pytest.raises(AIConsentRequired):
        run_async(case_summary.generate(db, doctor, doctor.user, uuid.UUID(c["id"])))


def test_unapproved_doctor_sees_nothing(client, db, seeded_case, make_doctor, make_admin):
    """A pending doctor holds a valid token and still resolves no patient data."""
    admin = make_admin()
    pending = make_doctor(email="pending@example.com", name="Dr. Pending")
    db.expire_all()
    profile = db.get(DoctorProfile, uuid.UUID(pending.id))
    from app.models.enums import DoctorApproval

    profile.approval_status = DoctorApproval.PENDING
    db.commit()

    c = request_consultation(client, seeded_case).json()
    r = client.get(f"{API}/doctors/me/consultations/{c['id']}", headers=pending.h)
    assert r.status_code == 403
    assert r.json()["code"] == "doctor_not_approved"
    assert admin  # the fixture exists to make the approval flow realistic
