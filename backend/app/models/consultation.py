from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, Timestamps, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import ConsultationStatus, ShareItemType, UserRole

if TYPE_CHECKING:
    from app.models.doctor import DoctorProfile
    from app.models.patient import PatientProfile


class Consultation(UUIDPrimaryKey, Timestamps, Base):
    """One patient ↔ one doctor episode. Consultations are never merged."""

    __tablename__ = "consultations"
    __table_args__ = (
        sa.Index("ix_consultations_doctor_status", "doctor_id", "status"),
        sa.Index("ix_consultations_patient_status", "patient_id", "status"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("doctor_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ConsultationStatus] = mapped_column(
        enum_column(ConsultationStatus, "consultation_status"),
        nullable=False,
        default=ConsultationStatus.REQUESTED,
        server_default=ConsultationStatus.REQUESTED.value,
    )
    # Optional note from the patient to this doctor, in the patient's own words.
    request_message: Mapped[str | None] = mapped_column(sa.Text)
    request_language: Mapped[LanguageCode | None] = mapped_column(
        enum_column(LanguageCode, "request_language")
    )
    # Immutable snapshot of the sharing decision (categories checked/unchecked,
    # item ids, time). Enforcement uses `consultation_shares`; this is the record.
    patient_shared_context: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    # Doctor's assessment/notes for this consultation, attributed to this doctor.
    doctor_assessment: Mapped[str | None] = mapped_column(sa.Text)

    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    cancelled_by_role: Mapped[UserRole | None] = mapped_column(enum_column(UserRole, "cancelled_by_role"))
    cancellation_reason: Mapped[str | None] = mapped_column(sa.Text)

    patient: Mapped[PatientProfile] = relationship()
    doctor: Mapped[DoctorProfile] = relationship()
    shares: Mapped[list[ConsultationShare]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan"
    )
    messages: Mapped[list[ConsultationMessage]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
        order_by="ConsultationMessage.created_at",
    )
    prescriptions: Mapped[list[Prescription]] = relationship(
        back_populates="consultation", order_by="Prescription.created_at"
    )

    def shared_ids(self, item_type: ShareItemType) -> set[uuid.UUID]:
        return {s.item_id for s in self.shares if s.item_type == item_type and s.revoked_at is None}


class ConsultationShare(UUIDPrimaryKey, Base):
    """A patient's grant letting this consultation's doctor see one item."""

    __tablename__ = "consultation_shares"
    __table_args__ = (
        sa.UniqueConstraint("consultation_id", "item_type", "item_id", name="uq_consultation_share_item"),
    )

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[ShareItemType] = mapped_column(enum_column(ShareItemType, "share_item_type"), nullable=False)
    # Polymorphic reference; ownership is validated in the service layer.
    item_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    consultation: Mapped[Consultation] = relationship(back_populates="shares")


class ConsultationMessage(UUIDPrimaryKey, Base):
    __tablename__ = "consultation_messages"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    sender_role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "sender_role"), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)  # original wording
    language: Mapped[LanguageCode | None] = mapped_column(enum_column(LanguageCode, "message_language"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    consultation: Mapped[Consultation] = relationship(back_populates="messages")


class Prescription(UUIDPrimaryKey, Base):
    """Doctor-authored. Immutable once issued. Never generated or edited by AI."""

    __tablename__ = "prescriptions"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("consultations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("doctor_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instructions: Mapped[str | None] = mapped_column(sa.Text)  # general advice
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    consultation: Mapped[Consultation] = relationship(back_populates="prescriptions")
    doctor: Mapped[DoctorProfile] = relationship()
    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.position"
    )


class PrescriptionItem(UUIDPrimaryKey, Base):
    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    medication: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    duration: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    instructions: Mapped[str | None] = mapped_column(sa.Text)

    prescription: Mapped[Prescription] = relationship(back_populates="items")
