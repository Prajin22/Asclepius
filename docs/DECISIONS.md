# Decision log

Small, reversible decisions taken while building Phases 1–5. Format: decision —
why — how to revisit.

## D-001 — Web (Next.js) rather than Flutter for Phase 1

The Tuesday prototype is demonstrated in a browser, and two audiences (patient,
clinician) need different layouts fast. Next.js + Tailwind gives the shortest
path to a responsive, accessible demo. Native clients remain possible later:
all logic lives behind the HTTP API, and `packages/shared-types` documents it.

## D-002 — Two separate frontends instead of one app with role switching (superseded by D-050)

Patient and doctor UIs differ in density, language and risk. Separate origins
(`:3000`, `:3001`) also isolate browser storage, so a patient session can never
be read by the doctor app on a shared machine.

## D-003 — Bearer token in `sessionStorage`, not a cookie

Cookies are not isolated by port, so both apps on `localhost` would share one
cookie. A bearer token in each app's `sessionStorage` keeps sessions separate,
needs no CSRF machinery, and disappears when the tab closes. Trade-off: a
successful XSS could read the token. Phase 9 should move to `HttpOnly`,
`SameSite=Strict` cookies on distinct hostnames plus CSRF tokens. See
SECURITY.md. Since D-050 there is one origin, so the isolation argument no
longer applies; the token stays in `sessionStorage`, one account per tab.

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

## D-050 — One web app; the role is chosen at sign-in

Supersedes D-002. Patients, doctors and administrators use one Next.js app
(`apps/patient-web` — the directory keeps its name so existing deployments keep
working). The sign-in page asks who you are, Patient or Doctor, and offers the
matching sign-up. After sign-in the account's role, not that choice, decides
where you land: `/home`, `/clinician` or `/admin`. Each area checks the role
again on the client; the API remains the only real boundary.

* One deployment and one CORS origin instead of two.
* The clinician workspace and the admin screens keep their English catalogue by
  nesting an `I18nProvider`; patient screens and the sign-in page keep the
  language switcher.
* **Trade-off:** separate origins no longer isolate browser storage. A tab holds
  one session (`asclepius.session` in `sessionStorage`), so a patient and a
  doctor sharing a machine sign out between uses, as on any single sign-in site.

Revisit: put the clinician area on its own hostname (not just a port) if session
isolation on shared machines matters more than a single deployment.

## D-051 — Doctors sign themselves up; an administrator approves them

A doctor applies with name, specialty, qualification, registration number and
languages (`POST /auth/register-doctor`). The account signs in at once but is
`pending`: every clinician route except its own profile and application answers
`403 doctor_not_approved`, the directory leaves it out, and a consultation
request to it is a `404`, as for a doctor who does not exist. An administrator
approves it, or rejects it with a reason the doctor sees. The doctor can correct
a pending or rejected application, which returns it to `pending`. Rejecting an
approved doctor revokes access immediately.

* **Verification is a person, not a lookup.** The administrator checks the
  number against the medical council register by hand. Nothing here queries the
  NMC or a state council, and the interface says so.
* Registration numbers are compared ignoring case, spacing and punctuation. A
  number another doctor account uses is flagged during review, and cannot be
  approved while an approved doctor holds it — so an impostor cannot take a real
  doctor's number, and an impostor's earlier application cannot block the real
  doctor from applying.
* Doctors created by an administrator (`POST /admin/doctors`) or by the seed are
  approved on creation; migration `0006` marks every existing doctor approved,
  and its downgrade deactivates accounts that were never approved rather than
  letting them in.
* Who reviewed, and when, is in the audit trail (`doctor.applied`,
  `doctor.approved`, `doctor.rejected`, `doctor.application_updated`); the row
  keeps only the status, the reason and `reviewed_at`.

Revisit: automate the register check where an official API exists, and ask for
a registration certificate before review.

## D-052 — The model never sees a database identifier

Every authorised item in a case-summary bundle gets an opaque handle — `S1`,
`S2` — valid only inside that one bundle. The provider is shown handles and
words; it returns groupings that cite handles; the application maps them back to
rows (`services/case_summary_bundle.py`, `services/summary_validation.py`).

This collapses four separate requirements into one mechanism. The model cannot
invent a document id, page number or bounding box, because it is never shown one
and has no field to put one in. It cannot cite an unshared item, because
unshared rows have no handle. It cannot leak an identifier, because it holds
none. And a hallucinated `S99` simply fails to resolve, so the item carrying it
is dropped — never repaired, never guessed at.

