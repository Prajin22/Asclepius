# Asclepius — Phase 5, Stage A

## Conversational history engine — architecture and foundation

Written for the Asclepius team and anyone reviewing the Phase 5 work.
Prototype on synthetic data. No clinical validation, no diagnostic capability,
no medical certification is claimed or implied.

---

## 1. Stage objective

Build the domain foundation for a controlled, structured patient-history
conversation: the question flow, the state machine, the storage, the API and
the tests.

Explicitly out of scope for this stage, and absent from the code: voice, speech
recognition, speech synthesis, Bhashini, microphone or audio handling, red-flag
triage, emergency alerts, diagnosis, treatment or prescription recommendation,
kiosk mode, ABHA, ABDM, FHIR, AYUSH, drug interactions, lab reference ranges,
and autonomous medical decisions of any kind.

**There is no AI in Phase 5A.** No model is called, no provider is configured,
no prompt exists. Every question the engine asks is chosen by a predicate over
answers already given. This is deliberate: the conversation's safety properties
are easier to establish and test when nothing in the loop is probabilistic, and
interpretation can be added later between "answer" and "candidate" without
moving any of the boundaries below.

## 2. What a conversation is

```
start
  → awaiting_answer        the engine chose a question, and recorded why
  → answer                 the patient's own words, kept as given
  → candidates             what the answer might mean, deterministically
  → …                      next applicable question
  → awaiting_confirmation  every applicable question answered
  → confirm / edit / reject each candidate
  → completed              "your responses have been collected"
```

`completed` means the configured flow reached its end. It does not mean a
history is complete, and nothing in the system scores completeness.

Two states are deliberately **not** stored. `not_started` is absent because a
patient with no session simply has no row — the same reasoning as D-054.
`active` is absent because it is exactly "awaiting_answer or
awaiting_confirmation", and a state that is the union of two others is a second
place for the truth to live.

## 3. The flow

`app/conversation/flow.py` — 16 questions across 10 sections, as frozen
dataclasses rather than rows in a table (**D-064**).

| Section | Questions |
|---|---|
| Current problem | `problem.description` |
| Onset & duration | `symptom.duration`, `symptom.happened_before` |
| Location | `symptom.is_pain`, `symptom.site` |
| Character | `symptom.character`, `symptom.radiates` |
| Associated symptoms | `symptom.associated` |
| Aggravating / relieving | `symptom.aggravating`, `symptom.relieving` |
| Relevant history | `history.conditions`, `history.family_conditions` |
| Medications | `medication.taking_any`, `medication.which` |
| Allergies | `allergy.any`, `allergy.which` |

These are the things a clinician asks anyone about a new complaint. **It is not
a diagnostic tree.** A branch selects the next *question*; it never draws a
conclusion, and no answer is treated as evidence of a condition.

Three properties keep old answers readable when wording changes:

- a **stable id** (`symptom.duration`) that never changes;
- a **version** that increments when wording or options change;
- a **localisation key**, so the text a patient saw is resolved in the browser
  and translating a question never rewrites history.

Branching is a plain predicate over prior answers. `symptom.site`,
`symptom.character` and `symptom.radiates` are asked only when the patient
answered yes to `symptom.is_pain` — the explicit answer, never a scan of the
free-text complaint for the word "pain". Reading prose for meaning is
extraction, and extraction goes through the patient.

Every selection carries its reason, stored on the session, so "why was I asked
this?" is answerable later without replaying anything. That stored reason is
English and stays on the server, for support and debugging. What a browser
receives is `because_key` — `conversation.why.pain` — so the explanation reaches
a Tamil speaker in Tamil. Putting an English sentence on screen is the same
defect whoever wrote it, and Phase 4 already paid for learning that once.

## 4. Data model — three tables, no Phase 4 changes

