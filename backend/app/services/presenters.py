"""ORM → response-schema mapping shared by patient and doctor views."""

from datetime import date

from app.models import Consultation, DoctorProfile, PatientProfile, Prescription
from app.schemas.consultation import (
    ConsultationSummary,
    DoctorAttribution,
    PatientIdentityOut,
    PrescriptionItemOut,
    PrescriptionOut,
    SharedConsultationOut,
)
from app.schemas.doctor import DoctorAccountOut, DoctorApplicationOut, DoctorPublicOut
from app.schemas.patient import PatientProfileOut


def doctor_attribution(d: DoctorProfile) -> DoctorAttribution:
    return DoctorAttribution(
        id=d.id, name=d.name, specialization=d.specialization, registration_identifier=d.registration_identifier
    )


def doctor_public(d: DoctorProfile) -> DoctorPublicOut:
    return DoctorPublicOut.model_validate(d)


def doctor_account(d: DoctorProfile) -> DoctorAccountOut:
    return DoctorAccountOut.model_validate(d)


def doctor_application(d: DoctorProfile, registration_conflict: bool) -> DoctorApplicationOut:
    return DoctorApplicationOut(
        **doctor_account(d).model_dump(),
        email=d.user.email,
        applied_at=d.created_at,
        registration_conflict=registration_conflict,
    )


def patient_profile(p: PatientProfile) -> PatientProfileOut:
    out = PatientProfileOut.model_validate(p)
    out.age = p.age_on(date.today())
    return out


def patient_identity(p: PatientProfile) -> PatientIdentityOut:
    return PatientIdentityOut(
        id=p.id,
        display_name=p.display_name,
        age=p.age_on(date.today()),
        sex=p.sex,
        preferred_language=p.preferred_language,
    )


def prescription(rx: Prescription) -> PrescriptionOut:
    return PrescriptionOut(
        id=rx.id,
        consultation_id=rx.consultation_id,
        authored_by=doctor_attribution(rx.doctor),
        instructions=rx.instructions,
        items=[PrescriptionItemOut.model_validate(i) for i in rx.items],
        created_at=rx.created_at,
    )


def consultation_summary(c: Consultation) -> ConsultationSummary:
    return ConsultationSummary(
        id=c.id,
        status=c.status,
        doctor=doctor_attribution(c.doctor),
        created_at=c.created_at,
        started_at=c.started_at,
        completed_at=c.completed_at,
        prescription_count=len(c.prescriptions),
    )


def shared_consultation(c: Consultation) -> SharedConsultationOut:
    return SharedConsultationOut(
        id=c.id,
        status=c.status,
        doctor=doctor_attribution(c.doctor),
        started_at=c.started_at,
        completed_at=c.completed_at,
        created_at=c.created_at,
        doctor_assessment=c.doctor_assessment,
    )
