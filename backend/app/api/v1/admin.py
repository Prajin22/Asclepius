import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import DB, AdminUser, Ctx
from app.models import AuditEvent
from app.models.enums import DoctorApproval
from app.schemas.common import ORMModel
from app.schemas.doctor import DoctorApplicationOut, DoctorCreate, DoctorPublicOut, DoctorRejectRequest
from app.services import auth_service, doctor_service, presenters

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditEventOut(ORMModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    action: str
    resource_type: str
    resource_id: str | None
    patient_id: uuid.UUID | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime


@router.post("/doctors", response_model=DoctorPublicOut, status_code=status.HTTP_201_CREATED)
def create_doctor(data: DoctorCreate, admin: AdminUser, db: DB, ctx: Ctx) -> DoctorPublicOut:
    return presenters.doctor_public(auth_service.create_doctor(db, data, admin, ctx))


@router.get("/doctors", response_model=list[DoctorApplicationOut])
def doctor_applications(
    _: AdminUser, db: DB, status_: DoctorApproval | None = Query(default=None, alias="status")
) -> list[DoctorApplicationOut]:
    doctors = doctor_service.list_applications(db, status_)
    conflicts = doctor_service.registration_conflicts(db, doctors)
    return [presenters.doctor_application(d, d.id in conflicts) for d in doctors]


@router.post("/doctors/{doctor_id}/approve", response_model=DoctorApplicationOut)
def approve_doctor(doctor_id: uuid.UUID, admin: AdminUser, db: DB, ctx: Ctx) -> DoctorApplicationOut:
    doctor = doctor_service.review_application(db, doctor_id, DoctorApproval.APPROVED, admin, ctx=ctx)
    return presenters.doctor_application(doctor, doctor.id in doctor_service.registration_conflicts(db, [doctor]))


@router.post("/doctors/{doctor_id}/reject", response_model=DoctorApplicationOut)
def reject_doctor(
    doctor_id: uuid.UUID, data: DoctorRejectRequest, admin: AdminUser, db: DB, ctx: Ctx
) -> DoctorApplicationOut:
    """Declines an application, or revokes an approved doctor's access. The reason is shown to the doctor."""
    doctor = doctor_service.review_application(
        db, doctor_id, DoctorApproval.REJECTED, admin, note=data.reason, ctx=ctx
    )
    return presenters.doctor_application(doctor, doctor.id in doctor_service.registration_conflicts(db, [doctor]))


@router.get("/audit-events", response_model=list[AuditEventOut])
def audit_events(
    _: AdminUser,
    db: DB,
    patient_id: uuid.UUID | None = None,
    action: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AuditEventOut]:
    q = select(AuditEvent)
    if patient_id:
        q = q.where(AuditEvent.patient_id == patient_id)
    if action:
        q = q.where(AuditEvent.action == action)
    return [AuditEventOut.model_validate(e) for e in db.scalars(q.order_by(AuditEvent.created_at.desc()).limit(limit))]
