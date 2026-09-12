import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import ConsultationStatus, Sex, UserRole
from app.schemas.common import ORMModel
from app.schemas.doctor import DoctorPublicOut
from app.schemas.document import MedicalDocumentOut
from app.schemas.patient import MedicalRecordOut

ItemText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


# ---------- sharing ----------


class ShareSelection(BaseModel):
    """What the patient chose to share with this doctor. Item-level, explicit."""

    current_problem_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    medical_record_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    consultation_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    prescription_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class ConsultationRequestCreate(BaseModel):
    doctor_id: uuid.UUID
    share: ShareSelection
    request_message: str | None = Field(default=None, max_length=2000)
    request_language: LanguageCode | None = None


# ---------- messages ----------


class MessageCreate(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    language: LanguageCode | None = None


class MessageOut(ORMModel):
    id: uuid.UUID
    sender_role: UserRole
    body: str
    language: LanguageCode | None
    created_at: datetime


# ---------- prescriptions ----------


class PrescriptionItemIn(BaseModel):
    medication: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    dosage: ItemText
    frequency: ItemText
    duration: ItemText
    instructions: str | None = Field(default=None, max_length=1000)


class PrescriptionCreate(BaseModel):
    items: list[PrescriptionItemIn] = Field(min_length=1, max_length=30)
    instructions: str | None = Field(default=None, max_length=4000)


class PrescriptionItemOut(ORMModel):
    position: int
    medication: str
    dosage: str
    frequency: str
    duration: str
    instructions: str | None


class DoctorAttribution(BaseModel):
    id: uuid.UUID
    name: str
    specialization: str
    registration_identifier: str


class PrescriptionOut(BaseModel):
    id: uuid.UUID
    consultation_id: uuid.UUID
    authored_by: DoctorAttribution
    authorship: str = "doctor"  # always doctor-authored; no AI path exists
    instructions: str | None
    items: list[PrescriptionItemOut]
    created_at: datetime


# ---------- consultations ----------


class AssessmentUpdate(BaseModel):
    doctor_assessment: str = Field(max_length=10000)


class DeclineRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ConsultationSummary(BaseModel):
    id: uuid.UUID
    status: ConsultationStatus
    doctor: DoctorAttribution
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    prescription_count: int


class SharedItemRef(BaseModel):
    item_type: str
    item_id: uuid.UUID


class PatientConsultationDetail(BaseModel):
    id: uuid.UUID
    status: ConsultationStatus
    doctor: DoctorPublicOut
    request_message: str | None
    request_language: LanguageCode | None
    doctor_assessment: str | None
    created_at: datetime
    accepted_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    shared_items: list[SharedItemRef]
    shared_categories: list[str]
    messages: list[MessageOut]
    prescriptions: list[PrescriptionOut]


# ---------- doctor case view ----------


class PatientIdentityOut(BaseModel):
    """Minimum identity a doctor sees for any consultation addressed to them."""

    id: uuid.UUID
    display_name: str
    age: int | None
    sex: Sex
    preferred_language: LanguageCode


class SharedConsultationOut(BaseModel):
    """An earlier consultation the patient chose to share — another doctor's opinion."""

    id: uuid.UUID
    status: ConsultationStatus
    doctor: DoctorAttribution
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    doctor_assessment: str | None


class AIFactSummary(BaseModel):
    """One machine-extracted item, as shown to a doctor."""

    category: str
    #: self | family | other | unknown — a relative's condition is not the patient's.
    subject: str
    subject_evidence: str | None
    value: str
    original_text: str | None
    evidence_quote: str
    validation_status: str
    review_state: str
    evidence_page_number: int | None = None
    evidence_bbox: list[float] | None = None


class AIRecordInsight(BaseModel):
    """Machine interpretation of one shared record: never replaces the original.

    Carries all three layers so a clinician can compare them side by side.
    """

    record_id: uuid.UUID
    status: str
    original_text: str | None = None
    normalization_check: dict | None = None
    detected_language: LanguageCode | None
    normalized_english: str | None
    unparsed: list[str] = Field(default_factory=list)
    provider: str | None
    model: str | None
    generated_at: datetime | None
    facts: list[AIFactSummary] = Field(default_factory=list)


class DocumentPageInsight(BaseModel):
    """What was read from one page of a shared document, and what was extracted."""

    page_number: int
    method: str
    engine: str
    confidence: float | None
    text: str
    blocks: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_language: LanguageCode | None = None
    ai_status: str
    normalized_english: str | None = None
    normalization_check: dict | None = None
    facts: list[AIFactSummary] = Field(default_factory=list)


class DocumentInsight(BaseModel):
    """Machine reading of a shared document. The original file stays the primary record."""

    document_id: uuid.UUID
    extraction_status: str
    error_code: str | None
    page_count: int
    pages_processed: int
    truncated: bool
    methods: list[str]
    engines: list[str]
    processed_at: datetime | None
    pages: list[DocumentPageInsight] = Field(default_factory=list)


class DoctorQueueItem(BaseModel):
    id: uuid.UUID
    status: ConsultationStatus
    patient: PatientIdentityOut
    current_problem_excerpt: str | None  # only if the patient shared a current problem
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class CaseView(BaseModel):
    id: uuid.UUID
    status: ConsultationStatus
    patient: PatientIdentityOut
    request_message: str | None
    request_language: LanguageCode | None
    doctor_assessment: str | None
    created_at: datetime
    accepted_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    shared_categories: list[str]
    current_problems: list[MedicalRecordOut]
    medical_history: list[MedicalRecordOut]
    documents: list[MedicalDocumentOut]
    shared_consultations: list[SharedConsultationOut]
    shared_prescriptions: list[PrescriptionOut]
    own_previous_consultations: list[SharedConsultationOut]
    messages: list[MessageOut]
    prescriptions: list[PrescriptionOut]
    # Machine-generated, shown beside the original — never instead of it.
    ai_insights: list[AIRecordInsight] = Field(default_factory=list)
    # Machine reading of shared documents, page by page, with evidence positions.
    document_insights: list[DocumentInsight] = Field(default_factory=list)


class PatientDashboard(BaseModel):
    display_name: str
    preferred_language: LanguageCode
    date_of_birth: date | None
    age: int | None
    latest_current_problem: MedicalRecordOut | None
    conditions: list[MedicalRecordOut]
    allergies: list[MedicalRecordOut]
    medications: list[MedicalRecordOut]
    recent_documents: list[MedicalDocumentOut]
    open_consultations: list[ConsultationSummary]
    recent_prescriptions: list[PrescriptionOut]
