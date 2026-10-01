# Asclepius — Phase 5, Stage B

## Deterministic history tree and adaptive branching

Written for the Asclepius team and anyone reviewing the Phase 5 work.
Prototype on synthetic data. No clinical validation, no diagnostic capability,
no medical certification is claimed or implied.

> **history_general v2 — status: `engineering_draft` · clinical review: `required`.**
> A reasonable structure for a first conversation about a new complaint,
> written by engineers. Not reviewed by a clinician, not validated against any
> guideline, not complete, and not a diagnostic tree. Every API payload says so.

---

## 1. Objective

Put a real general symptom-history tree on the Phase 5A foundation: which
questions exist, in what order, when each applies, what a valid answer is,
what is recorded when a question is *not* asked, and how the conversation
explains every step — all decided by the application, deterministically, with
no model anywhere.

**There is no AI in Phase 5B.** No provider is called, no prompt exists, and a
test fails if the engine module imports a model client, a clock or a random
source.

## 2. The history tree

21 questions across 11 sections, plus a review step. `?` marks a follow-up,
asked only when the question before it opens it.

| Order | Question | Type | Required | Opens / produces |
|---|---|---|---|---|
| 10 | `current_problem.primary` | free text | yes | symptom candidate (their words) |
| 20 | `symptom.onset.when` | single choice | yes (has *not sure*) | opens duration unless *not sure* |
| 30 | `symptom.duration` ? | duration or words | no | — |
| 40 | `symptom.location` | single choice | yes | *other* → where |
| 45 | `symptom.location.other` ? | free text | no | — |
| 50 | `symptom.character` | multi choice | yes | *other* → describe |
| 55 | `symptom.character.other` ? | free text | no | — |
| 60 | `symptom.radiation` | yes / no / not sure | yes | *yes* → where to |
| 65 | `symptom.radiation.location` ? | free text | no | — |
| 70 | `symptom.associated` | multi choice | yes | *other* → what else |
| 75 | `symptom.associated.other` ? | free text | no | symptom candidate |
| 80 | `symptom.aggravating` | multi choice | yes | *other* → describe |
| 85 | `symptom.aggravating.other` ? | free text | no | — |
| 90 | `symptom.relieving` | multi choice | yes | *other* → describe |
| 95 | `symptom.relieving.other` ? | free text | no | — |
| 100 | `history.relevant` | yes / no / not sure | yes | *yes* → details |
| 105 | `history.relevant.details` ? | free text | no | history candidate |
| 110 | `medications.current` | yes / no / not sure | yes | *yes* → which |
| 115 | `medications.details` ? | free text | no | medication candidate |
| 120 | `allergies.known` | yes / no / not sure | yes | *yes* → what |
| 125 | `allergies.details` ? | free text | no | allergy candidate |
| — | `review.confirm` | a step, not a question | — | — |

Two rules shape every question. **Every tap question offers an honest way
out** ("not sure", and where it fits "nothing noticed" or "none of these"), so
it can be required without forcing anyone to choose something they do not
believe. **Every free-text question can be declined**, because being made to
type something is not the same as having something to say — except the first,
since a conversation about a problem needs the problem.

Order is explicit numbers, not list position: a follow-up has a visible
insertion point (radiation 60, where it spreads 65), and nothing depends on the
order anything was written, stored or returned.

## 3. State transitions

```
start ──▶ awaiting_answer ──answer / decline──▶ awaiting_answer ─ … ─▶ awaiting_confirmation ──complete──▶ completed
              │    ▲                                  │                         │   ▲
            pause  resume                           revise ◀────────────────────┘   │
              ▼    │                                  └── opens a follow-up ─────────┘
            paused                                        (back to awaiting_answer)
   any open state ──abandon──▶ abandoned            completed / abandoned accept nothing further
```

After every accepted transition the service asks the engine to resolve the
whole flow from the answers on record, then reconciles three things to match
it exactly: the "not asked" rows, the current question and its reason, and the
status. Nothing depends on the path taken to reach a set of answers.

## 4. Branching examples

