from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import LanguageCode
from app.db.base import Base, Timestamps, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import DocumentStatus, DocumentType, RecordSource, RecordStatus, RecordType


class MedicalRecord(UUIDPrimaryKey, Timestamps, Base):
    """A single patient-owned health fact, in the words it was originally given.

    `content` is the source of truth and is never overwritten by AI.
    Normalised/translated forms live in `ai_artifacts` and point back here.
    """

    __tablename__ = "medical_records"
    __table_args__ = (sa.Index("ix_medical_records_patient_type", "patient_id", "type"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[RecordType] = mapped_column(enum_column(RecordType, "record_type"), nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(200))
    content: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    source: Mapped[RecordSource] = mapped_column(enum_column(RecordSource, "record_source"), nullable=False)
    source_language: Mapped[LanguageCode] = mapped_column(
        enum_column(LanguageCode, "source_language"), nullable=False
    )
    status: Mapped[RecordStatus] = mapped_column(
        enum_column(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.ACTIVE,
        server_default=RecordStatus.ACTIVE.value,
    )
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )


class MedicalDocument(UUIDPrimaryKey, Base):
    __tablename__ = "medical_documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(sa.String(160), nullable=False)  # sanitised display name
    mime_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(sa.String(500), nullable=False, unique=True)
    document_type: Mapped[DocumentType] = mapped_column(
        enum_column(DocumentType, "document_type"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(sa.String(200))
    source_language: Mapped[LanguageCode | None] = mapped_column(
        enum_column(LanguageCode, "document_language")
    )
    status: Mapped[DocumentStatus] = mapped_column(
        enum_column(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )
