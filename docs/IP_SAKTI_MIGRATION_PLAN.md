# IP-SAKTI Sahayak Migration Plan

**Problem statement:** IP-SAKTI Sahayak · SIH26045 · Ministry of Ayush / All India Institute of Ayurveda
**Phase:** 0 — audit and migration plan only. Nothing in this document has been implemented.
**Audited:** 2026-09-30, branch `ip-sakti` at `e6434e1` plus the uncommitted Phase 5 work described in §2.
**Status:** awaiting approval. Phase 1 does not start until "Proceed to Phase 1".

> **Read this first.** The Phase 0 instruction refers to "the IP-SAKTI Sahayak
> build brief supplied for this project". No such document is in the repository
> and none was supplied with the instruction. This plan therefore takes as its
> target only what the Phase 0 instruction itself states: the 20 requirements,
> the domain concepts, the pipeline, the eight invariants and the corpus
> categories. Wherever the instruction does not define something — the
> classification taxonomy, the confidence formula, role names, what an answer
> may contain beyond a quotation — this plan says so and lists it in §21 rather
> than inventing it.
>
> This plan contains **no legal text, no section numbers and no statement of
> what any law currently says**. Instrument names are taken from the Phase 0
> instruction. Every date, version and status must come from an official source
> through the curator workflow.

---

## 1. Executive Summary

**What exists.** A working, tested healthcare prototype (CareBridge, shown to
users as "Asclepius"): one Next.js app for patients, doctors and an
administrator, a FastAPI backend, PostgreSQL, a four-provider AI abstraction
with a deterministic offline mode, document reading with OCR, evidence-grounded
extraction, doctor-facing case summaries with hard evaluation gates, and a
deterministic question-tree engine. 21 tables, 66 endpoints, 9 migrations.

**The verdict in one paragraph.** The *infrastructure* is largely reusable and
several of its safety patterns are exactly what IP-SAKTI's invariants need. The
*domain* is not: medical vocabulary appears 2,150 times across 70 of the
backend's 91 non-empty source files, every healthcare table hangs off a patient or
doctor profile through a non-nullable foreign key, and there is **no retrieval, search or corpus code of any
kind**. IP-SAKTI is therefore a new domain built beside the healthcare one on
shared infrastructure, not a re-skin of it.

**Strongest reusable assets**

| Asset | Where | Why it matters for IP-SAKTI |
|---|---|---|
| Exact-quote locator | `backend/app/services/evidence.py` | Already finds a quotation in source text deterministically and ignores the model's own offsets — the core of invariant I-1 |
| Opaque source handles + "drop, never repair" validation | `backend/app/services/case_summary_bundle.py`, `summary_validation.py` | The model never sees a database id and cannot cite what it was not given — the shape a citation verifier needs |
| Closed response schemas | `backend/app/schemas/summary.py` | `extra="forbid"` with no field able to express a conclusion — the mechanism for I-2 |
| Deterministic offline provider | `backend/app/providers/ai/mock.py`, `mock_summary.py`, `DEMO_MODE` in `core/config.py` | I-7 |
| Pure, declared-data decision engine | `backend/app/conversation/engine.py`, `model.py` | A natural base for a deterministic, explainable product classifier |
| Approval workflow | `backend/app/services/doctor_service.py::review_application` | The pattern for curator approval of corpus material |
| Evaluation harness with hard gates that are proven able to fail | `backend/evaluation/run_summary_eval.py`, `tests/test_case_summary_eval_harness.py` | Requirement 20 |

**What is entirely new:** the legal corpus and its versioning, ingestion and
curator approval, retrieval in two separate lanes, the citation verifier, the
scope guard, planner, composer, confidence, abstention, product profiles,
classification sessions, facilitator escalation, and all IP-SAKTI screens.

**Recommended approach.** Additive only. A `PRODUCT` setting defaulting to
`carebridge`, so that nothing changes unless it is set; a new backend package
for the IP-SAKTI domain; new tables through new migrations; healthcare tables,
routes, screens and tests left in place and unmounted in IP-SAKTI mode.

**The four things that decide whether this succeeds**

1. **The legal corpus is a human dependency, not an engineering task.** Official
   texts must be obtained from their authorities, versioned and approved by a
   person competent to do so. The system cannot generate them (I-5) and this
   plan invents none. It is the longest pole and should start first.
2. **The build brief is missing.** Several Phase 3 and Phase 4 designs cannot be
   fixed without it (§21).
3. **Phase 5 of the healthcare product is uncommitted.** Migrations `0008` and
   `0009` and the engine IP-SAKTI would reuse exist only in the working tree.
   Where they are committed must be decided before any IP-SAKTI migration is
   written (§21, Q1).
4. **Two frontend tests are timing-sensitive** and fail on a busy machine
   (§3). Reported, not fixed.

---

## 2. Current Repository State

### 2.1 Git

| | |
|---|---|
| Branch before this phase | `main` at `e6434e1`, identical to `origin/main` |
| Branch now | `ip-sakti`, created from `main` at `e6434e1` |
| `main` | unchanged: still `e6434e1`, still equal to `origin/main` |
| History | not rewritten; nothing merged; nothing committed; nothing pushed |
| Working tree | 5 modified and 20 untracked paths, all Phase 5A/5B healthcare work, carried onto `ip-sakti` unchanged |
| This phase added | `docs/IP_SAKTI_MIGRATION_PLAN.md` only |

The uncommitted Phase 5 work: `backend/app/conversation/`,
`backend/app/models/conversation.py`, `backend/app/schemas/conversation.py`,
`backend/app/services/conversation_service.py`, `conversation_presenters.py`,
`backend/app/api/v1/conversations.py`, migrations
`backend/alembic/versions/0008_phase_5_conversation_engine.py` and
`0009_phase_5b_history_tree.py`, seven `backend/tests/test_conversation_*.py`
files, `backend/evaluation/conversation_paths.json` and
`run_conversation_eval.py`, two reports in `presentation-assets/`, and edits to
`backend/app/api/v1/router.py`, `backend/app/models/__init__.py`,
`backend/app/models/enums.py`, `backend/tests/test_migrations.py` and
`docs/DECISIONS.md`.

### 2.2 The documentation is behind the source

| Document | Says | Source says |
|---|---|---|
| `README.md` | "CareBridge — Phases 1–3"; Phase 4 "doctor-facing view is next" | Phase 4 complete including the doctor UI (`apps/patient-web/components/clinician/CaseSummary.tsx`), committed as `e6434e1` |
| `docs/ROADMAP.md` | Phase 4 "backend + providers + evaluation complete"; Phase 5 "not started" | Phases 5A and 5B built and tested, uncommitted |
| `docs/ARCHITECTURE.md`, `docs/SECURITY.md` | Titled "Phases 1–3" | Phase 4 sections appended; nothing on Phase 5 |
| `docs/AI_POLICY.md` | Case summaries "backend and providers implemented" | UI implemented too |
| `docs/DECISIONS.md` | D-001 to D-076 | Current; the only document that covers Phase 5 |

The real state below is taken from source, migrations and tests.

### 2.3 Layout

```
apps/patient-web        Next.js 16.3.5 app, every role        (Vercel)
packages/ui             shared components + design tokens
packages/i18n           catalogues: patient en/hi/ta, doctor en, common en/hi/ta
packages/api-client     typed fetch client + auth context
packages/shared-types   TypeScript mirror of the API (783 lines, hand-written)
backend/app             FastAPI application                   (Render)
backend/alembic         migrations 0001–0009, single head 0009
backend/evaluation      four offline evaluation harnesses
backend/tests           46 test modules
docs/                   architecture, policy, security, decisions, deployment
render.yaml             Render blueprint: API + PostgreSQL 16
```

### 2.4 Stack (from the manifests)

| Layer | Technology |
|---|---|
| Web | Next.js 16.3.5 (App Router), React 19.3, TypeScript 5.9.3, Tailwind CSS 4.3, `@phosphor-icons/react`, `three` |
| Web tests | Vitest 5, Testing Library, jsdom |
| API | Python ≥ 3.11 (3.12.7 on Render), FastAPI, Pydantic 2, pydantic-settings |
| Data | SQLAlchemy 2.0, Alembic, psycopg 3, PostgreSQL 16; SQLite for fast tests |
| Auth | PyJWT (HS256 bearer token), bcrypt |
| AI | `httpx` adapters for OpenAI, Anthropic, Gemini; deterministic mock |
| Documents | pdfplumber, pypdfium2, Pillow, rapidocr-onnxruntime |
| Tooling | `uv`, npm workspaces, Node ≥ 22.12 |
| Deploy | Vercel (web), Render blueprint (API + database) |

### 2.5 Existing switches

There is **no product flag today.** The switches that exist:

| Setting | Where | Effect |
|---|---|---|
| `DEMO_MODE` (default `true`) | `backend/app/core/config.py` | Pins the mock provider and offline OCR; no external call is possible |
| `AI_PROVIDER`, `AI_MODEL` | same | Provider selection when not in demo mode |
| `OCR_ENGINE` | same | `auto` / `local` / `provider` / `none` |
| `AI_*` limits, `SUMMARY_PER_CONSULTATION_LIMIT` | same | Budgets |
| `NEXT_PUBLIC_API_BASE_URL` | `packages/api-client`, web app | API location |
| `NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS` | `apps/patient-web` | Shows demo sign-in shortcuts |

---

## 3. Baseline Test Results

Run on 2026-09-30 on branch `ip-sakti`, before any file other than this one was
created. No application code was changed.

| Check | Command | Result |
|---|---|---|
| Backend, PostgreSQL 16 | `uv run pytest -p no:warnings` with `TEST_DATABASE_URL` and `MIGRATION_TEST_DATABASE_URL` set | **751 passed, 0 failed, 1 skipped** (11 min 22 s) |
| Backend, SQLite | `uv run pytest -p no:warnings` | **746 passed, 0 failed, 6 skipped** (11 min 22 s) |
| Frontend tests | `npm test` (four workspaces) | **114 passed, 0 failed** (82 + 8 + 13 + 11) when run on its own; **2 failed** when run alongside the backend suites — see below |
| Typecheck | `npm run typecheck` | exit 0, no output |
| Production build | `npm run build` | exit 0, no warnings or errors in the log |
| Lint | — | **none configured.** No ESLint config, no `lint` script in any workspace; `ruff` is not installed in the backend environment |
| Migrations | `uv run alembic heads` / `history` | single head `0009`; linear chain `0001 → 0009` |
| Migration tests | inside the PostgreSQL run (`backend/tests/test_migrations.py`, 5 tests) | base → head → base, `alembic check`, and per-revision reversibility for 0007, 0008, 0009 |

