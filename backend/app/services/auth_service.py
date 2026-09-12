from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import dummy_verify, hash_password, verify_password
from app.models import DoctorProfile, PatientProfile, User
from app.models.enums import UserRole
from app.schemas.auth import PatientRegisterRequest
from app.schemas.doctor import DoctorCreate
from app.services import audit
from app.services.audit import RequestContext
from app.services.errors import AuthenticationFailed, Conflict


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == _normalise_email(email)))


def authenticate(db: Session, email: str, password: str, ctx: RequestContext | None = None) -> User:
    user = get_user_by_email(db, email)
    if user is None:
        dummy_verify()  # keep timing similar for unknown emails
        ok = False
    else:
        ok = verify_password(password, user.password_hash) and user.is_active
    if not ok:
        audit.record(
            db,
            actor=user,
            action="auth.login_failed",
            resource_type="user",
            resource_id=user.id if user else None,
            ctx=ctx,
        )
        db.commit()
        raise AuthenticationFailed("Invalid email or password")
    audit.record(db, actor=user, action="auth.login", resource_type="user", resource_id=user.id, ctx=ctx)
    db.commit()
    return user


def _ensure_email_free(db: Session, email: str) -> None:
    if get_user_by_email(db, email) is not None:
        raise Conflict("An account with this email already exists", code="email_taken")


def register_patient(db: Session, data: PatientRegisterRequest, ctx: RequestContext | None = None) -> User:
    _ensure_email_free(db, data.email)
    user = User(role=UserRole.PATIENT, email=_normalise_email(data.email), password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    profile = PatientProfile(
        user_id=user.id, display_name=data.display_name, preferred_language=data.preferred_language
    )
    db.add(profile)
    db.flush()
    audit.record(
        db, actor=user, action="patient.registered", resource_type="patient", resource_id=profile.id,
        patient_id=profile.id, ctx=ctx,
    )
    db.commit()
    return user


def create_doctor(db: Session, data: DoctorCreate, actor: User | None, ctx: RequestContext | None = None) -> DoctorProfile:
    _ensure_email_free(db, data.email)
    user = User(role=UserRole.DOCTOR, email=_normalise_email(data.email), password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    doctor = DoctorProfile(
        user_id=user.id,
        name=data.name,
        specialization=data.specialization,
        qualification=data.qualification,
        registration_identifier=data.registration_identifier,
        clinic_name=data.clinic_name,
        clinic_address=data.clinic_address,
        phone=data.phone,
    )
    doctor.set_languages(data.languages)
    db.add(doctor)
    db.flush()
    audit.record(db, actor=actor, action="doctor.created", resource_type="doctor", resource_id=doctor.id, ctx=ctx)
    db.commit()
    return doctor
