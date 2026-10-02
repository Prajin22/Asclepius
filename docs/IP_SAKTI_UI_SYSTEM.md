# Asclepius — UI System (`PRODUCT=ip_sakti`)

Users see this product as **Asclepius**, subtitled "Intellectual Property &
Regulatory Guidance for Ayurvedic Products". *IP-SAKTI* / `ip_sakti` remain the
internal identifiers: the product value, the branch, routes, storage keys, file
names and migrations keep them.

**Applies when `NEXT_PUBLIC_PRODUCT=ip_sakti`.** CareBridge's design language is
[docs/DESIGN.md](DESIGN.md) and is unchanged. Both products share one component
library (`packages/ui`) and one Tailwind theme (`packages/ui/src/theme.css`).
IP-SAKTI gets its own look by redefining the theme's colour, radius and shadow
tokens under `html[data-product="ip_sakti"]` (`apps/patient-web/app/globals.css`).
No second UI framework is involved.

Phase 3.5 built this layer. It is presentation only: no retrieval, no answers,
no citations and no new API endpoints. Every screen reads the Phase 1–3 API as
it already is.

## 1. Principles

1. **Evidence before prose.** Legal words appear only as quotations of
   approved corpus text, on their own "source" material, with the
   provenance needed to check them. The product's own words never look like
   law.
2. **Never pretend.** A capability that does not exist yet is shown as not
   available, in words. No placeholder answer, citation, statute, conversation
   or person is ever drawn to fill a screen.
3. **Two lanes, never mixed.** India and International are separate panels.
   Each has its own name, icon and ruled edge, so colour is never the only cue.
4. **Unknown is a first-class answer.** "I don't know" is always offered, set
   apart but not alarming. It stops the classifier and says what is missing.
   Nothing is assumed.
5. **The user decides.** A classification result is a proposal until the user
   confirms it. Rejecting it never puts another category in its place.
6. **Calm and institutional.** No gradients, no glassmorphism, no chatbot
   bubbles, no medical imagery, no seals or emblems that suggest official
   standing.

## 2. Tokens

The IP-SAKTI layer is a cool herbarium-paper ground with deep-teal ink.
Contrast ratios below were computed against the surface each text sits on.

| Token | Value | Use | Contrast |
|---|---|---|---|
| `canvas` | `#eef2ef` | page ground | — |
| `surface` | `#fbfcfa` | cards, header, sidebar | — |
| `sunken` | `#f1f4f1` | wells, quiet panels | — |
| `line` / `line-strong` | `#d3ddd7` / `#7f9089` | dividers / control borders | line-strong 3.3:1 |
| `ink` / `muted` / `subtle` | `#13201d` / `#475450` / `#56635f` | text | 16.3 / 7.7 / 6.1:1 |
| `brand` / `brand-strong` | `#0e5f63` / `#0a4649` | primary action, active state | white on brand 7.4:1 |
| `brand-soft` / `brand-tint` | `#d9ece9` / `#eef6f4` | selected, active nav | — |
| `focus` | `#0a4649` | focus ring | — |
| `lane-india` on `lane-india-soft` | `#8a3b12` on `#f7ebe2` | India lane | 6.6:1 |
| `lane-intl` on `lane-intl-soft` | `#1f4b80` on `#e6edf7` | International lane | 7.5:1 |
| `source` / `source-line` / `source-ink` | `#fbf7ec` / `#d9c79c` / `#2b2417` | quoted official text | 14.4:1 |
| `demo` on `demo-soft` | `#6b4e00` on `#fbf3d9` | synthetic demo data | 7.0:1 |

Status colours (`info`, `success`, `warning`, `danger`) keep the shared
theme's values and meanings. Radii are softer than CareBridge's (`sm` 4px, `md`
8px, `lg` 10px). Shadows are cool-tinted, never black. Type uses the shared
scale (`text-display`, `title`, `page`, `heading`, `subheading`, `body`,
`small`, `caption`, `label`, `value`).

Motion is one entrance, `animate-rise` (4px, `--duration-base`). It is applied
only under `motion-safe:`, and the shared theme stops animation under
`prefers-reduced-motion`.

## 3. Navigation

`components/sakti/nav.ts` is the single source: `SAKTI_PAGES` (every screen
and whether its capability exists) and `SAKTI_NAV` (each role's destinations,
in order; the first is where the role lands, `lib/routes.ts`).