| Table | Holds |
|---|---|
| `conversation_sessions` | One run through the flow. Flow id and version, status, language, where the engine has got to and why, and a `revision` counter |
| `conversation_responses` | One answer per question. `answer_text` is the patient's own words and is never normalised; `answer_value` is the controlled form (option ids, duration) |
| `conversation_candidate_facts` | What an answer might mean, until the patient says it does |

Migration `0008`, reversible, tested base → head → base → head on PostgreSQL 16.
No existing table is altered, so Phases 1–4 behave identically with or without
the revision applied.

### Why candidates are not `AIExtractedFact` (D-060)

Reusing the Phase 2 table was the obvious move and it was wrong, for three
independent reasons. Its `artifact_id` is non-nullable and a deterministic
conversation produces no AI artifact, so reuse would mean altering a Phase 4
table. Its evidence shape — verbatim quote, character offsets, page, bounding
box — describes a document and cannot describe a tapped option, whose evidence
is (question id, question version, response id). And it is named and documented
as AI-extracted, which this is not.

What is **not** duplicated is the confirmed representation. A confirmed
candidate becomes a `MedicalRecord` through the mapping **imported from**
`app.services.ai_facts`, not restated, so the two paths cannot drift into
disagreeing about whether an allergy becomes a record. Conversation-derived
records therefore flow into sharing and the Phase 4 case bundle with no further
work.

## 5. Safety properties, and where each is enforced

| Property | Enforced by |
|---|---|
| The patient's words are never overwritten | `answer_text` written once; `MedicalRecord.content` is the original text, the edit lives in `edited_value` |
| A candidate is a suggestion until acted on | `review_state` starts `pending`; no record is written before confirmation |
| Attribution comes from the question, not the answer | `QuestionDefinition.subject`; `history.family_conditions` is `FAMILY` (**D-062**) |
| A relative's condition never becomes the patient's | `_record_type_for` → `FAMILY_HISTORY`; `other`/`unknown` write nothing |
| The client cannot steer the conversation | No `next_question_id` field exists; a mismatched `question_id` is `409` (**D-061**) |
| A client cannot write arbitrary JSON into a record | `AnswerValueIn` is a closed schema with `extra="forbid"` |
| An option that was not offered is refused | Server validates choices against the question's own option set |
| No payload can express a clinical conclusion | No field exists for diagnosis, severity, triage, risk or urgency |
| A doctor cannot reach a conversation | Every route resolves the patient from the token; there is no doctor route |
| Question text never crosses the wire | Only `prompt_key`, `help_key`, `label_key`, `because_key` |
| No English prose reaches a non-English speaker | The reason a question was asked travels as `because_key`; the English sentence stays on the server |
| The audit log holds ids, not sentences about symptoms | `question_id` and `section` are logged; the prose reason is not |

## 6. Idempotency and concurrency (D-063)

Two different problems, two mechanisms, both needed.

**Replays.** Every answer carries a client-supplied `idempotency_key`, unique
per session. The same request twice produces one response, one candidate, and
leaves the conversation on the same question at the same revision. The unique
constraint is the backstop when two replays race past the in-memory check.

**Races.** Every accepted transition increments `revision`. A client may send
the revision it last saw; an answer built against a stale one is refused with
`409 conversation_out_of_date` rather than both requests advancing and a
question being skipped.

## 7. API

All under `/api/v1/patients/me/conversations`. The patient is resolved from the
token on every route.

| Method | Path | Does |
|---|---|---|
| `POST` | `/` | Start, or hand back the conversation already open |
| `GET` | `/current` | The conversation in progress, or `404` |
| `GET` | `/{id}` | One conversation |
| `POST` | `/{id}/answers` | Record an answer; the **server** picks what comes next |
| `POST` | `/{id}/pause` | Pause |
| `POST` | `/{id}/resume` | Resume, choosing the next question afresh from the answers |
| `POST` | `/{id}/complete` | Close, once every applicable question is answered |
| `POST` | `/{id}/abandon` | Stop without finishing; answers already given are kept |
| `POST` | `/{id}/candidates/{cid}` | Confirm, edit or reject one candidate |

