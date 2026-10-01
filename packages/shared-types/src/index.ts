/**
 * API DTO types — a hand-written mirror of backend/app/schemas.
 * Keep in sync with the Pydantic models (Phase 9: generate from OpenAPI).
 */

export type UUID = string;
export type ISODateTime = string;
export type ISODate = string;

// ---------- enums ----------

/** Which product a build serves. Mirror of backend/app/core/product.py (D-077). */
export const PRODUCTS = ["carebridge", "ip_sakti"] as const;
export type Product = (typeof PRODUCTS)[number];

/** CareBridge's roles. */
export type CareBridgeRole = "patient" | "doctor" | "admin";
/** IP-SAKTI Sahayak's roles. `admin` belongs to both products (D-078). */
export type SaktiRole = "user" | "facilitator" | "curator" | "admin";
/** Every role an account can hold. Which ones a product accepts: ROLES_BY_PRODUCT. */
export type Role = CareBridgeRole | SaktiRole;

/** Mirror of backend/app/core/product_config.py. */
export const ROLES_BY_PRODUCT = {
  carebridge: ["patient", "doctor", "admin"],
  ip_sakti: ["user", "facilitator", "curator", "admin"],
} as const satisfies Record<Product, readonly Role[]>;

export function isProduct(value: unknown): value is Product {
  return typeof value === "string" && (PRODUCTS as readonly string[]).includes(value);
}

/** GET /meta/product — which product the API serves. */
export interface ProductInfo {
  product: Product;
  display_name: string;
  roles: Role[];
  demo_mode: boolean;
  ai_policy: { id: string; document: string; rules: string[]; capabilities: string[] };
}

export const LANGUAGE_CODES = ["en", "hi", "ta", "te", "kn", "ml", "mr", "bn", "gu", "pa", "or", "as"] as const;
export type LanguageCode = (typeof LANGUAGE_CODES)[number];

export interface LanguageInfo {
  code: LanguageCode;
  englishName: string;
  /** Autonym — shown as-is in every UI language. */
  nativeName: string;
  /** Whether the interface itself is translated into this language. */
  uiAvailable: boolean;
}

/** Mirror of backend/app/core/languages.py. */
export const LANGUAGES: readonly LanguageInfo[] = [
  { code: "en", englishName: "English", nativeName: "English", uiAvailable: true },
  { code: "hi", englishName: "Hindi", nativeName: "हिन्दी", uiAvailable: true },
  { code: "ta", englishName: "Tamil", nativeName: "தமிழ்", uiAvailable: true },
  { code: "te", englishName: "Telugu", nativeName: "తెలుగు", uiAvailable: false },
  { code: "kn", englishName: "Kannada", nativeName: "ಕನ್ನಡ", uiAvailable: false },
  { code: "ml", englishName: "Malayalam", nativeName: "മലയാളം", uiAvailable: false },
  { code: "mr", englishName: "Marathi", nativeName: "मराठी", uiAvailable: false },
  { code: "bn", englishName: "Bengali", nativeName: "বাংলা", uiAvailable: false },
  { code: "gu", englishName: "Gujarati", nativeName: "ગુજરાતી", uiAvailable: false },
  { code: "pa", englishName: "Punjabi", nativeName: "ਪੰਜਾਬੀ", uiAvailable: false },
  { code: "or", englishName: "Odia", nativeName: "ଓଡ଼ିଆ", uiAvailable: false },
  { code: "as", englishName: "Assamese", nativeName: "অসমীয়া", uiAvailable: false },
];

export const UI_LANGUAGES: readonly LanguageCode[] = LANGUAGES.filter((l) => l.uiAvailable).map((l) => l.code);

export function languageInfo(code: LanguageCode | null | undefined): LanguageInfo | undefined {
  return LANGUAGES.find((l) => l.code === code);
}

export function isLanguageCode(value: unknown): value is LanguageCode {
  return typeof value === "string" && (LANGUAGE_CODES as readonly string[]).includes(value);
}

export const SEX_VALUES = ["female", "male", "other", "undisclosed"] as const;
export type Sex = (typeof SEX_VALUES)[number];

export const RECORD_TYPES = [
  "condition",
  "allergy",
  "medication",
  "history_note",
  "current_problem",
  "family_history",
] as const;
export type RecordType = (typeof RECORD_TYPES)[number];
export type RecordSource = "patient" | "ai_extracted" | "doctor";
export const RECORD_SOURCES: readonly RecordSource[] = ["patient", "ai_extracted", "doctor"];
export type RecordStatus = "active" | "resolved";

