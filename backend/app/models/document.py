from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import LanguageCode
from app.db.base import Base, JSONType, UUIDPrimaryKey, enum_column, utcnow
from app.models.enums import DocumentExtractionStatus


class DocumentExtraction(UUIDPrimaryKey, Base):
    """One reading of one uploaded document.

    The uploaded file is never modified; `source_sha256` records the exact bytes
    that were read, so an extraction can be proven to belong to that file.
    """

    __tablename__ = "document_extractions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[DocumentExtractionStatus] = mapped_column(
        enum_column(DocumentExtractionStatus, "document_extraction_status"), nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(sa.String(64))
    source_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)  # pages in the file
    pages_processed: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    methods: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    engines: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )


class DocumentPage(UUIDPrimaryKey, Base):
    """The text read from one page, verbatim, with where each line sits.

    Identity is (document, page number, text hash): re-reading the same file
    with the same method yields the same row, so facts and the patient's
    decisions about them stay attached. If a re-read produces different text,
    the old row is superseded and a new one is created — different text is
    different evidence.
    """

    __tablename__ = "document_pages"
    __table_args__ = (
        sa.UniqueConstraint("document_id", "page_number", "text_sha256", name="uq_document_page_text"),
        sa.Index("ix_document_pages_document_current", "document_id", "superseded_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("patient_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The extraction that first produced this text.
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("document_extractions.id", ondelete="SET NULL")
    )
    page_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1-based
    text: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    text_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    method: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # pdf_text_layer | ocr | vision_provider | none
    engine: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    confidence: Mapped[float | None] = mapped_column(sa.Float)  # None when the text is exact
    width: Mapped[float | None] = mapped_column(sa.Float)
    height: Mapped[float | None] = mapped_column(sa.Float)
    # [{text, bbox: [x0, y0, x1, y1] as page fractions, char_start, char_end, confidence}]
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    detected_language: Mapped[LanguageCode | None] = mapped_column(enum_column(LanguageCode, "page_language"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow, server_default=sa.func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    extraction: Mapped[DocumentExtraction | None] = relationship()