| Answer | What happens | Recorded reason |
|---|---|---|
| radiation = **yes** | "where does it spread?" asked next | `radiation_reported`, trigger `symptom.radiation`, predicate `radiation_is_yes` |
| radiation = **no** | not asked; a skip row, no answer | `radiation_not_reported` |
| radiation = **not sure** | not asked; stored without a yes/no | `radiation_not_reported` — the same skip, because it claims only that radiation was not reported |
| location = **other** | "where is it?" asked | `location_other_chosen` |
| associated = **none of these** | nothing asked, nothing recorded as a fact | `associated_other_not_chosen` |
| onset = **not sure** | "how long?" not asked | `onset_not_known` |
| allergies = **yes**, details **declined** | details were asked; "no answer" is recorded | the response is `declined`, and produces nothing |
| allergies **yes → no** (revised) | the details answer is retired, not deleted; a skip row replaces it | `allergies_not_reported`, cause `no_longer_applicable` |
| radiation **no → yes** (revised) | the old skip is superseded; "where does it spread?" is asked next, even from review | `radiation_reported` |

## 5. The question model

```
FlowDefinition   flow_id · version · status · clinical_review · questions
QuestionDefinition
                 id · version · order · section · response_type
                 prompt_key · help_key · options · required
                 category · subject · branch
Option           id · label_key · exclusive
Branch           predicate_id · trigger · when_chosen · opened · closed
```

A branch is **declared**, never a function: "ask this when that question's
answer includes one of these options". That makes the whole tree inspectable,
fingerprintable and explainable without reading code (**D-066**), and it
leaves no callable for a model to sit behind (**D-076**).

**Versioning (D-068).** A session is walked under the flow version it started
with, for its whole life. Every published flow's canonical form is hashed into
`flow.PUBLISHED`; a test fails if one is edited in place. A question whose
wording, options or type change gets a new question version — v2 asks
`symptom.duration`, `symptom.character`, `symptom.associated`,
`symptom.aggravating` and `symptom.relieving` as version 2 — and its prompt key
carries that version, so an old answer always renders against the wording the
patient actually saw. **v1 is kept**, re-expressed declaratively with identical
questions and branches, and all 61 Phase 5A tests now run against it.

## 6. The reason-code model (D-069)

Every question asked, and every question not asked, carries:

```json
{ "code": "radiation_reported", "trigger_question_id": "symptom.radiation", "predicate_id": "radiation_is_yes" }
```

stored on the session, on every response and on every skip, and rendered in
the browser from `conversation.reason.<code>`. **No English sentence is stored
anywhere as a reason.**

| Code | Meaning |
|---|---|
| `flow_sequence` | an unconditional question, next in order |
| `<x>_reported` / `<x>_other_chosen` / `onset_known` | a branch opened |
| `<x>_not_reported` / `<x>_other_not_chosen` / `onset_not_known` | a branch stayed shut |
| `trigger_declined` | the question it depends on was declined — so nobody knows |
| `trigger_not_applicable` | the question it depends on was itself not asked |
| `configured_flow_complete` | nothing applicable is left; review is next |

Skip reasons are worded to be true of both "no" and "not sure":
`*_not_reported`, never `*_not_present` or `*_absent`. The brief's example
`radiation_not_present` is **deliberately not followed**: it would record an
absence the patient never stated. A test enforces the wording.

## 7. Negative-answer semantics (D-070)

| The patient… | Stored as | Means |
|---|---|---|
| said **no** | answer `{"choices": ["no"], "bool": false}` | no |
| said **not sure** | answer `{"choices": ["not_sure"]}` — **no `bool`** | not sure; cannot be read as "no" |
| chose **not to answer** | response with `declined: true`, nothing else | "no answer" |
| was **not asked** | no response at all; a `conversation_skips` row with the reason | "not asked" |
| ticked **none of these** | answer `{"choices": ["none_of_these"]}`, no fact | none of *these* — not "no symptoms" |

"None of these", "not sure" and "nothing noticed" are exclusive: ticking one
with anything else is refused. "Not sure" about allergies is never written as
"no known allergies"; with no confirmed allergy, nothing is written at all.
Durations typed as words stay words — "some time ago" and "three days" are
stored as text, never converted to a number.

## 8. Candidates and confirmation (D-071, D-072)

* A candidate is created **only from a free-text answer to a question with a
  category**, and its value is the patient's own words. Five v2 questions can
  produce one: the problem, "other" symptoms, history details, medications,
  allergies. Taps and structured durations produce none — they are already
  exactly what the patient said, and restating them would write an English
  rendering ("3 days", "nausea") into the record.
* Every candidate is `pending` until the patient acts on it. **Completing the
  conversation confirms nothing**; reading the review confirms nothing.
