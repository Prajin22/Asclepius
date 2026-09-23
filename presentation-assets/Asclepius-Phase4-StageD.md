# Asclepius — Phase 4, Stage D

## Doctor-facing case summary

Written for the Asclepius team and anyone reviewing the Phase 4 work.
Prototype on synthetic data. No clinical validation, no diagnostic capability,
no medical certification is claimed or implied.

---

## 1. Stage objective

Make the Phase 4 capability — already built, validated and evaluated in Stages B
and C — visible and useful to a doctor, without loosening a single safety
boundary those stages established.

Nothing in this stage changes what the backend does. The authorization
boundary, the source bundle, the validation and the audit trail are exactly as
they were; Stage D is the screen in front of them.

## 2. Doctor workflow

```
open an authorized consultation
    → everything the patient shared renders immediately
    → the summary panel shows its own state, fetched separately
    → "Generate summary"                       (explicit; the doctor decides)
    → organised sections, each line citing its sources
    → "View source" on any line
        → the patient's own words, or the confirmed item,
          or the document page, or the colleague's note
    → the doctor writes their assessment
    → the doctor writes the prescription
```

The case page never waits on AI. The case view and the summary are two
independent requests, so a slow or failed summary costs the doctor nothing —
the information they actually need is already on screen.

## 3. UI states

All five states the Stage C API exposes are implemented.

| State | What the doctor sees |
|---|---|
| **Not generated** | "Case summary not generated", with a note that everything shared is already below, and a **Generate summary** action |
| **Generating** | "Preparing case summary…" with a live region, and "Grouping the information the patient shared. Nothing is being analysed or diagnosed." No partial output is ever shown |
| **Ready** | Organised sections; when it was generated from; which provider produced it; a **Regenerate** action and the remaining generation budget |
| **Stale** | "The case changed after this summary was generated", with **Refresh summary**. The stored summary stays readable — it is labelled, not withdrawn |
| **Failed** | "The summary could not be generated." plus "The original patient information below is unaffected and still available.", and **Try again**. No provider name, error code, stack or infrastructure detail reaches the reader |

Loading language is deliberately honest. The screen never claims to be
analysing records, checking a diagnosis or evaluating risk, because Phase 4
does none of those things.

## 4. Evidence and provenance

Every summary line carries **View source**, a disclosure that opens the
resolved sources beneath it. A source shows:

* what kind it is — patient statement, patient-confirmed item, patient-entered
  health record, document, previous consultation, previous prescription;
* who authored it, when the source is doctor-authored;
* the page number, for anything read from a document;
* the language, the date, and the quoted text itself — the patient's own words
  on vermilion paper, unaltered;
* **why the doctor may see it**: "Shared by the patient" or "Your own previous
  consultation".

No database identifier appears anywhere in the interface. Not the record id,
not the document id, and not the opaque bundle handle — that is an
implementation detail too. This is asserted by a test that scans the rendered
DOM for a UUID pattern, and by a browser check that does the same on the live
page.

## 5. Attribution

Attribution is never silent and never inferred by the interface — it is
rendered from the `subject` the backend copied off the source fact.

| Subject | Rendering |
|---|---|
| `self` | No special marking; the statement stands as the patient's |
| `family` | The attributing words lead the line — "my father — diabetes" — plus an "About a relative" chip and a distinct border |
| `other` | "About someone else" |
| `unknown` | "Attribution unclear". It is never quietly treated as the patient |

A relative's condition never appears as a bare line. A browser check asserts
this on the live page by looking for a lone `diabetes` inside the summary
region.

## 6. Pending information

When facts are awaiting the patient's confirmation, the summary says so as a
count and shows none of their content:

> **1 patient-provided item awaiting confirmation is not included.** They are
> not shown as facts because the patient has not confirmed them.

Stage D adds no patient-confirmation interface. That belongs to the existing
Phase 2 flow and stays there.

Items that validation removed are also stated — "1 item was removed because the
shared information did not support it" — so a thinned summary can never read as
a complete one.

## 7. Multiple doctors

Each previous consultation and each previous prescription stays its own entry,
named. Two prescriptions from two doctors render as two lines, each with
"Written by Dr. …". Nothing merges them into one anonymous opinion, and nothing
ranks them.

## 8. Contradictions

A contradiction renders as one line, flagged, citing both sides:

> **Information differs across the shared records.** Both records are shown.
> Nothing here decides which is correct.

Opening its sources shows both, side by side, neither marked preferred. A test
asserts both sources survive and that no "preferred" / "recommended" /
"more reliable" wording appears.

## 9. Authorship, visually

The rule is that machine output must never resemble a doctor's own work.

* **Machine-organised** content wears the drawn crease: dashed edge, quiet
  ground, the standard machine chip. Never ink, never vermilion.
* **The doctor's own assessment and prescription** keep their inked identity in
  a separate column, each with the black Doctor chip.
* **Patient material** stays vermilion paper wherever it is quoted.
* A patient-typed health record title renders as **"Patient-reported"**, never
  as a verified or confirmed diagnosis. This is the residual semantic surface
  Stage C identified (D-055): the interface makes the provenance explicit
  rather than changing the backend's semantics.