**Existing evaluation gates** (run offline with `DEMO_MODE=true`, mock provider,
output redirected outside the repository so tracked result files were not
touched):

| Harness | Dataset | Result |
|---|---|---|
| `evaluation.run_eval` | 42 synthetic extraction cases | language accuracy 0.976 · extraction P 0.944 / R 0.882 / F1 0.912 · evidence validity 1.0 · unsupported-fact rate 0.0 · 0 failures |
| `evaluation.run_document_eval` | 5 synthetic documents, offline OCR | extraction P 0.938 / R 1.0 / F1 0.968 · page provenance 1.0 · evidence validity 1.0 · forbidden facts: none |
| `evaluation.run_summary_eval` | 52 synthetic consultations | hard gates **PASS**: unauthorised source leakage 0 · unsupported clinical claims 0 · fabricated references 0 |
| `evaluation.run_conversation_eval` | 29 hand-written paths | 29/29 · all six hard gates 0 · every v2 branch opened and shut |

**Known failures and caveats — not fixed, per Phase 0 rules**

* **Two frontend tests fail under load.** In the first baseline run the
  frontend suite ran at the same time as both backend suites; it took 121 s
  instead of about 18 s, and two tests in
  `apps/patient-web/components/clinician/PrescriptionForm.test.tsx` failed:
  *"submits exactly what the doctor typed, for multiple medicines"* hit
  Vitest's default 5 s timeout (it took 5.1 s), and *"can remove an added
  medicine"* asserted immediately after a click, before the removal had
  rendered. Re-run on an idle machine the file passed 3 times out of 3 and the
  whole frontend suite passed 114 of 114. These are timing-sensitive tests, not
  a product defect, but they will fail again on a slow or busy machine — which
  includes most CI runners. Not fixed in Phase 0.
* **Skipped tests.** One on both databases:
  `backend/tests/test_case_summary_example.py`, an opt-in utility that runs
  only when `SUMMARY_BUNDLE_DUMP` is set. Five more on SQLite: the migration
  tests, which need PostgreSQL. Several tests contain conditional
  `pytest.skip` calls that did not trigger.

* **Warnings were not collected.** On this machine pytest prints its summary
  line only with the warnings plugin disabled (`-p no:warnings`), so the number
  of warnings in the backend run is unknown.
* **One pre-existing defect is known and unfixed** (reported in the Phase 5B
  review): `backend/app/services/ai_facts.py` writes a value of up to 300
  characters into the 200-character `medical_records.title`. No test exercises
  it.
* **The PostgreSQL used for tests is a portable instance in a temporary
  directory.** It had stopped (the machine restarted) and was restarted for this
  run. It is not a project dependency, but the PostgreSQL numbers cannot be
  reproduced on this machine without it.

---

## 4. Existing Architecture Map

### 4.1 Backend — `backend/app/`

| Module | Lines | Role | Healthcare-specific? |
|---|---|---|---|
| `main.py` | 60 | App factory, CORS, size limit, security headers, one error translator | Title/description only |
| `core/config.py` | 166 | All settings; `DEMO_MODE` | No |
| `core/security.py` | 58 | bcrypt, JWT encode/decode | No |
| `core/languages.py` | 62 | `LanguageCode` (12 codes), which have a UI | No |
| `db/base.py`, `db/session.py` | — | Declarative base, naming convention, `enum_column` (VARCHAR + CHECK), session | No |
| `api/deps.py` | 94 | Bearer auth, `require_roles`, `CurrentPatient`, `CurrentDoctor` | Role names and profile lookups |
| `api/v1/router.py` | 25 | Mounts every router | Mounting order is healthcare-specific |
| `api/v1/auth.py` | 46 | `login`, `register` (patient), `register-doctor`, `me` | Two of four endpoints |
| `api/v1/meta.py` | 48 | `languages`, `ai` status | No |
| `api/v1/patients.py`, `doctors.py`, `admin.py`, `messages.py`, `ai.py`, `document_ai.py`, `conversations.py`, `files.py` | 720 | 59 endpoints; all healthcare except the admin audit view | Yes, except `/admin/audit-events` |
| `services/audit.py` | 41 | `audit.record(...)`: append an event in the caller's transaction | Optional `patient_id` argument only |
| `services/errors.py` | 82 | Domain errors → HTTP in one place | One class, `DoctorNotApproved` |
| `services/evidence.py` | 153 | Exact-quote locator and fact validation | Locator is neutral; allergy-absence rule is medical |
| `services/auth_service.py` | 107 | Authenticate, register patient, create/apply doctor | Mostly |
| `services/ai_pipeline.py` | 608 | Consent gate, cache, artifact storage, detect → normalise → extract | Pipeline shape neutral; content medical |
| `services/ai_limits.py` | 153 | Per-patient rate and cost budgets | Keyed on patient |
| `services/ai_facts.py`, `normalization_check.py` | 274 | Fact confirmation; meaning-drift check | Yes |
| `services/document_service.py` | 156 | MIME sniffing, safe filenames, upload validation, hashing | Validation neutral; ownership is patient |
| `services/document_pipeline.py` | 440 | Integrity check, page reading, per-page extraction | Reading neutral; extraction medical |
| `services/consultation_service.py` | 638 | Request/accept/complete state machine, sharing, messaging, the single authorization resolver | Yes |
| `services/case_summary*.py`, `summary_validation.py` | 1,316 | Source bundle, opaque refs, ten validation checks, append-only summaries | Pattern neutral; content medical |
| `services/doctor_service.py`, `patient_service.py`, `presenters.py`, `ai_presenters.py`, `document_presenters.py` | 571 | Directory, approval, profile, records, response shaping | Yes |
| `services/conversation_service.py`, `conversation_presenters.py` | 1,219 | Session state machine around the pure engine | Tables patient-scoped |
| `conversation/engine.py`, `model.py`, `flow.py` | 670 | Pure deterministic engine; flow registry; fingerprints | Engine neutral; `model.py` imports medical enums |
| `conversation/flows/history_general_v1.py`, `_v2.py` | 500 | The two symptom-history trees | Yes, entirely |
| `providers/ai/base.py` | 154 | `AIProvider` contract and result types | One abstract method is `extract_medical_information` |
| `providers/ai/http_base.py` | 323 | Shared HTTP provider: request build, structured output, parsing | Payload models are medical |
| `providers/ai/openai_provider.py`, `anthropic_provider.py`, `gemini_provider.py` | 222 | Wire formats | No |
| `providers/ai/runtime.py` | 86 | Timeout, retry, circuit breaker | No |
| `providers/ai/pricing.py`, `errors.py` | 90 | Cost table; provider errors | No |
| `providers/ai/prompts.py` | 296 | Five versioned prompts | Three are medical |
| `providers/ai/mock.py`, `mock_summary.py`, `lexicon.py` | 962 | Deterministic offline provider | Yes |
| `providers/documents/*` | 466 | PDF text layer, page rendering, offline OCR | No |
| `providers/storage/*` | 100 | `ObjectStorageProvider`, local-disk implementation | No |
| `models/*` | — | 21 tables | 19 healthcare; `users`, `audit_events` neutral |
| `seed.py`, `synthetic_documents.py` | 487 | Synthetic healthcare demo data and sample files | Yes |

### 4.2 Frontend

| Path | Role |
|---|---|
| `apps/patient-web/app/layout.tsx` | Root layout, fonts for Latin/Devanagari/Tamil, page metadata ("Asclepius") |
| `apps/patient-web/app/page.tsx` → `components/landing/LandingPage.tsx`, `FoldScene.tsx` | Public landing page with a `three` scene |
| `apps/patient-web/app/login/page.tsx` | One sign-in page; role chosen as patient or doctor |
| `apps/patient-web/app/(app)/…` | Patient area: `home`, `health`, `health/current-problem`, `documents`, `documents/[id]`, `consultations`, `consultations/[id]`, `find-care`, `find-care/[doctorId]`, `profile` |
| `apps/patient-web/app/clinician/…` | Doctor workspace: queue, `cases/[id]`, `consultations`, `patients`, `profile`, `application` |
| `apps/patient-web/app/admin/…` | Doctor applications and audit events |
| `apps/patient-web/components/AppShell.tsx`, `clinician/DoctorShell.tsx` | Navigation shells; nav items are hard-coded arrays |
| `apps/patient-web/lib/routes.ts` | `HOME_FOR_ROLE` — where each role lands |
| `apps/patient-web/lib/locale.tsx`, `components/LanguageSwitcher.tsx` | UI language state |
| `packages/ui/src/*` | `Button`, `Card`, `Badge`, `Field`, `Tabs`, `Sheet`, `Skeleton`, `Feedback`, `Provenance`, `DocumentViewer`, `PageImage`, `MessageThread`, `PrescriptionCard`, `Logo`, `fold`, `theme.css` |
| `packages/i18n/src/index.tsx` | Nested catalogues, keys split on `.`, English fallback |
| `packages/api-client/src/index.ts`, `react.tsx` | `createApiClient`, `ApiError`, `AuthProvider` (token in `sessionStorage`) |

---

## 5. Reuse / Adapt / New / Retire Matrix

**REUSE** = used as it is. **ADAPT** = kept, with a change named here.
**NEW** = does not exist. **HIDE** = stays in the repository, not mounted or
shown when `PRODUCT=ip_sakti`. Nothing is deleted.

