# Security — baseline and limitations (Phases 1–3)

> **This is a prototype.** It is **not** production-ready, **not** clinically
> validated, and **not** certified for real patient data. Every person, doctor,
> clinic, registration number and document in the demo is synthetic. Do not put
> real patient information into this system.

## What is implemented

| Control | Where |
|---|---|
| Password hashing with bcrypt (per-password salt) | `app/core/security.py` |
| Password policy: ≥ 8 characters, ≤ 72 bytes (no silent bcrypt truncation) | `app/schemas/auth.py` |
| Constant-ish login timing (dummy hash when the email is unknown) and one generic failure message | `app/services/auth_service.py` |
| Signed JWT access tokens (HS256) with `exp`, `iat`, `jti`; role in the token is re-checked against the database on every request | `app/core/security.py`, `app/api/deps.py` |
| Role-based access (`patient` / `doctor` / `admin`) enforced server-side on every route | `app/api/deps.py` |
| Doctor accounts from sign-up start `pending`; only an approved doctor reaches clinician routes, appears in the directory or can be sent a consultation request. One dependency enforces it, and rejecting an approved doctor revokes access on the next request | `app/api/deps.get_current_doctor`, D-051 |
| Ownership checks after role checks (a patient can only reach their own rows) | `app/services/*` |
| Patient-controlled sharing: a doctor sees only granted items, checked on every read, including file downloads | `app/services/consultation_service.py` |
| Consultation access revoked on decline/cancel | `_require_doctor_visibility` |
| Prescription `patient_id`/`doctor_id` taken from the consultation, never from the request body | `create_prescription` |
| Upload validation: MIME allow-list, magic-byte sniffing, extension check, size limit, empty-file rejection | `app/services/document_service.py` |
| Server-generated storage keys + path-traversal guard; user filenames are display-only | `document_service`, `providers/storage/local.py` |
| Oversized request bodies rejected before multipart parsing | `app/main.py` |
| File responses served with `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, `Cache-Control: private, no-store` | `app/api/v1/files.py` |
| Security headers and `no-store` on API responses; CORS limited to the configured web-app origin, credentials disabled | `app/main.py` |
| Input validation and length limits on every field | Pydantic schemas |
| Audit log of logins, failed logins, case views, document views by a doctor, sharing decisions, prescription creation, record changes | `app/services/audit.py`, `audit_events` |
| Secrets only in `.env` (git-ignored); `.env.example` holds placeholders; app refuses a default `JWT_SECRET` outside development | `app/core/config.py`, `.gitignore` |
| Automated tests for authn, authz, role separation, sharing, upload rejection, prescription ownership | `backend/tests/` |

## AI-specific controls (Phase 2)

| Control | Where |
|---|---|
| No AI processing without explicit patient consent; the provider is not even constructed when consent is missing | `services/ai_pipeline.require_consent` |
| Provider credentials are server-side only, typed as `SecretStr`, never serialised into any response and never written to a log | `core/config.py`, `providers/ai/http_base.py` |
| No credential is ever placed in a URL (Gemini key moved to a header) | `providers/ai/gemini_provider.py`, D-024 |
| `GET /meta/ai` exposes provider/model/prompt versions only — no keys | `api/v1/meta.py`, asserted by tests |
| Model output is validated against a JSON schema; nothing is string-scraped or executed | `providers/ai/http_base.py` |
| Extracted facts without evidence in the source are discarded | `services/evidence.py`, D-021 |
| AI artifacts and facts are owned by one patient; another patient gets 404 | `api/v1/ai.py`, tests |
| Doctors never call AI endpoints; they see machine output only for records the patient shared, through the case view | `services/consultation_service.build_case_view` |
| Cache entries are scoped by patient **and** content hash, so no output can cross accounts | `ai_pipeline.cache_key` + `patient_id` filter |
| Timeout, bounded retry and circuit breaker bound the damage of a failing or slow provider | `providers/ai/runtime.py` |
| Per-patient AI budget: hourly and daily run caps plus a rolling 24-hour estimated-cost cap, checked before any provider call; over-budget requests get 429 and are audited (`ai.rate_limited`) | `services/ai_limits.py`, D-030 |
| A relative's facts can never be written as the patient's own allergy, medication or history | `services/ai_facts.record_type_for`, D-029 |
| Response schemas statically checked against strict structured-output rules | `tests/test_ai_schemas.py` |
| Every AI operation and every patient decision is audited | `ai.processing_*`, `ai.fact_*`, `ai.consent_*` |

### AI risks that remain open

1. **Prompt injection.** Patient text is untrusted and reaches a model. Output
   is constrained by JSON schema and the evidence gate, and is never executed
   or treated as an instruction, but injection resistance has not been formally
   tested. Never feed AI output into a privileged action.
2. **Third-party data flow.** With `DEMO_MODE=false` and an external provider,
   patient text leaves the server. Consent is required, but there is no DPA,
   no regional pinning, no retention agreement and no redaction of identifiers
   before sending. Do not enable an external provider with real data.
3. **Cost and abuse.** Per-patient limits now exist (D-030), but patient
   self-registration is open, so one person can create many accounts, each with
   its own budget. There is no per-IP or global spend ceiling. Add account
   verification and an organisation-wide cap before enabling a paid provider
   publicly.
4. **Model output is not clinical truth** and must never drive an automated
   decision. See AI_POLICY.md.
5. **Estimated cost is an estimate** from a static price table; it is not
   billing data.

## Document controls (Phase 3)

| Control | Where |
|---|---|
| The stored file's sha256 must equal the upload hash before it is read or rendered; a mismatch returns 409 and nothing is read | `services/document_pipeline.load_original`, D-041 |
| Uploaded files are never modified; reading output lives in `document_extractions` / `document_pages` / `ai_extracted_facts` | D-035 |
| Reading requires AI consent; a budget check covers every page before any work | `process_document`, D-042/D-043 |
| Page cap (`DOCUMENT_PROCESSING_MAX_PAGES`), pixel cap checked before decoding an image (`DOCUMENT_MAX_PIXELS`, decompression-bomb guard), render scale lowered for oversized pages | `providers/documents/render.py` |
| Parser exceptions from malformed PDFs are contained and reported as `document_unreadable`; a document is never left stuck in `processing` | `providers/documents/__init__.py`, `document_pipeline` |
| Page images use the same response headers as file downloads (`nosniff`, `default-src 'none'; sandbox`, `private, no-store`) | `api/v1/files.page_image_response` |
| A patient can process, read or render only their own documents (404 otherwise); doctors get 403 on patient endpoints | `api/v1/document_ai.py`, tests |
| Doctors see readings and page images only for documents shared in that consultation; page views are audited | `consultation_service.doctor_shared_document`, D-044 |
| `DEMO_MODE=true` and `OCR_ENGINE=local` never send a page image anywhere; with vision enabled, only pages without a text layer are sent | `document_pipeline.ocr_mode`, D-038 |
| Processing is audited: `document.processing_requested/completed/failed`, `ai.rate_limited` | `document_pipeline` |

### Document risks that remain open

1. **Untrusted file parsing in-process.** pdfplumber/pdfminer, pdfium and Pillow
   parse attacker-controlled files inside the API process, with no sandbox,
   subprocess isolation, memory limit or timeout on the parse itself. A parser
   vulnerability or a pathological PDF could crash or stall a worker. Isolate
   parsing (separate process or container, resource limits) before any real use.
2. **Synchronous processing is a denial-of-service lever.** Each request can
   render and OCR up to 10 pages (seconds of CPU). Per-patient budgets bound
   it per account, but self-registration is open.
3. **Page images leave the server** when `OCR_ENGINE=provider` or `auto` with a
   vision-capable provider and `DEMO_MODE=false`. A page image carries
   everything printed on it — names, identifiers, signatures — with no redaction.
4. **Documents can carry instructions.** Text on a page reaches the model. Output
   is schema-constrained and evidence-gated, and the injection test passes for
   the local provider, but no real model has been tested against it.
5. **OCR model supply chain.** The ONNX models ship inside the `rapidocr-onnxruntime`
   wheel from PyPI; they are not independently verified.
6. **Uploads are not virus-scanned** (unchanged from Phase 1); reading a file does
   not make it safe to open in another viewer.

## Known limitations (deliberate, Phase 1)

1. **Token storage.** The JWT lives in `sessionStorage`, so a successful XSS in
   a frontend could steal it (D-003). No `HttpOnly` cookie, no CSRF tokens, no
   refresh-token rotation, no server-side session revocation — a stolen token
   is valid until `exp` (default 2 hours). One app now serves every role
   (D-050), so a browser tab holds one session; people sharing a machine must
   sign out between uses.
2. **No rate limiting or lockout.** Login and all other endpoints can be called
   as fast as the client likes. Add a reverse-proxy/ASGI rate limiter and
   progressive lockout before any deployment.
3. **No transport security.** Development runs over plain HTTP. TLS, HSTS and
   secure cookie flags are deployment concerns not covered here.
4. **Files are stored unencrypted** on local disk, and the database is not
   encrypted at rest. There is no antivirus scanning of uploads (a valid PDF
   can still carry a malicious payload for a vulnerable reader).
5. **No Content-Security-Policy on the frontends.** Next.js dev needs `eval`;
   a strict CSP with nonces should be added for any hosted build.
6. **Shared items are live references** (D-006): a doctor sees later edits, and
   deletions remove items from a case. Not suitable as a legal clinical record.
7. **No account recovery, email verification, MFA, or password rotation.**
   Patient self-registration and doctor applications are open by design for the demo.
8. **Doctor verification is manual.** An administrator approves each
   self-registered doctor (D-051) after checking the registration number by
   hand; nothing queries a medical council register, and no document is
   collected. The seeded admin password is published in the README, so on a
   public demo approval shows the flow but keeps no one out.
9. **Audit log is append-only by convention**, not by database permission, and
   is readable by any admin account. There is no tamper-evidence.
10. **No data-retention, export or deletion workflow** (patient right to erasure
    is not implemented). Deleting a record removes it immediately with no
    recoverable history.
11. **Authorisation is enforced per request, not per field, in the frontend.**
    The UI hides what it should, but the server is the only real boundary —
    treat any frontend check as cosmetic.
12. **No protection against a malicious admin.** The admin role can create,
    approve and revoke doctors and read the audit log; there is no separation of
    duties and no second reviewer.

## Reporting and handling

Anything resembling real patient data that reaches this repository must be
removed and the database re-seeded (`python -m app.seed --reset`). The demo
databases can be dropped and recreated at any time.

## Before any real deployment

TLS everywhere · `HttpOnly`+`SameSite` cookies with CSRF protection ·
rate limiting and lockout · encryption at rest and virus scanning for uploads ·
strict CSP · secret management (not `.env`) · backup/restore ·
retention and erasure workflows · access reviews · a security review of the
sharing logic · clinical sign-off on every user-facing string.
