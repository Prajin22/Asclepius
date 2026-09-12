from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import (
    AIArtifactStatus,
    AIReviewStatus,
    FactCategory,
    FactReviewState,
    FactSubject,
    FactValidation,
)

if TYPE_CHECKING:
    from app.models.medical import MedicalRecord


class AIArtifact(UUIDPrimaryKey, Base):
    """Output of one AI operation. Never ground truth; always traceable.

    Provenance for every run: operation, provider, model, prompt version,
    latency, token usage, estimated cost, status and the source it came from.
    `source_references` is a list like
    [{"type": "medical_record", "id": "...", "span": [start, end]}, ...].
    """

    __tablename__ = "ai_artifacts"
    __table_args__ = (
        sa.Index("ix_ai_artifacts_patient_type", "patient_id", "artifact_type"),
        sa.Index("ix_ai_artifacts_cache_key", "cache_key"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("consultations.id", ondelete="CASCADE")
    )
    # The pipeline operation (app.models.enums.AIOperation).
    artifact_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    model: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64))
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    # sha256 of the exact source text this artifact was derived from.
    source_hash: Mapped[str | None] = mapped_column(sa.String(64), index=True)
    # operation + provider + model + prompt version + language + source hash.
    cache_key: Mapped[str | None] = mapped_column(sa.String(255))
    input_language: Mapped[LanguageCode | None] = mapped_column(enum_column(LanguageCode, "input_language"))
    output_language: Mapped[LanguageCode | None] = mapped_column(enum_column(LanguageCode, "output_language"))
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(sa.Float)
    status: Mapped[AIArtifactStatus] = mapped_column(
        enum_column(AIArtifactStatus, "ai_artifact_status"),
        nullable=False,
        default=AIArtifactStatus.SUCCEEDED,
        server_default=AIArtifactStatus.SUCCEEDED.value,
    )
    error_code: Mapped[str | None] = mapped_column(sa.String(64))
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer)
    input_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    output_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(sa.Float)
    review_status: Mapped[AIReviewStatus] = mapped_column(
        enum_column(AIReviewStatus, "ai_review_status"),
        nullable=False,
        default=AIReviewStatus.UNREVIEWED,
        server_default=AIReviewStatus.UNREVIEWED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    facts: Mapped[list[AIExtractedFact]] = relationship(
        back_populates="artifact", cascade="all, delete-orphan", order_by="AIExtractedFact.position"
    )

    @property
    def operation(self) -> str:
        return self.artifact_type


class AIExtractedFact(UUIDPrimaryKey, Base):
    """One machine-extracted fact, with the evidence it was taken from.

    A fact is never a medical record on its own: it stays `pending` until the
    patient confirms, edits or rejects it.
    """

    __tablename__ = "ai_extracted_facts"
    __table_args__ = (sa.Index("ix_ai_facts_patient_state", "patient_id", "review_state"),)

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("ai_artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False
    )
    # The source the evidence points into (a medical record in Phase 2).
    source_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    category: Mapped[FactCategory] = mapped_column(enum_column(FactCategory, "fact_category"), nullable=False)
    # Whose health this describes. Family facts never become the patient's own
    # allergy or medication record (see services/ai_facts.py).
    subject: Mapped[FactSubject] = mapped_column(
        enum_column(FactSubject, "fact_subject"),
        nullable=False,
        default=FactSubject.SELF,
        server_default=FactSubject.SELF.value,
    )
    # The words that attributed it, when attribution was explicit.
    subject_evidence: Mapped[str | None] = mapped_column(sa.String(200))
    value: Mapped[str] = mapped_column(sa.String(300), nullable=False)  # English, machine-produced
    original_text: Mapped[str | None] = mapped_column(sa.Text)  # the patient's own words
    evidence_quote: Mapped[str] = mapped_column(sa.Text, nullable=False)
    evidence_start: Mapped[int | None] = mapped_column(sa.Integer)
    evidence_end: Mapped[int | None] = mapped_column(sa.Integer)
    # Documents: the page the evidence is on and where, as fractions of the page
    # [x0, y0, x1, y1]. Frozen at extraction time so provenance cannot drift.
    evidence_page_number: Mapped[int | None] = mapped_column(sa.Integer)
    evidence_bbox: Mapped[list[float] | None] = mapped_column(JSONType)
    confidence: Mapped[float | None] = mapped_column(sa.Float)

    validation_status: Mapped[FactValidation] = mapped_column(
        enum_column(FactValidation, "fact_validation"),
        nullable=False,
        default=FactValidation.NEEDS_REVIEW,
        server_default=FactValidation.NEEDS_REVIEW.value,
    )
    validation_note: Mapped[str | None] = mapped_column(sa.String(200))
    review_state: Mapped[FactReviewState] = mapped_column(
        enum_column(FactReviewState, "fact_review_state"),
        nullable=False,
        default=FactReviewState.PENDING,
        server_default=FactReviewState.PENDING.value,
    )
    edited_value: Mapped[str | None] = mapped_column(sa.String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    # Set when confirming created a patient health record from this fact.
    medical_record_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("medical_records.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )

    artifact: Mapped[AIArtifact] = relationship(back_populates="facts")
    medical_record: Mapped[MedicalRecord | None] = relationship()

    @property
    def effective_value(self) -> str:
        """What the patient stands behind: their edit if any, else the AI value."""
        return self.edited_value or self.value
