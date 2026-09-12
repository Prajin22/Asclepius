from enum import StrEnum


class UserRole(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class DoctorApproval(StrEnum):
    """Where a doctor's application stands.

    Only an approved doctor appears in the directory, receives consultations or
    sees any patient information. An admin checks the registration number by
    hand; nothing here queries a medical council register.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    UNDISCLOSED = "undisclosed"


class RecordType(StrEnum):
    CONDITION = "condition"
    ALLERGY = "allergy"
    MEDICATION = "medication"
    HISTORY_NOTE = "history_note"
    CURRENT_PROBLEM = "current_problem"
    # Something a relative has. Never the patient's own condition.
    FAMILY_HISTORY = "family_history"


class RecordSource(StrEnum):
    """Who asserted this information. Shown to users on every record."""

    PATIENT = "patient"
    AI_EXTRACTED = "ai_extracted"
    DOCTOR = "doctor"


class RecordStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class DocumentType(StrEnum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    SCAN = "scan"
    OTHER = "other"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"  # stored; processing arrives in Phase 3
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ConsultationStatus(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ShareItemType(StrEnum):
    MEDICAL_RECORD = "medical_record"
    DOCUMENT = "document"
    CONSULTATION = "consultation"
    PRESCRIPTION = "prescription"


class AIReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AIOperation(StrEnum):
    """One step of the AI pipeline. Stored as `ai_artifacts.artifact_type`."""

    LANGUAGE_DETECTION = "language_detection"
    NORMALIZATION = "normalization"
    EXTRACTION = "extraction"


class AIArtifactStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class FactCategory(StrEnum):
    """Categories the extractor may produce. Deliberately excludes diagnosis."""

    SYMPTOM = "symptom"
    DURATION = "duration"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    MEDICAL_HISTORY = "medical_history"
    MEASUREMENT = "measurement"


class FactValidation(StrEnum):
    """Result of checking the fact's evidence against the original source."""

    VALIDATED = "validated"  # evidence quote found in the source
    NEEDS_REVIEW = "needs_review"  # evidence weak/ambiguous — never auto-trusted
    UNSUPPORTED = "unsupported"  # evidence not in the source; rejected


class FactReviewState(StrEnum):
    """What the patient decided about an AI-extracted fact."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    REJECTED = "rejected"


class DocumentExtractionStatus(StrEnum):
    """Outcome of reading a document (not of interpreting it)."""

    SUCCEEDED = "succeeded"  # every processed page produced text
    PARTIAL = "partial"  # some pages unreadable, or the page limit was reached
    FAILED = "failed"  # nothing could be read


class FactSubject(StrEnum):
    """Whose health a fact describes.

    Getting this wrong is a clinical safety problem: a relative's diabetes must
    never land in the patient's own history, and a relative's drug allergy must
    never become the patient's allergy.
    """

    SELF = "self"  # the patient
    FAMILY = "family"  # a named relative
    OTHER = "other"  # someone else (friend, colleague)
    UNKNOWN = "unknown"
