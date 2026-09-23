# Asclepius — Phase 4 Final Report

## AI case summarisation across a consultation

Written for the Asclepius team and anyone auditing the Phase 4 work.

**Prototype on synthetic data.** No clinical validation, no diagnostic
capability, no medical certification is claimed or implied. Every number below
describes this codebase and this synthetic dataset only.

---

## 1. Phase 4 objective

Help a doctor understand information a patient has *already shared with them*,
faster, by organising it — without the machine ever concluding anything.

The one-line statement of what was built:

> The machine decides what sits next to what. Every line points back at the
> human who said it. The originals never move.

## 2. Stage B — architecture

**One authorization resolver.** `consultation_service.resolve_authorized_context()`
turns share grants into rows. The doctor's case view and the summary source
bundle both call it, so what a doctor may read and what a provider may be shown
cannot drift apart. Extracting it was done first, with a full Phase 1–3
regression run before and after, and zero behaviour change.

**Opaque references (D-052).** Each authorised item gets a handle — `S1`, `S2` —
valid only inside one bundle. A provider is never shown a database identifier, so
it cannot invent one, cannot leak one, and cannot cite an item that was not
shared: an unshared row simply has no handle.

**Content hashing (D-054).** Shared records are live references (D-006), so the
canonical bundle hash covers what each item *says*, not which rows they are.
That hash is both the cache key and the staleness test. Staleness is computed at
read time, never stored — a stored flag would be wrong the moment a patient
edited a record.

**Append-only storage.** `consultation_summaries` (migration `0007`, reversible,
PostgreSQL-tested). Each real generation adds a row, so what a doctor was shown
survives for audit; "current" is the newest row.

**Budget (D-057).** Summaries charge the patient's 24-hour spend cap and a
separate per-consultation generation cap. They do *not* consume the patient's
hourly/daily run allowance, which is reserved for the patient's own work.

## 3. Stage C — provider integration

`summarize_case` is one non-abstract method on `AIProvider`, implemented once on
the shared HTTP base. The vendor adapters are generic over any `Prompt`, so
**OpenAI, Anthropic and Gemini required no adapter changes at all** — OpenAI's
strict `json_schema`, Anthropic's strict tool and Gemini's `responseSchema` each
constrain the new capability exactly as they constrain extraction. The local
deterministic provider implements it as rules, and `DEMO_MODE` pins the public
deployment to it.

Prompt `case_summary_v1`, versioned like every other, with its section
vocabulary derived from the enum so prompt and schema cannot diverge.

**Live smoke test:** 6 real calls to OpenAI `gpt-6-astra`. 0 provider errors,
schema validity 1.0, both hard gates passed, median latency 4,403 ms,
4,281 input / 325 output tokens, **estimated cost reported as unknown** because
no pricing is configured for that model — unknown stays unknown. Anthropic and
Gemini were verified against their wire formats only; **no live model has been
run against either**, and the evaluation reports them as unavailable rather than
estimating.

## 4. Stage D — doctor UI

The summary sits at the top of the column that holds what the patient shared,
fetched separately so the case never waits on it. Machine output wears the drawn
crease — dashed edge, quiet ground, an "AI organised" chip. The doctor's own
assessment and prescription keep their inked identity in a separate column.

Five states, all implemented: not generated, generating, ready, stale, failed.
Loading language is honest: "Preparing case summary… Grouping the information
the patient shared. Nothing is being analysed or diagnosed."

## 5. Source-grounding model

```
statement  →  cites one or more opaque handles
           →  application resolves each to a real row
           →  origin, subject, evidence, dates attached from that row
           →  doctor opens the source and reads the original words
```

A statement is a confirmed value or an application-written label. It is never a
copy of free text (D-056): the validator drops any statement of 80+ characters
that appears verbatim inside a cited source. The words are not the problem;
presenting them as the summary's own line is.

A claim about the patient's health must rest on a confirmed fact, a doctor's
prescription, or the title of a health record the patient typed themselves
(D-055). Narrative text can support a pointer, never a claim — turning narrative
into a health claim is extraction, and extraction goes through the patient.

## 6. Authorization model

Six gates, all before anything is built or sent:

1. approved doctor · 2. their consultation (404, never 403) · 3. visible status
· 4. patient AI consent · 5. budget · 6. *then* the bundle is built.

There is no code path that loads a patient's record and asks a model to ignore
part of it. The frontend sends only a consultation id.

## 7. Attribution model

Every fact's `subject` — self, family, other, unknown — is copied from the
source, never inferred, and the model is not asked for it. A family-attributed
item can only become family history. A statement whose cited facts disagree
about whose health it describes is dropped rather than merged. The UI leads such
a line with the attributing words: "my father — diabetes", never a bare
"diabetes".