Backend endpoint count: **55 → 64**.

## 8. Verification

| Check | Result |
|---|---|
| Backend, PostgreSQL 16 | **559 passed, 1 skipped** (baseline 497/1) |
| Backend, SQLite | **556 passed, 4 skipped** (baseline 495/3) |
| New Phase 5A tests | **61** — 36 domain, 25 API |
| Migration `0008` base→head→base→head | Clean; `alembic check` reports no drift |
| `0008` reversible on its own | Confirmed; `medical_records` untouched by the downgrade |
| Frontend tests | **114 passed** (82 + 8 + 13 + 11) — unchanged |
| Frontend typecheck | Clean |
| Frontend production build | Clean, exit 0 |

The 61 tests cover all 25 scenarios the brief required: session creation, first
question, answering, advancing, conditional branching, skipping, candidate
creation, confirmation, editing, rejection, pause, resume, completion, invalid
transitions, duplicate responses, replayed requests, unauthorized access, wrong
patient, wrong doctor, old question version, old flow version, attribution,
multilingual response metadata, provenance and audit events.

## 9. Things to be told plainly

**Every number above is measured against the final tree.** Two earlier
backend runs were discarded rather than quoted, because source changed under
them — the record-title fix and then the localisation-key fix. The counts
reconcile exactly: PostgreSQL 497 → 559 is the 61 new conversation tests plus
the new migration test; SQLite 495 → 556 is the same 61, with the migration
test skipping as it does without a PostgreSQL URL.

**One Phase 4 test file was edited.** `tests/test_migrations.py` called
`alembic check` while the database sat at revision `0007`, which only means
anything at head; adding `0008` made head move and the assertion fail. The fix
is one added `upgrade(cfg, "head")` before the check. No Phase 4 production
code, migration or behaviour was touched, and the test's original intent —
0007 steps down and back up cleanly — is unchanged and still passing. Flagging
it because the brief asked to be told about any Phase 4 change at all.

**The localisation keys do not exist yet.** The flow references
`conversation.q.*` and `conversation.option.*`; no catalogue defines them.
That is correct for a backend-only stage with no UI, and it is a Phase 5B
prerequisite — the conversation cannot be shown to anyone until those strings
are written and reviewed by native speakers.

**A patient cannot yet change an earlier answer.** The `superseded_at` column
exists and every read path already filters on it, so turning the feature on
will not mean revisiting those queries — but nothing sets it today, and the
model docstring says so rather than implying otherwise.

**`review` is a declared section with no questions in it.**
`ConversationSection.REVIEW` covers the confirmation step, which is a state
rather than a question. It is not dead vocabulary, but nothing in the flow
tuple carries it.

**The flow is not clinically reviewed.** It is a reasonable general
symptom-history structure written by engineers. Before any use with real
people it needs a clinician to go through it question by question.

## 10. Decisions recorded

Appended to `docs/DECISIONS.md`, which is where D-001 to D-059 live — the brief
asked for `docs/decisions/D-060-*.md`, but that directory does not exist and
creating it would split the log across two mechanisms.

- **D-060** — Conversation candidates are their own staging table, not `AIExtractedFact`
- **D-061** — The server decides the next question; a client says only what it answered
- **D-062** — Attribution comes from the question, never from the answer
- **D-063** — A client-supplied key for replays, a revision for races
- **D-064** — Questions are versioned configuration, not rows in a table
- **D-065** — Why a question was asked travels as a key, not as a sentence

## 11. What Stage 5B would need

Not started, not designed, listed only so the boundary is clear: the
localisation catalogues; the patient-facing conversation UI in the Folded Sheet
language; a review screen for confirming candidates; and a decision about
whether an interpretation step belongs between answer and candidate — which is
the first point at which a model would enter this feature at all.
