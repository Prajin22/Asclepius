import uuid

from fastapi import APIRouter, status

from app.api.deps import DB, PatientOrDoctorUser
from app.schemas.consultation import MessageCreate, MessageOut
from app.services import consultation_service

router = APIRouter(prefix="/consultations", tags=["messages"])


@router.get("/{consultation_id}/messages", response_model=list[MessageOut])
def list_messages(consultation_id: uuid.UUID, user: PatientOrDoctorUser, db: DB) -> list[MessageOut]:
    return consultation_service.list_messages(db, user, consultation_id)


@router.post("/{consultation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def post_message(consultation_id: uuid.UUID, data: MessageCreate, user: PatientOrDoctorUser, db: DB) -> MessageOut:
    return consultation_service.post_message(db, user, consultation_id, data)