## 8. Pending-fact model

Only confirmed and edited facts become statements. Pending facts never enter the
bundle at all, so no provider is ever offered them. They are reported as a count:
"1 patient-provided item awaiting confirmation is not included." Rejected facts
never leave the database.

## 9. Contradiction model

Disagreeing sources produce one flagged item citing both. The UI says
"Information differs across the shared records. Both records are shown. Nothing
here decides which is correct." Two doctors' prescriptions stay two entries,
each named. Nothing selects, ranks, merges or resolves.

## 10. Cache model

Identity is **provider + model + prompt version + bundle hash**. Change any one
and it misses — which is what stops a changed prompt silently serving output
produced by the old wording. A hit returns the stored row, calls no provider and
costs nothing. Editing a shared source invalidates; editing an unshared one does
not, because it is invisible to that doctor.

## 11. Audit model

Every real run writes an `ai_artifacts` row: operation, provider, model, prompt
version, 64-character source hash, consultation, status, error code, latency,
tokens, estimated cost. Content is counts and shape only — never the summary
text, never the patient's words, never a credential. Verified by inspecting real
rows, not by reading the code.

Audit actions: `summary_requested`, `summary_generated`, `summary_regenerated`,
`summary_viewed`, `summary_failed`, `summary_rate_limited`.

## 12. Evaluation methodology

52 synthetic consultations, generated from composable templates
(`evaluation/summary_cases.py`) so the set is reproducible and reviewable.
Coverage: English/Tamil/Hindi, confirmed and pending and rejected facts, family
history, medications, allergies, measurements, multiple documents, several
doctors, contradictory statements and prescriptions, missing information, and
prompt injection in patient text, file names and doctor notes.

Each case also carries **decoys** — items that exist in the fixture but were
never authorised — so leakage is measured rather than assumed.

Because "1.0 everywhere" could equally mean a blind harness,
`test_case_summary_eval_harness.py` feeds the harness deliberately misbehaving
providers and asserts the gates trip: leakage, unsupported claims, lost
attribution, a resolved contradiction, doctor-authored recast as a patient claim,
fabricated references, invalid schema. 10 tests, all passing.

## 13. Final metrics

Local deterministic provider, 52 cases. Identical to Stage C on every
non-timing metric.

| Metric | Result |
|---|---|
| **Unauthorised source leakage** | **0** — hard gate |
| **Unsupported clinical claims** | **0** — hard gate |
| Schema validity | 1.0 |
| Fabricated references | 0 |
| Evidence validity | 1.0 |
| Subject attribution | 1.0 |
| Origin preservation | 1.0 |
| Prescription attribution | 1.0 |
| Contradiction preservation | 1.0 |
| Omission rate (expected citations missed) | 0.0 |
| Items proposed / kept / dropped | 116 / 116 / 0 |

Mapping to the names the Stage E brief uses: *supported-fact precision* is the
unsupported-claim rate (0) and the drop rate (0.0); *supported-fact recall* is
the inverse of the omission rate (0.0 missed); *citation validity* is evidence
validity (1.0) together with fabricated references (0). I have reported the
metrics the harness actually computes rather than renaming them.

## 14. Adversarial tests (Stage E)

Two dedicated suites, **59 tests**, all passing.

`test_phase4_invariants.py` — 34 tests stating the ten invariants as pass/fail
assertions. `test_phase4_adversarial.py` — 25 tests attacking cache
invalidation, budget accounting, document provenance, multilingual attribution,
six provider failure modes, and the append-only history.

Findings worth recording:

* A database identifier **cannot even be expressed** as a source reference — the
  ref pattern rejects a UUID before validation runs. Stronger than being dropped.
* A provider that obeys an injected instruction still stores nothing: every
  handle it cites is real and authorised, and the items are dropped because
  nothing the patient confirmed supports them.
* Editing an unshared record costs no provider call and does not invalidate the
  cache; editing a shared one does both.
* A failed regeneration leaves the earlier ready summary fully intact.

## 15. Browser validation

Headless Edge over the DevTools protocol, production build, live API,
PostgreSQL 16. The script builds its own fixture and plants a marker string in
an unshared record.

**30 of 30 checks passed**, re-run at the end of Stage E on the final bundle.
Desktop 1440, tablet 834, phone 390; zero horizontal overflow at both smaller
widths.

## 16. Accessibility validation

axe-core 4.13, WCAG 2.0/2.1 A + AA, with every source panel expanded so the
disclosures are audited rather than skipped for being hidden.

