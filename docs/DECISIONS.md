# Decision log

Small, reversible decisions taken while building Phases 1–3. Format: decision —
why — how to revisit.

## D-001 — Web (Next.js) rather than Flutter for Phase 1

The Tuesday prototype is demonstrated in a browser, and two audiences (patient,
clinician) need different layouts fast. Next.js + Tailwind gives the shortest
path to a responsive, accessible demo. Native clients remain possible later:
all logic lives behind the HTTP API, and `packages/shared-types` documents it.

## D-002 — Two separate frontends instead of one app with role switching

Patient and doctor UIs differ in density, language and risk. Separate origins
(`:3000`, `:3001`) also isolate browser storage, so a patient session can never
be read by the doctor app on a shared machine.

## D-003 — Bearer token in `sessionStorage`, not a cookie

Cookies are not isolated by port, so both apps on `localhost` would share one
cookie. A bearer token in each app's `sessionStorage` keeps sessions separate,
needs no CSRF machinery, and disappears when the tab closes. Trade-off: a
successful XSS could read the token. Phase 9 should move to `HttpOnly`,
`SameSite=Strict` cookies on distinct hostnames plus CSRF tokens. See
SECURITY.md.

## D-004 — Enumerations as `VARCHAR` + `CHECK`, not native PostgreSQL enums

`ALTER TYPE … ADD VALUE` cannot run in a transaction and complicates
migrations. A check constraint is a one-line migration change. Cost: no type
reuse in the database. Revisit if the enum set stabilises.

## D-005 — Sharing is stored twice, on purpose

`consultation_shares` holds per-item grants and is the **only** thing the
access checks read. `consultations.patient_shared_context` stores an immutable
JSON snapshot of the decision, including categories the patient left unchecked.
Enforcement needs the first; "what did the patient agree to, and when" needs
the second.

## D-006 — Shared records are live references, not copies

A doctor sees the current content of a shared record. If the patient edits it
later, the doctor sees the edit; if the patient deletes it, it disappears from
the case. This keeps the patient in control, but it means a consultation is not
a frozen clinical record. Phase 5 should snapshot shared items at the moment a
consultation is completed.

## D-007 — Accepting a consultation starts it immediately

The schema keeps `accepted` (for Phase 5 scheduling), but in Phase 1
`POST /accept` moves `requested → active` and sets both `accepted_at` and
`started_at`. A separate "start" step would add a click to the demo with no
behaviour behind it.

## D-008 — Prescriptions are immutable

There is no update or delete endpoint. A correction is a new prescription in
the same consultation. This keeps attribution and history honest. Revisit when
a "cancel/supersede" workflow is designed (Phase 6), which should add a status
rather than mutate rows.

## D-009 — Doctors see their own earlier consultations with a patient without a new grant

A doctor was party to those consultations and authored their content. Data the
patient shared with *another* doctor is never included. Patient-visible wording
should be added in Phase 5 so this is explicit to patients too.

## D-010 — Default sharing selections