The bundle is built *after* the authorization boundary closes and *before*
anything is sent, so there is no moment at which a provider is shown something
and asked to ignore it.

## D-053 — A summary item's origin is always a human

`SummaryItemOrigin` has three members: `patient_provided`, `patient_confirmed`,
`doctor_authored`. There is deliberately no machine origin. The application sets
it from the cited sources and the model is never asked, so a provider cannot
change who said something.

What the model contributes is grouping, de-duplication, ordering and noticing
that two sources disagree. That is organisation, which is the job `AI_POLICY.md`
assigns it; authorship stays with the person who wrote the words.

## D-054 — Staleness is computed, never stored

`consultation_summaries` has no `stale_at`. A summary is stale when its
`source_bundle_hash` differs from a freshly built one, and that comparison
happens when the summary is read.

Shared records are live references (D-006): a patient can edit one after sharing
it. A stored flag would be wrong the moment they did, and nothing would be
watching to correct it. A computed answer cannot be stale about staleness.

The hash therefore covers item *content*, not item ids — which is the only
reason a stale summary is detectable at all.

## D-055 — What a health claim may rest on

The six claim sections are exactly the six extraction categories. A statement in
one of them must cite a fact the patient confirmed, a prescription a doctor
authored, or the title of a health record the patient wrote themselves.

Narrative free text — a current problem, a message, a document, a doctor's note —
can support a *pointer* ("current problem recorded on the 23rd") but never a
claim about the patient's health. Turning narrative into a health claim is
extraction, and extraction goes through the patient (Phase 2).

A record's title is admitted because a health record is not narrative: the
patient typed it, chose its type and labelled it "Hypertension". Excluding their
own assertion from a summary whose purpose is to carry what they said would be
the wrong kind of caution. The record's free-text body is not admitted, so an
instruction hidden in one cannot become a finding.

This is the defence that does not depend on a word list. An earlier version
relied on the Phase 2 lexicon to catch unsupported terms, and a model that
invented "cancer" — a word the lexicon does not contain — passed. The structural
rule drops it whether or not the invented condition happens to be known.

## D-056 — Free text never becomes a statement

A statement is a confirmed value or an application-written label. It is never a
copy of a source's free text, and the validator drops any statement of 80
characters or more that appears verbatim inside a cited source.

The words are not the problem; presenting them as the summary's own organisation
is. An early version of the local provider lifted a whole record into the
`current_problem` statement, so a sentence a patient had written — including one
shaped like an instruction — read as a line the system had produced. Free text
reaches the doctor through the source block, labelled as the patient's own
words, where it belongs.

## D-057 — A case summary spends the patient's money, not their turns

Generating a summary counts against the patient's 24-hour estimated-spend cap —
so provider spend stays bounded exactly as before — and against a new
per-consultation generation cap (`SUMMARY_PER_CONSULTATION_LIMIT`, default 10).
It does *not* count against their hourly or daily run limits.

Those run limits exist so a patient can work on their own record. A doctor
pressing "refresh summary" must not be able to exhaust them. Cache hits create
no row and cost nothing; failures do count, because they spent a provider call
and a failing provider should not be an unlimited one.

`ai_limits.enforce_cost_limit` was split out of `enforce_rate_limit` for this,
with no change to what any existing caller does.

## D-058 — A doctor's own prior consultations are in the bundle, labelled

D-009 lets a doctor see their own earlier consultations with a patient without a
new grant, and the case view already returns them. They are included in the
summary bundle, and every bundle item carries an `authorization_basis` of
`patient_grant` or `own_prior_consultation`.

Excluding them would make the summary quietly less complete than the case view
directly beneath it, which reads as a bug rather than as caution. Both bases are
authorised; keeping them apart makes the reason auditable and lets the interface
say which is which.

## D-059 — Unconfirmed extraction is counted, never stated

Only confirmed and edited facts become summary statements. Facts still awaiting
the patient's decision are reported as a count — "3 extracted items are awaiting
the patient's confirmation and are not included" — and rejected facts never
leave the database.

A doctor who cannot tell a reviewed case from an unreviewed one is worse off
than one who is told the picture is incomplete. Stating the content of
unconfirmed items would put machine output in front of a doctor, which Phases 2
and 3 deliberately avoided.

## D-060 — Conversation candidates are their own staging table, not `AIExtractedFact`