| Scan | Violations |
|---|---|
| not generated · 1440 | 0 |
| ready · 1440 | 0 |
| stale · 1440 | 0 |
| failed · 1440 | 0 |
| generating · 1440 | 0 |
| ready · 834 | 0 |
| ready · 390 | 0 |

27 rules passing on each. The `generating` and `failed` states were produced by
writing the real rows the application itself writes, so the interface rendered
genuine states rather than mocks.

Manual checks axe cannot make — **7 of 7**: the source disclosure is in the
natural tab order (position 9 of 26 focusable elements); `aria-expanded` toggles
and the panel is revealed; a `:focus-visible` outline rule is defined
(`outline: 2px solid var(--color-focus)`); every disclosure is labelled and
wired to its panel; no infinite animation under `prefers-reduced-motion`; the
generating state has a polite live region with `aria-busy`; the failed state is
announced as an alert.

## 17. Known limitations

* **The unsupported-term check is lexicon-bounded**, exactly as the Phase 2
  drift check is. It cannot prove a statement faithful. The structural rule in
  D-055 carries the weight; the lexicon is a second layer.
* **Patient-typed record titles can support a claim** (D-055). The interface
  labels them "Patient-reported" and never as a verified diagnosis, but the
  title is still the patient's own text. Bounded to 60 characters.
* **Summary statements are English.** The doctor interface is English-only
  (D-018). Patient material is always quoted in its original language with `lang`
  set; the organised statements are not translated.
* **Source navigation expands in place** rather than driving a separate evidence
  pane — a deliberate choice, since the right column is the doctor's workspace.
* **Document evidence shows the page number, not the page image.** The Phase 3
  document panel further down the case view has the region viewer.
* **No live evaluation for Anthropic or Gemini.** Adapters verified against the
  wire format only.
* **The local provider is rule-based.** A demonstration of the same contract,
  measured by the same harness, and not clinical-grade.
* **One pre-existing flaky test.** `PrescriptionForm.test.tsx` (Phase 1) failed
  once in four full-suite runs on a `userEvent.type` timeout under parallel
  load; it passes in isolation and on repeat runs. Not introduced by Phase 4 and
  deliberately not touched.

## 18. Residual risks

1. **Lexicon coverage.** A model could assert a condition the lexicon does not
   know, citing a confirmed fact that happens to be about something else. The
   structural rule limits this to sources the patient confirmed, but does not
   eliminate it.
2. **Patient-typed titles.** The narrowest remaining semantic surface. A patient
   could type "Possible cancer" as a record title and the summary would carry it
   — labelled patient-reported, which is accurate, but it is their words in a
   clinical-looking list.
3. **Live-model behaviour is under-measured.** Six real calls is a smoke test,
   not an evaluation. The 52-case set has only ever been run against the local
   provider.
4. **Revocation is honoured but unreachable.** `consultation_shares.revoked_at`
   is respected everywhere, and a revoked item leaves the bundle and changes the
   hash — but no endpoint sets it yet.
5. **No formal security review or penetration test**, and no DPDP assessment.

## 19. Final test counts

| Suite | Result |
|---|---|
| Backend, SQLite | **495 passed, 3 skipped** |
| Backend, PostgreSQL 16 | **497 passed, 1 skipped** |
| — of which Phase 4 | 160 |
| — of which Stage E adversarial + invariants | 59 |
| Frontend (4 workspaces) | **114 passed** |
| Typecheck | clean, 5 workspaces |
| Production build | 18 routes |
| Browser validation | 30 / 30 |
| Accessibility (axe) | 0 violations, 7 scans |
| Accessibility (manual) | 7 / 7 |
| Phase 4 evaluation | 52 cases, both hard gates 0 |
| Phase 2 evaluation | unchanged (F1 0.912) |
| Phase 3 document evaluation | unchanged (all 1.0) |
| Migrations | base↔head twice, no drift |

Skips are the migration tests without a PostgreSQL URL, and a bundle-dump helper
that runs only when asked.

## 20. What Phase 4 does not do

**Asclepius Phase 4 does not diagnose patients, prescribe treatment, resolve
disagreements between doctors, or replace clinician judgment.**

It also does not: triage, score risk, rank or compare doctors, select or modify
a prescription, interpret a laboratory value against a reference range, infer
anything the sources do not state, turn absence of information into a negative
finding, or overwrite any original patient record.

Not implemented and not started: voice, speech-to-text, text-to-speech,
conversational history, adaptive interviews, SOCRATES interview structures,
red-flag triage, emergency alerts, kiosk mode, ABHA, ABDM, FHIR, AYUSH
workflows, and drug-interaction checking.

The machine organises. The patient confirms and controls sharing. The doctor
interprets and decides.
