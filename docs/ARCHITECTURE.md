# CareBridge — Architecture (Phases 1–3)

CareBridge is a healthcare **communication and information-management** platform.
It collects patient-provided health information, organises it, keeps it
understandable across languages, and helps doctors communicate with patients.

It is **not** an AI doctor. It does not diagnose, prescribe, or choose between
doctors. See [AI_POLICY.md](AI_POLICY.md).

---

## 1. System overview

```text
    ┌──────────────────────────────────────┐
    │  web app — Next.js :3000             │
    │  /home · /clinician · /admin         │
    └───────────────────┬──────────────────┘
                        │  HTTPS/JSON + Bearer JWT
                        ▼
            ┌──────────────────────┐
            │  FastAPI  :8000      │
            │  /api/v1/*           │
            │                      │
            │  api/       routers  │  ← HTTP only: parse, authorise, call service
            │  services/  domain   │  ← business rules, state machine, sharing policy
            │  models/    ORM      │  ← SQLAlchemy 2.0
            │  providers/ adapters │  ← storage, AI (swappable)
            └──────┬─────────┬─────┘
                   │         │
                   ▼         ▼
            ┌───────────┐ ┌────────────────────────┐
            │PostgreSQL │ │ ObjectStorageProvider  │
            │ (Alembic) │ │ local disk → S3/MinIO  │
            └───────────┘ └────────────────────────┘
```

One web app serves every role (D-050). Everyone signs in on the same page and
chooses Patient or Doctor; the account's role then decides the area — `/home`
for patients, `/clinician` for approved doctors (`/clinician/application` until
then), `/admin` for administrators. The areas keep their own density and
language rules, and the API enforces the role on every request.

## 2. Layering rules

| Layer | May depend on | Must not |
|---|---|---|
| `api/` | `services/`, `schemas/`, `api/deps.py` | contain business rules or raw SQL beyond simple lookups |
| `services/` | `models/`, `providers/` (via interfaces), `core/` | import FastAPI request objects (only `HTTPException`-free domain errors) |
| `providers/` | `core/config` | know about HTTP or the ORM |
| `models/` | `db/base` | import services |

Domain errors (`services/errors.py`) are translated to HTTP status codes in one
place (`main.py` exception handler). That keeps services testable without HTTP.

## 3. Domain model

```text
User (role: patient | doctor | admin)
 ├── PatientProfile ──┬── MedicalRecord*      (condition, allergy, medication,
 │                    │                        history_note, current_problem)
 │                    ├── MedicalDocument*    (file in object storage)
 │                    ├── Consultation* ──┬── ConsultationShare*   (patient grants)
 │                    │                  ├── ConsultationMessage*
 │                    │                  └── Prescription* ── PrescriptionItem*
 │                    └── AIArtifact*         (future AI output, evidence refs)
 └── DoctorProfile ── DoctorLanguage*
AuditEvent* (append-only access/change log)
```

### Key tables

| Table | Purpose | Notes |
|---|---|---|
| `users` | identity + role | email unique, bcrypt hash |
| `patient_profiles` | minimal personal info, preferred language, emergency info | DOB stored, age derived |
| `doctor_profiles` / `doctor_languages` | public doctor directory | synthetic data only |
| `medical_records` | patient-owned health facts | `source` = patient / ai_extracted / doctor; `source_language` + original `content` preserved |
| `medical_documents` | uploaded file metadata | `storage_reference` is opaque; `sha256` of the upload; `status` uploaded → processing → processed / failed (Phase 3) |
| `consultations` | one patient ↔ one doctor episode | independent; never merged |
| `consultation_shares` | per-item grants (what this doctor may see) | enforcement source of truth |
| `consultations.patient_shared_context` | immutable JSON snapshot of the sharing decision (incl. unchecked categories) | record-keeping |
| `consultation_messages` | text communication | original language kept |
| `prescriptions` / `prescription_items` | doctor-authored, immutable | `doctor_id` + `consultation_id` attribution |
| `ai_artifacts` | future AI outputs | `provider`, `model`, `source_references`, `confidence`, `review_status` |
| `audit_events` | who did what to which patient data | no FK on patient so logs survive deletes |

