"""Shapes of the legal source corpus API (Phase 2).

Two rules shape every model here. No response carries `storage_reference` or
any filesystem path: the original file is reachable only through its own
endpoint, after an integrity check. And no request carries legal text: provision
text is always cut from a parsed source by offsets, so there is no field a
client could put statutory wording into.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import (
    CorpusDocumentType,
    CorpusLane,
    CorpusReviewState,
    IngestionState,
    InstrumentType,
    LocatorType,
    ProvisionStatus,
    SourceAuthority,
    TermsStatus,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Issuer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Locator = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- references ----------


class UserRef(BaseModel):
    id: uuid.UUID
    email: str


class AuthorityOut(BaseModel):
    code: SourceAuthority
    name: str
    lane: CorpusLane
    terms_status: TermsStatus


class InstrumentRef(BaseModel):
    id: uuid.UUID
    title: str
    instrument_type: InstrumentType
    lane: CorpusLane


class ProvisionRef(BaseModel):
    id: uuid.UUID
    locator: str
    locator_type: LocatorType


class SourceRef(BaseModel):
    id: uuid.UUID
    title: str
    source_authority: SourceAuthority
    review_state: CorpusReviewState
    sha256: str


# ---------- instruments and provisions ----------


class InstrumentCreate(_Strict):
    lane: CorpusLane
    instrument_type: InstrumentType
    title: Title
    issued_by: Issuer
    description: Note | None = None


class ProvisionCreate(_Strict):
    locator: Locator
    locator_type: LocatorType


class VersionSummary(BaseModel):
    id: uuid.UUID
    lane: CorpusLane
    provision: ProvisionRef
    instrument: InstrumentRef
    source_id: uuid.UUID
    #: A version can be approved only once this is `approved`.
    source_review_state: CorpusReviewState
    version_number: int
    review_state: CorpusReviewState
    valid_from: date | None
    valid_to: date | None
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    ocr_derived: bool
    text_sha256: str
    created_at: datetime
    approved_at: datetime | None
    latest_status: ProvisionStatus | None = None


class ProvisionOut(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    lane: CorpusLane
    locator: str
    locator_type: LocatorType
    created_at: datetime
    versions: list[VersionSummary] = []


class InstrumentOut(BaseModel):
    id: uuid.UUID
    lane: CorpusLane
    instrument_type: InstrumentType
    title: str
    issued_by: str
    description: str | None
    created_at: datetime


class SourceSummary(BaseModel):
    id: uuid.UUID
    lane: CorpusLane
    title: str
    instrument: InstrumentRef
    source_authority: SourceAuthority
    authority_name: str
    document_type: CorpusDocumentType
    source_date: date | None
    retrieved_on: date
    terms_status: TermsStatus
    ingestion_state: IngestionState
    ingestion_issues: list[str]
    review_state: CorpusReviewState
    page_count: int | None
    #: The file's checksum: an approval must name it.
    sha256: str
    created_at: datetime
    approved_at: datetime | None


class InstrumentDetail(InstrumentOut):
    provisions: list[ProvisionOut]
    sources: list[SourceSummary]


# ---------- sources ----------


class SourceDetail(SourceSummary):
    source_url: str | None
    source_reference: str | None
    file_name: str
    mime_type: str
    size_bytes: int
    text_sha256: str | None
    text_length: int | None
    parse_error_code: str | None
    extraction_methods: list[str]
    extraction_engines: list[str]
    parsed_at: datetime | None
    uploaded_by: UserRef
    submitted_at: datetime | None
    approved_by: UserRef | None
    issues_acknowledged: bool
    rejected_at: datetime | None
    rejected_by: UserRef | None
    rejection_reason: str | None
    versions: list[VersionSummary]


class PageOut(BaseModel):
    page_number: int
    char_start: int
    char_end: int
    text: str
    method: str
    engine: str
    confidence: float | None
    warnings: list[str]


class ChunkOut(BaseModel):
    ordinal: int
    page_number: int
    char_start: int
    char_end: int


class SourceText(BaseModel):
    source_id: uuid.UUID
    text_sha256: str
    text_length: int
    pages: list[PageOut]
    chunks: list[ChunkOut]


class ApproveSource(_Strict):
    #: The checksum of the file the curator reviewed.
    expected_sha256: Sha256
    acknowledge_issues: bool = False


class Reject(_Strict):
    reason: Reason


# ---------- versions ----------


class VersionCreate(_Strict):
    provision_id: uuid.UUID
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    valid_from: date | None = None
    valid_to: date | None = None


class VersionUpdate(_Strict):
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, gt=0)
    valid_from: date | None = None
    valid_to: date | None = None


class ApproveVersion(_Strict):
    #: The checksum of the text the curator reviewed.
    expected_text_sha256: Sha256
    acknowledge_issues: bool = False


class StatusEventCreate(_Strict):
    status: ProvisionStatus
    effective_date: date | None = None
    basis_source_id: uuid.UUID | None = None
    basis_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    note: Note | None = None


class StatusEventOut(BaseModel):
    id: uuid.UUID
    status: ProvisionStatus
    effective_date: date | None
    basis_source: SourceRef | None
    basis_reference: str | None
    note: str | None
    recorded_by: UserRef
    recorded_at: datetime


class VersionDetail(VersionSummary):
    text: str
    source: SourceRef
    issues_acknowledged: bool
    approved_by: UserRef | None
    rejected_at: datetime | None
    rejected_by: UserRef | None
    rejection_reason: str | None
    status_events: list[StatusEventOut]


# ---------- diff and queues ----------


class DiffBaseline(BaseModel):
    kind: Literal["source", "version"]
    id: uuid.UUID
    label: str
    approved_at: datetime | None


class DiffOut(BaseModel):
    baseline: DiffBaseline | None
    stats: dict[str, int]
    blocks: list[dict[str, Any]]


class ReviewQueue(BaseModel):
    sources: list[SourceSummary]
    versions: list[VersionSummary]