| Subsystem | Decision | Files | What changes |
|---|---|---|---|
| Auth (tokens, passwords) | **REUSE** | `backend/app/core/security.py`, `api/deps.py::get_current_user`, `packages/api-client/src/react.tsx` | Nothing |
| Roles | **ADAPT** | `backend/app/models/enums.py::UserRole`, `api/deps.py::require_roles`, `packages/shared-types/src/index.ts::Role`, `apps/patient-web/lib/routes.ts` | New role values; `users.role` is VARCHAR + CHECK, so the constraint must be widened by migration |
| User management | **ADAPT** | `backend/app/services/auth_service.py`, `api/v1/auth.py`, `models/user.py` | `users` reused; registration for IP-SAKTI roles is new; patient/doctor registration hidden |
| Consent | **ADAPT** | `backend/app/services/ai_pipeline.py::require_consent`, `set_consent`; `models/patient.py::ai_processing_consent` | Consent is one boolean on the patient profile. IP-SAKTI needs a consent record not tied to a patient → new table, same gate pattern |
| Audit logging | **REUSE** | `backend/app/services/audit.py`, `models/audit.py`, `api/v1/admin.py` (`/audit-events`) | `patient_id` is already optional. Rule "ids and codes, never free text" carries over |
| Storage | **REUSE** | `backend/app/providers/storage/base.py`, `local.py` | Nothing. See risk R7 on ephemeral disk |
| Database | **REUSE** | `backend/app/db/*`, `alembic/` | New tables only |
| API client | **REUSE** | `packages/api-client/src/index.ts`, `react.tsx` | New typed calls added |
| i18n | **REUSE** | `packages/i18n/src/index.tsx`, `catalogs.ts` | New catalogues; machinery unchanged |
| Language normalisation | **ADAPT** | `backend/app/providers/ai/prompts.py` (`language_detection_v1`, `normalization_v2`), `services/normalization_check.py` | Detection reusable as is. Normalisation prompt and the drift check are written for patient health text |
| AI provider abstraction | **ADAPT** | `backend/app/providers/ai/base.py`, `http_base.py`, `__init__.py`, `runtime.py`, `pricing.py`, the three adapters | Add IP-SAKTI capabilities as non-abstract methods, the pattern `summarize_case` already uses. `extract_medical_information` stays for CareBridge |
| Document reader | **REUSE** | `backend/app/providers/documents/pdf_text.py`, `render.py`, `base.py`, `__init__.py` | Nothing |
| OCR / vision | **REUSE with a restriction** | `backend/app/providers/documents/ocr.py`; `transcribe_document_image` in the adapters | OCR output is machine transcription. It may never become approved legal text without a curator checking it against the official source (I-5) |
| Provenance / evidence | **ADAPT** | `backend/app/services/evidence.py`; `packages/ui/src/Provenance.tsx` | Extract the neutral locator; legal citations must accept **only** the exact-match tier (§10, I-1) |
| Consultations | **HIDE**; pattern reused | `backend/app/services/consultation_service.py`, `models/consultation.py`, `api/v1/patients.py`, `doctors.py` | Tables are bound to patient and doctor profiles. Escalation is new, modelled on this state machine |
| Messaging | **HIDE**; pattern reused | `backend/app/api/v1/messages.py`, `models/consultation.py::ConsultationMessage`, `packages/ui/src/MessageThread.tsx` | `MessageThread` component is reusable; the table is not |
| Escalation | **NEW** | — | No escalation exists. Nearest analogue: the consultation request → accept → complete flow |
| Case summary | **HIDE**; pattern reused | `backend/app/services/case_summary.py`, `case_summary_bundle.py`, `summary_validation.py`, `schemas/summary.py`, `models/summary.py`, `apps/patient-web/components/clinician/CaseSummary.tsx` | The bundle → opaque refs → validate → drop pattern is the template for the composer and citation verifier |
| Patient UI | **HIDE** | `apps/patient-web/app/(app)/**`, `components/AppShell.tsx`, `AIAssistPanel.tsx`, `DocumentReadingPanel.tsx`, `ShareSelector.tsx`, `UploadForm.tsx`, `records.tsx` | Not rendered in IP-SAKTI mode |
| Doctor UI | **HIDE** | `apps/patient-web/app/clinician/**`, `components/clinician/**` | Same |
| Admin UI | **ADAPT** | `apps/patient-web/app/admin/**` | Doctor applications hidden; audit view reusable; curator screens new |
| Classification logic | **ADAPT** | `backend/app/conversation/engine.py`, `model.py`, `flow.py` | The engine is pure and domain-neutral, but `model.py` imports `ConversationSection`, `FactCategory`, `FactSubject`. It needs decoupling before a classification flow can use it. The two history flows are hidden |
| Safety / policy | **ADAPT** | `docs/AI_POLICY.md`, `backend/app/schemas/summary.py`, `backend/tests/test_phase4_invariants.py`, `test_phase4_adversarial.py` | Principles carry over; every rule must be restated for legal information |
| Evaluation | **ADAPT** | `backend/evaluation/run_summary_eval.py`, `run_conversation_eval.py`, `backend/tests/test_case_summary_eval_harness.py`, `test_conversation_eval_harness.py` | Harness shape reused; datasets and gates new |
| Offline / demo mode | **REUSE + NEW** | `backend/app/core/config.py::demo_mode`, `effective_ai_provider`; `providers/ai/mock.py` | The switch is reused. Deterministic mock implementations of every new capability, and an offline retriever, are new |
| Landing page and brand | **ADAPT** | `apps/patient-web/components/landing/*`, `app/layout.tsx`, `packages/ui/src/Logo.tsx`, `packages/i18n/messages/common.*.json` (`app.name`) | Product-specific |
| Seed / demo data | **HIDE + NEW** | `backend/app/seed.py`, `synthetic_documents.py`, `scripts/sample-documents/*`, `apps/patient-web/lib/demo.ts` | Healthcare seed stays; IP-SAKTI seed is new |
| Deployment | **ADAPT** | `render.yaml`, `apps/patient-web/vercel.json`, `docs/DEPLOYMENT.md` | A second, separately configured deployment (§11) |

---

## 6. Healthcare-Specific Code Inventory

Nothing in this section is to be deleted.

### A. Infrastructure that can be reused

`backend/app/core/config.py`, `core/security.py`, `core/languages.py`,
`db/base.py`, `db/session.py`, `services/audit.py`, `services/errors.py` (base
classes), `providers/storage/*`, `providers/documents/*`,
`providers/ai/runtime.py`, `pricing.py`, `errors.py`, the three provider
adapters, the generic parts of `providers/ai/http_base.py`
(`_post`, `_build_request`, `_parse_response`, `_complete`, `_loads`),
`models/user.py`, `models/audit.py`, the locator in `services/evidence.py`
(`canonical`, `_comparable_with_offsets`, `_locate`),
`conversation/engine.py`; `packages/api-client`, `packages/i18n/src`,
`packages/ui/src` except `PrescriptionCard.tsx`; `backend/alembic/env.py`;
`backend/tests/conftest.py` (database and client fixtures).

### B. Healthcare domain logic to be replaced or left behind the flag

| Area | Files |
|---|---|
| Medical prompts | `backend/app/providers/ai/prompts.py`: `normalization_v2`, `medical_extraction_v3`, `document_transcription_v1` (wording), `case_summary_v1` |
| Medical provider contract | `backend/app/providers/ai/base.py`: `extract_medical_information`, `ExtractedFact`, `SourceType`; `http_base.py`: `_FactPayload`, `_ExtractionPayload` |
| Offline medical provider | `backend/app/providers/ai/mock.py`, `mock_summary.py`, `lexicon.py` |
| Medical vocabularies | `backend/app/models/enums.py`: `RecordType`, `RecordSource`, `DocumentType`, `FactCategory`, `FactSubject`, `SummarySectionKind`, `SummaryItemOrigin`, `BundleItemKind`, `AuthorizationBasis`, `ConversationSection`, `Sex`, `DoctorApproval`, `ConsultationStatus`, `ShareItemType` |
| Medical validation rules | `backend/app/services/evidence.py` (`_EXPLICIT_ABSENCE_CUES`, `_claims_absence`), `summary_validation.py`, `normalization_check.py`, `ai_facts.py` (`CATEGORY_TO_RECORD_TYPE`, family-history rule) |
| Medical services | `ai_pipeline.py`, `ai_facts.py`, `ai_limits.py` (patient-keyed), `document_pipeline.py` (extraction step), `document_service.py` (ownership), `consultation_service.py`, `case_summary.py`, `case_summary_bundle.py`, `doctor_service.py`, `patient_service.py`, `conversation_service.py`, all `*_presenters.py` |
| Medical question trees | `backend/app/conversation/flows/history_general_v1.py`, `history_general_v2.py` |
| Medical routes | `backend/app/api/v1/patients.py` (17), `doctors.py` (16), `conversations.py` (11), `admin.py` (4 of 5), `ai.py` (5), `document_ai.py` (3), `messages.py` (2), `auth.py` (`register`, `register-doctor`) |
| Medical schemas | `backend/app/schemas/ai.py`, `consultation.py`, `conversation.py`, `doctor.py`, `document.py`, `document_ai.py`, `patient.py`, `summary.py` |
| Synthetic medical data | `backend/app/seed.py`, `synthetic_documents.py`, `scripts/sample-documents/*`, `backend/evaluation/dataset.json`, `document_dataset.json`, `summary_dataset.json`, `summary_cases.py`, `conversation_paths.json` |
| Medical evaluation | `backend/evaluation/run_eval.py`, `run_document_eval.py`, `run_summary_eval.py`, `run_conversation_eval.py` |
| Medical tests | About 40 of the 46 modules in `backend/tests/` exercise healthcare behaviour. Closest to neutral: `test_settings.py`, `test_providers.py`, `test_migrations.py`, `test_evidence_positions.py`, and — though they go through patient and doctor accounts — `test_auth.py` and `test_roles.py` |
| Medical policy documents | `docs/AI_POLICY.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DESIGN.md`, `PRODUCT.md`, `README.md` |

### C. Healthcare UI to hide in IP-SAKTI mode

* Routes: everything under `apps/patient-web/app/(app)/`, `app/clinician/`, and
  the doctor-application part of `app/admin/`.