Enumerations are stored as constrained strings (`VARCHAR + CHECK`) rather than
native PostgreSQL enums, so adding a value is a simple migration.

### Original language (Principle 3)

`medical_records.content`, `consultations.request_message` and
`consultation_messages.body` always hold the **original patient wording** with
its language code. Phase 2 normalisation will write English/structured output
to `ai_artifacts` with a `source_references` pointer back to the original row —
never overwrite it.

### Consultation independence (Principle 4)

* A prescription belongs to exactly one consultation and one doctor.
  `patient_id`/`doctor_id` are taken from the consultation server-side, never
  from client input.
* There is no endpoint that merges, compares, or reconciles prescriptions.
* When a patient shares an earlier consultation or prescription with a new
  doctor, it is presented read-only with the original doctor's name and date.

### Consultation state machine

```text
requested ──accept──▶ active ──complete──▶ completed
    │                   
    ├──decline (doctor)─▶ cancelled
    └──cancel (patient)─▶ cancelled
```

`accepted` exists in the schema for Phase 5 (scheduling); in Phase 1 accepting
starts the consultation immediately (see DECISIONS D-007).

## 4. Access control

Role check first (`require_role`), then ownership:

* **Patient**: only their own profile, records, documents, consultations,
  prescriptions.
* **Doctor**: only consultations where they are the doctor, and inside those
  only items listed in `consultation_shares` (plus minimal identity: name, age,
  sex, preferred language, and the doctor's *own* earlier consultations with
  the patient). Visible while status ∈ {requested, accepted, active, completed};
  a cancelled consultation grants nothing.
* **Doctor, not yet approved**: signs in, reads and corrects their own
  application; every other clinician route returns `403 doctor_not_approved`,
  and patients cannot find or consult them (D-051).
* **Admin**: create doctors (approved on creation), review doctor applications —
  approve, reject with a reason, revoke — and read the audit log. Admin has no
  clinical-data endpoints.

Every doctor read of a case or document writes an `audit_event`.

## 5. API boundaries (`/api/v1`)

| Area | Endpoints |
|---|---|
| auth | `POST /auth/register` (patient self-signup), `POST /auth/register-doctor` (doctor application, starts pending), `POST /auth/login`, `GET /auth/me` |
| meta | `GET /meta/languages`, `GET /meta/ai` |
| patient | `GET/PUT /patients/me/profile`, `GET /patients/me/dashboard`, `GET/POST /patients/me/records`, `PATCH/DELETE /patients/me/records/{id}`, `GET/POST /patients/me/documents`, `GET /patients/me/documents/{id}`, `GET /patients/me/documents/{id}/file`, `GET/POST /patients/me/consultations`, `GET /patients/me/consultations/{id}`, `POST /patients/me/consultations/{id}/cancel`, `GET /patients/me/prescriptions` |
| directory | `GET /doctors`, `GET /doctors/{id}` (approved doctors only) |
| doctor | `GET /doctors/me/profile` (open before approval), `PUT /doctors/me/application` (before approval), `PUT /doctors/me/profile`, `GET /doctors/me/consultations`, `GET /doctors/me/consultations/{id}` (case view), `POST …/{id}/accept`, `POST …/{id}/decline`, `POST …/{id}/complete`, `PUT …/{id}/assessment`, `POST …/{id}/prescriptions`, `GET …/{id}/documents/{doc_id}/file` |
| messages | `GET/POST /consultations/{id}/messages` (either party) |
| admin | `POST /admin/doctors`, `GET /admin/doctors?status=`, `POST /admin/doctors/{id}/approve`, `POST /admin/doctors/{id}/reject`, `GET /admin/audit-events` |

OpenAPI docs are served at `http://localhost:8000/docs`.

## 6. Providers

### ObjectStorageProvider (`app/providers/storage`)

```python
put(key, data, content_type) -> str   # returns storage_reference
get(reference) -> bytes
delete(reference) -> None
exists(reference) -> bool
```

