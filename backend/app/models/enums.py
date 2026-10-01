from enum import StrEnum


class UserRole(StrEnum):
    """Every role an account can hold, across both products (D-078).

    One enumeration because `users` is one shared table. Which roles a running
    application accepts is decided by its product (`app.core.product_config`):
    CareBridge accepts patient, doctor and admin; IP-SAKTI Sahayak accepts user,
    facilitator, curator and admin. An account whose role its product does not
    accept cannot sign in to it.
    """

    # CareBridge (PRODUCT=carebridge)
    PATIENT = "patient"
    DOCTOR = "doctor"
    # Both products
    ADMIN = "admin"
    # IP-SAKTI Sahayak (PRODUCT=ip_sakti)
    USER = "user"
    FACILITATOR = "facilitator"
    CURATOR = "curator"


class CareBridgeRole(StrEnum):
    """The roles CareBridge's own tables record — who sent a consultation
    message, who cancelled a consultation.

    Kept apart from `UserRole` so that widening the shared role vocabulary for
    IP-SAKTI leaves these healthcare tables' CHECK constraints exactly as
    migration 0001 created them (D-078). The values equal `UserRole`'s, so a
    `UserRole` member can be stored here directly.
    """

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
    # Phase 4. Organises already-authorised information for one consultation;
    # it interprets nothing and produces no clinical conclusion.
    CASE_SUMMARY = "case_summary"


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


class SummaryStatus(StrEnum):
    """Stored lifecycle of a case summary.

    Two states the UI shows are deliberately *not* stored: `not_generated` is the
    absence of a row, and `stale` is computed by re-hashing the source bundle at
    read time (D-054). A stored staleness flag would be wrong the moment a
    patient edited a shared record, and nothing would be watching to correct it.
    """

    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class SummarySectionKind(StrEnum):
    """The only sections a case summary may contain.

    There is no diagnosis, differential, triage, risk or treatment member, and
    adding one would be a schema change reviewed like any other. The model
    chooses among these; it cannot invent a thirteenth.
    """

    CURRENT_PROBLEM = "current_problem"
    SYMPTOM = "symptom"
    DURATION = "duration"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    MEDICAL_HISTORY = "medical_history"
    MEASUREMENT = "measurement"
    DOCUMENT = "document"
    PRIOR_CONSULTATION = "prior_consultation"
    PATIENT_STATEMENT = "patient_statement"
    DOCTOR_AUTHORED_CONTEXT = "doctor_authored_context"
    UNRESOLVED_INFORMATION = "unresolved_information"


class SummaryItemOrigin(StrEnum):
    """Who asserted a summary item.

    There is deliberately no machine origin (D-053): the model groups, orders and
    de-duplicates, but every health claim in a summary traces to a human — the
    patient's own words, a fact the patient confirmed, or a doctor's authorship.
    The application sets this from the source; the model is never asked for it.
    """

    PATIENT_PROVIDED = "patient_provided"
    PATIENT_CONFIRMED = "patient_confirmed"
    DOCTOR_AUTHORED = "doctor_authored"


class BundleItemKind(StrEnum):
    """What one authorised source item in a case-summary bundle is.

    Not a database column — the bundle lives in JSON — but an enum so the builder
    and the validator cannot disagree about the vocabulary.
    """

    PATIENT_STATEMENT = "patient_statement"
    CURRENT_PROBLEM = "current_problem"
    HEALTH_RECORD = "health_record"
    FACT = "fact"
    DOCUMENT = "document"
    PRIOR_CONSULTATION = "prior_consultation"
    PRIOR_PRESCRIPTION = "prior_prescription"


class AuthorizationBasis(StrEnum):
    """Why this doctor may see this item.

    Both bases are authorised; keeping them apart makes the reason auditable and
    lets the interface say which is which (Stage A decision 1).
    """

    #: The patient selected this item when requesting the consultation.
    PATIENT_GRANT = "patient_grant"
    #: This doctor's own earlier consultation with the patient (D-009).
    OWN_PRIOR_CONSULTATION = "own_prior_consultation"


class ConversationStatus(StrEnum):
    """Where a history conversation stands.

    `not_started` is deliberately not stored: a patient with no session simply
    has no row, the same reasoning as D-054. `active` is not stored either — it
    is exactly "awaiting_answer or awaiting_confirmation", and a state that is
    the union of two others is a second place for the truth to live.
    """

    #: A question has been put to the patient and the engine is waiting.
    AWAITING_ANSWER = "awaiting_answer"
    #: Every question in the flow is answered; the patient is reviewing what
    #: their answers produced before any of it counts.
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PAUSED = "paused"
    COMPLETED = "completed"
    #: Abandoned by the patient, or superseded. Never deleted: the answers
    #: already given are still the patient's own words.
    ABANDONED = "abandoned"


class ResponseType(StrEnum):
    """The controlled vocabulary of answer shapes.

    Deliberately small: only what the first flow actually asks for. A future
    speech answer maps onto these same types rather than adding a new one, so
    voice does not become a parallel data model.
    """

    FREE_TEXT = "free_text"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    YES_NO = "yes_no"
    DURATION = "duration"


