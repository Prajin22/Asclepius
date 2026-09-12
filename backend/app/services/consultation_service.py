"""Consultations: requests, patient-controlled sharing, lifecycle, messages, prescriptions.

Invariants enforced here:
* A doctor sees only consultations addressed to them, and within those only
  items the patient granted (`consultation_shares`) plus minimal identity.
* Each consultation is independent. Prescriptions take patient/doctor from the
  consultation, never from client input, and are immutable once issued.
* Nothing here generates or alters clinical content.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Consultation,
    ConsultationMessage,
    ConsultationShare,
    DoctorProfile,
    MedicalDocument,
    MedicalRecord,
    PatientProfile,
    Prescription,
    PrescriptionItem,
    User,
)
from app.models.enums import ConsultationStatus as CS
from app.models.enums import RecordType, ShareItemType, UserRole
from app.schemas.consultation import (
    CaseView,
    ConsultationRequestCreate,
    DoctorQueueItem,
    MessageCreate,
    MessageOut,
    PatientConsultationDetail,
    PrescriptionCreate,
    SharedItemRef,
)
from app.schemas.document import MedicalDocumentOut
from app.schemas.patient import MedicalRecordOut
from app.services import audit, presenters
from app.services.audit import RequestContext
from app.services.errors import Conflict, Forbidden, InvalidInput, InvalidTransition, NotFound

SHARE_CATEGORIES = (
    "current_problem",
    "medical_history",
    "documents",
    "previous_consultations",
    "previous_prescriptions",
)
OPEN_STATUSES = {CS.REQUESTED, CS.ACCEPTED, CS.ACTIVE}
DOCTOR_VISIBLE_STATUSES = {CS.REQUESTED, CS.ACCEPTED, CS.ACTIVE, CS.COMPLETED}
MESSAGING_STATUSES = {CS.ACCEPTED, CS.ACTIVE}

# action -> (allowed from, to)
TRANSITIONS: dict[str, tuple[frozenset[CS], CS]] = {
    "accept": (frozenset({CS.REQUESTED}), CS.ACTIVE),
    "decline": (frozenset({CS.REQUESTED}), CS.CANCELLED),
    "cancel": (frozenset({CS.REQUESTED, CS.ACCEPTED}), CS.CANCELLED),
    "complete": (frozenset({CS.ACCEPTED, CS.ACTIVE}), CS.COMPLETED),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _load_options():
    return (
        selectinload(Consultation.doctor).selectinload(DoctorProfile.language_links),
        selectinload(Consultation.patient),
        selectinload(Consultation.shares),
        selectinload(Consultation.messages),
        selectinload(Consultation.prescriptions).selectinload(Prescription.items),
        selectinload(Consultation.prescriptions).selectinload(Prescription.doctor),
    )


def _load(db: Session, consultation_id: uuid.UUID) -> Consultation | None:
    return db.scalar(select(Consultation).where(Consultation.id == consultation_id).options(*_load_options()))


# ---------- request + sharing ----------


def _unique(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(ids))


def _require_owned(db: Session, model, ids: list[uuid.UUID], patient_id: uuid.UUID, *extra) -> None:
    if not ids:
        return
    found = set(db.scalars(select(model.id).where(model.id.in_(ids), model.patient_id == patient_id, *extra)))
    if found != set(ids):
        raise InvalidInput("One or more selected items cannot be shared", code="invalid_share_item")


def request_consultation(
    db: Session, patient: PatientProfile, actor: User, data: ConsultationRequestCreate, ctx: RequestContext | None = None
) -> Consultation:
    doctor = db.get(DoctorProfile, data.doctor_id)
    if doctor is None:
        raise NotFound("Doctor not found")
    if not doctor.is_accepting_consultations:
        raise Conflict("This doctor is not accepting consultations", code="doctor_unavailable")
    duplicate = db.scalar(
        select(Consultation.id).where(
            Consultation.patient_id == patient.id,
            Consultation.doctor_id == doctor.id,
            Consultation.status.in_(OPEN_STATUSES),
        )
    )
    if duplicate:
        raise Conflict("You already have an open consultation with this doctor", code="duplicate_open_consultation")

    sel = data.share
    cp_ids, rec_ids = _unique(sel.current_problem_ids), _unique(sel.medical_record_ids)
    doc_ids, con_ids, rx_ids = _unique(sel.document_ids), _unique(sel.consultation_ids), _unique(sel.prescription_ids)

    record_ids = set(cp_ids) | set(rec_ids)
    records = (
        {r.id: r for r in db.scalars(select(MedicalRecord).where(MedicalRecord.id.in_(record_ids)))}
        if record_ids
        else {}
    )
    for rid in cp_ids:
        r = records.get(rid)
        if r is None or r.patient_id != patient.id or r.type != RecordType.CURRENT_PROBLEM:
            raise InvalidInput("Selected current problem cannot be shared", code="invalid_share_item")
    for rid in rec_ids:
        r = records.get(rid)
        if r is None or r.patient_id != patient.id or r.type == RecordType.CURRENT_PROBLEM:
            raise InvalidInput("Selected health record cannot be shared", code="invalid_share_item")
    _require_owned(db, MedicalDocument, doc_ids, patient.id)
    _require_owned(db, Consultation, con_ids, patient.id, Consultation.status != CS.CANCELLED)
    _require_owned(db, Prescription, rx_ids, patient.id)

    by_category = {
        "current_problem": cp_ids,
        "medical_history": rec_ids,
        "documents": doc_ids,
        "previous_consultations": con_ids,
        "previous_prescriptions": rx_ids,
    }
    snapshot = {
        "version": 1,
        "decided_at": _now().isoformat(),
        "categories": {k: {"shared": bool(v), "item_ids": [str(i) for i in v]} for k, v in by_category.items()},
    }
    c = Consultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status=CS.REQUESTED,
        request_message=(data.request_message or "").strip() or None,
        request_language=data.request_language if data.request_message else None,
        patient_shared_context=snapshot,
    )
    item_type_for = {
        "current_problem": ShareItemType.MEDICAL_RECORD,
        "medical_history": ShareItemType.MEDICAL_RECORD,
        "documents": ShareItemType.DOCUMENT,
        "previous_consultations": ShareItemType.CONSULTATION,
        "previous_prescriptions": ShareItemType.PRESCRIPTION,
    }
    c.shares = [
        ConsultationShare(item_type=item_type_for[cat], item_id=i) for cat, ids in by_category.items() for i in ids
    ]
    db.add(c)
    db.flush()
    audit.record(
        db, actor=actor, action="consultation.requested", resource_type="consultation", resource_id=c.id,
        patient_id=patient.id, details={"doctor_id": str(doctor.id)}, ctx=ctx,
    )
    audit.record(
        db, actor=actor, action="consultation.sharing_decided", resource_type="consultation", resource_id=c.id,
        patient_id=patient.id, details={k: len(v) for k, v in by_category.items()}, ctx=ctx,
    )
    db.commit()
    return _load(db, c.id)  # type: ignore[return-value]


def shared_categories(c: Consultation) -> list[str]:
    cats = (c.patient_shared_context or {}).get("categories", {})
    return [k for k in SHARE_CATEGORIES if cats.get(k, {}).get("shared")]


# ---------- lifecycle ----------


def _transition(c: Consultation, action: str) -> None:
    allowed, target = TRANSITIONS[action]
    if c.status not in allowed:
        raise InvalidTransition(f"Cannot {action} a consultation that is {c.status.value}")
    now = _now()
    c.status = target
    if action == "accept":
        # Phase 1: accepting starts the consultation immediately (DECISIONS D-007).
        c.accepted_at = now
        c.started_at = now
    elif action == "complete":
        c.completed_at = now
    elif action in ("decline", "cancel"):
        c.cancelled_at = now


def get_doctor_consultation(db: Session, doctor: DoctorProfile, consultation_id: uuid.UUID) -> Consultation:
    c = _load(db, consultation_id)
    if c is None or c.doctor_id != doctor.id:
        raise NotFound("Consultation not found")  # do not reveal other doctors' consultations
    return c


def _require_doctor_visibility(c: Consultation) -> None:
    if c.status not in DOCTOR_VISIBLE_STATUSES:
        raise Forbidden("This consultation is no longer shared with you")


def doctor_action(
    db: Session, doctor: DoctorProfile, actor: User, consultation_id: uuid.UUID, action: str,
    reason: str | None = None, ctx: RequestContext | None = None,
) -> Consultation:
    if action not in ("accept", "decline", "complete"):
        raise InvalidInput("Unknown action")
    c = get_doctor_consultation(db, doctor, consultation_id)
    _transition(c, action)
    if action == "decline":
        c.cancelled_by_role = UserRole.DOCTOR
        c.cancellation_reason = (reason or "").strip() or None
    audit.record(
        db, actor=actor, action=f"consultation.{action}ed" if action != "decline" else "consultation.declined",
        resource_type="consultation", resource_id=c.id, patient_id=c.patient_id, ctx=ctx,
    )
    db.commit()
    return _load(db, c.id)  # type: ignore[return-value]


def set_assessment(db: Session, doctor: DoctorProfile, actor: User, consultation_id: uuid.UUID, text: str) -> Consultation:
    c = get_doctor_consultation(db, doctor, consultation_id)
    if c.status not in MESSAGING_STATUSES:
        raise InvalidTransition("Notes can only be edited during an active consultation")
    c.doctor_assessment = text.strip() or None
    audit.record(
        db, actor=actor, action="consultation.assessment_updated", resource_type="consultation",
        resource_id=c.id, patient_id=c.patient_id,
    )
    db.commit()
    return _load(db, c.id)  # type: ignore[return-value]


# ---------- prescriptions ----------


def create_prescription(
    db: Session, doctor: DoctorProfile, actor: User, consultation_id: uuid.UUID, data: PrescriptionCreate,
    ctx: RequestContext | None = None,
) -> Prescription:
    c = get_doctor_consultation(db, doctor, consultation_id)
    if c.status != CS.ACTIVE:
        raise InvalidTransition("Prescriptions can only be written during an active consultation")
    rx = Prescription(
        consultation_id=c.id,
        doctor_id=doctor.id,  # the authenticated doctor, never client-supplied
        patient_id=c.patient_id,  # from the consultation, never client-supplied
        instructions=(data.instructions or "").strip() or None,
        items=[
            PrescriptionItem(
                position=i,
                medication=item.medication,
                dosage=item.dosage,
                frequency=item.frequency,
                duration=item.duration,
                instructions=(item.instructions or "").strip() or None,
            )
            for i, item in enumerate(data.items, start=1)
        ],
    )
    db.add(rx)
    db.flush()
    audit.record(
        db, actor=actor, action="prescription.created", resource_type="prescription", resource_id=rx.id,
        patient_id=c.patient_id, details={"consultation_id": str(c.id), "item_count": len(data.items)}, ctx=ctx,
    )
    db.commit()
    return db.scalar(
        select(Prescription)
        .where(Prescription.id == rx.id)
        .options(selectinload(Prescription.items), selectinload(Prescription.doctor))
    )  # type: ignore[return-value]


def list_patient_prescriptions(db: Session, patient: PatientProfile) -> list[Prescription]:
    return list(
        db.scalars(
            select(Prescription)
            .where(Prescription.patient_id == patient.id)
            .options(selectinload(Prescription.items), selectinload(Prescription.doctor))
            .order_by(Prescription.created_at.desc())
        )
    )


# ---------- messages ----------


def get_consultation_for_party(db: Session, user: User, consultation_id: uuid.UUID) -> Consultation:
    c = _load(db, consultation_id)
    if c is None:
        raise NotFound("Consultation not found")
    is_party = (user.role == UserRole.PATIENT and c.patient.user_id == user.id) or (
        user.role == UserRole.DOCTOR and c.doctor.user_id == user.id
    )
    if not is_party:
        raise NotFound("Consultation not found")
    if user.role == UserRole.DOCTOR:
        _require_doctor_visibility(c)
    return c


def list_messages(db: Session, user: User, consultation_id: uuid.UUID) -> list[MessageOut]:
    c = get_consultation_for_party(db, user, consultation_id)
    return [MessageOut.model_validate(m) for m in c.messages]


def post_message(db: Session, user: User, consultation_id: uuid.UUID, data: MessageCreate) -> MessageOut:
    c = get_consultation_for_party(db, user, consultation_id)
    if c.status not in MESSAGING_STATUSES:
        raise InvalidTransition("Messages can only be sent during an active consultation")
    msg = ConsultationMessage(
        consultation_id=c.id, sender_user_id=user.id, sender_role=user.role, body=data.body, language=data.language
    )
    db.add(msg)
    db.commit()
    return MessageOut.model_validate(msg)


# ---------- patient views ----------


def list_patient_consultations(db: Session, patient: PatientProfile) -> list[Consultation]:
    return list(
        db.scalars(
            select(Consultation)
            .where(Consultation.patient_id == patient.id)
            .options(selectinload(Consultation.doctor), selectinload(Consultation.prescriptions))
            .order_by(Consultation.created_at.desc())
        )
    )


def get_patient_consultation(db: Session, patient: PatientProfile, consultation_id: uuid.UUID) -> Consultation:
    c = _load(db, consultation_id)
    if c is None or c.patient_id != patient.id:
        raise NotFound("Consultation not found")
    return c


def patient_cancel(
    db: Session, patient: PatientProfile, actor: User, consultation_id: uuid.UUID, ctx: RequestContext | None = None
) -> Consultation:
    c = get_patient_consultation(db, patient, consultation_id)
    _transition(c, "cancel")
    c.cancelled_by_role = UserRole.PATIENT
    audit.record(
        db, actor=actor, action="consultation.cancelled", resource_type="consultation", resource_id=c.id,
        patient_id=patient.id, ctx=ctx,
    )
    db.commit()
    return _load(db, c.id)  # type: ignore[return-value]


def patient_detail(c: Consultation) -> PatientConsultationDetail:
    return PatientConsultationDetail(
        id=c.id,
        status=c.status,
        doctor=presenters.doctor_public(c.doctor),
        request_message=c.request_message,
        request_language=c.request_language,
        doctor_assessment=c.doctor_assessment,
        created_at=c.created_at,
        accepted_at=c.accepted_at,
        started_at=c.started_at,
        completed_at=c.completed_at,
        cancelled_at=c.cancelled_at,
        cancellation_reason=c.cancellation_reason,
        shared_items=[
            SharedItemRef(item_type=s.item_type.value, item_id=s.item_id) for s in c.shares if s.revoked_at is None
        ],
        shared_categories=shared_categories(c),
        messages=[MessageOut.model_validate(m) for m in c.messages],
        prescriptions=[presenters.prescription(rx) for rx in c.prescriptions],
    )


# ---------- doctor views ----------


def doctor_queue(db: Session, doctor: DoctorProfile, statuses: set[CS] | None = None) -> list[DoctorQueueItem]:
    wanted = statuses or DOCTOR_VISIBLE_STATUSES
    wanted = wanted & DOCTOR_VISIBLE_STATUSES
    cons = list(
        db.scalars(
            select(Consultation)
            .where(Consultation.doctor_id == doctor.id, Consultation.status.in_(wanted))
            .options(selectinload(Consultation.patient), selectinload(Consultation.shares))
            .order_by(Consultation.created_at.desc())
        )
    )
    shared_record_ids = {i for c in cons for i in c.shared_ids(ShareItemType.MEDICAL_RECORD)}
    problems = (
        {
            r.id: r
            for r in db.scalars(
                select(MedicalRecord).where(
                    MedicalRecord.id.in_(shared_record_ids), MedicalRecord.type == RecordType.CURRENT_PROBLEM
                )
            )
        }
        if shared_record_ids
        else {}
    )
    items = []
    for c in cons:
        excerpt = None
        for rid in c.shared_ids(ShareItemType.MEDICAL_RECORD):
            r = problems.get(rid)
            if r is not None and r.patient_id == c.patient_id:
                excerpt = r.content[:180]
                break
        items.append(
            DoctorQueueItem(
                id=c.id,
                status=c.status,
                patient=presenters.patient_identity(c.patient),
                current_problem_excerpt=excerpt,
                created_at=c.created_at,
                started_at=c.started_at,
                completed_at=c.completed_at,
            )
        )
    return items


def build_case_view(db: Session, c: Consultation) -> CaseView:
    """Everything the doctor may see for this consultation — and nothing else."""
    _require_doctor_visibility(c)
    pid = c.patient_id

    rec_ids = c.shared_ids(ShareItemType.MEDICAL_RECORD)
    records = (
        list(
            db.scalars(
                select(MedicalRecord)
                .where(MedicalRecord.id.in_(rec_ids), MedicalRecord.patient_id == pid)
                .order_by(MedicalRecord.created_at.desc())
            )
        )
        if rec_ids
        else []
    )
    doc_ids = c.shared_ids(ShareItemType.DOCUMENT)
    docs = (
        list(
            db.scalars(
                select(MedicalDocument)
                .where(MedicalDocument.id.in_(doc_ids), MedicalDocument.patient_id == pid)
                .order_by(MedicalDocument.uploaded_at.desc())
            )
        )
        if doc_ids
        else []
    )
    con_ids = c.shared_ids(ShareItemType.CONSULTATION) - {c.id}
    shared_cons = (
        list(
            db.scalars(
                select(Consultation)
                .where(Consultation.id.in_(con_ids), Consultation.patient_id == pid)
                .options(selectinload(Consultation.doctor))
                .order_by(Consultation.created_at.desc())
            )
        )
        if con_ids
        else []
    )
    rx_ids = c.shared_ids(ShareItemType.PRESCRIPTION)
    shared_rxs = (
        list(
            db.scalars(
                select(Prescription)
                .where(Prescription.id.in_(rx_ids), Prescription.patient_id == pid)
                .options(selectinload(Prescription.items), selectinload(Prescription.doctor))
                .order_by(Prescription.created_at.desc())
            )
        )
        if rx_ids
        else []
    )
    # The doctor's own earlier consultations with this patient (they were a party to them).
    own_prev = list(
        db.scalars(
            select(Consultation)
            .where(
                Consultation.patient_id == pid,
                Consultation.doctor_id == c.doctor_id,
                Consultation.id != c.id,
                Consultation.status.in_(DOCTOR_VISIBLE_STATUSES),
            )
            .options(selectinload(Consultation.doctor))
            .order_by(Consultation.created_at.desc())
        )
    )
    # AI interpretation of the records the patient actually shared. Doctors see
    # the original text too; this never replaces it.
    from app.services import ai_pipeline, ai_presenters

    insights = [
        ai_presenters.record_insight(ai_pipeline.get_record_state(db, c.patient, record))
        for record in records
    ]
    insights = [i for i in insights if i.status != "not_processed"]

    # Machine reading of shared documents. The original file stays available beside it.
    from app.services import document_pipeline, document_presenters

    document_insights = []
    for doc in docs:
        state = document_pipeline.get_document_state(db, c.patient, doc)
        if state.extraction is not None:
            document_insights.append(document_presenters.document_insight(state))

    return CaseView(
        id=c.id,
        status=c.status,
        patient=presenters.patient_identity(c.patient),
        ai_insights=insights,
        document_insights=document_insights,
        request_message=c.request_message,
        request_language=c.request_language,
        doctor_assessment=c.doctor_assessment,
        created_at=c.created_at,
        accepted_at=c.accepted_at,
        started_at=c.started_at,
        completed_at=c.completed_at,
        shared_categories=shared_categories(c),
        current_problems=[MedicalRecordOut.model_validate(r) for r in records if r.type == RecordType.CURRENT_PROBLEM],
        medical_history=[MedicalRecordOut.model_validate(r) for r in records if r.type != RecordType.CURRENT_PROBLEM],
        documents=[MedicalDocumentOut.model_validate(d) for d in docs],
        shared_consultations=[presenters.shared_consultation(x) for x in shared_cons],
        shared_prescriptions=[presenters.prescription(rx) for rx in shared_rxs],
        own_previous_consultations=[presenters.shared_consultation(x) for x in own_prev],
        messages=[MessageOut.model_validate(m) for m in c.messages],
        prescriptions=[presenters.prescription(rx) for rx in c.prescriptions],
    )


def doctor_case_view(
    db: Session, doctor: DoctorProfile, actor: User, consultation_id: uuid.UUID, ctx: RequestContext | None = None
) -> CaseView:
    c = get_doctor_consultation(db, doctor, consultation_id)
    view = build_case_view(db, c)
    audit.record(
        db, actor=actor, action="consultation.case_viewed", resource_type="consultation", resource_id=c.id,
        patient_id=c.patient_id, ctx=ctx,
    )
    db.commit()
    return view


def doctor_shared_document(
    db: Session, doctor: DoctorProfile, actor: User, consultation_id: uuid.UUID, document_id: uuid.UUID,
    ctx: RequestContext | None = None, *, action: str = "document.viewed_by_doctor", details: dict | None = None,
) -> MedicalDocument:
    c = get_doctor_consultation(db, doctor, consultation_id)
    _require_doctor_visibility(c)
    doc = db.get(MedicalDocument, document_id)
    if doc is None or doc.patient_id != c.patient_id or document_id not in c.shared_ids(ShareItemType.DOCUMENT):
        raise NotFound("Document not found")
    audit.record(
        db, actor=actor, action=action, resource_type="document", resource_id=doc.id,
        patient_id=c.patient_id, details={"consultation_id": str(c.id), **(details or {})}, ctx=ctx,
    )
    db.commit()
    return doc
