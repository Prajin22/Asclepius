import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactReviewState, FactSubject, FactValidation
from app.schemas.common import ORMModel


class NormalizationCheckOut(BaseModel):
    """Whether the English rendering still means what the original said."""

    status: str  # "ok" | "review"
    added_terms: list[str] = Field(default_factory=list)
    dropped_facts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AIUsageOut(BaseModel):
    """This patient's position against their AI budget."""

    runs_last_hour: int
    runs_last_day: int
    spend_last_day_usd: float
    limit_per_hour: int
    limit_per_day: int
    daily_cost_limit_usd: float


class AIConsentUpdate(BaseModel):
    granted: bool


class AIFactOut(ORMModel):
    id: uuid.UUID
    source_type: str = "medical_record"
    #: Documents: the document and page the evidence is on, and its region [x0, y0, x1, y1] as page fractions.
    evidence_document_id: uuid.UUID | None = None
    evidence_page_number: int | None = None
    evidence_bbox: list[float] | None = None
    category: FactCategory
    #: Whose health this describes. Family facts never become the patient's own
    #: allergy or medication.
    subject: FactSubject
    subject_evidence: str | None
    value: str
    effective_value: str
    original_text: str | None
    evidence_quote: str  # exactly as the provider supplied it
    #: Where the application found the quote in the source (never the provider's offsets).
    evidence_start: int | None
    evidence_end: int | None
    confidence: float | None
    validation_status: FactValidation
    validation_note: str | None
    review_state: FactReviewState
    edited_value: str | None
    reviewed_at: datetime | None
    medical_record_id: uuid.UUID | None


class AIRunOut(BaseModel):
    """Provenance of one pipeline run over one source."""

    artifact_id: uuid.UUID | None = None
    operation: str
    provider: str
    model: str
    prompt_version: str | None = None
    status: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cached: bool = False
    created_at: datetime | None = None


class AIProcessingOut(BaseModel):
    """All three layers of one record, so any of them can be inspected.

    Layer 1 `original_text` (source of truth, never modified)
    Layer 2 `normalized_english` (machine working representation)
    Layer 3 `facts` (structured, each with evidence back into layer 1)
    """

    record_id: uuid.UUID
    status: Literal["ok", "unavailable", "not_processed"]
    error_code: str | None = None
    original_text: str | None = None
    normalization_check: NormalizationCheckOut | None = None
    usage: AIUsageOut | None = None
    detected_language: LanguageCode | None = None
    language_confidence: float | None = None
    normalized_english: str | None = None
    unparsed: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    facts: list[AIFactOut] = Field(default_factory=list)
    runs: list[AIRunOut] = Field(default_factory=list)
    generated_at: datetime | None = None
    provider: str | None = None
    model: str | None = None
    is_external_provider: bool | None = None


class AIFactAction(BaseModel):
    action: Literal["confirm", "edit", "reject"]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None = None


class AIArtifactOut(ORMModel):
    id: uuid.UUID
    artifact_type: str
    provider: str
    model: str
    prompt_version: str | None
    status: str
    input_language: LanguageCode | None
    output_language: LanguageCode | None
    content: dict
    confidence: float | None
    error_code: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    source_references: list[dict]
    created_at: datetime


class AIStatusOut(BaseModel):
    """Public, credential-free description of the AI configuration."""

    provider: str
    model: str
    demo_mode: bool
    is_external: bool
    enabled_features: list[str]
    prompt_versions: dict[str, str]