class ConversationSection(StrEnum):
    """The history taxonomy the flows walk.

    General-purpose symptom history. Not specialty-specific, and not a
    diagnostic tree: these are the things a clinician would ask anyone about a
    new complaint, in the order they would usually ask them. Engineering draft;
    not clinically reviewed.

    Values are only ever added. A section a published flow uses stays, because
    answers recorded under that flow still carry it.
    """

    CURRENT_PROBLEM = "current_problem"
    ONSET_DURATION = "onset_duration"
    LOCATION = "location"
    CHARACTER = "character"
    #: history_general v2.
    RADIATION_OR_SPREAD = "radiation_or_spread"
    ASSOCIATED_SYMPTOMS = "associated_symptoms"
    #: history_general v1 only. v2 asks the two separately.
    AGGRAVATING_RELIEVING = "aggravating_relieving"
    #: history_general v2.
    AGGRAVATING_FACTORS = "aggravating_factors"
    #: history_general v2.
    RELIEVING_FACTORS = "relieving_factors"
    RELEVANT_HISTORY = "relevant_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    REVIEW = "review"


# ---------------------------------------------------------------------------
# IP-SAKTI Sahayak — the legal and regulatory source corpus (Phase 2, D-081+)
# ---------------------------------------------------------------------------


class CorpusLane(StrEnum):
    """Which body of law a corpus record belongs to. Exactly one, always (D-082).

    The lanes never mix: an Indian rule is never an international text, and a
    record never changes lane. Later answers draw on one lane at a time.
    """

    INDIA = "india"
    INTERNATIONAL = "international"


class SourceAuthority(StrEnum):
    """The official sources a curator may upload from (D-083).

    An explicit list, not a free-text field: a source outside it cannot enter
    the corpus at all. Adding one is a reviewed code change. Whether each
    source's terms allow reuse has not been verified (see `TermsStatus`).
    """

    INDIA_CODE = "india_code"
    E_GAZETTE = "e_gazette"
    IP_INDIA = "ip_india"
    NBA = "nba"  # National Biodiversity Authority
    FSSAI = "fssai"
    WIPO_LEX = "wipo_lex"


class InstrumentType(StrEnum):
    """What kind of instrument a source sets out. A description, not a ruling."""

    ACT = "act"
    RULES = "rules"
    REGULATIONS = "regulations"
    NOTIFICATION = "notification"
    TREATY = "treaty"
    PROTOCOL = "protocol"
    DIRECTIVE = "directive"
    OTHER = "other"


class CorpusDocumentType(StrEnum):
    """What form of the instrument's text a source document is."""

    ORIGINAL_TEXT = "original_text"
    CONSOLIDATED_TEXT = "consolidated_text"
    AMENDMENT = "amendment"
    NOTIFICATION = "notification"
    OTHER = "other"


class LocatorType(StrEnum):
    """How the source itself labels a provision. No numbering scheme is assumed:
    the locator is copied as the source prints it, and this only says what kind
    of label it is."""

    SECTION = "section"
    SUBSECTION = "subsection"
    CLAUSE = "clause"
    RULE = "rule"
    REGULATION = "regulation"
    ARTICLE = "article"
    PARAGRAPH = "paragraph"
    SCHEDULE = "schedule"
    ITEM = "item"
    OTHER = "other"


class IngestionState(StrEnum):
    """How reading a source document went. Separate from whether it is approved.

    `needs_review`: text was read, but some of it is machine transcription (OCR)
    or some pages yielded nothing, so a curator must check it against the
    original before it can be approved. `failed`: nothing usable was read.
    """

    UPLOADED = "uploaded"
    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class CorpusReviewState(StrEnum):
    """The curator workflow, shared by source documents and provision versions.

    draft → under_review → approved | rejected. Nothing else. Approved and
    rejected are final: an approved text is never edited, and a correction is a
    new version (D-084).
    """

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class TermsStatus(StrEnum):
    """Whether a source's reuse and redistribution terms have been checked.

    Phase 2 records only `unknown`: no source's terms have been verified, and
    nothing may claim that redistribution is permitted. The other values exist
    so that a verification recorded later has somewhere to go.
    """

    UNKNOWN = "unknown"
    VERIFIED_PERMITTED = "verified_permitted"
    VERIFIED_RESTRICTED = "verified_restricted"


class ProvisionStatus(StrEnum):
    """What a curator records that a cited source says about an approved version.

    The smallest vocabulary the project specification names (D-085): the build
    brief's "in force, stayed or omitted" and the Phase 2 brief's list. Each is
    a record of what a source states, with that source attached — never the
    system's own conclusion about the law. What each value implies for an
    answer "as on" a date is not decided yet (migration plan Q7).
    """

    IN_FORCE = "in_force"
    NOT_YET_IN_FORCE = "not_yet_in_force"
    AMENDED = "amended"
    SUPERSEDED = "superseded"
    STAYED = "stayed"
    OMITTED = "omitted"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"