* Confirming writes a health record through Phase 2's own mapping (imported,
  not restated): allergy → allergy, medication → medication, history →
  history note. A symptom stays with the problem it describes (D-025).
* **Revising an answer** marks it superseded and adds the new one. Follow-ups
  the correction shuts are retired with it; follow-ups it opens are asked next.
  Nothing is deleted. A revision is **refused** while anything drawn from an
  affected answer is confirmed — the fact is in the patient's record now, and
  changes through the record or by rejecting it first, never as a side effect.

**Attribution.** Given *"My father has diabetes, but I have headaches."*, the
engine does not read the sentence. It is stored whole; its candidate is the
whole sentence, attributed by the question that was asked; no "diabetes"
anything is extracted; and even confirmed as history it becomes a note
carrying the full sentence — never a "diabetes" condition. Bounded
interpretation of free text is Phase 5C's job, and it will still need the
patient's confirmation.

## 9. Localisation boundary (D-074)

No wording travels. Questions, help, options and reasons are keys and codes;
stored answers are option ids, identical whichever language they were tapped
in, and taps carry no language at all. Typed words keep their language and
their exact form.

v2 keys are derived mechanically and namespaced away from v1's:

```
conversation.question.<id>.v<version>     21 keys
conversation.help.<id>.v<version>          2 keys
conversation.choice.<set>.<option>        41 keys
conversation.reason.<code>                24 keys
```

The catalogue is nested and looked up by splitting on `.`, so a key cannot be
both a string and a group. v2's ids nest (`symptom.radiation` and
`symptom.radiation.location`), and v1's `conversation.q.symptom.duration` would
have collided with a v2 key beneath it; a test checks every key in every flow.

**None of these 88 strings has a translation.** They are a hard prerequisite
for any patient UI, and must be written and reviewed by native speakers, not
drafted by engineers. The full list is in Appendix A.

## 10. Security model

| A client cannot… | Because |
|---|---|
| choose the flow or its version | no request schema has either field; unknown fields are refused (422) |
| choose the next question | no `next_question_id` exists anywhere; answering a non-current question is 409 |
| answer a question that was not asked | it is never current (409); revising it is 409 `question_not_answered` |
| write arbitrary JSON into an answer | `AnswerValueIn` is closed; the engine accepts one shape per response type |
| create or confirm a candidate directly | no route creates one; only the review action changes its state |
| reach another patient's conversation | every route resolves the patient from the token; anything else is 404 |
| reach any conversation as a doctor | there is no doctor route. A confirmed conversation record reaches a doctor **only** if the patient shares it through the existing consultation mechanism — tested end to end: the doctor it was shared with sees it, the doctor it was not shared with sees nothing |
| advance a conversation twice | the session row is versioned; partial unique indexes hold one current answer per question and one open conversation per patient (D-073) |
| change state with a refused request | every check runs before any write; tests snapshot revision, rows, candidates, skips, audit lines and records before and after each refusal |

Audit lines carry ids, codes, versions and a `transition_type` — never what the
patient said, and never an English reason. A test sends a sensitive sentence
through every answer path and checks no audit line contains it.

## 11. Test matrix

| Row | Case | Covered by |
|---|---|---|
| A | normal linear flow | tree, matrix, eval `A-linear` |
| B | radiation = yes | tree, matrix, eval `B-radiation-yes`, API |
| C | radiation = no / not sure | tree, matrix, eval `C-*` |
| D | location = other | tree, matrix, eval `D-location-other` |
| E | associated = none of these | tree, matrix, eval `E-associated-none` |
| F | associated = other | tree, matrix, eval `F-associated-other` |
| G / H | medications yes / no | tree, matrix, eval `G-*`, `H-*` |
| I / J | allergies yes / no / not sure | tree, matrix, eval `I-*`, `J-*`, `J2-*` |
| K | several branches at once | tree, matrix, eval `K-*`, `K2-*` |
| L | skipped and declined follow-ups | tree, matrix, eval `L-*`, API review |
| M | invalid option | tree, matrix, eval `M-*` (4 paths) |
| N | wrong response type | tree, matrix, eval `N-*` (5 paths), API |
| O | replayed answer | matrix, invariants (every step) |
| P | unauthorised patient | matrix, API, invariants (every step) |
| Q | unauthorised doctor | matrix (with an authorised consultation), API |
| R | completed session | matrix, invariants |
| S / T | paused / resumed | matrix |
| U | revised / superseded answer | matrix (6 tests), API, invariants (random revisions) |
| V | old flow version | tree, matrix, eval `V-*`, the 61 Phase 5A tests on v1 |
| W | old question version | tree, matrix |
| X | deterministic repeatability | tree (500 repeats, 200 shuffles), matrix, invariants, eval (50 repeats per path) |
| Y | concurrent transition | matrix: arranged races (same question, pause vs answer, confirm vs revise, double start) and **real threads** |
| Z | idempotent retry | matrix, invariants (every step), API |

