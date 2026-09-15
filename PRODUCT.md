# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Patients in India** who write in English, Hindi or Tamil, mostly on budget
  Android phones over mobile data (confirmed 2026-09-15). They describe a health
  problem in their own words, keep medical documents in one place, decide what a
  doctor may see, consult, and receive the doctor's instructions.
- **Doctors**, registered practitioners approved by an administrator, working
  mainly from a clinic laptop; on a phone they check the queue, read a case and
  reply to messages (confirmed 2026-09-15). They need to understand a case
  quickly and author the assessment and prescription themselves.
- **Administrators**, who review doctor applications.
- **Smart India Hackathon judges**, who evaluate a demo and must be able to follow
  the patient-to-doctor journey by looking at the interface alone.

## Product Purpose

Asclepius connects a patient's health information to a doctor with the source of
every item visible. It organises what the patient says and uploads; it never
decides. Success means a first-time patient uses it without explanation, a doctor
grasps a case in moments, and the software is never mistaken for the clinician.

## Positioning

Provenance is the product. Every item can be traced to its origin: the patient's
own words in their own language, or a page of an uploaded document with the
evidence marked. The interface shows how it was processed (copied exactly, read
by OCR, organised by AI) and whether the patient confirmed it. The doctor's own
work is authored, attributed and visibly distinct from anything a machine
produced.

## Operating Context

- Patient: describe a problem in any supported language → AI renders it in
  English and extracts facts, each with a quoted evidence span → the patient
  confirms, edits or rejects each fact. Upload a PDF or image → the text layer is
  copied exactly or the page is read by OCR → extracted items with page-level
  evidence → review. Find a doctor → choose the categories to share → request a
  consultation → messages → prescription.
- Doctor: queue of incoming, active and completed consultations → case view →
  accept or decline → assessment → prescription → messages → complete.
- Administrator: approve or reject doctor applications.
- The patient area is available in English, Hindi and Tamil; the clinician and
  admin areas are English only. Interface language and the patient's input
  language are separate settings.
- The public demo runs on Vercel (web) and a Render free-tier API that sleeps when
  idle, with `DEMO_MODE=true` and synthetic data.

## Capabilities and Constraints

- Built through Phase 3: patient and doctor authentication, patient profile,
  current problem, multilingual input, AI normalisation, structured AI facts with
  evidence, confirm/edit/reject, document upload, OCR and extraction, page-level
  evidence, document review, patient-controlled sharing, doctor case view,
  doctor-authored consultation and prescription, consent, audit, AI budget and
  rate limits, provider abstraction, doctor applications with admin approval.
- Out of scope: Phase 4 (diagnosis, clinical or treatment recommendations,
  triage, clinical reasoning, new AI capabilities, unrelated integrations).
  Useful Phase 4 ideas are documented, never built.
- AI never diagnoses, prescribes, chooses between doctors or invents facts. The
  patient's original input and original documents are never overwritten.
- Synthetic data only. No claims of clinical accuracy or regulatory compliance.
- Existing API, data, safety model, AI architecture and evidence model stay. A
  backend change happens only when a UI problem cannot be solved in the frontend,
  and then as the smallest tested change.
- One Next.js app serves every role; shared packages keep their internal
  `carebridge` identifiers. Every user-facing string says Asclepius.
- Phones are budget Android devices on mobile data: speed outranks visual effects
  there, and no workflow may depend on WebGL or animation.

## Brand Commitments

- The name is Asclepius.
- The mark is the rod of Asclepius. It may be redrawn to fit the visual language,
  but the idea stays (confirmed 2026-09-15).
- The interface must feel trustworthy, calm, intelligent, premium, human,
  technically sophisticated, accessible and fast. It must not feel like a student
  project, an admin template, a generic hospital portal, an AI chatbot or a
  science-fiction dashboard.
- No medical clichés: no large red crosses, cartoon doctors, hospital stock
  photography, heartbeat lines, excessive blue, spinning DNA, organs or crosses.
- Five kinds of information must look and behave differently: patient provided,
  AI processed, patient confirmed, doctor authored, and original source. AI output
  must never read as equivalent to a doctor's decision.

## Evidence on Hand

- A seeded synthetic demo (`backend/app/seed.py`): patient Arun Kumar, approved
  doctor Dr. Meera Sharma, pending applicant Dr. Kavya Nair, an administrator,
  a typed lab report and a scanned report read by OCR, consultations with
  prescriptions and messages.
- No real patients, testimonials, customers, usage figures, clinical validation
  or partnerships exist. None may be implied.

## Product Principles

1. Source before substance: nothing appears without where it came from.
2. The doctor decides; Asclepius organises.
3. The patient stays in control of consent, confirmation and sharing.
4. The web can be immersive; the phone must be effortless.
5. Safety stays visible: consent, evidence, originals and the emergency notice
   are never hidden behind decoration.

## Accessibility & Inclusion

- WCAG 2.2 AA: semantic structure, keyboard access, visible focus, sufficient
  contrast, labelled controls, clear errors, reduced motion honoured.
- Tamil and Devanagari scripts are first-class, never a fallback.
- One-handed phone use with touch targets of at least 44px.
- Status is never carried by colour alone.