| Role | Destinations |
|---|---|
| user | Dashboard · *Your products:* My Products, Classify · *Guidance:* Ask, Escalate |
| facilitator | Incoming escalations, Brief, Messages, Notes |
| curator | Corpus, Upload, Draft / Diff, Approve |
| admin | Facilitators |

`SaktiShell` provides:

- **Desktop (≥1024px):** a persistent sidebar with the wordmark, the area name,
  grouped destinations, an active indicator (tint plus a left bar), a "Later"
  marker on destinations whose capability does not exist yet, and the
  disclaimer.
- **Top bar:** the area name, the demo marker, the language switcher, and the
  account menu (email, role, sign out).
- **Phone and tablet (<1024px):** a compact header. The menu button opens the
  same destinations in the shared `Sheet` dialog, which has focus management,
  closes on Escape and returns focus. The wordmark, "Asclepius", gives way to its
  square below 400px.

## 4. Page inventory

| Route | Screen | State |
|---|---|---|
| `/` | Landing: what works today and what does not | built |
| `/login` | Sign-in, principles, synthetic demo accounts | built |
| `/dashboard` | Hero, three actions, products, readiness, recent classification, reference status, getting started | built |
| `/my-product` | Product cards, search, state filter | built |
| `/my-product/new` | Nine-section product editor | built |
| `/my-product/[id]` | Product state, the user's description, classification history | built |
| `/my-product/[id]/edit` | Product editor | built |
| `/classify` | Choose a product; its state and history | built |
| `/classify/[id]` | Guided questions, unknown stop, result and confirmation | built |
| `/ask` | Question form, two empty answer lanes | screen only — no answer service |
| `/escalate` | Placeholder | later |
| `/facilitator/*` | Incoming, Brief, Messages, Notes: real layouts, empty | later |
| `/curator` | Corpus stats, sources, classifier references, instruments | built (Phase 2, polished) |
| `/curator/upload` | Five-step upload: Select, Metadata, Parse, Review, Submit | built |
| `/curator/drafts`, `/curator/approve` | Queues | built |
| `/curator/sources/[id]/diff` | Side-by-side diff on wide screens, inline on narrow | built |
| `/admin` | Facilitator table (empty); demo accounts in demo mode | later |

## 5. Components

**UI kit** (`components/sakti/ui`):

| Component | Purpose |
|---|---|
| `StateBadge` | A product's classification state: icon, word and tone |
| `LaneMark`, `laneRule` | Lane name with its icon. Rule: solid 4px for India, double 6px for International |
| `DemoTag` | "Demo data", dashed amber. Only on synthetic records |
| `StatTile` | A labelled count |
| `StepProgress` | "Step n of total" as text, repeated by a segmented `role="progressbar"` |
| `ChoiceCard` | A real radio under a large target. The `unknown` kind is dashed and neutral |
| `SectionCard`, `NeedTag` | A numbered section; required / optional |
| `EmptyPanel`, `LaterRelease` | An honest empty state; a capability that is not built yet |
| `ReadinessItem` | Ready / not ready yet, with screen-reader text |
| `InfoOnly` | "Information only — not legal advice." |

**Product and classifier** (`components/sakti/classify`): `ProductEditor`,
`MyProducts` / `ProductCard`, `ProductDetail`, `ClassifyStart`,
`ClassificationFlow` (`QuestionCard`, `NeedsInformation`, `Result`),
`ClassificationTimeline`, `SessionBadge`, `ReferenceList`, `SampleProductButton`.

**Answer contract** (`components/sakti/answer`): the types a cited answer will
have (`types.ts`), and the pieces that will show it:

| Component | Shows |
|---|---|
| `AnswerPanel` | One lane: name, icon, ruled edge, scope. Either its answer or its empty state |
| `AnswerPoint` | A statement *about* the quoted text, with numbered links to its citations. Not rendered without a citation |
| `SourceCitation` | The evidence object: lane, authority, instrument, label, the exact words, version, validity, recorded status, retrieval date, source document, text checksum, OCR note |
| `ConfidenceBadge` | Supported / partly supported / not enough support, in words. Never a percentage |
| `NotCovered` | What the sources do not cover |
| `EscalationSuggestion` | A person can look; disabled until escalation exists |
| `AsOfDate` | The date the law is read at |