**Property tests (§37).** 4,500 seeded pure walks — 1,500 per flow plus 1,500
with five random revisions each — and 15 seeded walks through the real service
with random answers, declines, revisions, retries, intruder requests and
wrong-question attempts at every step. After every transition the persisted
state is checked against what the engine derives from the answers alone. All
ten invariants in the brief are asserted.

**Evaluation (`evaluation/run_conversation_eval.py`).** 29 hand-written paths,
expectations worked out from the flow definition rather than from the engine.
Six hard gates: wrong question, fake answer, collapsed negative, invented fact,
accepted invalid, nondeterminism. A harness test breaks the engine once per
gate and asserts each one trips — a clean run means the engine behaved, not
that the harness was looking away.

## 12. Measured results

| Check | Baseline (5A close) | Phase 5B |
|---|---|---|
| Backend, PostgreSQL 16 | 559 passed, 1 skipped | **751 passed, 1 skipped** |
| Backend, SQLite | 556 passed, 4 skipped | **746 passed, 6 skipped** (the migration tests need PostgreSQL) |
| Phase 5A tests (now on v1) | 61 | **61 passed** |
| New Phase 5B tests | — | **192** (98 tree · 61 matrix · 15 API · 5 invariants · 11 eval harness · 2 migration) |
| Evaluation paths | — | **29 / 29**; every v2 branch opened **10/10** and shut **10/10** |
| Hard gates | — | **0 · 0 · 0 · 0 · 0 · 0** (50 repeats per path) |
| Migration 0009 base→head→base→head | — | clean; `alembic check` no drift |
| New section values in the CHECK constraints | — | read back from PostgreSQL — present at head, absent at 0008 |
| 0009 downgrade with a v2 conversation on record | — | **refused**, nothing changed |
| Frontend tests | 114 | **114** (82 + 8 + 13 + 11) |
| Frontend typecheck / build | exit 0 / exit 0 | **exit 0 / exit 0** |
| API endpoints | 64 | **66** (+ review, + revision) |

The counts reconcile exactly: 559 + 192 new tests = 751 on PostgreSQL; 556 + 190 = 746 on SQLite, where the two new migration tests skip as the other three do. Both runs started after the last code or test change.
| Tables | 20 | **21** (+ `conversation_skips`) |

## 13. Clinical-review limitation

Both flows are `engineering_draft` with `clinical_review: required`, in code
and on every payload (**D-067**). Nothing in this stage should be described as
clinically validated, medically validated, physician-approved,
guideline-compliant, diagnostic or clinically complete. Specific things a
clinical reviewer would need to decide:

* whether location, character and radiation should be asked of everyone (they
  are, each with "not sure"), or only for some complaints;
* whether "how long?" should follow "when did it start?" (it does, optionally,
  unless the answer was "not sure");
* the option lists themselves, which are deliberately short;
* **family history, which v2 does not ask** — the brief's tree has none. The
  mechanism for it (D-062: attribution from the question) is intact and
  exercised by v1;
* red flags, which are out of scope here and must not be inferred from this
  tree.

## 14. Non-goals

Not built, not designed, not implied: LLM interpretation or generated
questions; voice, speech recognition or synthesis; Bhashini; audio; red-flag
detection; triage; emergency alerts; diagnosis or disease prediction; treatment
or prescription recommendation; drug-interaction checking; lab
reference ranges; kiosk mode; ABHA, ABDM, FHIR, AYUSH; a polished patient UI.

## 15. Remaining work

* **Localisation** — 88 strings, native-speaker written and reviewed.
* **Patient UI** — chat-style conversation, tap-to-answer, progress, review,
  editing. The API now carries everything it needs: the current step, the
  question with its reason, exclusive-option flags, the review with outcomes
  and what each candidate would become, and revision.
* **Clinical review** of the tree (§13).
* **Phase 5C** — bounded interpretation, in the one place D-076 allows.

