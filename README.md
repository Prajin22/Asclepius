# CareBridge — Phases 1–3

A healthcare **communication and information-management** platform. Patients
record health information in their own language, control exactly what they
share, and consult doctors. Doctors see only what was shared and write their
own prescriptions.

Phase 2 adds an AI layer that detects the language a patient wrote in,
normalises it to English for the doctor, and extracts structured facts — each
one backed by a verbatim quote from the patient's own words, and confirmed by
the patient before it counts.

Phase 3 reads uploaded medical documents page by page — copying a PDF's text
layer exactly, or transcribing scans and photos with OCR — and extracts items
that each point at the page and the region they came from. The patient reviews
them; a doctor sees them beside the untouched original file.

CareBridge is **not** an AI doctor: it does not diagnose, does not prescribe,
and never decides between doctors' opinions. See [docs/AI_POLICY.md](docs/AI_POLICY.md).

**The AI runs offline by default, OCR included.** `DEMO_MODE=true` pins a
deterministic local provider and local OCR, so no API key, quota or outage can
affect a demo, and no text or page image leaves the machine.

> Prototype software with **synthetic data only**. Not clinically validated,
> not production-ready. See [docs/SECURITY.md](docs/SECURITY.md).

```text
apps/patient-web   Next.js web app for every role (patient, doctor, admin) → http://localhost:3000
backend            FastAPI + PostgreSQL API   → http://localhost:8000  (docs at /docs)
packages/          shared types, API client, i18n catalogues, UI components
```

## Requirements

