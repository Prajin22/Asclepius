# Asclepius — design system

The product's job is to make the **source** of every piece of information
obvious, on a phone in a waiting room and on a laptop in a consulting room. The
visual system exists to serve that, not to decorate it.

> Brand concept: **the rod, not the oracle.** Asclepius is the instrument a
> patient and a doctor lean on. It never speaks as the authority.

## 1. Provenance — the one principle

Four sources must never look alike, and colour alone must never be what
separates them. Each carries a ruled edge, an icon and a label:

| Source | Surface | Rule | Component |
|---|---|---|---|
| Original — the patient's words, the uploaded file | `paper` (warm) | solid, paper | `ProvenanceBlock kind="original" \| "document"` |
| AI extracted — read text, English rendering, items | `ai` (cool steel) | **dashed**, steel | `kind="machine"` |
| Patient confirmed | `brand-tint` | solid, jade | `kind="confirmed"` |
| Doctor authored — assessment, prescription | `surface` | solid, ink | `kind="doctor"` |
| Needs review · Pending · Rejected | warning / surface / sunken | matching | `kind="needsReview" \| "pending" \| "rejected"` |

`ProvenanceChip` is the inline form, `ProvenanceBlock` wraps content, and
`ProvenanceLegend` explains all four where a newcomer first meets them.

Machine output is deliberately the quietest layer on screen: steel, dashed,
never jade. Jade is reserved for human action — the patient's decisions, the
doctor's authorship, primary buttons.

## 2. Tokens

All tokens live in `packages/ui/src/theme.css` as a Tailwind v4 `@theme` block.
Nothing in the apps should hard-code a colour, radius or duration.

**Type** — Geist for interface, Geist Mono for measured values (lab results,
dosages, page numbers), Noto Sans Tamil and Devanagari inside the same stack so
Indic scripts are first-class rather than a system fallback. Scale: `display`,
`title`, `heading`, `subheading`, `body-lg`, `body`, `small`, `caption`,
`label` (the only uppercase style), `value`.

**Colour** — ink, muted, subtle, line, line-strong, canvas, surface, sunken;
jade (`brand`, `brand-strong`, `brand-soft`, `brand-tint`, `focus`); paper
(`paper`, `paper-line`, `paper-ink`); steel (`ai`, `ai-strong`, `ai-soft`,
`ai-line`); status (`info`, `success`, `warning`, `danger`, each with a `-soft`
pair). Every text/background pair meets WCAG AA.

**Shape and depth** — radius `sm` 6px, `md` 10px, `lg` 14px, `xl` 20px,
`2xl` 28px. Shadows are tinted with ink, never pure black.

**Motion** — `--ease-out-soft` for entrances, `--ease-in-out-soft` for state,
durations 150 / 240 / 420 ms. Everything collapses under
`prefers-reduced-motion`, which `theme.css` enforces globally.

## 3. Components

`packages/ui` owns anything both apps use: `Button` (primary, secondary, ghost,
danger, onDark; sm/md/lg; loading state), `Card` with surface tones,
`Badge`/`StatusBadge`/`SourceBadge`, `Provenance*`, `Field` and inputs, `Sheet`
(bottom sheet on a phone, centred dialog above `sm`), `SegmentedTabs`,
`Skeleton*`, `Avatar`, `PageImage` (page with evidence outlined),
`ReadingProvenance` (how a page was read), `PrescriptionCard`, `MessageThread`,
`DocumentViewer`, `Feedback` states.

Icons come from one family at one weight — Phosphor, via
`@phosphor-icons/react/dist/ssr`. Hand-drawn SVG icons are not used.

## 4. Two device classes, one system

**Mobile** — bottom navigation within thumb reach, five destinations, 56px
targets; sheets instead of dialogs; sticky primary actions above the bar; full
page image then its reading, stacked; no WebGL.

**Desktop** — persistent rail, spacious canvas; the document workspace puts the
original page and what was read from it side by side, linked by selection; the
doctor's case view separates patient-shared material from the doctor's own work
(ink-ruled) as distinct zones.

## 5. Motion and 3D

GSAP drives the landing page's scroll reveals and the hero's assembly. In the
product, motion is only state: a button press, a loading state, a confirmation.

There is exactly one WebGL scene — the landing hero
(`components/landing/HelixScene.tsx`), where scattered information draws itself
into the rod. It is lazy-imported, skipped below 1024px, skipped under
`prefers-reduced-motion`, skipped when WebGL is unavailable, paused when
scrolled out of view, and disposed on unmount. A static SVG of the same idea is
the fallback. **No workflow depends on it.**

## 6. Copy and language

Every user-facing string lives in `packages/i18n/messages` — patient in English,
Hindi and Tamil; clinician in English. A test enforces key and placeholder
parity, and no component branches on a language code. The patient's original
wording is never replaced by a translation; both are shown, labelled.

## 7. Rules that are not negotiable

1. Machine output never wears jade, and never appears without a label.
2. A colour never carries a state on its own — icon and text always accompany it.
3. The original is always reachable from wherever its interpretation is shown.
4. Nothing implies a clinical decision has been made by the software.
5. Every interactive element has a visible focus state and a touch target of at
   least 44px on a phone.
