"""Document processing results → API schemas (patient and doctor views)."""

from typing import TYPE_CHECKING

from app.models.enums import FactReviewState
from app.schemas.ai import AIFactOut, AIRunOut, AIUsageOut, NormalizationCheckOut
from app.schemas.consultation import DocumentInsight, DocumentPageInsight
from app.schemas.document_ai import DocumentExtractionOut, DocumentPageOut, DocumentProcessingOut, TextBlockOut
from app.services.ai_presenters import fact_summary

if TYPE_CHECKING:
    from app.services.document_pipeline import DocumentProcessingResult, PageResult


def page_out(page_result: "PageResult") -> DocumentPageOut:
    row, ai = page_result.page, page_result.ai
    return DocumentPageOut(
        page_id=row.id,
        page_number=row.page_number,
        method=row.method,
        engine=row.engine,
        confidence=row.confidence,
        width=row.width,
        height=row.height,
        text=row.text,
        blocks=[TextBlockOut(**block) for block in row.blocks],
        warnings=list(row.warnings),
        detected_language=row.detected_language or ai.detected_language,
        ai_status=ai.status,
        ai_error_code=ai.error_code,
        normalized_english=ai.normalized_english,
        unparsed=ai.unparsed,
        needs_review=ai.needs_review,
        normalization_check=NormalizationCheckOut(**ai.normalization_check) if ai.normalization_check else None,
        facts=[AIFactOut.model_validate(f) for f in ai.facts],
        runs=[AIRunOut(**vars(r)) for r in ai.runs],
        generated_at=ai.generated_at,
    )


def processing_out(outcome: "DocumentProcessingResult") -> DocumentProcessingOut:
    return DocumentProcessingOut(
        document_id=outcome.document.id,
        document_status=outcome.document.status,
        status=outcome.status,
        error_code=outcome.error_code,
        extraction=DocumentExtractionOut.model_validate(outcome.extraction) if outcome.extraction else None,
        pages=[page_out(p) for p in outcome.pages],
        usage=AIUsageOut(**outcome.usage) if outcome.usage else None,
        provider=outcome.provider,
        model=outcome.model,
        is_external_provider=outcome.is_external_provider,
    )


def document_insight(outcome: "DocumentProcessingResult") -> DocumentInsight:
    """Doctor-facing: what was read, how, and what was extracted — beside the original file."""
    extraction = outcome.extraction
    assert extraction is not None
    return DocumentInsight(
        document_id=outcome.document.id,
        extraction_status=extraction.status.value,
        error_code=extraction.error_code,
        page_count=extraction.page_count,
        pages_processed=extraction.pages_processed,
        truncated=extraction.truncated,
        methods=list(extraction.methods),
        engines=list(extraction.engines),
        processed_at=extraction.created_at,
        pages=[
            DocumentPageInsight(
                page_number=p.page.page_number,
                method=p.page.method,
                engine=p.page.engine,
                confidence=p.page.confidence,
                text=p.page.text,
                blocks=list(p.page.blocks),
                warnings=list(p.page.warnings),
                detected_language=p.page.detected_language or p.ai.detected_language,
                ai_status=p.ai.status,
                normalized_english=p.ai.normalized_english,
                normalization_check=p.ai.normalization_check,
                facts=[fact_summary(f) for f in p.ai.facts if f.review_state != FactReviewState.REJECTED],
            )
            for p in outcome.pages
        ],
    )