* Components: `AppShell.tsx`, `AIAssistPanel.tsx`, `DocumentReadingPanel.tsx`,
  `ShareSelector.tsx`, `UploadForm.tsx`, `records.tsx`, `DoctorDetailsFields.tsx`,
  everything in `components/clinician/`, `components/landing/LandingPage.tsx`
  and `FoldScene.tsx`.
* Shared: `packages/ui/src/PrescriptionCard.tsx`.
* Text: `packages/i18n/messages/patient.{en,hi,ta}.json`, `doctor.en.json`, and
  the medical disclaimers in `common.{en,hi,ta}.json` (`notDiagnosis`).
* Brand: "Asclepius" in `app/layout.tsx` metadata, `packages/ui/src/Logo.tsx`,
  `common.*.json` → `app.name`, about eleven sentences in each
  `patient.*.json`, and the session key `asclepius.session` in
  `app/providers.tsx`.
* Demo shortcuts: `apps/patient-web/lib/demo.ts`.

The internal package scope `@carebridge/*` (228 occurrences in 83 files) is an
import name users never see. **Do not rename it**: it would touch every file
for no visible effect and would make every later merge with `main` conflict.

### D. Healthcare tables that stay intact for CareBridge compatibility

All nineteen: `patient_profiles`, `doctor_profiles`, `doctor_languages`,
`medical_records`, `medical_documents`, `document_extractions`,
`document_pages`, `ai_artifacts`, `ai_extracted_facts`, `consultations`,
`consultation_shares`, `consultation_messages`, `prescriptions`,
`prescription_items`, `consultation_summaries`, and the four
`conversation_*` tables. Every one of them hangs off `patient_profiles` or
`doctor_profiles` through a non-nullable foreign key (directly or through its
parent), which is why none can hold an IP-SAKTI entity without being altered —
and why none should be.

`users` and `audit_events` are shared by both products.

---

## 7. IP-SAKTI Requirement Gap Analysis

| # | Requirement | Status | Basis in the repository |
|---|---|---|---|
| 1 | Multilingual IP/regulatory assistant | **Completely new** (domain); partially exists (multilingual plumbing) | No legal or IP logic anywhere |
| 2 | India / International jurisdiction separation | **Completely new** | No notion of jurisdiction exists |
| 3 | Product / formulation classification | **Partially exists** | The deterministic engine in `backend/app/conversation/` fits a rule-based classifier; the taxonomy is not defined (§21, Q3) |
| 4 | Versioned legal corpus | **Completely new** | Nearest pattern: versioned, fingerprinted flows (`conversation/flow.py::PUBLISHED`) and superseded document pages |
| 5 | Source-grounded retrieval | **Completely new** | No retrieval, search or embedding code exists |
| 6 | Exact citation verification | **Exists but needs adaptation** | `services/evidence.py::_locate`; must be restricted to its exact tier |
| 7 | Time-aware provisions | **Completely new** | Nearest pattern: staleness computed, never stored (D-054) |
| 8 | Legal-text integrity | **Partially exists** | Upload hashing and the integrity check before every read (`document_pipeline.py::load_original`); exact text-layer copy (`providers/documents/pdf_text.py`) |
| 9 | No legal advice | **Exists but needs adaptation** | Closed schemas with `extra="forbid"` (`schemas/summary.py`); "no field can express a conclusion" tests (`test_phase4_invariants.py`) |
| 10 | Safe abstention | **Partially exists** | Summaries fail closed; AI failure degrades to the original text (`case_summary.py::_fail`, `ai_pipeline.py::record_failure`) |
| 11 | Confidence scoring | **Completely new** | Providers return a `confidence` number; nothing computes a calibrated answer confidence. Formula undefined (§21, Q5) |
| 12 | Human IP facilitator escalation | **Partially exists** (as a pattern) | Consultation request → accept → message → complete; human authorship attribution |
| 13 | Curator corpus workflow | **Partially exists** (as a pattern) | Administrator approval of doctor applications (`doctor_service.py::review_application`) |
| 14 | Auditability | **Already exists and reusable** | `services/audit.py`, `models/audit.py`, admin audit view |
| 15 | `DEMO_MODE` / offline demonstration | **Exists but needs adaptation** | Switch and pattern exist; every new capability needs a deterministic offline implementation |
| 16 | EN / HI / TA support | **Exists but needs adaptation** | UI machinery and three scripts' fonts exist; every IP-SAKTI string is new and needs native-speaker review |
| 17 | Product profile | **Completely new** | — |
| 18 | ABS helper | **Not required for MVP** (Stage 2 in the instruction) | — |
| 19 | TKDL / prior-art pointer | **Not required for MVP** (Stage 2) | — |
| 20 | Evaluation harness | **Exists but needs adaptation** | Four harnesses with hard gates and "the harness can fail" tests |

---

## 8. Domain Model Mapping

| Target concept | Decision | Existing model | Notes and migration risk |
|---|---|---|---|
| `users` | **REUSE** | `users` (`models/user.py`) | — |
| `roles` | **ADAPT** | `UserRole` enum: `patient`, `doctor`, `admin` | New values need the `ck_users_user_role` CHECK widened. Additive, but it is the one change to a shared table. Role names undefined (§21, Q4) |
| `consent` | **NEW** | boolean on `patient_profiles` | A separate consent table for IP-SAKTI users. Do not add columns to `patient_profiles` |
| `audit_log` | **REUSE** | `audit_events` | `patient_id` stays null for IP-SAKTI events |
| `instrument` | **NEW** | — | An Act, Rules, regulation or treaty. Carries jurisdiction lane and issuing authority |
| `provision` | **NEW** | — | A stable, addressable unit of an instrument. Its identifier scheme must come from the official text, not be invented |
| `provision_version` | **NEW** | pattern: `document_pages` superseding | The text as it stood between `valid_from` and `valid_to`. Immutable once approved |
| `provision_status_event` | **NEW** | pattern: append-only `consultation_summaries` | Enacted, amended, substituted, omitted, stayed, struck down, restored… — the vocabulary needs a legal reviewer (§21, Q7) |
| `corpus_document` | **NEW** | pattern: `medical_documents` (`sha256`, `storage_reference`) | The official source file with authority, URL, retrieval date, hash. `medical_documents` cannot be reused: `patient_id` is non-nullable |
| `chunk` | **NEW** | — | A retrieval unit derived from exactly one `provision_version`; never crosses a version or a lane |
| `glossary_term` | **NEW** | pattern: `providers/ai/lexicon.py` (in code) | Curated EN/HI/TA terminology; curator-approved |
| `product_profile` | **NEW** | — | What the user says about their product. Synthetic in demo |
| `classification_session` | **NEW**; engine **ADAPT** | `conversation_sessions` (patient-scoped) | New tables; the pure engine reused after decoupling |
| `question` | **NEW** | — | The user's question as asked, with language; never overwritten (the "original is never overwritten" rule carries over) |
| `answer` | **NEW** | pattern: `consultation_summaries` + `ai_artifacts` provenance | One lane each; `ai_artifacts` cannot be reused (`patient_id` non-nullable) |
| `answer_point` | **NEW** | pattern: summary items | No advice fields (I-2) |
| `citation` | **NEW** | pattern: `ai_extracted_facts.evidence_*` | `provision_version_id`, `quoted_span`, offsets computed by the application |
| `escalation` | **NEW** | pattern: `consultations` + `consultation_messages` | — |

**Migration risks**

1. **`0008` and `0009` are not committed.** Any IP-SAKTI migration would revise
   `0009`, which exists only in a working tree.
2. **Divergent heads.** If `main` later gains its own `0010`, the two branches
   have different heads. Give IP-SAKTI revisions a distinct prefix and an
   Alembic branch label, or agree that `main` is frozen for the hackathon.
3. **Widening `users.role`** is the only change to a table CareBridge uses. It
   is additive and reversible while no row has a new role; the downgrade must
   refuse rather than delete users (the rule migration `0009` already follows,
   D-075).
4. **Time ranges.** "No two versions of one provision valid at the same time" is
   naturally a PostgreSQL exclusion constraint, which needs the `btree_gist`
   extension and cannot be expressed in SQLite, where the fast test suite runs.
   Enforce in the service and test on PostgreSQL; add the constraint only if
   the hosted database permits the extension.
5. **One schema, two products.** Both products' tables would live in one
   database. That is what keeps switching `PRODUCT` migration-free, but it means
   the IP-SAKTI deployment's database also contains empty healthcare tables.

---

## 9. Target Architecture Mapping

```
Question → Scope Guard → Classifier → Planner → India Retriever ─┐
                                              → International ───┤
                                                  Retriever      ▼
                 Escalation ← Answer Panels OR Abstain ← Confidence ← Citation Verifier ← Composer
```

| Stage | Existing support | New module needed |
|---|---|---|
| **Question** intake | "Original words are never overwritten"; language detection (`language_detection_v1`); consent gate; audit | Question model and route |
| **Scope guard** | Injection handling patterns (D-056; `tests/test_case_summary_injection.py`) | Entirely new. Must be deterministic first, and must run before any provider is called |
| **Classifier** | `conversation/engine.py` — declared branches, reason codes, versioned and fingerprinted flows, invariant tests | Classification flow(s) as data; session tables. Taxonomy undefined (§21, Q3) |
| **Planner** | — | Entirely new: decides which lane(s) and which instruments a question touches |
| **India retriever** / **International retriever** | — | Entirely new. Two instances over disjoint partitions; see I-3 |
| **Composer** | `AIProvider` + `HttpJSONProvider._complete`; opaque handles (`case_summary_bundle.py`); closed schema (`schemas/summary.py`); deterministic mock | New capability on the provider; new prompt; new deterministic offline composer |
| **Citation verifier** | `services/evidence.py::_locate`; "drop, never repair" (`summary_validation.py`) | New module using the exact tier only |
| **Confidence** | — | Entirely new, deterministic, computed from verifiable signals only |
| **Answer panels / abstain** | Fail-closed summary states; five UI states in `CaseSummary.tsx` | New schemas and screens |
| **Escalation** | Consultation state machine; messaging; attribution of human authorship (`SummaryItemOrigin`, D-053); `MessageThread.tsx` | New tables, service, facilitator queue |
| Cross-cutting: provider resilience | `providers/ai/runtime.py` (timeout, retry, circuit breaker) | Reused |
| Cross-cutting: budgets | `services/ai_limits.py` | Adapt: keyed on patient today |
| Cross-cutting: caching | `ai_pipeline.py::cache_key` includes prompt version | Adapt: the key must also include the corpus version, or an answer could outlive the law it cited |