export const DOCUMENT_TYPES = ["prescription", "lab_report", "discharge_summary", "scan", "other"] as const;
export type DocumentType = (typeof DOCUMENT_TYPES)[number];
export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed";

export type ConsultationStatus = "requested" | "accepted" | "active" | "completed" | "cancelled";

export const SHARE_CATEGORIES = [
  "current_problem",
  "medical_history",
  "documents",
  "previous_consultations",
  "previous_prescriptions",
] as const;
export type ShareCategory = (typeof SHARE_CATEGORIES)[number];

export const UPLOAD_ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";
export const ALLOWED_UPLOAD_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"] as const;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

// ---------- auth ----------

export interface UserOut {
  id: UUID;
  role: Role;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserOut;
}

export interface MeResponse {
  user: UserOut;
  profile_id: UUID | null;
  display_name: string | null;
  /** Doctors only: where their application stands. */
  doctor_approval: DoctorApproval | null;
}

export interface PatientRegisterRequest {
  email: string;
  password: string;
  display_name: string;
  preferred_language: LanguageCode;
}

// ---------- patient ----------

export interface PatientProfile {
  id: UUID;
  display_name: string;
  date_of_birth: ISODate | null;
  age: number | null;
  sex: Sex;
  phone: string | null;
  preferred_language: LanguageCode;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_notes: string | null;
  /** Explicit opt-in before any AI processing. Never assumed. */
  ai_processing_consent: boolean;
  ai_consent_updated_at: ISODateTime | null;
  updated_at: ISODateTime;
}

export type PatientProfileUpdate = Partial<
  Pick<
    PatientProfile,
    | "display_name"
    | "date_of_birth"
    | "sex"
    | "phone"
    | "preferred_language"
    | "emergency_contact_name"
    | "emergency_contact_phone"
    | "emergency_notes"
  >
>;