`LocalStorageProvider` writes under `STORAGE_LOCAL_ROOT` with a path-traversal
guard. Keys are generated server-side (`patients/<id>/documents/<uuid>.<ext>`);
user filenames never touch the filesystem. An S3/MinIO provider implements the
same four methods — no application code changes.

### AIProvider (`app/providers/ai`) — Phase 2

```python
async detect_language(text) -> LanguageDetection
async normalize_to_english(text, source_language) -> NormalizationResult
async extract_medical_information(text, language) -> ExtractionResult
```

Implementations: `MockAIProvider` (deterministic, local, no credentials),
`OpenAIProvider` (Responses API, strict `json_schema`), `AnthropicProvider`
(Messages API, strict tool schema), `GeminiProvider` (`generateContent` with
`responseSchema`). All three HTTP adapters share `http_base.HttpJSONProvider`,
which renders the versioned prompt, validates the response against our Pydantic
schemas, maps transport failures to structured errors, and records latency,
tokens and estimated cost.

Selection is configuration only (`DEMO_MODE`, `AI_PROVIDER`, `AI_MODEL`);
`DEMO_MODE=true` pins the local provider so no external call is possible.
Model names never appear in the domain layer, and there is deliberately no
diagnose/prescribe capability on the interface.

### AI pipeline (`app/services/ai_pipeline.py`)

```text
original record (source of truth, never modified)
        │
        ├─ consent gate ── no consent → refuse, nothing sent anywhere
        ├─ cache lookup  ── operation+provider+model+prompt version+language+sha256(text)
        ▼
 detect language ──▶ normalise to English ──▶ extract facts
        │                    │                      │
        ▼                    ▼                      ▼
   ai_artifacts (provenance: status, prompt version, latency, tokens, cost)
                                                    │
                                      evidence validation (services/evidence.py)
                                        · quote must exist in the source (verbatim)
                                        · position located by the application;
                                          provider offsets ignored
                                        · unsupported → dropped
                                        · weak → needs_review
                                                    ▼
                                        ai_extracted_facts (review_state=pending)
                                                    ▼
                                   patient confirms / edits / rejects
                                                    ▼
                    confirmed allergy · medication · history → medical_records (source=ai_extracted)
```

Every provider call is wrapped by `runtime.call_with_resilience` (timeout,
bounded retry, circuit breaker). Any failure degrades to "original only" with a
`failed` artifact and an audit event — never to invented content.

**Hardening (pre-Phase 3).** Before any provider work the pipeline enforces the
patient's AI budget (`services/ai_limits.py`). Every fact carries `subject`
(self/family/other/unknown) and `subject_evidence`; confirmation maps family
facts only to `family_history` records (`services/ai_facts.record_type_for`).
After extraction, `services/normalization_check.py` compares the three layers
and stores the result on the extraction artifact. The API returns all three
layers together — `original_text`, `normalized_english`, `facts` — plus
`normalization_check` and the patient's budget `usage`, both to the patient
(`GET /patients/me/records/{id}/ai`) and to the doctor (`CaseView.ai_insights`).

### Phase 2 tables

| Table | Purpose |
|---|---|
| `ai_artifacts` (extended) | one row per operation: provider, model, `prompt_version`, `status`, `source_hash`, `cache_key`, `latency_ms`, token counts, `estimated_cost_usd`, `error_code` |
| `ai_extracted_facts` | machine-extracted fact + evidence quote/offsets, `validation_status`, `review_state`, `edited_value`, optional link to the created `medical_record` |
| `patient_profiles.ai_processing_consent` | explicit opt-in, default false, with `ai_consent_updated_at` |

### Phase 2 endpoints

`PUT /patients/me/ai-consent` · `POST /patients/me/records/{id}/ai-process` ·
`GET /patients/me/records/{id}/ai` · `POST /patients/me/ai/facts/{id}` ·
`GET /patients/me/ai/artifacts/{id}` · `GET /meta/ai`.
The doctor `CaseView` gains `ai_insights` — machine output for **shared**
records only, shown beside the original.