**Proposed location.** One new backend package, `backend/app/sakti/`, holding
its own `models/`, `schemas/`, `services/`, `pipeline/`, `retrieval/`, `api/`
and `seed.py`, with one rule enforced by a test: `app.sakti` may import shared
infrastructure; healthcare modules and shared infrastructure may not import
`app.sakti`. `backend/app/models/__init__.py` imports the new models so Alembic
sees them. This is a proposal for approval, not a decision taken.

---

## 10. Safety Invariant Mapping

Where each invariant would be enforced. Nothing here is implemented.

**I-1 — every answer point has a valid `provision_version_id` and an exact `quoted_span`.**
* *Database:* `citation.provision_version_id` non-nullable foreign key;
  `answer_point` cannot exist without at least one citation (enforced in the
  service inside one transaction, tested on PostgreSQL).
* *Application:* a citation verifier adapted from
  `backend/app/services/evidence.py`. That locator has three tiers — exact,
  whitespace-tolerant, and case/Unicode-folded — and today the looser tiers are
  accepted or sent for review. **For legal text only the first tier,
  `source.find(quote)`, may count.** Offsets are computed by the application
  and the model's are ignored (D-049).
* *Model boundary:* the composer receives opaque handles for retrieved
  provision versions, never database ids (D-052), so it cannot cite a version
  it was not given.
* *Failure:* an unverifiable point is dropped, never repaired; with none left
  the answer becomes an abstention. Pattern: `summary_validation.py`.

**I-2 — no legal advice; no `recommendation` / `advice` / `next_steps` fields.**
* Closed Pydantic models with `extra="forbid"` at three layers (what a provider
  may return, what is stored, what a browser receives), as
  `backend/app/schemas/summary.py` does.
* A test that walks every IP-SAKTI schema and fails on a forbidden field name,
  as `tests/test_phase4_invariants.py` does for clinical fields.
* A schema cannot stop advice phrased inside a free-text field. Phase 4's lesson
  (D-055, D-056) was that a word-list check is both too weak and too strict.
  The structural defence is to give points **no free-text field that can carry
  a conclusion** — which depends on Q6 in §21.

**I-3 — India and International retrieval stay separate; citation lane equals answer lane.**
* *Database:* `jurisdiction` on `instrument`, carried onto `provision_version`
  and `answer`, with a composite foreign key from `citation` to
  `(provision_version_id, jurisdiction)` and from `citation` to its answer's
  lane, so a cross-lane citation is a constraint violation, not a bug to catch.
* *Application:* two retriever instances, each constructed with one lane and
  unable to query the other; the composer is called once per lane with that
  lane's handles only.
* *Evaluation:* a hard gate, "jurisdiction leakage must be 0", modelled on
  Phase 4's "unauthorised source leakage must be 0" with decoy provisions.

**I-4 — provisions are time-aware.**
* `provision_version.valid_from` / `valid_to` and append-only
  `provision_status_event`.
* "In force on date D" is **computed** from those, never stored as a flag that
  can go stale (D-054).
* Every answer records the as-of date it was computed for; retrieval takes the
  date as a required argument with no default.

**I-5 — legal text is never generated.**
* Provision text enters only through curator ingestion of a `corpus_document`
  with authority, source URL, retrieval date and SHA-256, using the existing
  reader (`providers/documents/pdf_text.py` copies a PDF text layer exactly).
* OCR and vision output is machine transcription and is stored as *unverified*;
  it cannot be approved without a curator checking it against the source.
* An approved `provision_version` is immutable. A correction is a new version.
* No provider capability returns statutory text: the composer returns handles
  and quotations, and the quotation is then verified under I-1.
* Anything not approved is excluded from retrieval by the query itself, not by
  a filter a caller could forget.
* **Tests need text too, and must not invent law.** Test fixtures use an
  explicitly fictional instrument marked as a fixture, loadable only when
  `APP_ENV=test`, so invented wording can never be served as law.

**I-6 — human authority is explicitly attributed.**
* Escalation replies carry the facilitator's identity and role, the way doctor
  authorship is carried today (`DoctorAttribution`, `SummaryItemOrigin`, D-053).
* Machine-composed and human-written content are different record types and are
  rendered differently; `packages/ui/src/Provenance.tsx` already draws that
  distinction.

**I-7 — offline `DEMO_MODE`: question → classification → cited answer → escalation.**
* `Settings.effective_ai_provider` already pins the mock.
* New: a deterministic offline implementation of each new capability, and a
  retriever that needs no network — lexical retrieval over approved chunks, in
  process, which also keeps SQLite tests and PostgreSQL behaviour identical.
* The demo corpus must still be real approved text (I-5). "Synthetic demo data"
  applies to users, products and questions — never to law.

**I-8 — no client-side secrets; synthetic demo data.**
* Already the rule: keys are `SecretStr` in `core/config.py`, never serialised;
  the only browser-visible variables are `NEXT_PUBLIC_API_BASE_URL` and
  `NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS`. A `NEXT_PUBLIC_PRODUCT` flag is not a secret.
* Standing rule kept: scan every outgoing diff for key patterns and `.env`
  values before any push.

---

## 11. Feature Flag Strategy

**One setting, two values, default unchanged.**

```
PRODUCT=carebridge   (default — today's behaviour, byte for byte)
PRODUCT=ip_sakti
```

| Layer | Boundary | Files |
|---|---|---|
| Backend setting | `product` on `Settings`, validated to the two values | `backend/app/core/config.py` |
| Backend routes | Shared routers always; healthcare routers only for `carebridge`; IP-SAKTI routers only for `ip_sakti`. Routes of the other product are not mounted, so they answer 404 | `backend/app/api/v1/router.py` |
| Backend identity | API title and description | `backend/app/main.py` |
| Backend data | One schema containing both products' tables, so switching needs no migration | `backend/alembic/` |
| Seed | Product-specific seed | `backend/app/seed.py` (healthcare, unchanged), new IP-SAKTI seed |
| Frontend setting | `NEXT_PUBLIC_PRODUCT`, inlined at build time | web app environment |
| Frontend routes | Healthcare route groups stay where they are; IP-SAKTI screens in a new route group; each group's layout refuses to render for the other product | `apps/patient-web/app/(app)/layout.tsx`, `app/clinician/(workspace)/layout.tsx`, `app/admin/layout.tsx`, new group |
| Navigation | One nav array per product | `apps/patient-web/components/AppShell.tsx`, `clinician/DoctorShell.tsx`, new shell |
| Landing and sign-in | Product-specific landing; role options per product | `apps/patient-web/app/page.tsx`, `app/login/page.tsx`, `lib/routes.ts` |
| Brand | Name, logo, metadata, theme colour | `packages/i18n/messages/common.*.json` (`app.name`), `packages/ui/src/Logo.tsx`, `apps/patient-web/app/layout.tsx` |
| Text | A separate catalogue set for IP-SAKTI | `packages/i18n/messages/`, `packages/i18n/src/catalogs.ts` |
| Tests | Existing tests run with `PRODUCT=carebridge`; IP-SAKTI tests set their own | `backend/tests/conftest.py` |
| Deployment | A second Vercel project and a second Render service + database with `PRODUCT=ip_sakti`. The existing deployment is not reconfigured | `render.yaml`, Vercel settings |

**IP-SAKTI mode would expose:** IP-SAKTI branding, Ask, Classify, My Product,
India, International, Escalate, Curator, Facilitator.

**Two safeguards to build with the flag**

* A test that every healthcare endpoint is absent from the OpenAPI document
  when `PRODUCT=ip_sakti`, and every IP-SAKTI endpoint absent when
  `carebridge`.
* The full existing suite keeps passing with the flag unset. That is the
  regression gate for every later phase.

---

## 12. Database Migration Strategy

* **Additive only.** New tables through new revisions after `0009`. No column is
  added to, removed from or renamed in any healthcare table.
* **One exception to decide:** widening the `users.role` CHECK constraint
  (§8, risk 3).
* **Conventions already in force, to be kept:** enumerations as VARCHAR + CHECK
  (D-004); constraint names from the naming convention in
  `backend/app/db/base.py`; CHECK changes written by hand because autogenerate
  cannot see them (as in `0003` and `0009`); every revision reversible and
  tested base → head → base → head on PostgreSQL; `alembic check` for drift; a
  downgrade refuses rather than destroy data someone wrote (D-075).
* **Immutability in the schema where it is cheap:** approved provision versions
  never updated; status events append-only; partial unique indexes for "one
  current row" rules, as `0009` uses.
* **Revision naming:** a distinct prefix and an Alembic branch label for
  IP-SAKTI revisions, so a later merge with `main` is a deliberate merge
  revision rather than two competing `0010`s.
* **No migration is created in Phase 0.**

---

## 13. API Migration Strategy

* Keep `/api/v1` and the existing conventions: thin routes, all rules in
  services, domain errors translated once in `backend/app/main.py`, Pydantic
  models with `extra="forbid"`, the patient/actor resolved from the token and
  never from the request body, "not found" rather than "forbidden" for another
  user's resource.
* IP-SAKTI routes under their own prefix inside `/api/v1`, in routers mounted
  only for `PRODUCT=ip_sakti`.
* `auth` and `meta` are shared. `POST /auth/register` and
  `POST /auth/register-doctor` are healthcare registration and are unmounted in
  IP-SAKTI mode; IP-SAKTI registration is a new endpoint.
* The server decides every transition (D-061): a client states what it is
  answering or asking, never what comes next, never a jurisdiction to skip,
  never a confidence, never a citation.
* Idempotency keys and the versioned-row concurrency pattern from Phase 5
  (D-073) apply to classification sessions and escalations.
