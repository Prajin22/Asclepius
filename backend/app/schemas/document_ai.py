"""Phase 3 API schemas: a document, what was read from it, and what was extracted."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.languages import LanguageCode
from app.models.enums import DocumentExtractionStatus, DocumentStatus
from app.schemas.ai import AIFactOut, AIRunOut, AIUsageOut, NormalizationCheckOut
from app.schemas.common import ORMModel


class DocumentExtractionOut(ORMModel):
    id: uuid.UUID
    status: DocumentExtractionStatus
    error_code: str | None
    source_sha256: str
    page_count: int
    pages_processed: int
    truncated: bool
    methods: list[str]
    engines: list[str]
    warnings: list[str]
    latency_ms: int | None
    created_at: datetime


class TextBlockOut(BaseModel):
    text: str
    bbox: list[float]
    char_start: int
    char_end: int
    confidence: float | None = None


class DocumentPageOut(BaseModel):
    """One page: the machine-read text (with positions), its English, and its facts."""

    page_id: uuid.UUID
    page_number: int
    # How the text was obtained. pdf_text_layer is exact; ocr/vision_provider are transcriptions.
    method: str
    engine: str
    confidence: float | None
    width: float | None
    height: float | None
    text: str
    blocks: list[TextBlockOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_language: LanguageCode | None = None
    ai_status: Literal["ok", "unavailable", "not_processed"]
    ai_error_code: str | None = None
    normalized_english: str | None = None
    unparsed: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    normalization_check: NormalizationCheckOut | None = None
    facts: list[AIFactOut] = Field(default_factory=list)
    runs: list[AIRunOut] = Field(default_factory=list)
    generated_at: datetime | None = None


class DocumentProcessingOut(BaseModel):
    document_id: uuid.UUID
    document_status: DocumentStatus
    status: Literal["processed", "failed", "not_processed"]
    error_code: str | None = None
    extraction: DocumentExtractionOut | None = None
    pages: list[DocumentPageOut] = Field(default_factory=list)
    usage: AIUsageOut | None = None
    provider: str | None = None
    model: str | None = None
    is_external_provider: bool | None = None