export interface MedicalRecord {
  id: UUID;
  type: RecordType;
  title: string | null;
  content: string;
  source: RecordSource;
  source_language: LanguageCode;
  status: RecordStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface MedicalRecordCreate {
  type: RecordType;
  title?: string | null;
  content?: string;
  source_language: LanguageCode;
  status?: RecordStatus;
}

export type MedicalRecordUpdate = Partial<Pick<MedicalRecord, "title" | "content" | "source_language" | "status">>;

export interface MedicalDocument {
  id: UUID;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  document_type: DocumentType;
  title: string | null;
  source_language: LanguageCode | null;
  status: DocumentStatus;
  uploaded_at: ISODateTime;
}

// ---------- doctors ----------

export interface DoctorPublic {
  id: UUID;
  name: string;
  specialization: string;
  qualification: string;
  registration_identifier: string;
  clinic_name: string | null;
  clinic_address: string | null;
  phone: string | null;
  languages: LanguageCode[];
  is_accepting_consultations: boolean;
}

export type DoctorProfileUpdate = Partial<
  Pick<
    DoctorPublic,
    "name" | "specialization" | "qualification" | "clinic_name" | "clinic_address" | "phone" | "languages" | "is_accepting_consultations"
  >
>;

/** Only an approved doctor appears in the directory or sees patient information. */
export type DoctorApproval = "pending" | "approved" | "rejected";

/** What a doctor submits for an administrator to check. */
export interface DoctorDetails {
  name: string;
  specialization: string;
  qualification: string;
  registration_identifier: string;
  clinic_name: string | null;
  clinic_address: string | null;
  phone: string | null;
  languages: LanguageCode[];
}

export interface DoctorApplication extends DoctorDetails {
  email: string;
  password: string;
}

/** A doctor's own profile, including where their application stands. */
export interface DoctorAccount extends DoctorPublic {
  approval_status: DoctorApproval;
  /** The administrator's reason when an application is not approved. */
  approval_note: string | null;
  reviewed_at: ISODateTime | null;
}

/** What an administrator reviews. */
export interface DoctorApplicationReview extends DoctorAccount {
  email: string;
  applied_at: ISODateTime;
  /** Another doctor account uses the same registration number. */
  registration_conflict: boolean;
}

export interface DoctorAttribution {
  id: UUID;
  name: string;
  specialization: string;
  registration_identifier: string;
}

// ---------- consultations ----------

export interface PrescriptionItem {
  position: number;
  medication: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string | null;
}

export interface Prescription {
  id: UUID;
  consultation_id: UUID;
  authored_by: DoctorAttribution;
  authorship: "doctor";
  instructions: string | null;
  items: PrescriptionItem[];
  created_at: ISODateTime;
}

export interface PrescriptionItemInput {
  medication: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string | null;
}

export interface PrescriptionCreate {
  items: PrescriptionItemInput[];
  instructions?: string | null;
}

export interface Message {
  id: UUID;
  sender_role: Role;
  body: string;
  language: LanguageCode | null;
  created_at: ISODateTime;
}

export interface ConsultationSummary {
  id: UUID;
  status: ConsultationStatus;
  doctor: DoctorAttribution;
  created_at: ISODateTime;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  prescription_count: number;
}

export interface SharedItemRef {
  item_type: "medical_record" | "document" | "consultation" | "prescription";
  item_id: UUID;
}

export interface PatientConsultationDetail {
  id: UUID;
  status: ConsultationStatus;
  doctor: DoctorPublic;
  request_message: string | null;
  request_language: LanguageCode | null;
  doctor_assessment: string | null;
  created_at: ISODateTime;
  accepted_at: ISODateTime | null;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  cancelled_at: ISODateTime | null;
  cancellation_reason: string | null;
  shared_items: SharedItemRef[];
  shared_categories: ShareCategory[];
  messages: Message[];
  prescriptions: Prescription[];
}

export interface ShareSelection {
  current_problem_ids: UUID[];
  medical_record_ids: UUID[];
  document_ids: UUID[];
  consultation_ids: UUID[];
  prescription_ids: UUID[];
}

export interface ConsultationRequestCreate {
  doctor_id: UUID;
  share: ShareSelection;
  request_message?: string | null;
  request_language?: LanguageCode | null;
}

export interface PatientIdentity {
  id: UUID;
  display_name: string;
  age: number | null;
  sex: Sex;
  preferred_language: LanguageCode;
}

export interface SharedConsultation {
  id: UUID;
  status: ConsultationStatus;
  doctor: DoctorAttribution;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  created_at: ISODateTime;
  doctor_assessment: string | null;
}

export interface DoctorQueueItem {
  id: UUID;
  status: ConsultationStatus;
  patient: PatientIdentity;
  current_problem_excerpt: string | null;
  created_at: ISODateTime;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
}

export interface CaseView {
  id: UUID;
  status: ConsultationStatus;
  patient: PatientIdentity;
  request_message: string | null;
  request_language: LanguageCode | null;
  doctor_assessment: string | null;
  created_at: ISODateTime;
  accepted_at: ISODateTime | null;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  shared_categories: ShareCategory[];
  current_problems: MedicalRecord[];
  medical_history: MedicalRecord[];
  documents: MedicalDocument[];
  shared_consultations: SharedConsultation[];
  shared_prescriptions: Prescription[];
  own_previous_consultations: SharedConsultation[];
  messages: Message[];
  prescriptions: Prescription[];
  /** Machine interpretation of shared records, shown beside the originals. */
  ai_insights: AIRecordInsight[];
  /** Machine reading of shared documents, page by page. The original file stays primary. */
  document_insights: DocumentInsight[];
}

// ---------- AI (Phase 2) ----------

export const FACT_CATEGORIES = [
  "symptom",
  "duration",
  "medication",
  "allergy",
  "medical_history",
  "measurement",
] as const;
export type FactCategory = (typeof FACT_CATEGORIES)[number];

/** Result of checking a fact's evidence against the original source. */
export type FactValidation = "validated" | "needs_review" | "unsupported";

/** What the patient decided about a machine-extracted fact. */
export type FactReviewState = "pending" | "confirmed" | "edited" | "rejected";

/**
 * Whose health a fact describes. A relative's condition is never the patient's,
 * and a relative's drug allergy is never the patient's allergy.
 */
export const FACT_SUBJECTS = ["self", "family", "other", "unknown"] as const;
export type FactSubject = (typeof FACT_SUBJECTS)[number];

/** Whether the English rendering still means what the original said. */
export interface NormalizationCheck {
  status: "ok" | "review";
  added_terms: string[];
  dropped_facts: string[];
  notes: string[];
}

/** Where the patient stands against their AI budget. */
export interface AIUsage {
  runs_last_hour: number;
  runs_last_day: number;
  spend_last_day_usd: number;
  limit_per_hour: number;
  limit_per_day: number;
  daily_cost_limit_usd: number;
}

export type AIProcessingStatus = "ok" | "unavailable" | "not_processed";

export interface AIFact {
  id: UUID;
  category: FactCategory;
  subject: FactSubject;
  /** The words that attributed it to someone else ("my father"), when present. */
  subject_evidence: string | null;
  /** What the AI produced. Never overwritten by an edit. */
  value: string;
  /** The patient's edit if they made one, otherwise `value`. */
  effective_value: string;
  original_text: string | null;
  evidence_quote: string;
  evidence_start: number | null;
  evidence_end: number | null;
  confidence: number | null;
  validation_status: FactValidation;
  validation_note: string | null;
  review_state: FactReviewState;
  edited_value: string | null;
  reviewed_at: ISODateTime | null;
  medical_record_id: UUID | null;
  /** "medical_record" or "document_page". */
  source_type?: string;
  /** Documents only: the document and page the evidence is on, and where on it. */
  evidence_document_id?: UUID | null;
  evidence_page_number?: number | null;
  evidence_bbox?: PageBBox | null;
}

export interface AIRun {
  artifact_id: UUID | null;
  operation: string;
  provider: string;
  model: string;
  prompt_version: string | null;
  status: string;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  cached: boolean;
  created_at: ISODateTime | null;
}

export interface AIProcessing {
  record_id: UUID;
  status: AIProcessingStatus;
  error_code: string | null;
  /** Layer 1: the patient's own words, never modified. */
  original_text: string | null;
  /** Did layer 2 change the meaning of layer 1? */
  normalization_check: NormalizationCheck | null;
  usage: AIUsage | null;
  detected_language: LanguageCode | null;
  language_confidence: number | null;
  /** Machine interpretation. The original record text remains the source of truth. */
  normalized_english: string | null;
  unparsed: string[];
  needs_review: string[];
  facts: AIFact[];
  runs: AIRun[];
  generated_at: ISODateTime | null;
  provider: string | null;
  model: string | null;
  is_external_provider: boolean | null;
}

export type AIFactActionType = "confirm" | "edit" | "reject";

export interface AIFactAction {
  action: AIFactActionType;
  value?: string;
}

/** Doctor-facing summary attached to a shared record. */
export interface AIFactSummary {
  category: FactCategory;
  subject: FactSubject;
  subject_evidence: string | null;
  value: string;
  original_text: string | null;
  evidence_quote: string;
  validation_status: FactValidation;
  review_state: FactReviewState;
  evidence_document_id?: UUID | null;
  evidence_page_number?: number | null;
  evidence_bbox?: PageBBox | null;
}

export interface AIRecordInsight {
  record_id: UUID;
  status: AIProcessingStatus;
  original_text: string | null;
  normalization_check: NormalizationCheck | null;
  detected_language: LanguageCode | null;
  normalized_english: string | null;
  unparsed: string[];
  provider: string | null;
  model: string | null;
  generated_at: ISODateTime | null;
  facts: AIFactSummary[];
}

export interface AIStatus {
  provider: string;
  model: string;
  demo_mode: boolean;
  is_external: boolean;
  enabled_features: string[];
  prompt_versions: Record<string, string>;
}

// ---------- Case summary (Phase 4) ----------

/**
 * The only sections a case summary can contain. There is deliberately no
 * diagnosis, differential, triage, risk or treatment member — the machine
 * organises already-authorised information and never concludes anything.
 */
export type SummarySectionKind =
  | "current_problem"
  | "symptom"
  | "duration"
  | "medication"
  | "allergy"
  | "medical_history"
  | "measurement"
  | "document"
  | "prior_consultation"
  | "patient_statement"
  | "doctor_authored_context"
  | "unresolved_information";

/**
 * Who asserted a summary item. Always a human: the machine groups and orders,
 * it never authors a health claim, so there is no machine origin here.
 */
export type SummaryItemOrigin = "patient_provided" | "patient_confirmed" | "doctor_authored";

/** What kind of authorised source an item points back at. */
export type SummarySourceKind =
  | "patient_statement"
  | "current_problem"
  | "health_record"
  | "fact"
  | "document"
  | "prior_consultation"
  | "prior_prescription";

/** Why this doctor may see the source: the patient granted it, or it is their own. */
export type AuthorizationBasis = "patient_grant" | "own_prior_consultation";

/**
 * `not_generated` and `stale` are computed when the summary is read, never
 * stored: shared records are live references, so staleness is only true as of
 * the moment it is asked.
 */
export type CaseSummaryStatus = "not_generated" | "generating" | "ready" | "stale" | "failed";

/** A resolved pointer from a summary item back to the row it came from. */
export interface CaseSummarySource {
  ref: string;
  kind: SummarySourceKind;
  authorization_basis: AuthorizationBasis;
  record_id: UUID | null;
  document_id: UUID | null;
  consultation_id: UUID | null;
  prescription_id: UUID | null;
  fact_id: UUID | null;
  page_number: number | null;
  /** [x0, y0, x1, y1] as fractions of the page, when the reader measured it. */
  bbox: PageBBox | null;
  quote: string | null;
  original_text: string | null;
  language: LanguageCode | null;
  doctor_name: string | null;
  occurred_at: ISODateTime | null;
}

export interface CaseSummaryItem {
  section: SummarySectionKind;
  statement: string;
  origin: SummaryItemOrigin;
  /** Copied from the source fact, never inferred. A relative's stays a relative's. */
  subject: FactSubject | null;
  subject_evidence: string | null;
  /** The cited sources disagree. It says so; it never picks a side. */
  is_contradiction: boolean;
  occurred_at: ISODateTime | null;
  sources: CaseSummarySource[];
}

export interface CaseSummarySection {
  kind: SummarySectionKind;
  items: CaseSummaryItem[];
}

export interface CaseSummaryPayload {
  version: 1;
  sections: CaseSummarySection[];
  unresolved_notes: string[];
  /** Extracted items the patient has not confirmed. Counted, never stated. */
  pending_fact_count: number;
  /** Source kinds that were capped when the bundle was built. */
  truncated: string[];
}

export interface CaseSummary {
  consultation_id: UUID;
  status: CaseSummaryStatus;
  /** The shared information changed after this summary was generated. */
  is_stale: boolean;
  summary: CaseSummaryPayload | null;
  generated_at: ISODateTime | null;
  language: LanguageCode | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  /** False in demo mode, where the deterministic local provider runs. */
  is_external_provider: boolean | null;
  /** How many items validation removed. Shown, never hidden. */
  dropped_item_count: number;
  warnings: string[];
  error_code: string | null;
  generations_remaining: number | null;
}

// ---------- Documents (Phase 3) ----------

/**
 * How a page's text was obtained. Only `pdf_text_layer` is exact; `ocr` and
 * `vision_provider` are machine transcriptions and can misread.
 */
export type ReadingMethod = "pdf_text_layer" | "ocr" | "vision_provider" | "none";

export type DocumentExtractionStatus = "succeeded" | "partial" | "failed";

/** A region of a page: [x0, y0, x1, y1] as fractions of its width and height, origin top-left. */
export type PageBBox = [number, number, number, number];

/** One line of read text and where it sits on the page. */
export interface TextBlock {
  text: string;
  bbox: PageBBox;
  char_start: number;
  char_end: number;
  confidence: number | null;
}

export interface DocumentExtraction {
  id: UUID;
  status: DocumentExtractionStatus;
  error_code: string | null;
  /** sha256 of the exact file that was read. */
  source_sha256: string;
  page_count: number;
  pages_processed: number;
  truncated: boolean;
  methods: ReadingMethod[];
  engines: string[];
  warnings: string[];
  latency_ms: number | null;
  created_at: ISODateTime;
}

/** One page: what was read (with positions), its English version, and the items found on it. */
export interface DocumentPage {
  page_id: UUID;
  page_number: number;
  method: ReadingMethod;
  engine: string;
  /** Mean OCR confidence; null when the text was copied exactly. */
  confidence: number | null;
  width: number | null;
  height: number | null;
  text: string;
  blocks: TextBlock[];
  warnings: string[];
  detected_language: LanguageCode | null;
  ai_status: AIProcessingStatus;
  ai_error_code: string | null;
  normalized_english: string | null;
  unparsed: string[];
  needs_review: string[];
  normalization_check: NormalizationCheck | null;
  facts: AIFact[];
  runs: AIRun[];
  generated_at: ISODateTime | null;
}

export interface DocumentProcessing {
  document_id: UUID;
  document_status: DocumentStatus;
  status: "processed" | "failed" | "not_processed";
  error_code: string | null;
  extraction: DocumentExtraction | null;
  pages: DocumentPage[];
  usage: AIUsage | null;
  provider: string | null;
  model: string | null;
  is_external_provider: boolean | null;
}

/** Doctor-facing reading of one page of a shared document. */
export interface DocumentPageInsight {
  page_number: number;
  method: ReadingMethod;
  engine: string;
  confidence: number | null;
  text: string;
  blocks: TextBlock[];
  warnings: string[];
  detected_language: LanguageCode | null;
  ai_status: AIProcessingStatus;
  normalized_english: string | null;
  normalization_check: NormalizationCheck | null;
  facts: AIFactSummary[];
}

export interface DocumentInsight {
  document_id: UUID;
  extraction_status: DocumentExtractionStatus;
  error_code: string | null;
  page_count: number;
  pages_processed: number;
  truncated: boolean;
  methods: ReadingMethod[];
  engines: string[];
  processed_at: ISODateTime | null;
  pages: DocumentPageInsight[];
}

export interface PatientDashboard {
  display_name: string;
  preferred_language: LanguageCode;
  date_of_birth: ISODate | null;
  age: number | null;
  latest_current_problem: MedicalRecord | null;
  conditions: MedicalRecord[];
  allergies: MedicalRecord[];
  medications: MedicalRecord[];
  recent_documents: MedicalDocument[];
  open_consultations: ConsultationSummary[];
  recent_prescriptions: Prescription[];
}

// ---------------------------------------------------------------------------
// IP-SAKTI Sahayak — the legal source corpus (Phase 2, D-081–D-086)
// ---------------------------------------------------------------------------

export const CORPUS_LANES = ["india", "international"] as const;
export type CorpusLane = (typeof CORPUS_LANES)[number];
export const SOURCE_AUTHORITIES = ["india_code", "e_gazette", "ip_india", "nba", "fssai", "wipo_lex"] as const;
export type SourceAuthority = (typeof SOURCE_AUTHORITIES)[number];
export const INSTRUMENT_TYPES = [
  "act", "rules", "regulations", "notification", "treaty", "protocol", "directive", "other",
] as const;
export type InstrumentType = (typeof INSTRUMENT_TYPES)[number];
export const CORPUS_DOCUMENT_TYPES = [
  "original_text", "consolidated_text", "amendment", "notification", "other",
] as const;
export type CorpusDocumentType = (typeof CORPUS_DOCUMENT_TYPES)[number];
export const LOCATOR_TYPES = [
  "section", "subsection", "clause", "rule", "regulation", "article", "paragraph", "schedule", "item", "other",
] as const;
export type LocatorType = (typeof LOCATOR_TYPES)[number];
export const PROVISION_STATUSES = [
  "in_force", "not_yet_in_force", "amended", "superseded", "stayed", "omitted", "disputed", "withdrawn",
] as const;
export type ProvisionStatus = (typeof PROVISION_STATUSES)[number];
export type IngestionState = "uploaded" | "parsed" | "needs_review" | "failed";
export type CorpusReviewState = "draft" | "under_review" | "approved" | "rejected";
export type TermsStatus = "unknown" | "verified_permitted" | "verified_restricted";

export interface CorpusUserRef {
  id: UUID;
  email: string;
}

export interface SourceAuthorityInfo {
  code: SourceAuthority;
  name: string;
  lane: CorpusLane;
  terms_status: TermsStatus;
}

export interface InstrumentRef {
  id: UUID;
  title: string;
  instrument_type: InstrumentType;
  lane: CorpusLane;
}

export interface Instrument {
  id: UUID;
  lane: CorpusLane;
  instrument_type: InstrumentType;
  title: string;
  issued_by: string;
  description: string | null;
  created_at: ISODateTime;
}

export interface InstrumentCreate {
  lane: CorpusLane;
  instrument_type: InstrumentType;
  title: string;
  issued_by: string;
  description?: string | null;
}

export interface ProvisionVersionSummary {
  id: UUID;
  lane: CorpusLane;
  provision: { id: UUID; locator: string; locator_type: LocatorType };
  instrument: InstrumentRef;
  source_id: UUID;
  /** A version can be approved only once this is `approved`. */
  source_review_state: CorpusReviewState;
  version_number: number;
  review_state: CorpusReviewState;
  valid_from: ISODate | null;
  valid_to: ISODate | null;
  page_start: number;
  page_end: number;
  char_start: number;
  char_end: number;
  ocr_derived: boolean;
  text_sha256: string;
  created_at: ISODateTime;
  approved_at: ISODateTime | null;
  latest_status: ProvisionStatus | null;
}

export interface Provision {
  id: UUID;
  instrument_id: UUID;
  lane: CorpusLane;
  locator: string;
  locator_type: LocatorType;
  created_at: ISODateTime;
  versions: ProvisionVersionSummary[];
}

export interface CorpusSourceSummary {
  id: UUID;
  lane: CorpusLane;
  title: string;
  instrument: InstrumentRef;
  source_authority: SourceAuthority;
  authority_name: string;
  document_type: CorpusDocumentType;
  source_date: ISODate | null;
  retrieved_on: ISODate;
  terms_status: TermsStatus;
  ingestion_state: IngestionState;
  ingestion_issues: string[];
  review_state: CorpusReviewState;
  page_count: number | null;
  /** The file's checksum: an approval must name it. */
  sha256: string;
  created_at: ISODateTime;
  approved_at: ISODateTime | null;
}

export interface InstrumentDetail extends Instrument {
  provisions: Provision[];
  sources: CorpusSourceSummary[];
}

export interface CorpusSourceDetail extends CorpusSourceSummary {
  source_url: string | null;
  source_reference: string | null;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  text_sha256: string | null;
  text_length: number | null;
  parse_error_code: string | null;
  extraction_methods: string[];
  extraction_engines: string[];
  parsed_at: ISODateTime | null;
  uploaded_by: CorpusUserRef;
  submitted_at: ISODateTime | null;
  approved_by: CorpusUserRef | null;
  issues_acknowledged: boolean;
  rejected_at: ISODateTime | null;
  rejected_by: CorpusUserRef | null;
  rejection_reason: string | null;
  versions: ProvisionVersionSummary[];
}

export interface CorpusPageText {
  page_number: number;
  char_start: number;
  char_end: number;
  text: string;
  method: string;
  engine: string;
  confidence: number | null;
  warnings: string[];
}

export interface CorpusSourceText {
  source_id: UUID;
  text_sha256: string;
  text_length: number;
  pages: CorpusPageText[];
  chunks: { ordinal: number; page_number: number; char_start: number; char_end: number }[];
}

export interface CorpusSourceUpload {
  file: File;
  lane: CorpusLane;
  instrumentId: UUID;
  title: string;
  sourceAuthority: SourceAuthority;
  documentType: CorpusDocumentType;
  retrievedOn: ISODate;
  sourceUrl?: string | null;
  sourceReference?: string | null;
  sourceDate?: ISODate | null;
}

export interface ProvisionVersionCreate {
  provision_id: UUID;
  char_start: number;
  char_end: number;
  valid_from?: ISODate | null;
  valid_to?: ISODate | null;
}

export interface StatusEvent {
  id: UUID;
  status: ProvisionStatus;
  effective_date: ISODate | null;
  basis_source: { id: UUID; title: string; source_authority: SourceAuthority; review_state: CorpusReviewState; sha256: string } | null;
  basis_reference: string | null;
  note: string | null;
  recorded_by: CorpusUserRef;
  recorded_at: ISODateTime;
}

export interface StatusEventCreate {
  status: ProvisionStatus;
  effective_date?: ISODate | null;
  basis_source_id?: UUID | null;
  basis_reference?: string | null;
  note?: string | null;
}

export interface ProvisionVersionDetail extends ProvisionVersionSummary {
  text: string;
  source: { id: UUID; title: string; source_authority: SourceAuthority; review_state: CorpusReviewState; sha256: string };
  issues_acknowledged: boolean;
  approved_by: CorpusUserRef | null;
  rejected_at: ISODateTime | null;
  rejected_by: CorpusUserRef | null;
  rejection_reason: string | null;
  status_events: StatusEvent[];
}

export type DiffWordOp = "equal" | "delete" | "insert";
export interface DiffBlock {
  op: "equal" | "insert" | "delete" | "replace";
  old_start: number;
  new_start: number;
  lines?: string[];
  skipped?: number;
  tail?: string[];
  old?: string[];
  new?: string[];
  words?: { op: DiffWordOp; text: string }[];
}

export interface CorpusDiff {
  baseline: { kind: "source" | "version"; id: UUID; label: string; approved_at: ISODateTime | null } | null;
  stats: { added: number; removed: number; changed: number; unchanged: number };
  blocks: DiffBlock[];
}

export interface CorpusQueue {
  sources: CorpusSourceSummary[];
  versions: ProvisionVersionSummary[];
}

// ---------------------------------------------------------------------------
// IP-SAKTI Sahayak — product profiles and the formulation classifier (Phase 3)
// ---------------------------------------------------------------------------

export const FORMULATION_CATEGORIES = [
  "classical", "patent_proprietary", "new_or_non_classical", "phytopharmaceutical", "ayurveda_aahara", "cosmetic",
] as const;
export type FormulationCategory = (typeof FORMULATION_CATEGORIES)[number];
export type ClassificationStatus =
  | "incomplete"
  | "requires_information"
  | "determined"
  | "user_confirmed"
  | "user_rejected"
  | "superseded";
export type ReferenceStatus = "verified" | "unverified" | "corpus_required";
export const ADMINISTRATION_ROUTES = ["oral", "topical", "nasal", "parenteral", "other", "unknown"] as const;
export type AdministrationRoute = (typeof ADMINISTRATION_ROUTES)[number];

export interface ProductIngredient {
  name: string;
  part_used?: string | null;
  quantity?: string | null;
}

/** What the user says about their product. Their facts, never a classification. */
export interface ProductFields {
  name: string;
  intended_use?: string | null;
  dosage_form?: string | null;
  administration_route?: AdministrationRoute | null;
  ingredients?: ProductIngredient[];
  preparation_method?: string | null;
  classical_reference?: string | null;
  extract_description?: string | null;
  standardization_description?: string | null;
  markers?: string[];
  notes?: string | null;
  text_language?: LanguageCode | null;
}

export interface ProductProfile extends Required<Omit<ProductFields, "ingredients" | "markers">> {
  id: UUID;
  ingredients: ProductIngredient[];
  markers: string[];
  revision: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  confirmed_classification: {
    session_id: UUID;
    outcome_id: UUID;
    category: FormulationCategory;
    tree_version: number;
    decided_at: ISODateTime;
  } | null;
  open_session_id: UUID | null;
}

export interface ClassifierNode {
  id: string;
  question_key: string;
  help_key: string;
  missing_key: string;
  why_key: string;
  choices: { id: string; label_key: string }[];
  context_fields: string[];
  references: string[];
}

export interface ClassifierSlot {
  id: string;
  lane: CorpusLane;
  describes_key: string;
  status: ReferenceStatus;
  /** Approved, stored metadata only — present only when verified. */
  provision: {
    provision_version_id: UUID;
    locator: string;
    version_number: number;
    instrument_title: string;
    source_title: string;
    source_authority: SourceAuthority;
  } | null;
}

export interface ClassifierTree {
  classifier_id: string;
  version: number;
  fingerprint: string;
  current: boolean;
  status: string;
  legal_review: string;
  start: string;
  nodes: ClassifierNode[];
  categories: FormulationCategory[];
  slots: ClassifierSlot[];
}

export interface ClassificationStep {
  node_id: string;
  choice: string;
}

export interface ClassificationOutcome {
  id: UUID;
  sequence: number;
  kind: "determined" | "requires_information";
  category: FormulationCategory | null;
  stop_node_id: string | null;
  path: ClassificationStep[];
  answers_sha256: string;
  tree_version: number;
  references: { slot_id: string; status: ReferenceStatus; provision_version_id: UUID | null }[];
  created_at: ISODateTime;
}

export interface ClassificationSummary {
  id: UUID;
  product_id: UUID;
  status: ClassificationStatus;
  tree_version: number;
  category: FormulationCategory | null;
  created_at: ISODateTime;
  decided_at: ISODateTime | null;
  restarted_from_id: UUID | null;
}

export interface ClassificationSession extends ClassificationSummary {
  product_name: string;
  classifier_id: string;
  tree_fingerprint: string;
  current_node_id: string | null;
  path: ClassificationStep[];
  latest_outcome: ClassificationOutcome | null;
  outcomes: ClassificationOutcome[];
  answer_history: { node_id: string; choice: string; answered_at: ISODateTime; superseded_at: ISODateTime | null }[];
  references: ClassifierSlot[];
  product_revision: number;
  product_snapshot: Record<string, unknown>;
  decided_outcome_id: UUID | null;
  rejection_reason: string | null;
  updated_at: ISODateTime;
}
