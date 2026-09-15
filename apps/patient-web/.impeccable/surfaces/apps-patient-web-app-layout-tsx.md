---
version: 1
slug: "apps-patient-web-app-layout-tsx"
primary_target: "apps/patient-web/app/layout.tsx"
related_targets: ["apps/patient-web/components/landing/LandingPage.tsx","apps/patient-web/components/AppShell.tsx","apps/patient-web/components/clinician/DoctorShell.tsx","packages/ui/src/theme.css"]
---

# Asclepius V2 (patient app, clinician workspace, landing)

Scope: every user-facing surface of apps/patient-web plus the shared system in
packages/ui. Visitor mode: Operate for the product, Persuade for the landing.

Audience: patients in India on budget Android phones writing in Tamil, Hindi or
English; approved doctors on a clinic laptop, phone for checking; administrators;
SIH judges reading the journey off the screen. Task: describe a problem, have
documents read, confirm what was found, choose what to share, consult, receive
doctor-authored instructions. Constraints: no Phase 4, no backend change unless
forced, WCAG AA, Indic scripts first class, speed over effects on phones.

Memorable moment: unfolding an organised item back to the words it came from.

## Direction contract

THESIS: Asclepius is one uncut sheet. Everything the machine derives stays
creased to the patient's original, and nothing is ever cut away or overwritten.
It refuses the dashboard of identical white cards that the category ships.

OWN-WORLD: Vermilion washi for the original, washi-cream ground, fold-white
crease lines, sumi ink for human authorship, one gold dot for what needs you.
Panels are divided by creases, not floated as cards; sequences carry a numbered
margin column; corners are near square; Noto Sans carries Latin, Tamil and
Devanagari as one humanist family, with mono for measured values.

STORY: A patient writes in their own language, watches Asclepius fold it into an
organised version whose every item unfolds back to their words, confirms each
one, chooses what to share, and receives the doctor's inked instructions.

FIRST VIEWPORT: The document workspace at 1440. Left, the original page on its
sheet, evidence lit where the selected value came from. Right, organised values
as valley-creased panels that press solid when confirmed. A numbered margin
column runs 1 Original, 2 Reading, 3 Organised, 4 Evidence, 5 Confirmed, with
the gold dot on the current step. The primary action sits at the foot of the
right column, and above the tab bar on a phone.

FORM: Folded Sheet, the orizuru sequence dealt as a challenger and chosen by the
user over Carved Relief and The Patient's Report File; seed key 629d3a70.

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance.

## Open decisions

- Whether the landing keeps GSAP or moves to a small scroll-progress hook (the
  3D fold sequence decides it).
- Doctor "Patients" grouping is derived from consultations in the frontend; no
  new endpoint.