* `packages/shared-types/src/index.ts` is hand-written and already 783 lines.
  IP-SAKTI types go in a separate file in that package rather than lengthening it.

---

## 14. Frontend Migration Strategy

* **One app, two products, chosen at build time.** Healthcare route groups are
  not moved or renamed.
* **Reuse:** `packages/ui` components and tokens, the i18n machinery, the API
  client and auth context, the three-script font setup in `app/layout.tsx`, the
  language switcher.
* **New:** an IP-SAKTI route group and shell; screens for Ask, Classify, My
  Product, the India and International panels, Escalate, Curator and
  Facilitator; a product-specific landing page.
* **Design.** The current design system ("Folded Sheet") encodes *provenance* —
  whose words these are, what is machine output, what a human confirmed. That
  idea transfers directly to "official text / machine-composed / human
  facilitator". The medical metaphors and the brand do not. Whether to reuse
  the visual system or commission a new direction is a product decision
  (§21, Q9); `PRODUCT.md` and `docs/DESIGN.md` describe the healthcare product
  only.
* **Two lanes must look like two lanes.** India and International are separate
  panels that can never be merged into one list — a rule to write into the
  components, not leave to layout.
* **Accessibility baseline to keep:** the healthcare screens passed axe with no
  violations at the Phase 4 freeze; new screens meet the same bar.
* **No UI work in Phase 0.**

---

## 15. Legal Corpus Strategy

**Nothing was fetched, copied or summarised in Phase 0.** This section lists
what must be obtained, from whom, and what must be recorded about it. It states
no section number, no wording and no current status of any instrument.

**Rules for every item**

* Text comes only from the issuing authority's official publication.
* A curator records: authority, official source location, retrieval date, the
  exact file, its SHA-256, the date the text is stated to be current to, and the
  amending instruments it incorporates.
* A second person approves before the text can be retrieved or cited.
  *(Phase 2: a setting, `CORPUS_SEPARATE_APPROVER`, off by default until a legal
  reviewer is named — see §23 and D-084.)*
* Status is a sequence of dated events taken from official notifications and
  orders. It is never inferred, and never asserted by the system without a
  source.
* Reuse terms differ between authorities and must be checked before any text is
  committed to a public repository or shown in a public demo (§21, Q8).

### India lane

| Corpus item | Source authority (to be confirmed by the curator) | Version / date needed | Approval | Status tracking |
|---|---|---|---|---|
| Patents Act | Legislative Department (India Code); Office of the Controller General of Patents, Designs and Trade Marks | Consolidated text current to a recorded date, plus each amending Act needed for time-aware answers | Curator + legal reviewer | Amendments, commencement dates |
| Patents Rules and relevant amendments | Same Office; Gazette of India | Rules as amended to a recorded date; each amending notification | Same | Each amendment as a dated event |
| Drugs and Cosmetics Act and Rules | Ministry of Health and Family Welfare / CDSCO; Ministry of Ayush for Ayurveda, Siddha and Unani matters; Gazette of India | As above | Same | As above |
| Rule 170 — history and status | Gazette of India notifications; court orders | Every notification and order affecting it, each as its own dated event | Curator + legal reviewer; **highest scrutiny** | Its status has changed over time and has been before the courts. The corpus must carry each event from its primary source. This plan asserts no current status |
| Trade Marks framework | Office of the Controller General of Patents, Designs and Trade Marks; India Code | Act and Rules current to a recorded date | Same | Amendments |
| Geographical Indications framework | Geographical Indications Registry; India Code | Same | Same | Amendments |
| Biological Diversity framework | Ministry of Environment, Forest and Climate Change; National Biodiversity Authority | Act, Rules and access-and-benefit-sharing instruments current to a recorded date | Same | Amendments and commencement |
| FSSAI / Ayurveda Aahara material | Food Safety and Standards Authority of India | Regulations and amendments current to a recorded date | Same | Amendments; operationalisation dates |
| Drugs and Magic Remedies framework | India Code; the administering ministry | Act and Rules current to a recorded date | Same | Amendments |

### International lane

| Corpus item | Source authority | Version / date needed | Approval | Status tracking |
|---|---|---|---|---|
| TRIPS | World Trade Organization | Authentic text including any amendment in force | Curator + legal reviewer | Amendments; India's acceptance |
| Convention on Biological Diversity | CBD Secretariat | Authentic text | Same | India's party status and date, from the depositary |
| Nagoya Protocol | CBD Secretariat | Authentic text | Same | Entry into force; India's party status and date |
| WIPO GRATK Treaty | World Intellectual Property Organization | Adopted text | Same | **Adoption, signature, ratification and entry into force are separate events** and must each come from WIPO. Whether it is in force, and for whom, must not be assumed |
| Patent Cooperation Treaty | WIPO | Treaty and Regulations current to a recorded date | Same | Regulation amendments; India's status |
| Madrid system | WIPO | Protocol and Regulations current to a recorded date | Same | Same |
| Hague system | WIPO | Applicable Act(s) and Regulations | Same | India's membership status must be verified, not assumed |
| Budapest Treaty | WIPO | Treaty and Regulations | Same | India's status |
| Relevant EU framework | EUR-Lex (Publications Office of the EU) | The instruments are **not named in the Phase 0 instruction** and must be specified (§21, Q2) | Same | Consolidated versions and amendments |

**Open design point.** "International" covers both treaties and a foreign
regional legal order (the EU). These behave differently — a treaty binds
states, EU law binds in the EU — so an instrument needs a sub-type within its
lane, and the lane label alone must never imply that a provision applies in India.

---

## 16. Multilingual Strategy

**What exists**

* `LanguageCode` with 12 codes (`backend/app/core/languages.py`), three of them
  with a user interface: English, Hindi, Tamil.
* Nested catalogues with English fallback; fonts for Latin, Devanagari and Tamil
  loaded only when their glyphs appear.
* Language detection and English normalisation prompts, and a meaning-drift
  check between the original and its English rendering.
* Standing rules: the user's original words are never overwritten; machine
  translation is labelled as machine output; no English sentence is written into
  stored data as though it were the user's own (D-065, D-069).

**What IP-SAKTI needs**

* **The question** is kept exactly as asked, with its language. An English
  rendering for retrieval is a labelled machine artifact.
* **The law is quoted in the language of the official text.** A quotation is
  never translated and presented as the provision (I-5). Whether a translated
  gloss may appear beside it is Q6 in §21.
* **Interface text** in English, Hindi and Tamil from new catalogues. Hindi and
  Tamil legal and regulatory terminology must be reviewed by competent native
  speakers; machine-drafted legal vocabulary is a real risk, not a formality.
* **`glossary_term`** holds curated term equivalents so the same concept is
  rendered the same way every time; it is corpus material and goes through
  curator approval.
* **Codes, not sentences:** reasons, statuses and abstention causes travel as
  codes and are rendered in the browser, as in Phase 5.
* **Catalogue keys** are nested and split on `.`; a key cannot be both a string
  and a group. Phase 5 has a test for that (`tests/test_conversation_tree.py`);
  the same check applies to IP-SAKTI keys.

---

## 17. Evaluation Strategy

Keep the form the repository already uses: a dataset whose expectations are
written by hand and never generated by the system under test, a runner that
works offline, results that are pass/fail rather than a percentage, and tests
that break the system deliberately to prove each gate can trip.

**Hard gates proposed (each must be 0)**

