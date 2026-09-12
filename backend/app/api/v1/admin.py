import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import DB, AdminUser, Ctx
from app.models import AuditEvent
from app.schemas.common import ORMModel
from app.schemas.doctor import DoctorCreate, DoctorPublicOut
from app.services import auth_service, presenters

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