### Phase 3 — document intelligence

```text
uploaded file (never modified) ── sha256 must equal the upload hash before every read or render
        │
        ├─ consent gate · budget check covering every page to be interpreted
        ▼
 providers/documents — reading only, no medical meaning
   · PDF page with a text layer → copied exactly (pdfplumber), line boxes kept
   · scanned page / image       → OCR: local RapidOCR (default, offline)
                                   or the configured provider's vision input
   · every page: method, engine, confidence, warnings
        ▼
 document_pages — verbatim text + line boxes (reused if unchanged, superseded if not)
        ▼
 the Phase 2 pipeline, once per page (AISource = document page)
   detect → normalise → extract → evidence validation → meaning check
        ▼
 ai_extracted_facts (+ evidence_page_number, evidence_bbox from the reader's geometry)
        ▼
 patient confirms / edits / rejects ─▶ shares with a doctor ─▶ CaseView.document_insights
```

**Reading** (`app/providers/documents`) returns `PageText` per page: text, page
size, method (`pdf_text_layer` · `ocr` · `vision_provider`), engine, mean OCR
confidence, warnings and `TextBlock`s — one per line, with character offsets
into the page text and a box in page fractions. PDF pages are rendered with
pypdfium2 for OCR and for page images; images are size-checked before decoding
and EXIF-rotated. Parser failures surface as `DocumentReadError`, never as a
crash.

**Orchestration** (`services/document_pipeline.py`): integrity check → consent →
budget → read (worker thread) → upsert pages → for each page with text,
`ai_pipeline.interpret` + `ai_pipeline.finish` (the functions records use,
generalised over `AISource`) → document status → audit. A reading failure
records a failed `document_extractions` row and leaves the file untouched; an AI
failure on one page keeps that page's text and marks the page `unavailable`.

**Evidence regions**: a fact's box is `PageText.bbox_for_span(start, end)`, the
union of the lines its validated evidence touches. Vision transcription reports
no positions, so those facts carry a page number and no box.

| Table / column | Purpose |
|---|---|
| `document_extractions` | one row per reading attempt: status (succeeded / partial / failed), error code, `source_sha256`, page count, pages processed, truncated, methods, engines, warnings, latency, requester |
| `document_pages` | verbatim page text, `text_sha256`, method, engine, confidence, size, line blocks, warnings, detected language; unique on `(document_id, page_number, text_sha256)`; `superseded_at` |
| `ai_extracted_facts.evidence_document_id` / `evidence_page_number` / `evidence_bbox` | which document and page a fact's evidence is on, and where (`evidence_start`/`evidence_end` are always the validator's located position) |
| `ai_artifacts` (`document_transcription`) | vision transcriptions, with prompt version, tokens and cost |

**Endpoints**: `POST /patients/me/documents/{id}/process` ·
`GET /patients/me/documents/{id}/extraction` ·
`GET /patients/me/documents/{id}/pages/{n}/image` ·
`GET /doctors/me/consultations/{cid}/documents/{doc_id}/pages/{n}/image`
(share-checked, audited). Fact review reuses `POST /patients/me/ai/facts/{id}`.
`CaseView.document_insights` carries the reading of **shared** documents only.

**Configuration**: `OCR_ENGINE` (`auto` · `local` · `provider` · `none`),
`OCR_MIN_TEXT_LAYER_CHARS`, `DOCUMENT_PROCESSING_MAX_PAGES`,
`DOCUMENT_RENDER_SCALE`, `DOCUMENT_MAX_PIXELS`.

**Frontend**: `DocumentReadingPanel` on the patient document page and
`DocumentInsight` inside each shared document in the doctor case view (collapsed
by default). `packages/ui` adds `PageImage` (the original page with evidence
boxes as an overlay) and `ReadingProvenance` (exact copy vs machine
transcription, confidence, warnings).

## 7. Localisation

* Language codes: `app/core/languages.py` (backend) and
  `packages/shared-types` (frontend): en, hi, ta, te, kn, ml, mr, bn, gu, pa,
  or, as. Each has `ui_available` and `ai_status` flags — we do not claim support
  we have not built.
