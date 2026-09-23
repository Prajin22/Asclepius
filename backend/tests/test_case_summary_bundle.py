"""Phase 4: the authorised source bundle.

The bundle is the security boundary. These tests assert what may be in it, what
may never be in it, and that the same authorised state always produces the same
bytes — because the hash over those bytes is what detects a stale summary.
"""

import json
import uuid

from sqlalchemy import select

from app.models import Consultation, DoctorProfile
from app.models.enums import AuthorizationBasis, BundleItemKind, SummaryItemOrigin
from app.services import case_summary_bundle, consultation_service
from tests.conftest import API, request_consultation


def _bundle(db, doctor_id, consultation_id):
    doctor = db.get(DoctorProfile, uuid.UUID(doctor_id))
    c = db.get(Consultation, uuid.UUID(consultation_id))
    context = consultation_service.resolve_authorized_context(db, c)
    return case_summary_bundle.build_source_bundle(db, context)


def test_bundle_contains_only_shared_items(client, db, seeded_case):
    """The unshared record and unshared document must not appear anywhere."""
    c = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])

    blob = bundle.canonical()
    assert "not shared" not in blob
    assert "private.pdf" not in blob
    assert "Private note" not in blob

    # …and they are not reachable through the resolution half either.
    resolved = json.dumps([i.resolution for i in bundle.items])
    assert seeded_case.private_rec["id"] not in resolved
    assert seeded_case.private_doc["id"] not in resolved

    # What the patient did share is present.
    assert "Hypertension" in blob
    assert "தலைவலி" in blob


def test_provider_payload_carries_no_database_identifiers(client, db, seeded_case):
    """The model sees opaque refs only — no UUIDs, no emails, no names."""
    c = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])
    payload = json.dumps(bundle.provider_payload())

    for identifier in (
        c["id"], seeded_case.problem["id"], seeded_case.shared_rec["id"], seeded_case.shared_doc["id"],
        seeded_case.patient.id, seeded_case.doctor.id,
    ):
        assert identifier not in payload, f"{identifier} leaked into the provider payload"
    assert "@example.com" not in payload
    assert "Arun Kumar" not in payload  # the patient's name is never needed
    assert "password" not in payload.lower()

    # Every item is addressed by an opaque handle instead.
    refs = [item["ref"] for item in bundle.provider_payload()["items"]]
    assert refs == [f"S{i}" for i in range(1, len(refs) + 1)]


def test_patient_identity_is_minimal(client, db, seeded_case):
    c = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])
    assert set(bundle.patient) == {"age", "sex", "preferred_language"}


def test_bundle_is_deterministic(client, db, seeded_case):
    """Same authorised state, same bytes, same hash — twice."""
    c = request_consultation(client, seeded_case).json()
    first = _bundle(db, seeded_case.doctor.id, c["id"])
    second = _bundle(db, seeded_case.doctor.id, c["id"])
    assert first.canonical() == second.canonical()
    assert first.hash() == second.hash()
    assert len(first.hash()) == 64


def test_hash_changes_when_a_shared_record_is_edited(client, db, seeded_case):
    """Shared records are live references (D-006), so content must be hashed."""
    c = request_consultation(client, seeded_case).json()
    before = _bundle(db, seeded_case.doctor.id, c["id"]).hash()

    r = client.patch(
        f"{API}/patients/me/records/{seeded_case.shared_rec['id']}",
        json={"content": "8 years, worse recently"},
        headers=seeded_case.patient.h,
    )
    assert r.status_code == 200, r.text
    db.expire_all()

    after = _bundle(db, seeded_case.doctor.id, c["id"]).hash()
    assert after != before, "editing a shared record must change the bundle hash"


def test_hash_is_stable_when_an_unshared_record_changes(client, db, seeded_case):
    """Private edits are invisible to the doctor, so they cannot make a summary stale."""
    c = request_consultation(client, seeded_case).json()
    before = _bundle(db, seeded_case.doctor.id, c["id"]).hash()

    client.patch(
        f"{API}/patients/me/records/{seeded_case.private_rec['id']}",
        json={"content": "still private, now longer"},
        headers=seeded_case.patient.h,
    )
    db.expire_all()

    assert _bundle(db, seeded_case.doctor.id, c["id"]).hash() == before


def test_request_message_is_a_patient_statement(client, db, seeded_case):
    c = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])
    statements = [i for i in bundle.items if i.kind == BundleItemKind.PATIENT_STATEMENT]
    assert len(statements) == 1
    assert statements[0].origin == SummaryItemOrigin.PATIENT_PROVIDED
    assert statements[0].payload["text"] == "Please review"
    # Shaped so a future transcript fits without a schema change (Phase 6).
    assert statements[0].payload["content_kind"] == "text"
    assert statements[0].payload["language"] == "en"


def test_every_item_has_an_authorization_basis(client, db, seeded_case):
    c = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, c["id"])
    assert bundle.items
    for item in bundle.items:
        assert item.authorization_basis in set(AuthorizationBasis)
        assert item.resolution["authorization_basis"] == item.authorization_basis.value