## 16. Things to be told plainly

**Phase 5A had defects, and 5B fixes them.** The audit found, and this stage
corrects:

1. *The engine ignored `flow_version`.* 5A stored it but always walked the one
   tree, so the first new version would have changed every conversation in
   progress. Fixed by the registry (D-068).
2. *The concurrency protection was not atomic.* 5A compared `expected_revision`
   in Python, then wrote; two different answers arriving together would both
   have been recorded. **5A's report and D-063 overstated this.** Fixed with a
   versioned row and partial unique indexes, and tested with real threads (D-073).
3. *Two simultaneous starts could open two conversations.* Fixed by a partial
   unique index.
4. *A retry of the answer that entered review was refused* (409 for a request
   that had succeeded). Replays are now recognised before status checks.
5. *"Unsure" was stored as `bool: false`* — readable as "no". Fixed for every flow.
6. *Duration candidates wrote English ("3 days") into data.* Structured answers
   no longer produce candidates (D-071). This changes one v1 behaviour.
7. *A candidate over 200 characters would have overflowed the record title on
   PostgreSQL.* The title is now cut to fit; the content keeps every word.

**Phase 5A code and tests were changed.** The service, schemas, presenters,
models and flow module were rebuilt on the engine. The 5A API changed where 5B
required it: `skipped` is now `declined`, `because_key` is now `reason`, options
carry `exclusive`. The 61 Phase 5A tests were pinned to v1 and adapted for those
renames and for the registry — the rewording test now uses v1 and v2's real
`symptom.duration` instead of a monkeypatched question — and the flow-version
test was strengthened to check that a v1 session keeps being asked v1
questions. Their intent is unchanged and all pass.

**A pre-existing Phase 2 defect was found and not fixed.** `ai_facts` writes a
fact value of up to 300 characters into a 200-character record title — the same
overflow as item 7. Phase 2 is approved and outside this stage, so it is
reported, not touched.

**No Phase 4 production code, migration or behaviour was changed.** Migration
0009 alters only Phase 5 tables.

**The downgrade departs from precedent.** 0003 deleted rows its narrower schema
could not hold; 0009 refuses instead, because these rows are things patients
said (D-075).

**Nothing is committed.** Phase 5A (approved) and Phase 5B sit together,
uncommitted, in the working tree.

**Decisions are in `docs/DECISIONS.md`** (D-066 to D-076), where D-001 onwards
live. D-063 is marked corrected and D-065 partly superseded.

---

## Appendix A — localisation keys awaiting translation

**Questions** (`conversation.question.<id>.v<n>`): current_problem.primary.v1,
symptom.onset.when.v1, symptom.duration.v2, symptom.location.v1,
symptom.location.other.v1, symptom.character.v2, symptom.character.other.v1,
symptom.radiation.v1, symptom.radiation.location.v1, symptom.associated.v2,
symptom.associated.other.v1, symptom.aggravating.v2,
symptom.aggravating.other.v1, symptom.relieving.v2, symptom.relieving.other.v1,
history.relevant.v1, history.relevant.details.v1, medications.current.v1,
medications.details.v1, allergies.known.v1, allergies.details.v1.

**Help** (`conversation.help.<id>.v<n>`): current_problem.primary.v1,
symptom.duration.v2.

**Choices** (`conversation.choice.<set>.<option>`): common — yes, no, not_sure,
other, none_of_these, nothing_noticed · onset — today, days_ago, weeks_ago,
months_ago, years_ago · location — head, chest, abdomen, back, arm, leg ·
character — sharp, dull, burning, aching, throbbing, pressure, cramping ·
associated — nausea, vomiting, dizziness, fever, cough, shortness_of_breath,
fatigue, weakness · aggravating — movement, activity, food, position,
time_of_day · relieving — rest, position, food, medication.

**Reasons** (`conversation.reason.<code>`): flow_sequence,
configured_flow_complete, trigger_declined, trigger_not_applicable,
onset_known, onset_not_known, location_other_chosen, location_other_not_chosen,
character_other_chosen, character_other_not_chosen, radiation_reported,
radiation_not_reported, associated_other_chosen, associated_other_not_chosen,
aggravating_other_chosen, aggravating_other_not_chosen,
relieving_other_chosen, relieving_other_not_chosen, history_reported,
history_not_reported, medications_reported, medications_not_reported,
allergies_reported, allergies_not_reported.
