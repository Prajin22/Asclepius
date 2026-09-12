"""PipelineResult → API schemas."""

from app.schemas.ai import AIFactOut, AIProcessingOut, AIRunOut, AIUsageOut, NormalizationCheckOut
from app.schemas.consultation import AIFactSummary, AIRecordInsight
from app.services.ai_pipeline import PipelineResult


def processing_out(result: PipelineResult) -> AIProcessingOut:
    return AIProcessingOut(
        record_id=result.record.id,
        status=result.status,
        error_code=result.error_code,
        original_text=result.original_text,
        normalization_check=(
            NormalizationCheckOut(**result.normalization_check) if result.normalization_check else None
        ),
        usage=AIUsageOut(**result.usage) if result.usage else None,
        detected_language=result.detected_language,
        language_confidence=result.language_confidence,
        normalized_english=result.normalized_english,
        unparsed=result.unparsed,
        needs_review=result.needs_review,
        facts=[AIFactOut.model_validate(f) for f in result.facts],
        runs=[AIRunOut(**vars(r)) for r in result.runs],
        generated_at=result.generated_at,
        provider=result.provider,
        model=result.model,
        is_external_provider=result.is_external_provider,
    )


def fact_summary(f) -> AIFactSummary:
    return AIFactSummary(
        category=f.category,
        subject=f.subject,
        subject_evidence=f.subject_evidence,
        value=f.effective_value,
        original_text=f.original_text,
        evidence_quote=f.evidence_quote,
        validation_status=f.validation_status,
        review_state=f.review_state,
        evidence_document_id=f.evidence_document_id,
        evidence_page_number=f.evidence_page_number,
        evidence_bbox=f.evidence_bbox,
    )


def record_insight(result: PipelineResult) -> AIRecordInsight:
    """Doctor-facing view: all three layers, with evidence and attribution."""
    return AIRecordInsight(
        record_id=result.record.id,
        status=result.status,
        original_text=result.original_text,
        normalization_check=result.normalization_check,
        detected_language=result.detected_language,
        normalized_english=result.normalized_english,
        unparsed=result.unparsed,
        provider=result.provider,
        model=result.model,
        generated_at=result.generated_at,
        facts=[fact_summary(f) for f in result.facts if f.review_state.value != "rejected"],
    )
