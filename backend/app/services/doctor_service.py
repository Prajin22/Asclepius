import re
import uuid
from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.languages import LanguageCode
from app.db.base import utcnow
from app.models import DoctorLanguage, DoctorProfile, User
from app.models.enums import DoctorApproval
from app.schemas.doctor import DoctorDetails, DoctorProfileUpdate
from app.services import audit
from app.services.audit import RequestContext
from app.services.errors import Conflict, InvalidInput, InvalidTransition, NotFound


def search_directory(
    db: Session, q: str | None = None, specialization: str | None = None, language: LanguageCode | None = None
) -> list[DoctorProfile]:
    stmt = (
        select(DoctorProfile)
        .options(selectinload(DoctorProfile.language_links))
        .where(DoctorProfile.approval_status == DoctorApproval.APPROVED)
    )
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
    # To a patient, an unapproved doctor is indistinguishable from no doctor.
    if d is None or not d.is_approved:
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


# ---------- applications ----------


def _registration_key(number: str) -> str:
    """Registration numbers compare without spacing, punctuation or case."""
    return re.sub(r"[^0-9a-z]", "", number.lower()) or number


def _registration_holders(db: Session, *, approved_only: bool = False) -> dict[str, set[uuid.UUID]]:
    stmt = select(DoctorProfile.id, DoctorProfile.registration_identifier)
    if approved_only:
        stmt = stmt.where(DoctorProfile.approval_status == DoctorApproval.APPROVED)
    holders: dict[str, set[uuid.UUID]] = defaultdict(set)
    for doctor_id, number in db.execute(stmt):
        holders[_registration_key(number)].add(doctor_id)
    return holders


def registration_conflicts(db: Session, doctors: list[DoctorProfile]) -> set[uuid.UUID]:
    """Doctors whose registration number another doctor account also uses."""
    holders = _registration_holders(db)
    return {d.id for d in doctors if holders.get(_registration_key(d.registration_identifier), set()) - {d.id}}


def list_applications(db: Session, status: DoctorApproval | None = None) -> list[DoctorProfile]:
    stmt = select(DoctorProfile).options(selectinload(DoctorProfile.language_links), selectinload(DoctorProfile.user))
    if status is not None:
        stmt = stmt.where(DoctorProfile.approval_status == status)
    # Oldest first: applications are reviewed in the order they arrived.
    return list(db.scalars(stmt.order_by(DoctorProfile.created_at, DoctorProfile.id)))


# decision -> the states it may be made from. Rejecting an approved doctor
# revokes their access immediately.
_REVIEWABLE_FROM = {
    DoctorApproval.APPROVED: {DoctorApproval.PENDING, DoctorApproval.REJECTED},
    DoctorApproval.REJECTED: {DoctorApproval.PENDING, DoctorApproval.APPROVED},
}


def review_application(
    db: Session,
    doctor_id: uuid.UUID,
    decision: DoctorApproval,
    actor: User,
    *,
    note: str | None = None,
    ctx: RequestContext | None = None,
) -> DoctorProfile:
    doctor = db.get(DoctorProfile, doctor_id)
    if doctor is None:
        raise NotFound("Doctor not found")
    if doctor.approval_status not in _REVIEWABLE_FROM[decision]:
        raise InvalidTransition(f"This doctor is already {doctor.approval_status.value}")
    if decision == DoctorApproval.APPROVED:
        holders = _registration_holders(db, approved_only=True)
        if holders.get(_registration_key(doctor.registration_identifier), set()) - {doctor.id}:
            raise Conflict("An approved doctor already uses this registration number", code="registration_in_use")
    previous = doctor.approval_status
    doctor.approval_status = decision
    doctor.approval_note = note if decision == DoctorApproval.REJECTED else None
    doctor.reviewed_at = utcnow()
    audit.record(
        db, actor=actor, action=f"doctor.{decision.value}", resource_type="doctor", resource_id=doctor.id,
        details={"from": previous.value}, ctx=ctx,
    )
    db.commit()
    db.refresh(doctor)
    return doctor


def update_application(
    db: Session, doctor: DoctorProfile, data: DoctorDetails, actor: User, ctx: RequestContext | None = None
) -> DoctorProfile:
    """Correct the details an admin reviews. Sends the application back for review."""
    if doctor.is_approved:
        raise InvalidTransition("This doctor is approved; edit the profile instead", code="application_closed")
    previous = doctor.approval_status
    for field, value in data.model_dump(exclude={"languages"}).items():
        setattr(doctor, field, value)
    doctor.set_languages(data.languages)
    doctor.approval_status = DoctorApproval.PENDING
    doctor.approval_note = None
    doctor.reviewed_at = None
    audit.record(
        db, actor=actor, action="doctor.application_updated", resource_type="doctor", resource_id=doctor.id,
        details={"from": previous.value}, ctx=ctx,
    )
    db.commit()
    db.refresh(doctor)
    return doctor