An answer to a question produces a `conversation_candidate_facts` row, not an
`ai_extracted_facts` row, even though both are "a suggestion the patient must
confirm" and both reuse the Phase 2 vocabulary for category, attribution and
review state.

Three reasons, any one of which would be enough. `AIExtractedFact.artifact_id`
is non-nullable and a deterministic conversation produces no AI artifact, so
reuse would mean making a Phase 4 column nullable. Its evidence shape is a
verbatim quote with character offsets, a page and a bounding box, which
describes a document and does not describe a tapped option — a conversation
answer's evidence is (question id, question version, response id). And it is
named and documented as AI-extracted, which this is not: no model is consulted
anywhere in Phase 5A.

What is *not* duplicated is the confirmed representation. A confirmed candidate
becomes a `MedicalRecord` through the same mapping Phase 2 uses, imported from
`app.services.ai_facts` rather than restated, so the two paths cannot drift into
disagreeing about whether an allergy becomes a record. Phase 5A changes no
Phase 4 table, and conversation-derived records flow into sharing and the
Phase 4 bundle with no further work.

Revisit if interpretation is added between answer and candidate: at that point
a candidate may carry both a question reference and a model artifact, and the
two tables may be worth merging behind one staging interface.

## D-061 — The server decides the next question; a client says only what it answered

`AnswerIn` carries `question_id` — what is being answered — and there is no
field anywhere in the API for what to ask next. If the id does not match the
question the session is waiting on, the answer is refused with `409
unexpected_question` rather than silently accepted.

A client that could name the next question could walk a patient past the
questions it found inconvenient, and the stored history would not show it had
happened. Keeping selection in `app/conversation/flow.py` also means "why was I
asked this?" is answerable from a stored string rather than by replaying
anything.

Revisit only if a clinician-authored flow needs to jump explicitly; even then
the jump belongs in the flow definition, not in the request body.

## D-062 — Attribution comes from the question, never from the answer

`QuestionDefinition.subject` says whose health an answer describes, and the
candidate copies it. `history.family_conditions` is `FactSubject.FAMILY`
because it asks about relatives; no part of Phase 5A reads an answer to decide
whose it is.

Inferring attribution from wording is exactly the failure D-025 exists to
prevent — a father's penicillin allergy becoming the patient's. A question
knows who it asked about before anyone answers it, so the safe answer is free.

Revisit when one question can cover several people ("who in your family?"); the
subject then comes from a structured follow-up, still never from prose.

## D-063 — A client-supplied key for replays, a revision for races (corrected by D-073)

Every answer carries an `idempotency_key`, unique per session, so a retried
request is recognised as the same answer rather than recorded twice. Every
accepted transition increments `ConversationSession.revision`; a client may
send the revision it last saw, and an answer built against a stale one is
refused with `409 conversation_out_of_date`.

These solve different problems and both are needed. The key handles the same
request arriving twice — a flaky connection, a double tap. The revision handles
two *different* requests racing, where recording both would advance the
conversation twice and skip a question. The unique constraint is the backstop
when two replays race each other past the in-memory check.

Revisit if sessions ever become multi-device, where a soft revision check will
not be enough and the transition needs a row lock.

## D-064 — Questions are versioned configuration, not rows in a table

The flow lives in `app/conversation/flow.py` as frozen dataclasses with a
stable id, a version and a localisation key. A session stores the flow version
it started under; a response stores the question version the patient actually
saw.

A question's wording is not patient data, and changing it should be a reviewable
diff rather than a migration. The id/version/key split is what keeps old
answers readable: rewording bumps the version and leaves every stored answer
pointing at the wording it was given under, and translating a question never
rewrites history because the text is resolved in the browser.

Revisit if non-engineers need to edit flows; that argues for a table, and the
versioning rules above become the table's constraints rather than disappearing.

## D-065 — Why a question was asked travels as a key, not as a sentence (partly superseded by D-069)

`QuestionDefinition` carries both `applies_because` (English prose) and
`because_key` (a localisation key). The prose is written to the session and
stays on the server, for support and debugging. The API returns only the key,
which the browser resolves.

The engine has to be able to explain itself — "why am I being asked where the
pain is?" is a fair question, and the answer must not require replaying
anything. But an explanation that arrives as an English sentence is useless to
the Tamil speaker it was written for, and Phase 4 already paid for learning
that: server strings leaked onto the screen there and had to be chased out of
`_label()` afterwards. Deciding it at the schema boundary costs nothing now and
cannot be forgotten later.

