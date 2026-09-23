from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, Timestamps, UUIDPrimaryKey, enum_column
from app.models.enums import SummaryStatus


class ConsultationSummary(UUIDPrimaryKey, Timestamps, Base):
    """One machine-organised view of one consultation's authorised information.

    Rows are append-only: each real generation adds one, so the history of what a
    doctor was shown survives for audit. "Current" is the newest row for the
    consultation.

    The summary is never authoritative. It reorganises information the doctor is
    already entitled to read, every item points back at the source it came from,
    and the originals stay exactly where they were. Nothing here is a clinical
    conclusion, and the stored payload cannot express one.

    `source_bundle_hash` is the sha256 of the canonical form of the authorised
    source bundle. Staleness is not stored — it is this hash compared against a
    freshly built one (D-054), because shared records are live references (D-006)
    and a stored flag would silently go wrong the moment a patient edited one.
    """

    __tablename__ = "consultation_summaries"
    __table_args__ = (
        sa.Index("ix_consultation_summaries_consultation_created", "consultation_id", "created_at"),
        sa.Index("ix_consultation_summaries_bundle", "consultation_id", "source_bundle_hash"),
    )

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The doctor who asked for it. A summary is generated for one reader.
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False
    )
    #: The provider run behind it. Null while generating, and after a failure
    #: that never reached the provider.
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("ai_artifacts.id", ondelete="SET NULL")
    )

    source_bundle_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64))
    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    model: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    status: Mapped[SummaryStatus] = mapped_column(
        enum_column(SummaryStatus, "summary_status"),
        nullable=False,
        default=SummaryStatus.GENERATING,
        server_default=SummaryStatus.GENERATING.value,
    )
    #: Language the organised statements are written in. Originals keep their own.
    language: Mapped[LanguageCode] = mapped_column(
        enum_column(LanguageCode, "summary_language"),
        nullable=False,
        default=LanguageCode.EN,
        server_default=LanguageCode.EN.value,
    )

    #: The validated payload: sections, items, resolved sources. Empty until ready.
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    #: How many items validation removed. Shown to the doctor rather than hidden,
    #: so a thinned summary never looks like a complete one.
    dropped_item_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    warnings: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(sa.String(64))
    generated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    @property
    def is_ready(self) -> bool:
        return self.status == SummaryStatus.READY