* UI strings live in `packages/i18n/messages/{en,hi,ta}.json`. Components call
  `t("key")`; there are no language conditionals in components. A unit test
  enforces key parity across catalogues.
* Font stack uses system fonts with Indic coverage (Nirmala UI on Windows,
  Noto Sans elsewhere) so the demo works offline.

## 8. Frontend structure

```text
apps/patient-web      the one Next.js App Router app (name kept for deployments):
                        /login       role choice, sign-in, patient sign-up, doctor application
                        /home …      patient area, calm/large targets
                        /clinician   doctor workspace, denser case view; /clinician/application before approval
                        /admin       doctor applications
packages/shared-types API DTO types (hand-written mirror of Pydantic schemas)
packages/api-client   fetch wrapper + typed endpoint functions
packages/i18n         message catalogues + I18nProvider/useT
packages/ui           shared presentational components (Button, Card, SourceBadge…)
```

Auth token: JWT in this tab's `sessionStorage` (one account per tab), sent as
`Authorization: Bearer`. See SECURITY.md for the trade-off.

## 9. Testing

* Backend: pytest against SQLite (fast, default) or PostgreSQL
  (`TEST_DATABASE_URL`). A migration test runs `alembic upgrade head` /
  `downgrade base` when PostgreSQL is configured.
* Frontend: Vitest + Testing Library (jsdom) for components, i18n catalogue
  parity, and the API client.

## Case summarisation (Phase 4)

```text
consultation
   → authorization: approved doctor, their consultation, visible status
   → patient AI consent
   → budget: patient spend cap + per-consultation generation cap
   → resolve_authorized_context()      ← the one authorization resolver
   → build_source_bundle()             ← the boundary is now closed
   → sha256(canonical bundle) → cache lookup
   → AIProvider.summarize_case()       ← organisation only
   → ModelCaseSummary (strict schema)
   → validate_summary()                ← ten checks; failures are dropped
   → ai_artifacts + consultation_summaries
   → audit
```

`resolve_authorized_context()` in `services/consultation_service.py` is the
single place that turns share grants into rows. `build_case_view()` and
`build_source_bundle()` both call it, so what a doctor may read and what a
provider may be shown cannot drift apart.

**Bundle** (`services/case_summary_bundle.py`). Each authorised row becomes an
item in two halves: a `payload` the provider sees — words, no identifiers — and
a `resolution` the application keeps, which turns a returned `S7` back into a
real row. The two never travel together. Items are ordered deterministically and
handles assigned in that order, so the same authorised state always produces the
same bytes. The canonical form is hashed over *content*, because shared records
are live references (D-006), and that hash is both the cache key and the
staleness test.

The provider is handed `bundle.canonical()` — byte for byte the text that was
hashed — so what was sent and what was hashed are provably the same.

**Schema** (`schemas/summary.py`). Three layers: `ModelCaseSummary` is all a
provider may return (section, statement, source handles, a contradiction flag);
`StoredCaseSummary` is what the application writes once provenance is attached;
`CaseSummaryOut` is what the browser receives. `extra="forbid"` throughout, and
the section enum has no member that could carry a conclusion.

**Providers**. `summarize_case` is one non-abstract method on `AIProvider`,
implemented once on `HttpJSONProvider` — the vendor adapters are generic over
any `Prompt`, so OpenAI's strict `json_schema`, Anthropic's strict tool and
Gemini's `responseSchema` all constrain it with no adapter change. The local
provider implements it as deterministic rules (`providers/ai/mock_summary.py`),
which is what `DEMO_MODE` pins the public deployment to.

**Storage**. `consultation_summaries` is append-only: each real generation adds
a row, so what a doctor was shown survives for audit, and "current" is the
newest row. Failures are stored too, with the reasons items were dropped, so a
doctor can tell an outage from a summary whose every line was rejected.

**API**. `POST` and `GET /doctors/me/consultations/{id}/summary`. `POST` reuses
a stored summary when nothing shared has changed; `GET` never generates.