| Gate | Guards |
|---|---|
| Unverified citation served | I-1 |
| Answer point without a citation | I-1 |
| Advice field or advisory conclusion present | I-2 |
| Jurisdiction leakage (a citation outside its answer's lane) | I-3 |
| Provision cited outside its validity on the as-of date | I-4 |
| Text served that is not an approved provision version | I-5 |
| Machine content presented as human, or human content unattributed | I-6 |
| Network call made in `DEMO_MODE` | I-7 |
| Answered when it should have abstained (out of scope, no support) | Safe abstention |
| Nondeterminism in `DEMO_MODE` | I-7 |

**Measured, not gated:** retrieval recall on a labelled question set, abstention
rate on answerable questions, classification agreement with a labelled set,
escalation rate, latency.

**Decoys, as in Phase 4:** the corpus for evaluation carries provisions that
look relevant but belong to the other lane, or were superseded, so leakage is
measured rather than assumed.

**Who writes the expectations matters.** Whether a question is answerable from
a given provision is a legal judgement. The labelled set needs a legal
reviewer; engineers can build the harness, not the ground truth.

---

## 18. Phase-by-Phase Migration Plan

None of these phases is executed by this document.

### Phase 1 — Re-domain the application shell

| | |
|---|---|
| Prerequisites | Approval of this plan; Q1 (where Phase 5 is committed) and Q4 (role names) answered |
| Backend | `core/config.py` (the `product` setting), `api/v1/router.py` (conditional mounting), `main.py` (title), the new package skeleton, `tests/conftest.py` |
| Database | At most the `users.role` CHECK widening; otherwise none |
| API | Healthcare routers unmounted in IP-SAKTI mode; an IP-SAKTI registration and a health/identity endpoint |
| Frontend | `NEXT_PUBLIC_PRODUCT`, a new route group and shell with empty screens for the nine destinations, product-specific landing, brand and catalogues |
| Tests | Flag tests on both values; OpenAPI surface test; the full existing suite unchanged with the flag unset |
| Safety gates | I-8 (no secret reaches the client); no legal content of any kind yet |
| Demo impact | None on the CareBridge demo. IP-SAKTI shows navigation and empty states only |
| Rollback | Unset `PRODUCT`. Revert the branch. `main` is untouched throughout |

### Phase 2 — Legal corpus and ingestion

*Built 2026-10-01 — see §23 for what was built and where it departs from this table.*

| | |
|---|---|
| Prerequisites | A named curator and legal reviewer; Q2, Q7, Q8 answered; official source files in hand |
| Backend | New models (`instrument`, `provision`, `provision_version`, `provision_status_event`, `corpus_document`, `chunk`, `glossary_term`); ingestion service using `providers/documents`; curator approval service modelled on `doctor_service.review_application` |
| Database | New tables; validity and immutability rules |
| API | Curator endpoints: upload source, propose provisions and versions, approve, record status events |
| Frontend | Curator screens |
| Tests | Integrity (hash before every read), immutability of approved text, validity-range rules, approval transitions, "unapproved text is unreachable" |
| Safety gates | I-4, I-5 |
| Demo impact | A small, real, approved corpus is the minimum for any later demo |
| Rollback | Drop the new tables (they hold no user data). Source files remain in storage |

### Phase 3 — Product / formulation classifier

*Built 2026-10-01 — see §24 for what was built and where it departs from this table.*

| | |
|---|---|
| Prerequisites | Q3 (the taxonomy and its authority); decoupling of `conversation/model.py` from medical enums |
| Backend | The engine reused; classification flow(s) as declared data with fingerprints; `product_profile`, `classification_session` and their service |
| Database | New tables |
| API | Start, answer, review, complete — the Phase 5 shape |
| Frontend | Classify and My Product |
| Tests | Branch coverage, determinism, invariants, idempotency, concurrency — the Phase 5 suites as a template |
| Safety gates | A classification is a *category the user's own answers lead to*, shown with the reasons; it is not a legal determination. I-2 applies to its wording |
| Demo impact | First interactive IP-SAKTI feature; fully offline |
| Rollback | Unmount the router; drop the tables. The healthcare flows are not touched — they are immutable and fingerprinted |

### Phase 4 — Dual-lane cited answer MVP

| | |
|---|---|
| Prerequisites | Phase 2 corpus approved; Q5 and Q6 answered |
| Backend | Scope guard, planner, two retrievers, composer capability on `AIProvider` with a deterministic offline implementation, citation verifier, confidence, abstention; `question`, `answer`, `answer_point`, `citation` |
| Database | New tables with the cross-lane constraint |
| API | Ask; read an answer with its two panels |
| Frontend | Ask, India panel, International panel, abstention state |
| Tests | Every invariant as a test; adversarial tests for injection through the question and through corpus text |
| Safety gates | I-1, I-2, I-3, I-4, I-5, I-7 — all of them, before any demo |
| Demo impact | The core demonstration |
| Rollback | Unmount; drop tables. No effect on the corpus or the classifier |

### Phase 5 — Facilitator escalation

| | |
|---|---|
| Prerequisites | Q4 (who a facilitator is and how they are approved) |
| Backend | `escalation` with a state machine modelled on `consultation_service.py`; facilitator queue; attributed replies |
| Database | New tables |
| API | Escalate, queue, accept, reply, close |
| Frontend | Escalate and Facilitator; `MessageThread` reused |
| Tests | Authorization (only the asker and the assigned facilitator), attribution, state transitions |
| Safety gates | I-6. A facilitator's reply is a human's statement and is labelled as one; what a facilitator may say is outside the system's control and must be governed by policy, not code |
| Demo impact | Completes question → classification → cited answer → escalation |
| Rollback | Unmount; drop tables |

### Phase 6 — Evaluation harness and gates

| | |
|---|---|
| Prerequisites | A labelled question set written with a legal reviewer |
| Backend | `backend/evaluation/` runner and dataset; harness tests |
| Tests | Each gate proven able to fail |
| Safety gates | All ten in §17 at 0 |
| Demo impact | The evidence behind every claim made to judges |
| Rollback | None needed; read-only |

### Stage 2 — knowledge graph, agents, ABS helper, TKDL pointer, change watcher

Each needs its own design. Two cautions now: a **change watcher** must never
alter approved text on its own — it may only raise an item for a curator; and a
**TKDL pointer** points to an external resource whose access terms must be
checked before anything is built on it.

### Stage 3 — paid sources, more languages, voice, markets, kiosks

Out of scope for planning until Stage 1 is demonstrated. Paid sources bring
licence terms that may forbid storing or displaying text; voice adds a
transcription step whose errors must not reach a legal question unconfirmed.

---

## 19. Risks and Mitigations

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | The legal corpus cannot be assembled and approved in time | High / blocks Phases 2–6 | Start now; scope the demo corpus to a few instruments; name the curator and reviewer before Phase 1 ends |
| R2 | The build brief never arrives and designs are guessed | Medium / high | §21 lists every blocked decision; do not begin Phases 3–4 without answers |
| R3 | Phase 5 work is lost or ends up on the wrong branch | Medium / high | Decide Q1 and commit before any further work |
| R4 | A wrong or superseded provision is shown as law | — / severe | I-1, I-4, I-5 as constraints and gates; two-person approval; immutable versions |
| R5 | An answer reads as legal advice | Medium / severe | I-2 structurally; no free-text conclusion field; abstention by default; facilitator for anything beyond the text |
| R6 | Jurisdiction leakage | Medium / high | Database constraint, not just code; separate retrievers; a hard gate with decoys |
| R7 | The hosted free tier loses uploaded files on restart and its database expires after 30 days | High / medium | Re-ingest the approved corpus at start from a controlled source, or use a paid instance with a disk for the judged demo |
| R8 | Hindi and Tamil legal terminology is wrong | High / medium | Native-speaker review; curated glossary; quote the official text untranslated |
| R9 | Reuse terms forbid storing or showing some official texts | Unknown / high | Check per authority before committing any text (Q8) |
| R10 | The healthcare product breaks while the shell is re-domained | Low / high | Flag defaults to `carebridge`; the full existing suite is the gate for every phase |
| R11 | OCR output is mistaken for official text | Medium / severe | Unverified by default; cannot be approved without comparison to the source |
| R12 | Prompt injection through a question or through corpus text | Medium / high | Scope guard before any provider call; composer sees handles, not instructions; quotations verified after the fact |
| R13 | Two migration heads when branches meet | Medium / medium | Prefixed revisions and a branch label, or freeze `main` |
| R14 | Test flakiness hides a real failure | Medium / medium | See §3; run frontend tests on their own before trusting a red or a green |
| R15 | The portable test database disappears again | High / low | Provide PostgreSQL through `docker-compose.yml`, which already defines it |

---

## 20. Rollback Strategy

* **`main` is the rollback.** It is at `e6434e1`, equal to `origin/main`, and is
  not touched by any phase. The deployed CareBridge demo is built from it.
* **Phase 0** is undone by deleting this file and the `ip-sakti` branch. The
  uncommitted Phase 5 work is in the working tree, not on the branch, and
  survives switching back to `main`.
* **Every later phase is additive**, so its rollback is: unset `PRODUCT`
  (immediate, no deploy of old code needed), then revert the phase's commits,
  then downgrade its migrations. IP-SAKTI tables hold no healthcare data.
* **Downgrades refuse rather than destroy** anything a person wrote.
* **Deployments are separate.** The IP-SAKTI deployment has its own service and
  database, so nothing done to it can affect the CareBridge one.
* **Before each phase:** a tag on the last green commit, and a full baseline run
  recorded as in §3.

---

## 21. Open Questions

**Must be answered before Phase 1**

- **Q1.** **Where is Phase 5A/5B committed?** It is approved (5A) or awaiting approval
  (5B) healthcare work, uncommitted, currently sitting in the working tree of
  `ip-sakti`. Options: (a) commit it to `main` first, then rebase `ip-sakti`
  onto it — cleanest, but it modifies `main`, which this phase was told not to
  do; (b) commit it on `ip-sakti` only — `main` stays untouched, but CareBridge's
  Phase 5 then lives only on the IP-SAKTI branch; (c) a separate
  `carebridge-phase-5` branch from `main`, with `ip-sakti` branched from that.
  IP-SAKTI's classifier depends on this code and on migrations `0008`–`0009`.
  **Answered 2026-10-01: option (c).** Phase 5 was committed as `48f2a90` on
  `carebridge-phase-5`, branched from `main` at `e6434e1`; `ip-sakti` was
  fast-forwarded onto it. `main` was not touched.
- **Q2.** **Can the build brief be supplied?** And in particular: which EU instruments
  are "the relevant EU framework"?
  *Partly answered 2026-10-01: the only IP-SAKTI document found is the team's
  SIH26045 idea deck (§23). It names no EU instrument and supplies no source
  file.*
- **Q4.** **What are the roles?** The instruction names an end user implicitly, a
  facilitator and a curator. Their names, who approves a facilitator, and
  whether the administrator role is kept, are not defined.

**Must be answered before the phase named**

- **Q3.** *(Phase 3)* **What is the classification taxonomy, and on whose authority?**
  The categories a product or formulation may fall into are a regulatory
  question. This plan does not propose any.
  *Answered for Phase 3: the build brief's six categories and Q1–Q4 tree (§24).
  Whether they match the governing law is for the legal reviewer (Q7).*
- **Q5.** *(Phase 4)* **How is confidence defined?** Which signals, what scale, what
  threshold triggers abstention.
- **Q6.** *(Phase 4)* **What may an answer point contain besides the quotation?** A
  plain-language gloss in the user's language would be helpful and is exactly
  where legal advice and mistranslation could enter. If allowed, it must be
  labelled as machine text and can never stand in for the quotation.
- **Q7.** *(Phase 2)* **What is the vocabulary of provision status events**, and who
  is the legal reviewer who signs off corpus material?
  *Phase 2 recorded the smallest specified list (D-085); what each value means
  for an answer is still open, and no reviewer is named.*
- **Q8.** *(Phase 2)* **What are the reuse terms** of each authority's texts, and may
  they be committed to a repository that may become public?
  *Still open: every source records `terms_status = unknown` (D-083).*
- **Q9.** *(Phase 1)* **Visual direction:** reuse the existing design system with a new
  brand, or a new direction?
- **Q10.** **What cut-off dates** does the time-aware corpus need — current law only,
  or history back to a stated year?
- **Q11.** **Is `main` frozen** for the duration of the hackathon?
- **Q12.** **Does the IP-SAKTI deployment replace the public CareBridge demo**, or run
  beside it?
- **Q13.** **Should "Asclepius"/CareBridge documentation be brought up to date**
  (§2.2) before the branch diverges further, so the healthcare product is left
  in a documented state?

---

## 22. Phase 1 Readiness Checklist

| Item | State |
|---|---|
| Branch `ip-sakti` exists; `main` untouched and equal to `origin/main` | ✅ |
| Baseline recorded (§3) | ✅ backend 0 failures; frontend 0 failures when run alone, 2 timing-sensitive failures under load |
| Existing evaluation gates pass | ✅ |
| Migration chain is a single head | ✅ `0009` |
| Module-level map and reuse matrix | ✅ §4, §5 |
| Healthcare inventory | ✅ §6 |
| Feature-flag boundary identified in real files | ✅ §11 |
| No IP-SAKTI feature implemented; no legal content added | ✅ |
| Phase 5 work committed somewhere durable | ✅ `carebridge-phase-5` (Q1, answered 2026-10-01) |
| Build brief available | ❌ Q2 |
| Role names defined | ❌ Q4 |
| Visual direction chosen | ❌ Q9 |
| Curator and legal reviewer named; corpus sourcing started | ❌ needed for Phase 2, should start during Phase 1 |
| Lint configured | ❌ none exists; optional, but there is no automated style or unused-code check |

**Assessment.** Phase 1 is technically ready: the flag boundary is clear, it is
additive, and it can be built and rolled back without touching `main` or the
healthcare product. It is **not ready to start** until Q1 is decided, because
every subsequent commit and migration depends on where Phase 5 lives. Q2, Q4 and
Q9 should be answered at the same time; none of them blocks the flag itself, but
each changes what Phase 1 builds on top of it.

---

## 23. Phase 2 — as built (2026-10-01)

**What the specification was.** No separate build brief exists in the
repository or in the team's files. The only IP-SAKTI document found is the
team's SIH26045 idea deck (`SIH26045_IP-SAKTI_Idea_PPT 55.pptx`, the latest of
four near-identical copies). For Phase 2 it specifies: a version-tracked corpus
pipeline (collect official sources → read PDF/OCR → parse section/rule → tag
date and status → approve by a human curator); status that knows "in force,
stayed or omitted"; an official corpus from India Code, IP India, NBA and WIPO
Lex; statutes kept verbatim; and RapidOCR. Phase 2 was built to that deck and to
the Phase 2 instructions. Its "index / hybrid search" step is Phase 4 and was
not built.

