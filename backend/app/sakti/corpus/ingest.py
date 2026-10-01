"""Bringing an official source file in: validation, storage, reading.

An uploaded file is untrusted input. It is accepted only if it is a PDF by its
declared type, its extension and its own first bytes; it is stored under a key
the server generates, never under its name; and it is never executed, only
parsed. A URL the curator gives is recorded as provenance and never fetched.

Reading reuses the document readers Phase 3 built: a PDF text layer is copied
exactly; a page without one goes to the offline OCR engine and is marked as
machine transcription. No page is ever sent to an AI provider — IP-SAKTI's AI
policy permits no capability, and legal text must not pass through a model.
A source with more pages than the limit is refused whole rather than read in
part, because a partial statute would look complete.
"""

import hashlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.config import Settings
from app.models import CorpusDocument
from app.providers.documents import (
    METHOD_OCR,
    PDF_MIME,
    DocumentReadError,
    PageText,
    ReadOptions,
    local_ocr_engine,
    read_document,
)
from app.providers.documents.render import pdf_page_count
from app.providers.storage import ObjectNotFound, get_storage
from app.services.document_service import safe_filename, sniff_mime
from app.services.errors import DocumentIntegrityError, InvalidInput, NotFound

ISSUE_OCR = "ocr_text_requires_verification"
ISSUE_LOW_CONFIDENCE = "low_ocr_confidence"
ISSUE_EMPTY_PAGE = "page_without_text"
ISSUE_OCR_UNAVAILABLE = "ocr_unavailable"


def validate_source_file(filename: str | None, declared_mime: str | None, data: bytes, max_bytes: int) -> str:
    """The display name of an acceptable PDF, or InvalidInput. The name is never a path."""
    if not data:
        raise InvalidInput("The file is empty", code="empty_file")
    if len(data) > max_bytes:
        raise InvalidInput(f"File is larger than the {max_bytes // (1024 * 1024)} MB limit", code="file_too_large")
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared != PDF_MIME:
        raise InvalidInput("Official sources must be PDF files", code="unsupported_type")
    if sniff_mime(data) != PDF_MIME:
        raise InvalidInput("File content does not match its type", code="content_mismatch")
    raw_name = (filename or "").lower()
    if "." in raw_name and not raw_name.endswith(".pdf"):
        raise InvalidInput("File extension is not allowed for this type", code="bad_extension")
    return safe_filename(filename or "", ".pdf", (".pdf",))


def validate_source_url(url: str | None) -> str | None:
    """An http(s) URL to record as provenance. Recorded only — the server never requests it."""
    if url is None or not url.strip():
        return None
    url = url.strip()
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises on a malformed port
    except ValueError:
        raise InvalidInput("The source URL must be an http or https address", code="invalid_source_url") from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or any(ch.isspace() for ch in url)
        or parts.username
        or parts.password
        or len(url) > 2000
    ):
        raise InvalidInput("The source URL must be an http or https address", code="invalid_source_url")
    return url


def store_source(document_id, data: bytes) -> str:
    """Store the original under a server-generated key; returns the opaque reference."""
    return get_storage().put(f"corpus/sources/{document_id}.pdf", data, PDF_MIME)


def load_original(document: CorpusDocument) -> bytes:
    """The stored file, verified to be exactly the bytes that were uploaded."""
    try:
        data = get_storage().get(document.storage_reference)
    except ObjectNotFound as exc:
        raise NotFound("The source file is missing from storage") from exc
    if hashlib.sha256(data).hexdigest() != document.sha256:
        raise DocumentIntegrityError("The stored source file does not match what was uploaded")
    return data


@dataclass
class Reading:
    pages: list[PageText] = field(default_factory=list)
    page_count: int = 0
    error_code: str | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.error_code is not None


def read_source(data: bytes, settings: Settings) -> Reading:
    """Read every page of a PDF, or fail as a whole. Never a partial reading."""
    try:
        total = pdf_page_count(data)
    except DocumentReadError as exc:
        return Reading(error_code=exc.code)
    if total == 0:
        return Reading(error_code="document_unreadable")
    if total > settings.corpus_max_pages:
        return Reading(page_count=total, error_code="too_many_pages")

    options = ReadOptions(
        max_pages=total,
        min_text_layer_chars=settings.ocr_min_text_layer_chars,
        render_scale=settings.document_render_scale,
        max_pixels=settings.document_max_pixels,
    )
    # The local engine or none at all. Never a provider (see the module docstring).
    engine = None if settings.ocr_engine == "none" else local_ocr_engine()
    try:
        result = read_document(data, PDF_MIME, options, engine)
    except DocumentReadError as exc:
        return Reading(page_count=total, error_code=exc.code)
    if result.truncated or len(result.pages) != total:
        return Reading(page_count=total, error_code="incomplete_reading")

    reading = Reading(pages=result.pages, page_count=total)
    if not any(page.text.strip() for page in result.pages):
        reading.error_code = "no_text_found"
        return reading
    issues: list[str] = []
    for page in result.pages:
        if page.method == METHOD_OCR:
            issues.append(ISSUE_OCR)
        if "low_ocr_confidence" in page.warnings:
            issues.append(ISSUE_LOW_CONFIDENCE)
        if "no_text_layer_and_ocr_unavailable" in page.warnings:
            issues.append(ISSUE_OCR_UNAVAILABLE)
        if not page.text.strip():
            issues.append(ISSUE_EMPTY_PAGE)
    reading.issues = list(dict.fromkeys(issues))
    return reading