No status is carried by colour alone — every state ships with an icon and a
word, consistent with the rest of the product.

## 10. Accessibility

Verified with axe-core 4.13 (WCAG 2.0/2.1 A and AA) against the running
application, with every source panel expanded so the disclosures are actually
audited rather than skipped for being hidden.

| Scan | Violations | Rules passed |
|---|---|---|
| Desktop · not generated | **0** | 27 |
| Desktop · ready, sources open | **0** | 27 |
| Tablet · ready | **0** | 27 |
| Phone · ready | **0** | 27 |

Implemented: semantic headings per section, `aria-expanded` and `aria-controls`
on every source toggle, panels hidden with the `hidden` attribute rather than
unmounted so assistive technology can reach them, a polite live region with
`aria-busy` while generating, `role="alert"` on failures, visible focus from
the existing token system, `lang` on every quoted non-English passage, and no
information conveyed by colour alone.

## 11. Responsive behaviour

| Width | Behaviour |
|---|---|
| 1440 desktop | Two columns: shared information and summary on the left, the doctor's own workspace on the right. Sources expand in place |
| 834 tablet | Same structure, single column below the grid breakpoint |
| 390 phone | Single column, progressive disclosure. Sources stay behind their toggles; the doctor's workspace follows the shared information |

Horizontal overflow measured at 0 px at both tablet and phone widths. No 3D and
no decorative animation anywhere on this screen.

## 12. Browser validation

Performed against a **production build** driven by headless Edge over the
DevTools protocol, with a live API and PostgreSQL 16. The script builds its own
fixture through the API — a Tamil current problem with a relative's history, all
facts confirmed, a second unconfirmed problem, a shared record, and an
**unshared private record** used as a leak marker.

**30 of 30 checks passed.** Raw results in `stage-d/browser-checks.json`.

Covered: the case rendering without waiting on the summary; not-generated,
ready and stale states; generation; section rendering; no raw language code or
ISO date leaking into a statement; source panel opening; the patient's Tamil
words appearing as the source; no UUID shown; family attribution inside the
summary region; pending count; the doctor's assessment as a separate region;
keyboard focus and `aria-expanded`; refresh; tablet and phone rendering with
zero overflow; and the authorization checks below.

## 13. Security regression

Verified in the browser and against the API on the same live stack:

| Scenario | Result |
|---|---|
| Another doctor opens the consultation URL | No patient content rendered |
| Another doctor calls the summary API | **404** — not "forbidden", which would itself disclose existence |
| The patient calls the doctor summary API | **403** |
| Anonymous request | **401** |
| An unshared private record | Absent from the summary, the source panels and the whole rendered page |

The leak check uses a distinctive marker string planted in an unshared record
and asserts it appears nowhere in the rendered case.

The frontend sends only the consultation id. Authorization, source resolution,
bundle construction, provider invocation, validation, persistence and audit all
remain on the server exactly as Stage C left them.

## 14. Tests

| Suite | Result |
|---|---|
| `CaseSummary.test.tsx` (new) | **27 passed** |
| Patient-web total | 82 passed |
| Frontend total (4 workspaces) | **114 passed** |
| Backend total, PostgreSQL 16 | **438 passed, 1 skipped** |
| Typecheck | Clean, 5 workspaces |
| Production build | 18 routes |

The new frontend tests cover all fourteen scenarios the stage asked for, plus
the four distinctions that matter most: AI summary ≠ doctor assessment, family
fact ≠ patient fact, pending fact ≠ confirmed fact, and unshared content
appearing nowhere.

## 15. Known limitations

* **The summary is English.** The doctor interface is English-only (D-018);
  patient material is always quoted in its original language with `lang` set,
  but the organised statements are not translated.
* **Source navigation expands in place** rather than driving a separate evidence
  pane. This was a deliberate choice: the right column is the doctor's own
  workspace, and Stage D's brief requires the summary never to overpower it.
  A dedicated evidence pane would be a larger layout change.
* **Document evidence shows the page number, not the page image.** Region
  highlighting on a rendered page exists in the Phase 3 document panel further
  down the case view; the summary links to the page rather than duplicating
  that viewer.
* **Statement text comes from the provider.** The interface cannot localise or
  reformat it, which is why the local provider now emits labels with no dates or
  language codes in them — those belong to the source line, where the interface
  formats them.
* **No patient-facing summary.** Out of scope for Stage D by design.
* **Browser validation used the local deterministic provider** (`DEMO_MODE`).
  Live-provider behaviour was smoke-tested in Stage C, not re-run through the UI.

## 16. Screenshots

In `presentation-assets/stage-d/`:

| File | Shows |
|---|---|
| `01-desktop-not-generated.png` | The entry point before anything is generated |
| `02-desktop-ready.png` | A generated summary in the case view |
| `03-desktop-source-open.png` | A source expanded, showing the patient's Tamil words |
| `04-desktop-stale.png` | The stale banner after shared information changed |
| `05-tablet.png` | 834 px |
| `06-mobile.png` | 390 px, progressive disclosure |
| `07-other-doctor-denied.png` | Another doctor gets no patient content |