**Official corpus status: unavailable.** No official legal source file is in the
repository, none was downloaded, and none was written from memory. The corpus
is empty. Every test uses synthetic, non-legal PDFs generated in memory at test
time (`backend/tests/corpus_fixtures.py`), each headed "SYNTHETIC TEST FIXTURE -
NOT A LEGAL TEXT"; none is committed as a file, seeded or loadable as corpus.

### Schema (migration `ipsakti_0002`)

| Table | Holds | Lane |
|---|---|---|
| `instruments` | What a source is a text of: title, type, issued by, curator note | own, fixed |
| `corpus_documents` | One official file: authority, document type, URL and/or reference, source date, retrieval date, SHA-256, storage reference (internal), reading state, review state, terms status | = instrument's (composite FK) |
| `corpus_pages` | The text read from each page, verbatim, with method, engine, confidence, line positions | via its document |
| `corpus_chunks` | Line-bounded slices of the document text, in order, never across a page | = document's (composite FK) |
| `provisions` | A provision's identity: locator as printed, locator type | = instrument's (composite FK) |
| `provision_versions` | An exact span of a document's text, its pages, OCR flag, `valid_from` / `valid_to`, review state, version number | = provision's and = document's (two composite FKs) |
| `provision_status_events` | Append-only: status, effective date, basis (approved source and/or reference), curator note | = version's and = basis's (composite FKs) |

Indexes cover lane, review state, instrument, provision, document, validity
dates and version number. No vector index, no search index.

### Lifecycle

    upload (file + provenance; stored as is; draft, unread)
      → parse (exact text layer, or local OCR flagged for checking; whole or nothing)
      → draft provision versions (two offsets → the server cuts the text)
      → submit → approve (names the checksum; OCR must be acknowledged) | reject (with a reason)
      → status events on approved versions, each citing its basis

Sources and versions share one state machine: draft → under_review → approved |
rejected. A version can be approved only after its source. Approved and rejected
records are final — refused by the service (and audited), and by database
triggers. A correction is a new version or a new upload; old versions are never
overwritten.

### Source provenance and terms

Every source names one of six official authorities (India Code, e-Gazette, IP
India, NBA, FSSAI for India; WIPO Lex for international) and gives a URL, a
reference or both. URLs are recorded, never fetched. **No authority's reuse or
redistribution terms have been verified; every source records `unknown`.**

### Decisions and controls

D-081 – D-086 in `docs/DECISIONS.md`. Security controls for uploads are in
`docs/SECURITY.md`. API: `/api/v1/corpus/*`, mounted for IP-SAKTI only; every
change needs the curator role, administrators may read, users and facilitators
have no access. Screens: Corpus, Upload, Draft / Diff, Approve, and source,
version and instrument pages.

### Departures from this plan

* §15 says a second person approves. Phase 2 makes that a setting,
  `CORPUS_SEPARATE_APPROVER`, **off by default**, because the Phase 2 brief has
  one curator upload, review and approve, and no legal reviewer is named (Q7).
* §18's Phase 2 row names `glossary_term`; it is not built (no glossary work in
  Phase 2).
* §15 notes that the international lane needs a sub-type (treaty vs a regional
  legal order); not built — `instrument_type` and the lane are all there is.

### Known limitations

* The corpus is empty: no official source is available (Q2, Q8).
* Status vocabulary semantics are unresolved (Q7); events are records of what
  sources say and are not combined into "the law on a date".
* Separate approval is off by default (see above).
* Uploads are PDF only. Parsing runs inside the request; a long scanned source is
  slow. The offline OCR engine reads printed English only, so Hindi or Tamil
  scans produce text that needs checking or nothing at all.
* Provisions are flat, and a version is one contiguous span: a provision that
  runs across a page break includes whatever the pages print at the break, such
  as running headers.
* Offsets assume text in the Basic Multilingual Plane, which covers Devanagari
  and Tamil; a character outside it would shift the client's line offsets, and
  the server's returned text is what the curator then sees.
* The Hindi and Tamil interface strings are unreviewed drafts.

---

## 24. Phase 3 — as built (2026-10-01)

**Specification.** The classification section of the IP-SAKTI build brief, as
quoted in the Phase 3 instruction: six categories and the Q1–Q4 decision tree,
with "unknown" stopping the classifier. The brief document itself is still not
in the repository. This answers Q3 for Phase 3: the taxonomy is the brief's;
whether it matches the governing law is for the legal reviewer (Q7).

### Product profile

`product_profiles` (migration `ipsakti_0003`): name, intended use, dosage form,
administration route, ingredients (name, part used, quantity), preparation
method, the classical text the user follows (by name), extract and
standardisation details, defined markers, notes, the language the free text is
written in, and a revision number. **User-provided facts only** — no category,
no conclusion. Owned by one user; anyone else's is "not found". API:
`GET/POST /products`, `GET/PATCH /products/{id}`, `GET /products/{id}/classifications`.

### Classifier tree

`ip_sakti_formulation` v1, as data, fingerprinted and pinned (D-087):

    Q1 purpose             nutrition → AYURVEDA_AAHARA · external beautification → COSMETIC · therapeutic → Q2
    Q2 classical_formula    yes → CLASSICAL · no → Q3
    Q3 schedule_combination yes → PATENT_PROPRIETARY · no → Q4
    Q4 phytopharmaceutical  yes → PHYTOPHARMACEUTICAL · no → NEW_OR_NON_CLASSICAL
    any question           unknown → stop: requires information, no category

Each node has a question, help, "what is missing" and "why it is needed" text
key, its choices' keys, the profile fields shown beside it, and its reference
slot ids. Categories' machine ids: `classical`, `patent_proprietary`,
`new_or_non_classical`, `phytopharmaceutical`, `ayurveda_aahara`, `cosmetic`.
The walk is pure and deterministic (D-088). No AI is involved anywhere.

### Sessions, outcomes, confirmation

`classification_sessions` record the product, the profile as it stood, the tree
id, version and fingerprint, and the status: incomplete · requires information ·
determined · user confirmed · user rejected · superseded. `classification_answers`
are append-only (a revision supersedes); `classification_outcomes` are immutable
(a category only when determined, by CHECK). A determined result awaits the
user's explicit confirmation of the outcome they saw; rejecting puts nothing in
its place; "start again" makes a new session and keeps the old one (D-090).
API: `POST /classifications`, `GET /classifications/{id}`,
`POST /classifications/{id}/responses | restart | confirm | reject`,
`GET /classification-tree[/{version}]`.

### Legal pointers

Seven reference slots in v1, all India lane: the First Schedule the questions
refer to, and the official description of each of the six categories. A slot is
`corpus_required` until a curator links it to an approved provision version
(`POST /classification-tree/{version}/references/{slot_id}`, curator only), then
`verified`; text that is not approved can never be linked (D-091). **Every v1
slot is `corpus_required`**: the corpus holds no official text.

### Authorisation

Users: their own products and classifications only. Facilitators, curators and
administrators: no access to products or sessions; every IP-SAKTI role may read
the tree; only curators link references. CareBridge has none of these routes.

### Audit

session created · question presented · answer recorded · answer changed · unknown
encountered · determined · confirmed · rejected · restarted · change refused ·
reference linked · product created · product updated — each with the tree
version and ids or choice codes, never the profile's free text.

### Departures from this plan

* §18 said "the engine reused" after decoupling `conversation/model.py` from
  medical enums. The healthcare engine was left untouched instead; the
  classifier follows its pattern (data, fingerprints, pinned versions, a pure
  walk) in its own small module (D-087).
* §18 suggested the API "start, answer, review, complete". The answer endpoint is
  `/responses`, and "complete" is the explicit confirm or reject.

### Known limitations

* Every legal pointer is `corpus_required` until official text is curated (Q8).
* v1 is an engineering draft; no legal reviewer has gone through the questions
  or the categories (Q7).
* Product documents are not attached in Phase 3; a profile is text only.
* There is no free-text answering and no AI normalisation; answers are choices.
* Hindi and Tamil strings are unreviewed drafts.
* "Start again" begins from Q1; earlier answers are not carried over.