Pre-ticked: the latest active current problem, active medical-history entries,
and uploaded documents. Unticked: previous consultations and previous
prescriptions (another doctor's opinion is shared only on a deliberate choice).
Every box is visible and changeable before sending, and the decision is stored.

## D-011 — Patients may edit only patient-provided records

`source` is set server-side to `patient` for anything created through the
patient API; doctor-provided and (future) AI-extracted entries are read-only to
the patient. Attribution must never be rewritable by another party.

## D-012 — Upload validation: allow-list + magic bytes + server-generated keys

Declared MIME type must be in the allow-list, the file's magic bytes must match
it, and the extension must match too. Stored object keys are
`patients/<id>/documents/<uuid>.<ext>` — user filenames are display-only, so a
crafted filename cannot touch the filesystem.

## D-013 — Tests run on SQLite by default, PostgreSQL on demand

Contributors get a fast suite with no services (`pytest`). Setting
`TEST_DATABASE_URL` runs the same suite on PostgreSQL, and
`MIGRATION_TEST_DATABASE_URL` additionally applies migrations and asserts (via
`alembic check`) that they match the models. Models therefore avoid
PostgreSQL-only constructs except `JSONB`, which has a portable variant.

## D-014 — Hand-written TypeScript DTOs rather than generated ones

`packages/shared-types` mirrors the Pydantic schemas by hand. It is small,
readable and has no build step. Phase 9 should generate it from the OpenAPI
document; the module boundary is already in place.

## D-015 — No AI in any Phase 1 code path

`AI_PROVIDER=mock` and the provider is never called from a router or service.
`GET /api/v1/meta/ai` reports `enabled_features: []` so the demo cannot imply
AI processing that does not exist.

## D-016 — System font stack with Indic coverage

`Segoe UI` / `Nirmala UI` (Windows) and `Noto Sans` elsewhere, rather than
`next/font` downloads. Tamil and Devanagari render offline, which matters for a
venue demo with unreliable Wi-Fi.

## D-017 — `python -m app.seed` owns demo data

Seeding is a module in the backend (not raw SQL) so it goes through the same
validation as real requests, including document upload. `--reset` refuses to
run outside development/test.

## D-019 — The provider interface became async (Phase 2 breaking change)

HTTP providers need `async`. The three Phase 1 placeholder capabilities
(`summarize_case`, `analyze_document`, `translate`) were removed from the
contract: they belong to Phases 3–6 and an unimplemented method on an interface
invites accidental use. Only `tests/test_providers.py` changed; every
behavioural Phase 1 test was left untouched and still passes.

## D-020 — Consent gates *all* AI processing, not only third-party calls

The brief requires consent before sending data to an external provider. We
require it before any AI processing, including the local provider: the patient
is opting into machine interpretation of their words, not only into a network
call. It is one honest switch, it is testable, and it makes the demo show the
consent step. Cost: one extra click before the first run.

## D-021 — Unsupported facts are dropped, not stored with a flag

If the evidence quote is not in the source, the fact does not exist as far as
CareBridge is concerned. Storing it "flagged" would leave invented content in
the database, one UI bug away from being shown. Weak-but-present evidence is
kept as `needs_review`.

## D-022 — Artifacts are the cache

Rather than a separate cache store, a successful artifact with a matching
`cache_key` (operation + provider + model + prompt version + language + source
hash) is reused. One place to look, provenance preserved, and changed text or a
bumped prompt version can never hit a stale entry.

## D-023 — Raw HTTP adapters rather than vendor SDKs

Three SDKs would add three dependency trees and three upgrade cadences for
three POST requests. `httpx` was already a dependency. Each adapter is ~60
lines and testable against a stub transport with no credentials. Revisit if we
need streaming or vendor-specific features.

## D-024 — Gemini's API key goes in a header, not the query string

The documented `?key=` form puts a credential in a URL, which lands in proxy
and server logs. `x-goog-api-key` carries the same value out of the URL.

## D-025 — Only some confirmed categories become health records

Confirming an allergy, medication or history item creates a `medical_record`
(`source=ai_extracted`) whose content is the patient's original wording.
Symptoms, durations and measurements stay attached to the problem they came
from — a symptom is an episode, not a standing record.

## D-026 — Re-processing preserves patient decisions

Re-running the pipeline deletes only `pending` facts. Confirmed, edited and
rejected items survive: the patient's judgement outranks a fresh model run.
A re-extracted fact that matches one the patient already decided (same
category, subject and value) is not added again, and duplicates within one run
are collapsed — so the patient is never asked twice and the structured layer
carries no duplicates. (The live hardening run found a confirmed "3 days"
reappearing as a pending copy after re-processing.)

## D-027 — `DEMO_MODE` pins the local provider

`DEMO_MODE=true` (the default) ignores `AI_PROVIDER` entirely, so no key, quota
or outage can affect a demo, and no patient text can leave the machine by
accident. It is the same code path as production — the same interface, schemas,
evidence validation and storage — not a separate fake.

## D-028 — The mock provider is a rule-based lexicon, measured like any other

It is deterministic and offline, so it is honest about what it can do: a small
multilingual lexicon plus conservative patterns. It is scored by the same
evaluation harness as a real model, and its limitations are published in
AI_POLICY.md rather than hidden behind demo-quality output.

## D-029 — Attribution: family needs an explicit cue; the default is the patient

A current problem is the patient's own health entry, so a statement with no
attribution cue is about the patient. Anything attributed to a relative needs
an explicit cue *in the same clause* ("my father", "என் அம்மாவுக்கு",
"मेरे पिताजी"), and the cue is stored as `subject_evidence`. Attribution never
crosses a clause boundary. A confirmed family fact can only ever become a
`family_history` record — never the patient's allergy, medication or history.
`other` and `unknown` attribution create no record at all.

## D-030 — Rate limits are counted from artifacts and checked before any call

Hourly and daily run caps plus a 24-hour estimated-cost cap, per patient,
counted from `ai_artifacts` — no new infrastructure, and the counters survive a
restart. The check runs before the provider is constructed, so an over-budget
request sends nothing. A cache hit writes no artifact and costs nothing, but
the check is deliberately conservative: it precedes the cache lookup, so a
fully cached re-run is also refused while the patient is over budget. Reading
stored results (`GET …/ai`) is never limited.

## D-031 — The meaning-drift check is a signal, not a gate

It flags medical terms the English adds without support, facts the English
drops, and lost family attribution. It blocks nothing: the result is stored
with the extraction artifact and shown to patient and doctor. Blocking would
hide the original's interpretation exactly when a human most needs to see where
the layers disagree. Its vocabulary is the lexicon, so it detects only the
drift it has words for; that limit is published in AI_POLICY.md.

## D-032 — The OpenAI smoke test runs against a wire-format emulator until a key exists

No API key is available in this environment. `scripts/openai_emulator.py`
speaks the documented `/v1/responses` format over a real socket, so the
production adapter, pipeline, evidence gate and storage all run for real.
Because a real provider rejects a non-conforming schema before the model runs —
something no emulator reveals — `tests/test_ai_schemas.py` statically enforces
strict structured-output rules. The live run is one command away once a key is
configured (`scripts/ai_smoke_test.py --provider openai`).

## D-033 — Every schema property is required; optionality is a nullable type

Strict structured output requires every property of every object to appear in
`required`. Optional values are expressed as `["string", "null"]`. This caught
`evidence.start/end`, which were optional in `medical_extraction_v2`.

## D-034 — Prompt versions bumped in the hardening pass

`normalization_v2` (meaning-preservation rules) and `medical_extraction_v3`
(attribution field and the strict-mode fix). Because the cache key includes the
prompt version (D-022), no output produced under the old instructions can be
reused.

## D-035 — Reading and interpreting are separate layers

`app/providers/documents` turns bytes into page text and line positions, and
records how (method, engine, confidence). It knows nothing about medicine.
Interpretation is the Phase 2 pipeline, run once per page: a page is an
`AISource` exactly like a patient-written record, so consent, budget, caching,
evidence validation, attribution and the meaning check are the same code, not a
second copy.

## D-036 — An exact text layer beats any OCR

A PDF page with at least `OCR_MIN_TEXT_LAYER_CHARS` (20) embedded characters is
copied exactly and never OCR'd, so digital reports carry no transcription
error. OCR runs only on pages without a usable text layer, and on images.

## D-037 — Offline OCR by default

RapidOCR (PP-OCRv4 ONNX models bundled in the Python package) reads printed
text with no network and no key, so the document demo works like the Phase 2
demo: offline, deterministic, nothing leaves the machine. Its bundled models
read Latin and Chinese scripts only — Tamil and Devanagari scans need the
vision path — and it does not read handwriting. Both limits are published.

## D-038 — The vision path sends only what cannot be read locally

`OCR_ENGINE=auto` uses the configured provider's image input when it has one
and `DEMO_MODE=false`; `local` and `none` never send an image. Even with vision,
pages with a text layer are read locally and only image pages are sent.
`DEMO_MODE=true` always reads locally. A vision transcription reports no line
positions, so its facts carry a page number and **no** box — CareBridge does not
draw a box it did not measure.

## D-039 — Evidence regions come from the reader's geometry, not from a model

Line boxes are stored as fractions of the page (origin top-left), so they
survive any rendering scale. A fact's region is the union of the lines its
validated evidence characters touch (`PageText.bbox_for_span`). A model is never
asked for coordinates.

## D-040 — Page rows are content-addressed

`document_pages` is unique on `(document_id, page_number, text_sha256)`.
Re-reading a page that yields the same text reuses the row, so the cache and
every patient decision on its facts survive. Different text supersedes the old
row (`superseded_at`) rather than deleting it, so earlier facts keep their
provenance.

## D-041 — Integrity before every read

The stored file's sha256 must equal the hash taken at upload before it is read
or rendered. A mismatch returns `409 document_integrity_failed` and nothing is
read: extracting facts from bytes the patient did not upload would break the
chain from evidence to original.

## D-042 — Synchronous processing with a page cap and an upfront budget

`POST …/process` reads and interprets in the request (reading runs in a worker
thread), capped at `DOCUMENT_PROCESSING_MAX_PAGES` (10). The budget check counts
every page that will be interpreted before anything runs. Truncation is
recorded (`partial`, `truncated`, `only_first_N_of_M_pages_processed`) and shown
to both users — never silent. A job queue belongs to Phase 9/10; a prototype
that finishes in seconds does not need one.

## D-043 — Reading needs AI consent; viewing a page does not

Reading a document is AI processing (D-020). Rendering a page of the patient's
own file — or of a file shared with a doctor — is viewing the original, so it
needs only the usual ownership or share check (and is audited for doctors).

## D-044 — Doctors see a reading only beside a shared original

`CaseView.document_insights` includes only documents in `consultation_shares`,
collapsed by default under the original file. Items the patient rejected are
not shown. The page-image endpoint applies the same share check as file
download and is audited as `document.page_viewed_by_doctor`.

## D-045 — Numbers keep the label the source gives them (mock provider)

Running the Phase 2 extractor over lab reports exposed a meaning error: every
`NNN mg/dL` was labelled "blood sugar", so a cholesterol value became a sugar
reading. Measurements are now labelled only with the words on the same line
("total cholesterol 212 mg/dL"); a bare number gets no fact. Dates are no longer
read as blood pressure, "follow up in 4 weeks" is no longer a symptom duration,
and document-style lines ("Allergies: Penicillin", "Allergies: NKDA") are read.
The Phase 2 evaluation is unchanged (F1 0.912).

## D-046 — One Phase 1 string changed on purpose

The upload confirmation said "Processing will be available in the next phase".
It now says how to have a document read. `UploadForm.test.tsx` was updated for
this string only; no other Phase 1 or Phase 2 test was changed except fixtures
that gained the new `document_insights` field.

## D-047 — Anthropic strict tools get schemas without numeric bounds

The first live Anthropic call (the Phase 3 smoke test) returned HTTP 400:
"For 'number' type, properties maximum, minimum are not supported". Strict tool
schemas do not accept numeric range keywords. The adapter now strips `minimum`
and `maximum` from the tool schema (as the Gemini adapter strips
`additionalProperties`) while keeping `strict: true` and the forced tool, and
the response models enforce `0 ≤ confidence ≤ 1`, so an out-of-range value is a
structured `ai_malformed_output`, not an unhandled error. Stub transports and
the emulator could not reveal this; only a live call did (see D-032). This is a
fix to a Phase 2 adapter, made in Phase 3 because Phase 3 exposed it.

## D-048 — Offset drift from a live model stays `needs_review` (superseded by D-049)

The first live runs (Phase 3) superseded D-032's emulator-only status. Anthropic
quoted evidence verbatim with high confidence, but its character offsets were
1–5 characters off, so the Phase 2 validator marked every fact `needs_review`.
Phase 3 does not change that rule: it is Phase 2 behaviour and a product
decision. Page outlines are unaffected — they are computed from the position the
validator locates. Options for review: (a) accept a verbatim quote and replace
the model's offsets with the located span, keeping `needs_review` for
non-verbatim matches; (b) instruct models to return null offsets (prompt version
bump); (c) keep the current rule.

## D-049 — The application, not the model, locates evidence

Resolves D-048 with option (a), as a deliberate change to Phase 2 behaviour.
The provider supplies a verbatim quote; the validator finds it in the
authoritative source text (the patient's record, or the text read from a
document page) and stores **that** position. Character offsets reported by the
provider are never used, so offset drift no longer causes `needs_review`, and a
wrong offset can never move a stored position or a page outline.

* **Verbatim** means character for character, allowing only layout
  differences: whitespace runs, line breaks and zero-width marks.
* A quote that matches only when letter case or Unicode character forms are
  ignored is `needs_review` (previously `validated`): "×109/L" is not "×10⁹/L".
* A quote that cannot be found is `unsupported` and dropped, whatever position
  was claimed. The quote is never rewritten, and a position alone is never
  evidence.
* A quote that appears more than once resolves to its first occurrence — the
  existing deterministic behaviour; no provider hint is used to disambiguate.
* An unstated "no allergies" claim is rejected before any other check
  (previously a mismatched offset could turn it into `needs_review`).
* A validated fact whose provider offsets disagreed carries the note
  "provider position ignored; quote located by the application", so offset
  drift stays measurable.
* Stored evidence names its quote (as supplied), validated start/end
  (`evidence_start`/`evidence_end`), page (`evidence_page_number`) and document
  (`evidence_document_id`, new; migration `0005`).

No prompt or schema change is needed: models may still return offsets, and
every run — including a cache hit — is validated under the new rule. Facts
already stored keep their status until their source is processed again. The
Phase 2 test asserting that wrong offsets need review now asserts they are
ignored.

## D-018 — Doctor UI is English-only in Phase 1

All doctor strings still come from a catalogue (`doctor.en.json`), so adding a
language is a file, not a refactor. Patient UI ships English, Hindi and Tamil;
those translations are drafted by the team and need native-speaker review
before any real use.