In Phase 3.5 these appear on screen only in their empty states. They are
exercised with synthetic, plainly non-legal fixtures in
`components/sakti/answer/answer.test.tsx` only.

## 6. Status semantics

Every status pairs an icon and a word with its tone.

**Product classification state.** It is derived on the client
(`classify/overview.ts`) from what the API returns:

| State | When | Tone / icon |
|---|---|---|
| Not classified | no open session, no confirmed classification (a rejected result leaves this) | neutral / dashed circle |
| Classification in progress | open session, `incomplete` | info / hourglass |
| Requires information | open session stopped at "I don't know" | warning / question |
| Awaiting confirmation | open session `determined` | brand / clock |
| Confirmed | the product has a confirmed classification | success / seal |

**Session status:** in progress, requires information, determined from your
answers, confirmed by you, rejected by you, replaced by a newer
classification.

**Corpus:** review state draft / under review / approved / rejected, and
reading state not read / text read / read — needs checking / could not be read.

**Reference slots:** verified (names stored metadata only), unverified (not
relied on), corpus required (nothing cited).

## 7. Breakpoints

The Tailwind defaults apply: `sm` 640, `md` 768, `lg` 1024, `xl` 1280. The
sidebar appears at `lg`. Layouts were checked at 390, 430, 768, 1024, 1280 and
1440px in English, Hindi and Tamil for horizontal overflow and for raw
catalogue keys. Wide-only features degrade rather than shrink: the diff is
side by side only at `lg` and above, and the editor's section index appears
only at `xl`.

## 8. Accessibility

- Semantic landmarks: skip link, `nav`, `main`, and labelled `section`s.
  Headings are in order, with one `h1` per page.
- Every control has a visible label. Hints and errors are wired through
  `aria-describedby`, and invalid fields set `aria-invalid`. The product
  editor moves focus to a missing name.
- Answer cards and lane toggles are native radios and buttons. Toggles use
  `aria-pressed`, disclosures use `aria-expanded`/`aria-controls`, and step
  lists use `aria-current="step"`.
- Dialogs (menu sheet, demo explanation) are modal (`aria-modal`), take focus
  when they open, close on Escape and return focus to what opened them. The account menu closes on Escape or an outside
  click and returns focus to its button.
- Status changes (a question held, unsaved changes, result counts) use
  `role="status"`; errors use `role="alert"`.
- Focus is always visible. Targets are at least 44px on touch. No state is
  carried by colour alone. Motion respects `prefers-reduced-motion`.

## 9. Demo mode

When the API reports `demo_mode: true` (`GET /meta/product`):

- A "Demo data" marker sits in the header on every signed-in screen. Pressing
  it explains what is synthetic: the accounts, and a sample product if one is
  loaded.
- The dashboard and My Products offer **Load a sample product**, which adds one
  product to the signed-in user's own list through the ordinary API. Its name
  carries "DEMO DATA", it is labelled wherever it appears, and its values are
  generic ("Sample ingredient A").
- The administrator sees the four synthetic demo accounts (emails and roles,
  never passwords), labelled as configuration and not real people.
- **Never synthetic:** legal text, statutes, citations, provisions, sources,
  government information, escalations, conversations or facilitators. The
  corpus holds only what curators add from official sources.

Outside demo mode none of this appears.

## 10. Phase 4 integration points

- **Ask:** `AskPage` collects question, product, as-of date, lanes and answer
  language. Replace the "held" branch of `submit` with the answer request, and
  render each lane's `LaneAnswer` in the existing `AnswerPanel`.
- **Answer contract:** `components/sakti/answer/types.ts`. Its points must
  carry citations whose `SourceRef` comes from approved provision versions
  only. `AnswerPoint` already refuses an uncited point.
- **Confidence:** map the engine's support levels to the three words in
  `ConfidenceBadge`. Do not show numbers.
- **Abstention and escalation:** `NotCovered` and `EscalationSuggestion`
  (`available` turns the button on when escalation exists).
- **Navigation:** flip `SAKTI_PAGES.ask.available` (and later `escalate`,
  `incoming`, `brief`, `messages`, `notes`, `facilitators`) in the change that
  builds the capability. The "Later" markers and the landing page follow.
- **Dashboard readiness:** "Cited answer engine" is hard-coded as not ready.
  Read it from the API when the service reports its own state.