* **Node.js 22.12+** (or 24+) and npm 10+
* **Python 3.11+**
* **PostgreSQL 16** — via Docker (`docker compose up -d postgres`) or any local
  instance. [uv](https://docs.astral.sh/uv/) is optional but recommended.

## Setup from a fresh clone

```bash
# 1. Secrets / configuration
cp .env.example .env
#    then set JWT_SECRET:  python -c "import secrets; print(secrets.token_urlsafe(48))"
#    and make sure DATABASE_URL matches your PostgreSQL.

# 2. Database
docker compose up -d postgres          # or start your own PostgreSQL 16

# 3. Backend
cd backend
uv sync                                # or: python -m venv .venv && .venv/Scripts/pip install -e . 
uv run alembic upgrade head            # create the schema
uv run python -m app.seed              # synthetic demo data (prints logins)
uv run uvicorn app.main:app --reload --port 8000

# 4. Web app (from the repository root, in another terminal)
npm install
npm run dev                            # http://localhost:3000 — everyone signs in here
```

Without `uv`, use a virtual environment and `pip install -e backend`, then run
`alembic upgrade head`, `python -m app.seed` and `uvicorn app.main:app` from
`backend/`.

Health check: <http://localhost:8000/health> → `{"status":"ok"}`.

## Demo accounts (synthetic)

| Role | Email | Password |
|---|---|---|
| Patient | `arun.kumar@carebridge.demo` | `Patient@2026` |
| Doctor | `meera.sharma@carebridge.demo` | `Doctor@2026` |
| Doctor (cardiology, has an earlier consultation) | `rajesh.iyer@carebridge.demo` | `Doctor@2026` |
| Doctor (dermatology) | `fatima.khan@carebridge.demo` | `Doctor@2026` |
| Doctor (endocrinology) | `anitha.rao@carebridge.demo` | `Doctor@2026` |
| Doctor who applied and awaits approval | `kavya.nair@carebridge.demo` | `Doctor@2026` |
| Admin (reviews doctor applications) | `admin@carebridge.demo` | `Admin@2026` |

Everyone signs in at the same page and picks **Patient** or **Doctor**; the
administrator can sign in under either.

`python -m app.seed --reset` wipes all data and re-seeds (development only).

## Demo walkthrough (~5 minutes)

1. **Patient** opens <http://localhost:3000>, chooses **Patient** and signs in. The interface starts in
   **English**; switch to हिन्दी or தமிழ் with the selector at the top right.
   The UI language and the language the patient writes in are separate.
2. **Dashboard** — current conditions, allergies, medications, the last problem
   he described, documents, and an earlier consultation.
3. **My Health** — every entry carries a source badge (*Patient provided* /
   *Doctor provided*); only patient-provided entries are editable.
4. **Describe a problem** — type in any language; the exact words are stored.
5. **Documents** — upload a sample from `scripts/sample-documents/`. The
   original file is stored unchanged and can be opened at any time (reading it
   is shown in the *Document demo* below).
6. **Find Care** — filter by specialty/language, choose Dr. Meera Sharma.
7. **Request a consultation** — tick exactly what to share. Previous
   consultations/prescriptions start unticked. Send the request.
8. **Doctor** — sign out, choose **Doctor** and sign in as Meera: the request is
   in *Incoming*, with the patient's own words. Open the case — only shared items
   appear — then **Accept**.
9. Exchange a message, write **Assessment / notes**, and **Issue prescription**.
10. Back in the patient app: the consultation is active, the notes and the
    prescription are visible, attributed to the doctor who wrote them.
11. Repeat 6–9 with a second doctor to see two independent consultations that
    are never merged.

## Doctor sign-up and approval

A doctor can create their own account, but it opens nothing until an
administrator approves it.

1. At <http://localhost:3000/login> choose **Doctor** → **Apply to join** and
   give name, specialty, qualification, registration number and languages.
2. The new account lands on **Your doctor application**, waiting for review. It
   cannot see any patient and does not appear in Find Care; the API answers its
   clinician requests with `403 doctor_not_approved`.
3. Sign in as the **Admin** → **Doctor applications**. Check the registration
   number against the medical council register — by hand; nothing is looked up
   automatically — then **Approve**, or **Reject** with a reason the doctor will
   see. A registration number another doctor account uses is flagged, and cannot
   be approved while an approved doctor holds it.
4. Sign back in as the doctor. Approved: the clinician workspace opens.
   Rejected: the reason is shown and the details can be corrected and
   resubmitted. Rejecting an approved doctor revokes their access at once.

Doctors created by `python -m app.seed` or by an admin through
`POST /api/v1/admin/doctors` are approved from the start.

## AI demo (Phase 2, works entirely offline)

1. **Patient** → *Describe a problem*. Write in Tamil, Hindi or English, e.g.
   `எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது.` and save.
2. The **AI assistance** panel appears. It is off until you allow it — click
   **Allow AI processing** (consent is stored and audited; nothing is processed
   before this).
3. Click **Process with AI**. The panel shows, as three separate things:
   *what you wrote*, the *AI-normalised English* (labelled machine-generated,
   with the detected language), and the *extracted items* — each with the exact
   quote it came from.
4. **Confirm**, **edit** or **reject** each item. Only confirmed allergies,
   medicines and history items become health records, marked *AI extracted*,
   keeping your original wording.
5. Share the problem with a doctor (steps 6–7 above).
6. **Doctor** → open the case. The patient's original Tamil text is shown
   first; **Show AI interpretation** reveals the normalisation, the extracted
   items, their evidence and whether the patient confirmed them.
7. Turn consent off in **Profile** to see AI processing refused while the rest
   of CareBridge keeps working.

## Document demo (Phase 3, works offline)

Sample files live in `scripts/sample-documents/` (regenerate with
`uv run python -m app.seed --write-samples ../scripts/sample-documents` from
`backend/`). All are synthetic.

1. **Patient** → **Documents** → open *Discharge summary* (seeded), or upload
   `synthetic-discharge-summary.pdf` (text layer), `synthetic-scanned-lab.pdf`
   (image-only, needs OCR) or `synthetic-prescription-photo.png`.
2. In **Read this document**, allow AI processing if asked, then **Read
   document**. The first OCR run loads its models; expect a few seconds per
   scanned page on a laptop CPU.
3. For each page you see the original page image, and beside it:
   *1 · Text read from the page* — labelled **Copied exactly from the PDF** or
   **Read by OCR — machine transcription, can misread**, with confidence;
   *2 · English version*; *3 · Items found on this page*, each with its quote
   and page. **Show on page** outlines the evidence on the image.
4. **Confirm**, **edit** or **reject** items. "Father has diabetes" is marked
   *About a family member* and can only become family history.
5. Upload `synthetic-injection-attempt.pdf`: the instruction it contains is shown
   as read text, and no item follows it.
6. Share the document in a consultation. **Doctor** → open the case →
   *Documents shared by the patient*: **View** opens the original file;
   **Show machine reading** shows the page image, how it was read, the text, the
   English version and the items with the patient's confirmations. Items the
   patient rejected are not shown. The doctor's assessment is their own.

To read scans with a vision model instead (needed for Tamil or Hindi scans):
`DEMO_MODE=false`, `AI_PROVIDER=openai|anthropic|gemini`, `OCR_ENGINE=provider`.
Page images of pages without a text layer are then sent to that provider.

To try a real provider, set `DEMO_MODE=false`, `AI_PROVIDER=openai|anthropic|gemini`
and that provider's API key in `.env`. Keys stay server-side; they are never
sent to a browser. With no key configured the app still runs — AI simply
reports itself unavailable and the original information is untouched.

## Real-provider smoke test (synthetic data only)

```bash
cd backend
# The real OpenAI adapter over real HTTP, against a local server speaking the
# documented wire format — no key, no spend. Includes 401/429/500/malformed paths.
uv run python scripts/ai_smoke_test.py --emulate

# The real API. Needs OPENAI_API_KEY in the environment or .env.
uv run python scripts/ai_smoke_test.py --provider openai

# Also read one synthetic scanned page through the provider's vision input.
uv run python scripts/ai_smoke_test.py --provider anthropic --document
```

It reports language detection, the English version, extracted facts with
attribution and evidence validation, the three-layer meaning check, token
counts, latency and estimated cost. Cost reads "unknown" when the model is not
in the pricing table — it is never shown as $0.

## AI evaluation

```bash
cd backend
uv run python -m evaluation.run_eval                       # local provider
uv run python -m evaluation.run_eval --compare mock,anthropic   # benchmark
```

42 synthetic cases (English/Tamil/Hindi, code-mixed, misspellings, negations,
stated and unstated allergies, measurements, ambiguity, family-history traps)
with ground truth. Reports language accuracy, per-category precision/recall/F1,
evidence validity, unsupported-fact rate, normalisation coverage, latency and
estimated cost, and writes `evaluation/results/benchmark.md`. Numbers describe
that dataset only — they are not a clinical accuracy claim.

```bash
uv run python -m evaluation.run_document_eval              # documents: local OCR + local provider
```

Five synthetic documents with known text. Reports reading accuracy by method,
extraction precision/recall/F1, family attribution, page provenance, whether
evidence regions cover the quoted line, and any forbidden (e.g. injected) facts.
The scans are clean renders, so the reading numbers do not describe real
photographs or handwriting.

## Tests

```bash
# Backend (SQLite by default — fast, no services needed)
cd backend && uv run pytest

# Backend against PostgreSQL, including the migration check
$env:TEST_DATABASE_URL="postgresql+psycopg://carebridge:carebridge_dev_password@localhost:5432/carebridge_test"
$env:MIGRATION_TEST_DATABASE_URL="postgresql+psycopg://carebridge:carebridge_dev_password@localhost:5432/carebridge_migrations_test"
uv run pytest                     # create both databases first; names must contain "test"

# Frontend (all workspaces)
npm test
npm run typecheck
```

## Deploy

One Next.js app on Vercel, the API and its database on Render. The repository
carries [`render.yaml`](render.yaml), so Render creates both from a blueprint.

1. **Render** → New → Blueprint → this repository. Creates `asclepius-api` and
   its PostgreSQL database, runs migrations and seeds the demo data.
2. **Vercel** → one project from the repository, root directory
   `apps/patient-web`, with `NEXT_PUBLIC_API_BASE_URL` set to the Render URL.
3. **Render** → set `CORS_ORIGINS` to the Vercel URL and redeploy.

The deployed demo keeps `DEMO_MODE=true`, so no AI provider key is involved and
nothing leaves the server. The walkthrough, including the free-plan caveats
(instances that sleep, a database that expires after 30 days, ephemeral uploads,
OCR memory) and how to avoid them, is in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Documentation

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — structure, domain model, API surface, providers
* [docs/DESIGN.md](docs/DESIGN.md) — design system: provenance rules, tokens, components, motion and 3D limits
* [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — deploying to Vercel and Render
* [docs/AI_POLICY.md](docs/AI_POLICY.md) — what the AI may and may not do
* [docs/SECURITY.md](docs/SECURITY.md) — controls and known limitations
* [docs/DECISIONS.md](docs/DECISIONS.md) — decision log
* [docs/ROADMAP.md](docs/ROADMAP.md) — phases

## Configuration

All settings come from `.env` (see `.env.example`): `DATABASE_URL`,
`JWT_SECRET`, `JWT_EXPIRES_MINUTES`, `CORS_ORIGINS`, `STORAGE_PROVIDER`,
`STORAGE_LOCAL_ROOT`, `MAX_UPLOAD_BYTES`, `DEMO_MODE`, `AI_PROVIDER`, `AI_MODEL`,
the `AI_*` limits, provider keys, `OCR_ENGINE`, `OCR_MIN_TEXT_LAYER_CHARS`,
`DOCUMENT_PROCESSING_MAX_PAGES`, `DOCUMENT_RENDER_SCALE`, `DOCUMENT_MAX_PIXELS`
and `NEXT_PUBLIC_API_BASE_URL`. The application runs with **no AI API key**:
`DEMO_MODE=true` uses the local provider and local OCR.
