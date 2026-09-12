import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.languages import LanguageCode
from app.models import DoctorLanguage, DoctorProfile, User
from app.schemas.doctor import DoctorProfileUpdate
from app.services import audit
from app.services.errors import InvalidInput, NotFound


def search_directory(
    db: Session, q: str | None = None, specialization: str | None = None, language: LanguageCode | None = None
) -> list[DoctorProfile]:
    stmt = select(DoctorProfile).options(selectinload(DoctorProfile.language_links))
    if q:
        like = f"%{q.strip()[:100]}%"
        stmt = stmt.where(
            or_(
                DoctorProfile.name.ilike(like),
                DoctorProfile.specialization.ilike(like),
                DoctorProfile.clinic_name.ilike(like),
            )
        )
    if specialization:
        stmt = stmt.where(DoctorProfile.specialization == specialization)
    if language:
        stmt = stmt.where(
            DoctorProfile.id.in_(select(DoctorLanguage.doctor_id).where(DoctorLanguage.language_code == language))
        )
    return list(db.scalars(stmt.order_by(DoctorProfile.name)))


def get_doctor(db: Session, doctor_id: uuid.UUID) -> DoctorProfile:
    d = db.get(DoctorProfile, doctor_id)
    if d is None:
        raise NotFound("Doctor not found")
    return d


def update_profile(db: Session, doctor: DoctorProfile, data: DoctorProfileUpdate, actor: User) -> DoctorProfile:
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "specialization", "qualification", "languages", "is_accepting_consultations"):
        if required in changes and changes[required] is None:
            raise InvalidInput(f"{required} cannot be empty")
    languages = changes.pop("languages", None)
    for field, value in changes.items():
        setattr(doctor, field, value)
    if languages is not None:
        if not languages:
            raise InvalidInput("At least one language is required")
        doctor.set_languages(languages)
    audit.record(
        db, actor=actor, action="doctor.profile_updated", resource_type="doctor", resource_id=doctor.id,
        details={"fields": sorted([*changes, *(["languages"] if languages is not None else [])])},
    )
    db.commit()
    db.refresh(doctor)
    return doctor