def test_own_prior_consultation_is_labelled(client, db, seeded_case):
    """Stage A decision 1: included, and distinguishable from a patient grant."""
    first = request_consultation(client, seeded_case).json()
    client.post(f"{API}/doctors/me/consultations/{first['id']}/accept", headers=seeded_case.doctor.h)
    client.put(
        f"{API}/doctors/me/consultations/{first['id']}/assessment",
        json={"doctor_assessment": "Reviewed the reported headache."},
        headers=seeded_case.doctor.h,
    )
    client.post(f"{API}/doctors/me/consultations/{first['id']}/complete", headers=seeded_case.doctor.h)

    second = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, second["id"])

    priors = [i for i in bundle.items if i.kind == BundleItemKind.PRIOR_CONSULTATION]
    assert len(priors) == 1
    assert priors[0].authorization_basis == AuthorizationBasis.OWN_PRIOR_CONSULTATION
    assert priors[0].origin == SummaryItemOrigin.DOCTOR_AUTHORED
    # The doctor's words travel verbatim; nothing rewrites them.
    assert priors[0].payload["doctor_assessment"] == "Reviewed the reported headache."


def test_another_doctors_consultation_is_not_in_the_bundle(client, db, seeded_case, make_doctor):
    """D-009 covers this doctor's own history — not a colleague's."""
    other = make_doctor(email="other@example.com", name="Dr. Other")
    theirs = request_consultation(client, seeded_case, doctor=other).json()
    client.post(f"{API}/doctors/me/consultations/{theirs['id']}/accept", headers=other.h)
    client.put(
        f"{API}/doctors/me/consultations/{theirs['id']}/assessment",
        json={"doctor_assessment": "Colleague's private note."},
        headers=other.h,
    )

    mine = request_consultation(client, seeded_case).json()
    bundle = _bundle(db, seeded_case.doctor.id, mine["id"])
    assert "Colleague's private note." not in bundle.canonical()


def test_pending_facts_are_counted_not_stated(client, db, consented_patient, make_doctor):
    """Stage A decision 2: unconfirmed extraction never becomes a statement."""
    from tests.conftest import create_problem, process_record

    doctor = make_doctor()
    problem = create_problem(client, consented_patient)
    processed = process_record(client, consented_patient, problem["id"]).json()
    assert processed["facts"], "expected the mock provider to extract something"

    r = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [problem["id"]], "medical_record_ids": [],
                      "document_ids": [], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    )
    c = r.json()
    bundle = _bundle(db, doctor.id, c["id"])

    assert bundle.pending_fact_count == len(processed["facts"])
    # No unconfirmed fact becomes a source item, so none can become a statement.
    assert not [i for i in bundle.items if i.kind == BundleItemKind.FACT]
    resolved = json.dumps([i.resolution for i in bundle.items])
    for fact in processed["facts"]:
        assert fact["id"] not in resolved

    # The patient's own words — and the English rendering of them the doctor
    # already sees in the case view — are still there. That is patient-provided
    # content, not an unconfirmed machine claim, and decision 2 does not touch it.
    problems = [i for i in bundle.items if i.kind == BundleItemKind.CURRENT_PROBLEM]
    assert problems and problems[0].payload["text"] == problem["content"]


def test_confirmed_facts_enter_the_bundle_with_attribution(client, db, consented_patient, make_doctor):
    from tests.conftest import create_problem, process_record

    doctor = make_doctor()
    problem = create_problem(client, consented_patient)
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    first = facts[0]
    assert client.post(
        f"{API}/patients/me/ai/facts/{first['id']}", json={"action": "confirm"}, headers=consented_patient.h
    ).status_code == 200

    c = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [problem["id"]], "medical_record_ids": [],
                      "document_ids": [], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    ).json()
    bundle = _bundle(db, doctor.id, c["id"])

    fact_items = [i for i in bundle.items if i.kind == BundleItemKind.FACT]
    assert len(fact_items) == 1
    item = fact_items[0]
    assert item.origin == SummaryItemOrigin.PATIENT_CONFIRMED
    assert item.payload["subject"] == first["subject"]
    assert item.payload["value"] == first["effective_value"]
    assert item.resolution["fact_id"] == first["id"]
    assert bundle.pending_fact_count == len(facts) - 1


def test_rejected_facts_never_appear(client, db, consented_patient, make_doctor):
    from tests.conftest import create_problem, process_record

    doctor = make_doctor()
    problem = create_problem(client, consented_patient)
    facts = process_record(client, consented_patient, problem["id"]).json()["facts"]
    rejected = facts[0]
    client.post(
        f"{API}/patients/me/ai/facts/{rejected['id']}", json={"action": "reject"}, headers=consented_patient.h
    )

    c = client.post(
        f"{API}/patients/me/consultations",
        json={
            "doctor_id": doctor.id,
            "share": {"current_problem_ids": [problem["id"]], "medical_record_ids": [],
                      "document_ids": [], "consultation_ids": [], "prescription_ids": []},
        },
        headers=consented_patient.h,
    ).json()
    bundle = _bundle(db, doctor.id, c["id"])

    resolved = json.dumps([i.resolution for i in bundle.items])
    assert rejected["id"] not in resolved
    assert bundle.pending_fact_count == len(facts) - 1


def test_revoking_a_share_removes_the_item_from_the_bundle(client, db, seeded_case):
    """No revoke endpoint exists yet, but the column is honoured. When one is
    added it must take effect here without touching this module."""
    from app.models import ConsultationShare
    from datetime import UTC, datetime

    c = request_consultation(client, seeded_case).json()
    before = _bundle(db, seeded_case.doctor.id, c["id"])
    assert "Hypertension" in before.canonical()

    share = db.scalar(
        select(ConsultationShare).where(
            ConsultationShare.consultation_id == uuid.UUID(c["id"]),
            ConsultationShare.item_id == uuid.UUID(seeded_case.shared_rec["id"]),
        )
    )
    share.revoked_at = datetime.now(UTC)
    db.commit()
    db.expire_all()

    after = _bundle(db, seeded_case.doctor.id, c["id"])
    assert "Hypertension" not in after.canonical()
    assert after.hash() != before.hash()
