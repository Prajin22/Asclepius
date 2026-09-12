"""Medical document intelligence (Phase 3).

    uploaded file (never modified; sha256 verified before every read)
        → read: exact PDF text layer, or OCR / vision transcription (machine)
        → document_pages: verbatim text + where each line sits, per page
        → the Phase 2 pipeline per page: detect → normalise → extract → evidence
        → facts carrying page number and position → the patient confirms,
          edits or rejects them → shared documents show all of it to the doctor

Reading is transcription, not interpretation, and OCR can misread. Pages keep
their method, engine and confidence so uncertainty stays visible. Nothing here
interprets medical meaning, flags a value as abnormal, or makes any clinical
judgement; the doctor makes clinical decisions from the original document.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.models import DocumentExtraction, DocumentPage, MedicalDocument, PatientProfile, User
from app.models.enums import AIArtifactStatus, DocumentExtractionStatus, DocumentStatus
from app.providers.ai import get_ai_provider, get_circuit_breaker
from app.providers.ai.base import AIProvider
from app.providers.ai.errors import AIError
from app.providers.ai.runtime import call_with_resilience
from app.providers.documents import (
    IMAGE_MIMES,
    METHOD_VISION,
    PDF_MIME,
    DocumentReadError,
    DocumentReadResult,
    PageText,
    ReadOptions,
    local_ocr_engine,
    read_document,
)
from app.providers.documents.render import load_image, pdf_page_count, png_bytes, render_pdf_page
from app.providers.storage import ObjectNotFound, get_storage
from app.services import ai_limits, ai_pipeline, audit
from app.services.ai_pipeline import AISource, PipelineResult
from app.services.audit import RequestContext
from app.services.errors import AIRateLimited, DocumentIntegrityError, DocumentUnreadable, NotFound

TRANSCRIPTION_OPERATION = "document_transcription"
PAGE_IMAGE_SCALE = 1.5


@dataclass
class PageResult:
    page: DocumentPage
    ai: PipelineResult


@dataclass
class DocumentProcessingResult:
    document: MedicalDocument
    extraction: DocumentExtraction | None
    status: str  # "processed" | "failed" | "not_processed"
    error_code: str | None = None
    pages: list[PageResult] = field(default_factory=list)
    usage: dict | None = None
    provider: str | None = None
    model: str | None = None
    is_external_provider: bool | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_original(document: MedicalDocument) -> bytes:
    """The stored file, verified to be exactly the bytes that were uploaded."""
    try:
        data = get_storage().get(document.storage_reference)
    except ObjectNotFound as exc:
        raise NotFound("The document file is missing from storage") from exc
    if _sha256(data) != document.sha256:
        raise DocumentIntegrityError("The stored document does not match what was uploaded")
    return data


def ocr_mode(settings: Settings, provider: AIProvider) -> str:
    """How pages without a text layer are read. DEMO_MODE never sends an image anywhere."""
    mode = settings.ocr_engine
    if settings.demo_mode:
        return "none" if mode == "none" else "local"
    if mode == "auto":
        return "provider" if provider.supports_vision else "local"
    return mode


def _read_options(settings: Settings) -> ReadOptions:
    return ReadOptions(
        max_pages=settings.document_processing_max_pages,
        min_text_layer_chars=settings.ocr_min_text_layer_chars,
        render_scale=settings.document_render_scale,
        max_pixels=settings.document_max_pixels,
    )


def _pages_to_read(data: bytes, mime_type: str, settings: Settings) -> int:
    if mime_type != PDF_MIME:
        return 1
    try:
        return max(1, min(pdf_page_count(data), settings.document_processing_max_pages))
    except DocumentReadError:
        return 1  # reading will fail properly and be recorded


async def _transcribe(
    db: Session, patient: PatientProfile, document: MedicalDocument, provider: AIProvider, image, page_number: int
) -> PageText:
    """Vision transcription of one page image, recorded as an AI artifact."""
    settings = get_settings()
    png = png_bytes(image)
    engine = f"{provider.name} {provider.model}"
    source = AISource(type="document", id=document.id, text="", page_number=page_number, document_id=document.id)
    try:
        transcription = await call_with_resilience(
            lambda: provider.transcribe_document_image(png, page_number),
            timeout_seconds=settings.ai_timeout_seconds,
            max_attempts=settings.ai_max_attempts,
            breaker=get_circuit_breaker(),
        )
    except AIError as exc:
        ai_pipeline.store_artifact(
            db, patient=patient, source=source, operation=TRANSCRIPTION_OPERATION, provider=provider,
            prompt_version=None, content={"error": exc.code}, status=AIArtifactStatus.FAILED,
            digest=document.sha256, key=None, error_code=exc.code,
        )
        return PageText(page_number, "", float(image.width), float(image.height), METHOD_VISION, engine,
                        warnings=[f"vision_failed:{exc.code}"])

    ai_pipeline.store_artifact(
        db, patient=patient, source=source, operation=TRANSCRIPTION_OPERATION, provider=provider,
        prompt_version=transcription.prompt_version,
        content={
            "text": transcription.text,
            "language": transcription.language.value if transcription.language else None,
            "unreadable": transcription.unreadable,
        },
        status=AIArtifactStatus.SUCCEEDED, digest=document.sha256, key=None, usage=transcription.usage,
    )
    warnings = ["vision_has_no_line_positions"]
    if transcription.unreadable:
        warnings.append("vision_reported_unreadable_regions")
    return PageText(page_number, transcription.text, float(image.width), float(image.height), METHOD_VISION,
                    engine, warnings=warnings)


async def _read(
    db: Session, patient: PatientProfile, document: MedicalDocument, data: bytes, settings: Settings,
    provider: AIProvider,
) -> DocumentReadResult:
    options = _read_options(settings)
    mode = ocr_mode(settings, provider)
    if mode in ("local", "none"):
        engine = local_ocr_engine() if mode == "local" else None
        return await run_in_threadpool(read_document, data, document.mime_type, options, engine)

    # Provider vision: exact text layers stay on this machine; only pages that
    # cannot be read locally are sent.
    if document.mime_type in IMAGE_MIMES:
        image = await run_in_threadpool(load_image, data, max_pixels=options.max_pixels)
        return DocumentReadResult(pages=[await _transcribe(db, patient, document, provider, image, 1)], page_count=1)
    result = await run_in_threadpool(read_document, data, document.mime_type, options, None)
    for index, page in enumerate(result.pages):
        if len(page.text.strip()) >= options.min_text_layer_chars:
            continue
        image = await run_in_threadpool(
            render_pdf_page, data, page.page_number - 1, scale=options.render_scale, max_pixels=options.max_pixels
        )
        result.pages[index] = await _transcribe(db, patient, document, provider, image, page.page_number)
    return result


def _current_pages(db: Session, document_id: uuid.UUID) -> list[DocumentPage]:
    return list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id, DocumentPage.superseded_at.is_(None))
            .order_by(DocumentPage.page_number)
        )
    )


def _upsert_pages(
    db: Session, document: MedicalDocument, patient: PatientProfile, extraction: DocumentExtraction,
    pages: list[PageText],
) -> list[DocumentPage]:
    """Reuse a page row when the text is unchanged; supersede it when it differs."""
    current = {page.page_number: page for page in _current_pages(db, document.id)}
    now = datetime.now(UTC)
    rows: list[DocumentPage] = []
    for page in pages:
        digest = _sha256(page.text.encode("utf-8"))
        existing = current.get(page.page_number)
        if existing is not None and existing.text_sha256 == digest:
            rows.append(existing)
            continue
        if existing is not None:
            existing.superseded_at = now
        earlier = db.scalar(
            select(DocumentPage).where(
                DocumentPage.document_id == document.id,
                DocumentPage.page_number == page.page_number,
                DocumentPage.text_sha256 == digest,
            )
        )
        if earlier is not None:  # the same text as an older reading: bring it back
            earlier.superseded_at = None
            rows.append(earlier)
            continue
        row = DocumentPage(
            document_id=document.id,
            patient_id=patient.id,
            extraction_id=extraction.id,
            page_number=page.page_number,
            text=page.text,
            text_sha256=digest,
            method=page.method,
            engine=page.engine[:160],
            confidence=page.confidence,
            width=page.width,
            height=page.height,
            blocks=[block.as_dict() for block in page.blocks],
            warnings=list(page.warnings),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


async def process_document(
    db: Session,
    patient: PatientProfile,
    actor: User,
    document: MedicalDocument,
    ctx: RequestContext | None = None,
    provider: AIProvider | None = None,
) -> DocumentProcessingResult:
    """Read the document and interpret each page. The file itself is never changed."""
    ai_pipeline.require_consent(patient)  # reading a document is AI processing (D-020)
    settings = get_settings()
    data = load_original(document)  # integrity before anything else

    needed = _pages_to_read(data, document.mime_type, settings)
    try:
        ai_limits.enforce_rate_limit(db, patient.id, runs_needed=needed)
    except AIRateLimited:
        audit.record(
            db, actor=actor, action="ai.rate_limited", resource_type="document", resource_id=document.id,
            patient_id=patient.id, details={"pages": needed}, ctx=ctx,
        )
        db.commit()
        raise

    provider = provider or get_ai_provider()
    outcome = DocumentProcessingResult(
        document=document, extraction=None, status="not_processed", provider=provider.name,
        model=provider.model, is_external_provider=provider.is_external,
    )
    mode = ocr_mode(settings, provider)
    audit.record(
        db, actor=actor, action="document.processing_requested", resource_type="document",
        resource_id=document.id, patient_id=patient.id,
        details={"pages": needed, "ocr_mode": mode, "provider": provider.name}, ctx=ctx,
    )
    document.status = DocumentStatus.PROCESSING
    db.commit()

    try:
        return await _process(db, patient, actor, document, data, settings, provider, outcome, ctx)
    except Exception:
        # Never leave a document stuck in "processing".
        db.rollback()
        stuck = db.get(MedicalDocument, document.id)
        if stuck is not None:
            stuck.status = DocumentStatus.FAILED
            db.commit()
        raise


async def _process(
    db: Session, patient: PatientProfile, actor: User, document: MedicalDocument, data: bytes,
    settings: Settings, provider: AIProvider, outcome: DocumentProcessingResult, ctx: RequestContext | None,
) -> DocumentProcessingResult:
    started = time.perf_counter()
    try:
        read = await _read(db, patient, document, data, settings, provider)
    except DocumentReadError as exc:
        extraction = DocumentExtraction(
            document_id=document.id, patient_id=patient.id, status=DocumentExtractionStatus.FAILED,
            error_code=exc.code, source_sha256=document.sha256,
            latency_ms=int((time.perf_counter() - started) * 1000), requested_by_user_id=actor.id,
        )
        db.add(extraction)
        document.status = DocumentStatus.FAILED
        audit.record(
            db, actor=actor, action="document.processing_failed", resource_type="document",
            resource_id=document.id, patient_id=patient.id, details={"error": exc.code}, ctx=ctx,
        )
        db.commit()
        outcome.extraction, outcome.status, outcome.error_code = extraction, "failed", exc.code
        outcome.usage = ai_limits.usage_snapshot(db, patient.id)
        return outcome

    readable = [page for page in read.pages if page.text.strip()]
    if not readable:
        status = DocumentExtractionStatus.FAILED
    elif read.truncated or len(readable) < len(read.pages):
        status = DocumentExtractionStatus.PARTIAL
    else:
        status = DocumentExtractionStatus.SUCCEEDED
    extraction = DocumentExtraction(
        document_id=document.id,
        patient_id=patient.id,
        status=status,
        error_code=None if readable else "no_text_found",
        source_sha256=document.sha256,
        page_count=read.page_count,
        pages_processed=len(read.pages),
        truncated=read.truncated,
        methods=sorted({page.method for page in read.pages}),
        engines=sorted({page.engine for page in read.pages}),
        warnings=list(dict.fromkeys([*read.warnings, *(w for page in read.pages for w in page.warnings)])),
        latency_ms=int((time.perf_counter() - started) * 1000),
        requested_by_user_id=actor.id,
    )
    db.add(extraction)
    db.flush()
    rows = _upsert_pages(db, document, patient, extraction, read.pages)

    ai_failures = 0
    for row, page in zip(rows, read.pages, strict=True):
        source = AISource(
            type="document_page", id=row.id, text=row.text, fallback_language=document.source_language,
            page_number=row.page_number, document_id=document.id, span_to_bbox=page.bbox_for_span,
        )
        result = PipelineResult(
            record=None, source_id=row.id, provider=provider.name, model=provider.model,
            is_external_provider=provider.is_external, original_text=row.text,
        )
        if not row.text.strip():
            result.status = "not_processed"
            outcome.pages.append(PageResult(row, result))
            continue
        try:
            interpreted = await ai_pipeline.interpret(db, patient, source, provider, result)
        except AIError as exc:
            ai_pipeline.record_failure(db, patient, source, provider, exc)
            result.status, result.error_code = "unavailable", exc.code
            result.facts = ai_pipeline.existing_facts(db, patient.id, row.id)
            ai_failures += 1
            outcome.pages.append(PageResult(row, result))
            continue
        ai_pipeline.finish(db, patient, source, interpreted, result)
        row.detected_language = result.detected_language
        outcome.pages.append(PageResult(row, result))

    document.status = DocumentStatus.PROCESSED if readable else DocumentStatus.FAILED
    audit.record(
        db, actor=actor, action="document.processing_completed", resource_type="document",
        resource_id=document.id, patient_id=patient.id,
        details={
            "extraction_status": status.value,
            "pages_read": len(read.pages),
            "methods": extraction.methods,
            "facts": sum(len(p.ai.facts) for p in outcome.pages),
            "ai_failures": ai_failures,
        },
        ctx=ctx,
    )
    db.commit()
    for page_result in outcome.pages:
        for fact in page_result.ai.facts:
            db.refresh(fact)

    outcome.extraction = extraction
    outcome.status = "processed" if readable else "failed"
    outcome.error_code = None if readable else "no_text_found"
    outcome.usage = ai_limits.usage_snapshot(db, patient.id)
    return outcome


def latest_extraction(db: Session, document_id: uuid.UUID) -> DocumentExtraction | None:
    return db.scalar(
        select(DocumentExtraction)
        .where(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.created_at.desc())
        .limit(1)
    )


def get_document_state(db: Session, patient: PatientProfile, document: MedicalDocument) -> DocumentProcessingResult:
    """Stored reading and interpretation of a document, without calling anything."""
    extraction = latest_extraction(db, document.id)
    outcome = DocumentProcessingResult(document=document, extraction=extraction, status="not_processed")
    if extraction is not None:
        outcome.status = "failed" if extraction.status == DocumentExtractionStatus.FAILED else "processed"
        outcome.error_code = extraction.error_code
    for row in _current_pages(db, document.id):
        source = AISource(
            type="document_page", id=row.id, text=row.text, fallback_language=document.source_language,
            page_number=row.page_number, document_id=document.id,
        )
        state = ai_pipeline.get_source_state(db, patient, source)
        outcome.pages.append(PageResult(row, state))
        if state.provider and outcome.provider is None:
            outcome.provider, outcome.model = state.provider, state.model
    outcome.usage = ai_limits.usage_snapshot(db, patient.id)
    return outcome


def page_image_png(document: MedicalDocument, page_number: int) -> bytes:
    """A page of the original document as an image, for viewing evidence in place."""
    settings = get_settings()
    data = load_original(document)
    try:
        if document.mime_type == PDF_MIME:
            if page_number < 1 or page_number > pdf_page_count(data):
                raise NotFound("Page not found")
            image = render_pdf_page(data, page_number - 1, scale=PAGE_IMAGE_SCALE, max_pixels=settings.document_max_pixels)
        elif document.mime_type in IMAGE_MIMES:
            if page_number != 1:
                raise NotFound("Page not found")
            image = load_image(data, max_pixels=settings.document_max_pixels)
        else:
            raise NotFound("Page not found")
    except DocumentReadError as exc:
        raise DocumentUnreadable(exc.message) from exc
    return png_bytes(image)
