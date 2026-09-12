import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Consultation, MedicalDocument, MedicalRecord, PatientProfile, Prescription, User
from app.models.enums import ConsultationStatus, RecordSource, RecordStatus, RecordType
from app.schemas.consultation import PatientDashboard
from app.schemas.document import MedicalDocumentOut
from app.schemas.patient import (
    CurrentProblemCreate,
    MedicalRecordCreate,
    MedicalRecordOut,
    MedicalRecordUpdate,
    PatientProfileUpdate,
)
from app.services import audit, presenters
from app.services.errors import Forbidden, InvalidInput, NotFound

OPEN_STATUSES = (ConsultationStatus.REQUESTED, ConsultationStatus.ACCEPTED, ConsultationStatus.ACTIVE)


def update_profile(db: Session, patient: PatientProfile, data: PatientProfileUpdate, actor: User) -> PatientProfile:
    changes = data.model_dump(exclude_unset=True)
    if "display_name" in changes and changes["display_name"] is None:
        raise InvalidInput("display_name cannot be empty")
    if "preferred_language" in changes and changes["preferred_language"] is None:
        raise InvalidInput("preferred_language cannot be empty")
    if "sex" in changes and changes["sex"] is None:
        raise InvalidInput("sex cannot be empty")
    for field, value in changes.items():
        setattr(patient, field, value)
    audit.record(
        db, actor=actor, action="patient.profile_updated", resource_type="patient", resource_id=patient.id,
        patient_id=patient.id, details={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(patient)
    return patient


# ---------- medical records ----------


def list_records(db: Session, patient: PatientProfile, type_: RecordType | None = None) -> list[MedicalRecord]:
    q = select(MedicalRecord).where(MedicalRecord.patient_id == patient.id)
    if type_ is not None:
        q = q.where(MedicalRecord.type == type_)
    return list(db.scalars(q.order_by(MedicalRecord.created_at.desc())))


def get_own_record(db: Session, patient: PatientProfile, record_id: uuid.UUID) -> MedicalRecord:
    rec = db.get(MedicalRecord, record_id)
    if rec is None or rec.patient_id != patient.id:
        raise NotFound("Record not found")
    return rec


def create_record(db: Session, patient: PatientProfile, data: MedicalRecordCreate, actor: User) -> MedicalRecord:
    if data.type != RecordType.CURRENT_PROBLEM and not data.title:
        raise InvalidInput("title is required for this record type")
    if data.type == RecordType.CURRENT_PROBLEM and not data.content.strip():
        raise InvalidInput("content is required for a current problem")
    rec = MedicalRecord(
        patient_id=patient.id,
        type=data.type,
        title=data.title,
        content=data.content,
        source=RecordSource.PATIENT,  # patients can only author patient-provided records
        source_language=data.source_language,
        status=data.status,
        recorded_by_user_id=actor.id,
    )
    db.add(rec)
    db.flush()
    audit.record(
        db, actor=actor, action="record.created", resource_type="medical_record", resource_id=rec.id,
        patient_id=patient.id, details={"type": data.type.value},
    )
    db.commit()
    return rec


def create_current_problem(db: Session, patient: PatientProfile, data: CurrentProblemCreate, actor: User) -> MedicalRecord:
    return create_record(
        db,
        patient,
        MedicalRecordCreate(type=RecordType.CURRENT_PROBLEM, content=data.text, source_language=data.language),
        actor,
    )


def update_record(
    db: Session, patient: PatientProfile, record_id: uuid.UUID, data: MedicalRecordUpdate, actor: User
) -> MedicalRecord:
    rec = get_own_record(db, patient, record_id)
    if rec.source != RecordSource.PATIENT:
        # Doctor-provided and AI-extracted records keep their attribution intact.
        raise Forbidden("Only patient-provided records can be edited by the patient")
    changes = data.model_dump(exclude_unset=True)
    for field in ("source_language", "status"):
        if field in changes and changes[field] is None:
            raise InvalidInput(f"{field} cannot be empty")
    for field, value in changes.items():
        setattr(rec, field, "" if field == "content" and value is None else value)
    audit.record(
        db, actor=actor, action="record.updated", resource_type="medical_record", resource_id=rec.id,
        patient_id=patient.id, details={"fields": sorted(changes)},
    )
    db.commit()
    return rec


def delete_record(db: Session, patient: PatientProfile, record_id: uuid.UUID, actor: User) -> None:
    rec = get_own_record(db, patient, record_id)
    if rec.source != RecordSource.PATIENT:
        raise Forbidden("Only patient-provided records can be deleted by the patient")
    db.delete(rec)
    audit.record(
        db, actor=actor, action="record.deleted", resource_type="medical_record", resource_id=record_id,
        patient_id=patient.id,
    )
    db.commit()


# ---------- dashboard ----------


def dashboard(db: Session, patient: PatientProfile) -> PatientDashboard:
    records = list_records(db, patient)

    def active(t: RecordType) -> list[MedicalRecordOut]:
        return [
            MedicalRecordOut.model_validate(r) for r in records if r.type == t and r.status == RecordStatus.ACTIVE
        ]

    problems = [r for r in records if r.type == RecordType.CURRENT_PROBLEM]
    docs = db.scalars(
        select(MedicalDocument)
        .where(MedicalDocument.patient_id == patient.id)
        .order_by(MedicalDocument.uploaded_at.desc())
        .limit(3)
    )
    open_consultations = db.scalars(
        select(Consultation)
        .where(Consultation.patient_id == patient.id, Consultation.status.in_(OPEN_STATUSES))
        .options(selectinload(Consultation.doctor), selectinload(Consultation.prescriptions))
        .order_by(Consultation.created_at.desc())
    )
    rxs = db.scalars(
        select(Prescription)
        .where(Prescription.patient_id == patient.id)
        .options(selectinload(Prescription.doctor), selectinload(Prescription.items))
        .order_by(Prescription.created_at.desc())
        .limit(3)
    )
    profile = presenters.patient_profile(patient)
    return PatientDashboard(
        display_name=patient.display_name,
        preferred_language=patient.preferred_language,
        date_of_birth=patient.date_of_birth,
        age=profile.age,
        latest_current_problem=MedicalRecordOut.model_validate(problems[0]) if problems else None,
        conditions=active(RecordType.CONDITION),
        allergies=active(RecordType.ALLERGY),
        medications=active(RecordType.MEDICATION),
        recent_documents=[MedicalDocumentOut.model_validate(d) for d in docs],
        open_consultations=[presenters.consultation_summary(c) for c in open_consultations],
        recent_prescriptions=[presenters.prescription(rx) for rx in rxs],
    )
