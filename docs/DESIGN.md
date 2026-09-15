# Asclepius — design system

The product's job is to make the **source** of every piece of information
obvious, on a phone in a waiting room and on a laptop in a consulting room. The
visual system exists to serve that, not to decorate it.

> Brand concept: **one uncut sheet.** A sheet can be folded many times and still
> be the same sheet: every crease records what was done to it, and any fold can be
> opened again. Asclepius never cuts the paper. The machine draws a crease, the
> patient presses it, the doctor writes in ink.

## 1. The fold language — the one principle

Five kinds of information must never look alike, and colour alone must never be
what separates them. Each carries an edge, an icon and a word:

| Source | Material | Edge | Component |
|---|---|---|---|
| Patient provided · original source | vermilion washi (`paper`) | solid | `ProvenanceBlock kind="original" \| "document"` |
| AI processed | quiet ground (`ai-soft`) | **dashed** | `kind="machine"` |
| Patient confirmed | surface | solid ink | `kind="confirmed"` |
| Doctor authored | surface, inked header | solid ink | `kind="doctor"`, `PrescriptionCard`, `Card tone="ink"` |
| Needs you | gold mark | solid | `Mark`, `kind="needsReview"` |

Also in the vocabulary: `pending`, `rejected` (an opened crease, always
restorable), `processing`, `shared`, `failed`.

`ProvenanceChip` is the inline form, `ProvenanceBlock` wraps content, and
`ProvenanceLegend` teaches all of it where a newcomer first meets it. Machine
output is deliberately the quietest layer: dashed, never vermilion, never inked.

The **gold dot** (`Mark`) means one thing only: this is waiting for the person
reading the screen. One per screen wherever possible.

## 2. Tokens

All tokens live in `packages/ui/src/theme.css` as a Tailwind v4 `@theme` block.
Nothing in the apps hard-codes a colour, radius or duration.

**Type** — Noto Sans carries Latin, Tamil and Devanagari as one humanist family,
so a patient's sentence and its English rendering match in weight and rhythm; each
script's file loads only when its glyphs appear. Geist Mono sets measured values,
because a lab result is an instrument reading, not prose. Scale: `display`,
`title`, `page`, `heading`, `subheading`, `body-lg` (the patient's own words),
`body`, `small`, `caption`, `label` (small caps, the only uppercase style),
`value`, `step`.

**Colour** — ink `#1A1A1A`, muted, subtle, line, line-strong, canvas `#EFE9DC`,
surface `#FBF8F1`, sunken; vermilion (`brand` `#D83A2E`, `brand-strong`
`#A82B1C`, `brand-soft`, `brand-tint`); paper (`paper`, `paper-line`,
`paper-ink`); crease (`ai`, `ai-strong`, `ai-soft`, `ai-line`); the mark
(`mark` `#D4AF37`, `mark-ink` `#7E5F0F`, `mark-soft`); status (`info`, `success`,
`warning`, `danger` `#8C1D18`, each with a `-soft` pair). Every pair was computed:
white on vermilion is 4.6:1, ink on surface 16.4:1, muted on surface 6.5:1, the
mark's ring 3.6:1 on the ground. Danger is deliberately darker than the sheet's
vermilion and never fills a large area.

**Shape and depth** — paper has corners: radius `sm` 2px, `md` 4px, `lg`/`xl`
6px, `2xl` 8px. Only true dots are round. Shadows are offset and soft, tinted
with ink, and are spent only on things that genuinely sit above the page.

**Motion** — `--ease-out-soft` for entrances, `--ease-in-out-soft` for state,
durations 180 / 240 / 400 ms. Everything collapses under
`prefers-reduced-motion`, which `theme.css` enforces globally.

**Browser surfaces** — selection, caret, native checkbox and radio accent,
scrollbars and link underline offset come from the palette, not browser defaults.

## 3. Components

`packages/ui` owns anything more than one surface uses: `Button` (primary,
secondary, ghost, danger, onDark; sm/md/lg; loading), `Card` with tones
(surface, paper, machine, quiet, ink), `Badge`/`StatusBadge`/`SourceBadge`,
`Provenance*`, `FoldTrack`/`Mark`/`Crease`, `Field` and inputs, `Sheet` (a sheet
on a phone, a centred dialog above `sm`), `SegmentedTabs` (tabs along a crease),
`Skeleton*`, `Avatar`, `PageImage` (page with evidence outlined), `ReadingProvenance`
(how a page was read, with engine and confidence behind a disclosure),
`PrescriptionCard`, `MessageThread`, `DocumentViewer`, `Feedback` states.

`FoldTrack` is the numbered margin column. It appears only where a sequence is
real: describing a problem, reading a document, a consultation's four folds. On a
phone it collapses to one line with a crease that fills as you go.

Icons come from one family at one weight — Phosphor, via
`@phosphor-icons/react/dist/ssr`. Hand-drawn SVG icons are not used, except the
mark itself (`Logo`) and the landing page's crease pattern.

## 4. Two device classes, one system

**Mobile** — bottom navigation within thumb reach (five destinations for
patients, four for doctors), 56px bars and 44px targets; sheets instead of
dialogs; sticky primary actions; collapsed sections with counts; page first, then
its reading; no WebGL and no scroll effects.

**Desktop** — a rail, a spacious canvas, and registered pairs: the original page
and what was read from it at the same scale, the patient's words beside the
organised version, the doctor's inked column in view while the shared material
scrolls.

## 5. Motion and 3D

Four moments, then silence: a crease drawn (machine output arriving), a crease
pressed (the patient confirms), something unfolded (rejected or reopened), the
mark moving on (the consultation advances). Nothing animates on page load, and no
section fades in on scroll.

There is exactly one WebGL scene — the landing hero
(`components/landing/FoldScene.tsx`), where a square of vermilion paper printed
with real demo text folds along its creases. It is lazy-imported, skipped below
1024px, skipped under `prefers-reduced-motion`, skipped on a data-saving
connection or a low-memory device, skipped without WebGL, paused off-screen, and
disposed on unmount. A static crease pattern of the same folds is the fallback.
**No workflow depends on it.**

## 6. Copy and language

Every user-facing string lives in `packages/i18n/messages` — patient in English,
Hindi and Tamil; clinician in English. A test enforces key and placeholder parity,
and no component branches on a language code. The patient's original wording is
never replaced by a translation; both are shown, labelled. Engine names, model
names and confidence scores are developer material and sit behind a technical
disclosure, never in a patient's reading line.

## 7. Rules that are not negotiable

1. Machine output never wears vermilion or ink, and never appears without a label.
2. A colour never carries a state on its own — an icon and a word always accompany it.
3. The original is always reachable from wherever its interpretation is shown.
4. Nothing implies a clinical decision has been made by the software.
5. Every interactive element has a visible focus state and a touch target of at
   least 44px on a phone.
6. Colour is spent in one place per screen: the sheet, and the primary action.
