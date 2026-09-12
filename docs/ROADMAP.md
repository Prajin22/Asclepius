# Roadmap

Each phase ends with: tests, a working demo, documentation, known issues, an
explicit summary — then waits for approval before the next phase starts.

| Phase | Goal | Status |
|---|---|---|
| **1** | Foundation: patient/doctor platform, records, documents, consultations, prescriptions, sharing | **complete** |
| **2** | AI foundation: multilingual normalisation, evidence-grounded extraction, patient confirmation, consent, provider abstraction, evaluation | **complete** |
| **3** | Medical document intelligence: text layer / OCR / vision reading, page evidence, patient review, doctor view | **complete — awaiting review** |
| 4 | AI case summarisation with evidence grounding | not started |
| 5 | Richer doctor consultation + communication | not started |
| 6 | Prescription translation + patient explanation | not started |
| 7 | Hospital/clinic discovery + urgency workflows | not started |
| 8 | Multilingual expansion + speech | not started |
| 9 | AI evaluation + security hardening + interoperability | not started |
| 10 | Demo hardening, deployment, presentation | not started |

## Phase 1 (done)

Patient and doctor web apps, FastAPI + PostgreSQL backend, authentication and
role-based access, health records in the patient's own language, document
upload and viewing, doctor discovery, patient-controlled sharing, consultation
lifecycle with text messaging, doctor-authored prescriptions, audit log,
`AIProvider`/`ObjectStorageProvider` interfaces, synthetic demo data, tests.

## Phase 2 (done)

Async `AIProvider` with mock/OpenAI/Anthropic/Gemini adapters; `DEMO_MODE`;
versioned prompts; language detection, English normalisation and structured
extraction; evidence validation that drops unsupported facts; patient
confirm/edit/reject; consent gate; artifact provenance (prompt version,
latency, tokens, cost); caching by content hash; timeout/retry/circuit breaker
with degradation to the original text; doctor case view showing original +
normalisation + facts + evidence + confirmation status; 42-case synthetic
evaluation set with a runner and provider benchmark.

## Phase 2 hardening pass (done, before Phase 3)

* Subject attribution (self/family/other/unknown) with evidence; a relative's
  facts can only become `family_history`.
* Per-patient AI budget: hourly/daily runs and 24-hour estimated cost.
* OpenAI adapter exercised end-to-end over real HTTP against a wire-format
  emulator, plus static strict-mode schema checks. A live run against the real
  API awaits a key.
* Three layers (original → English → facts) returned and shown together, with a
  meaning-drift check.

## Phase 3 — Medical document intelligence (done)

* Reading layer (`providers/documents`): exact PDF text layer, offline OCR
  (RapidOCR) for scans and images, or the provider's vision input; every page
  records method, engine, confidence, warnings and line positions.
* Integrity check against the upload hash before every read or render.
* `document_extractions` and `document_pages`; pages reused when unchanged and
  superseded when not.
* The Phase 2 pipeline runs per page; facts gain `evidence_page_number` and
  `evidence_bbox`, drawn from the reader's own geometry.
* Patient document page: read, see each page with evidence outlined, the text
  read from it, its English version, and confirm / edit / reject each item.
* Doctor case view: the reading of shared documents beside the original file,
  with page images (share-checked, audited).
* Vision adapters for OpenAI, Anthropic and Gemini (`document_transcription_v1`).
* Synthetic document evaluation: reading accuracy, page provenance, region
  agreement, extraction, prompt-injection safety.

## Phase 4 — AI case summarisation (next, not started)

* Summaries built only from confirmed or evidenced items, each statement linking
  to its source record, document page or region.
* Per consultation, never merged across doctors.

## Superseded plan — Phase 2 as originally sketched

* Implement a real `AIProvider` (re-checking official model docs first), keeping
  `mock` as the default and the test provider.
* On patient text: `detect_language` → `normalize_language` → store an
  `AIArtifact` (`artifact_type="normalization"`) referencing the source row.
  The original row is never modified.
* `extract_medical_information` producing candidate facts with `span`
  references, surfaced to the **patient** for confirmation before they become
  `ai_extracted` records; nothing is auto-accepted.
* Doctor case view shows original text with an English rendering beside it,
  labelled as machine output with its provider/model.
* Cost/latency controls: caching by content hash, size limits, timeouts, and a
  circuit breaker that degrades to "original only".
* Evaluation harness on a **synthetic** set (see AI_POLICY.md) before any model
  is preferred; no accuracy claims without it.
* Privacy: an explicit patient setting for sending text to a third-party model,
  plus documentation of what leaves the server.

Out of scope for Phase 2: OCR, diagnosis, prescription generation, summaries
across consultations.

## Later phases (sketch)

* **3** OCR/vision for uploaded documents → `document_analysis` artifacts with
  page/region references; `MedicalDocument.status` finally moves past `uploaded`.
* **4** Case summaries built only from referenced evidence, each statement
  linking to its source; per-consultation, never merged across doctors.
* **5** Scheduling (the `accepted` state), attachments in messages, snapshots of
  shared items at completion (D-006), notifications.
* **6** Prescription translation/explanation for patients, labelled as a
  translation of the doctor's words, with the original always shown.
* **7** Clinic/hospital discovery, availability, and conservative rule-based
  urgency guidance with fixed clinician-reviewed safety messages.
* **8** More UI languages, speech input for patients with low literacy, and
  review of machine-drafted translations by native speakers.
* **9** AI evaluation suite, security hardening (SECURITY.md "before any real
  deployment"), FHIR-shaped export, generated API types.
* **10** Deployment, seed/demo scripts, performance, presentation materials.