The same reasoning removed the prose reason from the audit details. The audit
contract is ids and categories; "the patient said this involves pain" is a
sentence about someone's symptoms, and it was already stored on the session.

Revisit if a reason ever needs to interpolate a value (a date, a previous
answer); the key then takes parameters, and the prose still does not travel.

## D-066 — The history tree is data, walked by a pure engine

A flow is a tuple of frozen `QuestionDefinition`s with explicit `order`
numbers. A branch is a declared `Branch` — predicate id, trigger question, the
options that open it, and a reason code for each outcome — not a function.
`app/conversation/engine.py` resolves where every question stands from the flow
and the answers alone: no clock, no randomness, no I/O, no model, and a test
fails if the module so much as imports one. The service adds authorization,
persistence, idempotency and audit around it and makes no decision of its own.

Declared branches can be fingerprinted, listed, covered by an evaluation, and
explained without reading code. A pure engine means the service, the
evaluation harness and the tests all run literally the same decisions, and
"same answers, same next question" is a property of the code rather than a
hope. Only an explicit, controlled answer can open a branch; free text is never
read to decide what to ask.

Revisit only if a branch genuinely needs more than "the trigger's answer
includes one of these options". Even then, add a declared condition type; do
not reintroduce callables.

## D-067 — Every flow says, on every payload, that it is a draft

`FlowDefinition.status = engineering_draft` and `clinical_review = required`,
and `ConversationOut` carries both on every response. Both published flows are
engineering drafts: reasonable structures written by engineers, not reviewed
by a clinician, not validated against any guideline, not complete. Nothing in
the repository establishes otherwise, so nothing may say otherwise.

Putting it in the payload rather than only in documentation means no screen
built on the API can present the tree as a protocol without deliberately
dropping a field it was given.

Revisit when a clinician has reviewed a flow. That review produces a new flow
version with a new status; it does not relabel this one.

## D-068 — A session is walked under the flow it started with; published flows are immutable

Flows live in a registry keyed by `(flow_id, version)`. The service resolves a
session's questions from `session.flow_version`, never from the current flow.
Every published flow's canonical form is hashed into `flow.PUBLISHED`, and a
test fails if a published flow changes. A question whose wording, options or
type change gets a new question version, and its localisation key includes the
version, so an old answer always renders against the wording actually shown.

This corrects a Phase 5A gap: 5A stored `flow_version` but always walked the one
global tree, so the first new version would have silently changed every
conversation in progress. v1 is kept, re-expressed declaratively with identical
questions and branches, and the Phase 5A tests now run against it.

Revisit if flows ever need authoring outside code; the registry becomes a
table, and immutability becomes a constraint on it.

## D-069 — Reasons are codes; skip reasons claim only what was said

Why a question was asked, or not, is a reason code (`radiation_reported`,
`radiation_not_reported`, `flow_sequence`, `configured_flow_complete`) plus the
trigger question and predicate id. It is stored on the session, on every
response and on every skip, sent to the browser as `reason: {code,
trigger_question_id, predicate_id}`, and rendered from
`conversation.reason.<code>`. No English sentence is stored anywhere as a
reason. This supersedes the part of D-065 that kept an English explanation on
the session, and replaces its `because_key`.

A shut branch is shut for "no" and for "not sure" alike, so its reason must be
true of both: `*_not_reported`, `*_not_chosen`, `*_not_known` — never
`*_not_present` or `*_absent`, which would record an absence the patient never
stated. The Phase 5B brief's example `radiation_not_present` is deliberately
not followed, for exactly that reason; a test enforces the wording.

## D-070 — "No", "not sure", "no answer" and "not asked" are four different facts

* **no** — a stored answer, `{"choices": ["no"], "bool": false}`.
* **not sure** — a stored answer with no `bool` at all, so it cannot be misread
  as "no". Phase 5A stored `bool: false` for "unsure"; that is fixed for every
  flow.
* **no answer** — the patient declined an optional question: a response with
  `declined = true` and nothing else. The Phase 5A column `skipped` is renamed
  `declined` (migration 0009), because "skipped" was about to mean two things.
* **not asked** — the branch stayed shut. There is no response at all, only a
  `conversation_skips` row with the reason. Nothing fakes an answer for a
  question nobody was asked.

"None of these", "not sure" and "nothing noticed" are exclusive options: each is
a complete answer and cannot be ticked with anything else. "None of these"
means none of *these* and produces no fact. Every required tap question offers
an honest way out, so it can be required without forcing a belief; every
free-text question except the first can be declined.

## D-071 — Only the patient's own words become candidates

A candidate is created only from a free-text answer to a question with a
category, and its value is the patient's words. A tapped option or a structured
duration is already exactly what the patient said, in controlled form — and
restating it as a candidate would mean writing an English rendering ("3 days",
"nausea") into the record, the defect D-065 exists to prevent. This changes one
Phase 5A behaviour: v1's `symptom.duration` no longer produces a "3 days"
candidate.

Durations typed as words stay words: "some time ago" and "three days" are
stored as text with no structured value. A structured duration exists only when
the patient entered one.

## D-072 — Revising an answer supersedes it, and never behind a confirmed fact

`POST .../answers/{question_id}/revision` marks the current answer superseded,
adds the new one, and lets the engine work out the consequences: answered
follow-ups whose branch the correction shuts are retired too (with a
`no_longer_applicable` cause and a skip row), and follow-ups it opens are asked
next. Candidates from retired answers are superseded, stay on record, and can
no longer be acted on. Nothing is deleted.

A revision is refused (`answer_has_confirmed_facts`) while anything drawn from
an affected answer is confirmed or edited: that fact is in the patient's record
now, and it changes through the record, or by rejecting the candidate first,
never as a side effect. Only answered questions can be revised — a question
that was not asked has nothing to change and cannot be given an answer this way.

## D-073 — Concurrency is enforced by the database, not by a check

`ConversationSession.revision` is a SQLAlchemy version column: every UPDATE of
the session carries `WHERE revision = <value read>`, so of two requests that
read the same revision only the first can write, and the loser is told
`conversation_out_of_date` with nothing it did kept. Confirming a candidate
moves the revision too, so a confirmation cannot race a revision of the answer
it came from. Partial unique indexes hold at most one current answer and one
current skip per question, and at most one open conversation per patient.

This corrects D-063, which described Phase 5A's `expected_revision` comparison
as race protection. It was a comparison in Python followed by a write: it
caught stale clients, not races, and two different answers arriving together
would both have been recorded. Two further 5A gaps are fixed here: a retry of
the answer that moved a conversation into review was refused, because status
was checked before the replay was recognised (replays are now recognised
first); and a request key reused for a different question was silently treated
as a replay (it is now refused).

## D-074 — Localisation keys are versioned and cannot collide

v2 keys are derived mechanically — `conversation.question.<id>.v<version>`,
`conversation.help.<id>.v<version>`, `conversation.choice.<set>.<option>`,
`conversation.reason.<code>` — under roots separate from v1's
`conversation.q.*` / `conversation.option.*`. The i18n catalogue is nested and
looked up by splitting on `.`, so a key cannot be both a string and a group;
v2's question ids nest (`symptom.radiation`, `symptom.radiation.location`), and
v1's `conversation.q.symptom.duration` is a leaf that a v2 key beneath it would
have broken. A test checks every key across every flow for that collision.

No key has a translation yet. They are a prerequisite for any patient UI, and
need native-speaker review before use.

## D-075 — A downgrade refuses rather than destroy patient answers

Migration 0009's downgrade stops, and changes nothing, if any history_general
v2 conversation or any superseded candidate exists: 0008 cannot hold v2's
sections, and 0008's code would offer a superseded candidate for confirmation
again. Migration 0003 deleted the rows its narrower schema could not hold; that
was a derived record type, and these are things patients said. Export or remove
the data deliberately, then downgrade.

## D-076 — Where Phase 5C's model may stand, and where it may not

Interpretation may be added in exactly one place: between a free-text answer
and a candidate, producing suggestions that stay `pending` until the patient
acts on them. It may not choose a question, open or shut a branch, change a
reason, validate an answer, or confirm anything. The engine is pure and the
flows are data precisely so that this boundary is structural: there is no
callable in a flow for a model to sit behind, and the test that forbids the
engine from importing a client or a clock will fail if one is added.

## D-018 — Doctor UI is English-only in Phase 1

All doctor strings still come from a catalogue (`doctor.en.json`), so adding a
language is a file, not a refactor. Patient UI ships English, Hindi and Tamil;
those translations are drafted by the team and need native-speaker review
before any real use.
