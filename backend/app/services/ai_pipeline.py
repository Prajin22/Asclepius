"""The AI pipeline: detect → normalise → extract → validate evidence → store.

It interprets a *source*: a patient-written record, or one page of text read
from an uploaded document. Both go through exactly the same steps.

Guarantees enforced here, not in the providers:
* nothing runs without the patient's explicit consent;
* the source is never modified — all output lands in `ai_artifacts` and
  `ai_extracted_facts`, referencing the source;
* every fact's evidence is checked against the source before it is stored, and
  unsupported facts are dropped with an audit trail;
* every provider call is time-boxed, retried once, and circuit-broken; failure
  degrades to "original text only" and never to invented content;
* deterministic results are cached by source hash + provider + model + prompt
  version, so changed text or changed prompts never reuse stale output.
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.languages import DEFAULT_LANGUAGE, LanguageCode
from app.models import AIArtifact, AIExtractedFact, MedicalRecord, PatientProfile, User
from app.models.enums import AIArtifactStatus, AIOperation, FactReviewState, FactSubject, FactValidation
from app.providers.ai import get_ai_provider, get_circuit_breaker
from app.providers.ai.base import AIProvider, ExtractionResult, LanguageDetection, NormalizationResult
from app.providers.ai.errors import AIError
from app.providers.ai.runtime import call_with_resilience
from app.services import ai_limits, audit
from app.services.audit import RequestContext
from app.services.errors import AIConsentRequired, AIRateLimited, NotFound
from app.services.evidence import canonical, validate_fact
from app.services.normalization_check import NormalizationCheck, check_normalization

KEEP_STATES = (FactReviewState.CONFIRMED, FactReviewState.EDITED, FactReviewState.REJECTED)

SpanToBBox = Callable[[int | None, int | None], tuple[float, float, float, float] | None]


@dataclass(frozen=True)
class AISource:
    """What the pipeline interprets: a patient-written record, or one document page."""

    type: str  # "medical_record" | "document_page"
    id: uuid.UUID
    text: str
    fallback_language: LanguageCode | None = None
    page_number: int | None = None
    document_id: uuid.UUID | None = None
    # Maps a character span of `text` to its region on the page (documents only).
    span_to_bbox: SpanToBBox | None = None

    def reference(self) -> dict:
        ref: dict = {"type": self.type, "id": str(self.id)}
        if self.page_number is not None:
            ref["page"] = self.page_number
        if self.document_id is not None:
            ref["document_id"] = str(self.document_id)
        return ref

    @classmethod
    def for_record(cls, record: MedicalRecord) -> "AISource":
        return cls(
            type="medical_record",
            id=record.id,
            text=record.content or "",
            fallback_language=record.source_language,
        )


@dataclass
class RunInfo:
    operation: str
    provider: str
    model: str
    prompt_version: str | None = None
    status: str = AIArtifactStatus.SUCCEEDED.value
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cached: bool = False
    artifact_id: uuid.UUID | None = None
    created_at: datetime | None = None


@dataclass
class PipelineResult:
    record: MedicalRecord | None
    status: str = "ok"
    error_code: str | None = None
    detected_language: LanguageCode | None = None
    language_confidence: float | None = None
    normalized_english: str | None = None
    unparsed: list[str] = field(default_factory=list)
    needs_review: list[str] = field(default_factory=list)
    facts: list[AIExtractedFact] = field(default_factory=list)
    runs: list[RunInfo] = field(default_factory=list)
    generated_at: datetime | None = None
    provider: str | None = None
    model: str | None = None
    is_external_provider: bool | None = None
    # Layer 1 of three. Kept on the result so original, normalisation and facts
    # can always be inspected together.
    original_text: str | None = None
    # Did the English rendering change the meaning? (services/normalization_check)
    normalization_check: dict | None = None
    # Where this patient stands against their AI budget.
    usage: dict | None = None
    source_id: uuid.UUID | None = None


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key(operation: str, provider: AIProvider, prompt_version: str | None, language: str, digest: str) -> str:
    return f"{operation}:{provider.name}:{provider.model}:{prompt_version or '-'}:{language}:{digest}"


def require_consent(patient: PatientProfile) -> None:
    if not patient.ai_processing_consent:
        raise AIConsentRequired(
            "AI processing is off for this account. Turn it on in your profile to use it."
        )


def _find_cached(db: Session, patient_id: uuid.UUID, key: str) -> AIArtifact | None:
    if not get_settings().ai_cache_enabled:
        return None
    return db.scalar(
        select(AIArtifact)
        .where(
            AIArtifact.patient_id == patient_id,
            AIArtifact.cache_key == key,
            AIArtifact.status == AIArtifactStatus.SUCCEEDED,
        )
        .order_by(AIArtifact.created_at.desc())
        .limit(1)
    )


def store_artifact(
    db: Session,
    *,
    patient: PatientProfile,
    source: AISource,
    operation: str,
    provider: AIProvider,
    prompt_version: str | None,
    content: dict,
    status: AIArtifactStatus,
    digest: str,
    key: str | None,
    input_language: LanguageCode | None = None,
    output_language: LanguageCode | None = None,
    confidence: float | None = None,
    usage=None,
    error_code: str | None = None,
) -> AIArtifact:
    artifact = AIArtifact(
        patient_id=patient.id,
        artifact_type=operation,
        provider=provider.name,
        model=provider.model,
        prompt_version=prompt_version,
        source_references=[source.reference()],
        source_hash=digest,
        cache_key=key,
        input_language=input_language,
        output_language=output_language,
        content=content,
        confidence=confidence,
        status=status,
        error_code=error_code,
        latency_ms=getattr(usage, "latency_ms", None),
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        estimated_cost_usd=getattr(usage, "estimated_cost_usd", None),
    )
    db.add(artifact)
    db.flush()
    return artifact


async def _run_step(coro_factory):
    settings = get_settings()
    return await call_with_resilience(
        coro_factory,
        timeout_seconds=settings.ai_timeout_seconds,
        max_attempts=settings.ai_max_attempts,
        breaker=get_circuit_breaker(),
    )


async def process_record(
    db: Session,
    patient: PatientProfile,
    actor: User,
    record: MedicalRecord,
    ctx: RequestContext | None = None,
    provider: AIProvider | None = None,
) -> PipelineResult:
    """Run the full pipeline over one patient-authored record."""
    require_consent(patient)
    # Budget check before anything is constructed or sent.
    try:
        ai_limits.enforce_rate_limit(db, patient.id)
    except AIRateLimited:
        audit.record(
            db, actor=actor, action="ai.rate_limited", resource_type="medical_record",
            resource_id=record.id, patient_id=patient.id, ctx=ctx,
        )
        db.commit()
        raise
    provider = provider or get_ai_provider()
    source = AISource.for_record(record)
    result = PipelineResult(
        record=record, source_id=record.id, provider=provider.name, model=provider.model,
        is_external_provider=provider.is_external, original_text=source.text,
    )

    audit.record(
        db, actor=actor, action="ai.processing_requested", resource_type="medical_record",
        resource_id=record.id, patient_id=patient.id,
        details={"provider": provider.name, "model": provider.model, "external": provider.is_external}, ctx=ctx,
    )

    if not source.text.strip():
        result.status = "not_processed"
        db.commit()
        return result

    try:
        extraction = await interpret(db, patient, source, provider, result)
    except AIError as exc:
        # Degrade: keep the original information, record the failure, invent nothing.
        record_failure(db, patient, source, provider, exc)
        audit.record(
            db, actor=actor, action="ai.processing_failed", resource_type="medical_record",
            resource_id=record.id, patient_id=patient.id, details={"error": exc.code}, ctx=ctx,
        )
        db.commit()
        result.status = "unavailable"
        result.error_code = exc.code
        result.facts = existing_facts(db, patient.id, source.id)
        result.usage = ai_limits.usage_snapshot(db, patient.id)
        return result

    check = finish(db, patient, source, extraction, result)

    audit.record(
        db, actor=actor, action="ai.processing_completed", resource_type="medical_record",
        resource_id=record.id, patient_id=patient.id,
        details={
            "provider": provider.name,
            "model": provider.model,
            "facts": len(result.facts),
            "dropped_unsupported": len(extraction.facts) - len(result.facts),
            "normalization_check": check.status,
            "family_attributed": sum(1 for f in extraction.facts if f.subject == FactSubject.FAMILY),
        },
        ctx=ctx,
    )
    db.commit()
    for fact in result.facts:
        db.refresh(fact)
    result.usage = ai_limits.usage_snapshot(db, patient.id)
    return result


def record_failure(db: Session, patient: PatientProfile, source: AISource, provider: AIProvider, exc: AIError) -> None:
    store_artifact(
        db, patient=patient, source=source, operation=AIOperation.EXTRACTION.value, provider=provider,
        prompt_version=None, content={"error": exc.code}, status=AIArtifactStatus.FAILED,
        digest=source_hash(source.text), key=None, error_code=exc.code,
    )


async def interpret(
    db: Session, patient: PatientProfile, source: AISource, provider: AIProvider, result: PipelineResult
) -> ExtractionResult:
    """detect → normalise → extract (each cached), filling `result`. Raises AIError."""
    text = source.text
    digest = source_hash(text)

    detection = await _cached_or_call(
        db, patient, source, provider, AIOperation.LANGUAGE_DETECTION, digest, result,
        language_tag="auto",
        call=lambda: provider.detect_language(text),
        to_content=lambda r: {"language": r.language.value if r.language else None, "confidence": r.confidence},
        from_content=lambda c: LanguageDetection(
            provider=provider.name, model=provider.model,
            language=LanguageCode(c["language"]) if c.get("language") else None,
            confidence=c.get("confidence"),
        ),
    )
    language = detection.language or source.fallback_language or DEFAULT_LANGUAGE
    result.detected_language = detection.language
    result.language_confidence = detection.confidence

    normalization = await _cached_or_call(
        db, patient, source, provider, AIOperation.NORMALIZATION, digest, result,
        language_tag=language.value,
        call=lambda: provider.normalize_to_english(text, language),
        to_content=lambda r: {"normalized_english": r.normalized_text_en, "unparsed": r.unparsed},
        from_content=lambda c: NormalizationResult(
            provider=provider.name, model=provider.model, original_text=text, source_language=language,
            normalized_text_en=c.get("normalized_english", ""), unparsed=c.get("unparsed", []),
        ),
        input_language=language,
        output_language=LanguageCode.EN,
    )
    result.normalized_english = normalization.normalized_text_en
    result.unparsed = normalization.unparsed

    extraction = await _cached_or_call(
        db, patient, source, provider, AIOperation.EXTRACTION, digest, result,
        language_tag=language.value,
        call=lambda: provider.extract_medical_information(text, language),
        to_content=lambda r: {
            "facts": [f.model_dump(mode="json") for f in r.facts],
            "needs_review": r.needs_review,
            "unparsed": r.unparsed,
        },
        from_content=lambda c: ExtractionResult.model_validate(
            {"provider": provider.name, "model": provider.model, **c}
        ),
        input_language=language,
    )
    result.needs_review = list(extraction.needs_review)
    return extraction


def finish(
    db: Session, patient: PatientProfile, source: AISource, extraction: ExtractionResult, result: PipelineResult
) -> NormalizationCheck:
    """Check the three layers agree, then validate and store the facts."""
    extraction_artifact_id = next(
        (r.artifact_id for r in result.runs if r.operation == AIOperation.EXTRACTION.value), None
    )

    check = check_normalization(source.text, result.normalized_english, extraction.facts)
    result.normalization_check = check.as_dict()
    if extraction_artifact_id is not None:
        stored = db.get(AIArtifact, extraction_artifact_id)
        if stored is not None:
            stored.content = {**stored.content, "normalization_check": check.as_dict()}

    result.facts = _store_facts(
        db, patient=patient, source=source, extraction=extraction, artifact_id=extraction_artifact_id
    )
    result.generated_at = max((r.created_at for r in result.runs if r.created_at), default=None)
    return check


async def _cached_or_call(
    db: Session,
    patient: PatientProfile,
    source: AISource,
    provider: AIProvider,
    operation: AIOperation,
    digest: str,
    result: PipelineResult,
    *,
    language_tag: str,
    call,
    to_content,
    from_content,
    input_language: LanguageCode | None = None,
    output_language: LanguageCode | None = None,
):
    from app.providers.ai.prompts import PROMPTS

    prompt_version = PROMPTS[_PROMPT_NAMES[operation]].version
    key = cache_key(operation.value, provider, prompt_version, language_tag, digest)

    cached = _find_cached(db, patient.id, key)
    if cached is not None:
        # The same text in another source (e.g. the same file uploaded twice)
        # reuses the result; record that this source used it too.
        if not any(ref.get("id") == str(source.id) for ref in cached.source_references):
            cached.source_references = [*cached.source_references, source.reference()]
        result.runs.append(
            RunInfo(
                operation=operation.value, provider=cached.provider, model=cached.model,
                prompt_version=cached.prompt_version, status=cached.status.value, cached=True,
                latency_ms=cached.latency_ms, input_tokens=cached.input_tokens,
                output_tokens=cached.output_tokens, estimated_cost_usd=cached.estimated_cost_usd,
                artifact_id=cached.id, created_at=cached.created_at,
            )
        )
        return from_content(cached.content)

    response = await _run_step(call)
    artifact = store_artifact(
        db, patient=patient, source=source, operation=operation.value, provider=provider,
        prompt_version=response.prompt_version or prompt_version, content=to_content(response),
        status=AIArtifactStatus.SUCCEEDED, digest=digest, key=key,
        input_language=input_language, output_language=output_language,
        confidence=response.confidence, usage=response.usage,
    )
    result.runs.append(
        RunInfo(
            operation=operation.value, provider=provider.name, model=provider.model,
            prompt_version=artifact.prompt_version, status=artifact.status.value,
            latency_ms=artifact.latency_ms, input_tokens=artifact.input_tokens,
            output_tokens=artifact.output_tokens, estimated_cost_usd=artifact.estimated_cost_usd,
            artifact_id=artifact.id, created_at=artifact.created_at,
        )
    )
    return response


_PROMPT_NAMES = {
    AIOperation.LANGUAGE_DETECTION: "language_detection",
    AIOperation.NORMALIZATION: "normalization",
    AIOperation.EXTRACTION: "extraction",
}


def _fact_key(category, subject, value: str) -> tuple[str, str, str]:
    """Identity of a fact for de-duplication: same kind, same person, same value."""
    return (str(category), str(subject), canonical(value))


def _store_facts(
    db: Session,
    *,
    patient: PatientProfile,
    source: AISource,
    extraction: ExtractionResult,
    artifact_id: uuid.UUID | None,
) -> list[AIExtractedFact]:
    """Validate evidence, drop unsupported facts, replace previous pending facts."""
    source_text = source.text

    # Decisions the patient already made are preserved; only pending facts are replaced.
    for stale in db.scalars(
        select(AIExtractedFact).where(
            AIExtractedFact.patient_id == patient.id,
            AIExtractedFact.source_id == source.id,
            AIExtractedFact.review_state == FactReviewState.PENDING,
        )
    ):
        db.delete(stale)

    # A fact the patient already confirmed, edited or rejected is not asked about
    # again — otherwise every re-run would add a duplicate pending copy of it.
    decided = list(
        db.scalars(
            select(AIExtractedFact).where(
                AIExtractedFact.patient_id == patient.id,
                AIExtractedFact.source_id == source.id,
                AIExtractedFact.review_state.in_(KEEP_STATES),
            )
        )
    )
    seen = {_fact_key(f.category, f.subject, f.value) for f in decided}

    position = max((f.position for f in decided), default=0)
    for fact in extraction.facts:
        key = _fact_key(fact.category, fact.subject, fact.value)
        if key in seen:
            continue  # already decided by the patient, or repeated within this run
        outcome = validate_fact(fact, source_text)
        if outcome.status == FactValidation.UNSUPPORTED:
            continue  # the AI cannot create evidence that is not in the source
        seen.add(key)
        position += 1
        start = outcome.start if outcome.start is not None else fact.evidence.start
        end = outcome.end if outcome.end is not None else fact.evidence.end
        bbox = source.span_to_bbox(start, end) if source.span_to_bbox else None
        db.add(
            AIExtractedFact(
                artifact_id=artifact_id,
                patient_id=patient.id,
                source_type=source.type,
                source_id=source.id,
                position=position,
                category=fact.category,
                subject=fact.subject,
                subject_evidence=(fact.subject_evidence or None),
                value=fact.value[:300],
                original_text=fact.original_text,
                evidence_quote=fact.evidence.quote,
                evidence_start=start,
                evidence_end=end,
                evidence_page_number=source.page_number,
                evidence_bbox=list(bbox) if bbox else None,
                confidence=fact.confidence,
                validation_status=outcome.status,
                validation_note=outcome.note,
                review_state=FactReviewState.PENDING,
            )
        )
    db.flush()
    return existing_facts(db, patient.id, source.id)


def existing_facts(db: Session, patient_id: uuid.UUID, source_id: uuid.UUID) -> list[AIExtractedFact]:
    return list(
        db.scalars(
            select(AIExtractedFact)
            .where(AIExtractedFact.patient_id == patient_id, AIExtractedFact.source_id == source_id)
            .options(selectinload(AIExtractedFact.artifact))
            .order_by(AIExtractedFact.position)
        )
    )


def get_source_state(
    db: Session, patient: PatientProfile, source: AISource, *, record: MedicalRecord | None = None
) -> PipelineResult:
    """Stored AI view for a source, without calling any provider."""
    result = PipelineResult(record=record, source_id=source.id, status="not_processed", original_text=source.text)
    result.usage = ai_limits.usage_snapshot(db, patient.id)
    artifacts = [
        a
        for a in db.scalars(
            select(AIArtifact)
            .where(
                AIArtifact.patient_id == patient.id,
                AIArtifact.source_hash == source_hash(source.text),
                AIArtifact.source_references.isnot(None),
            )
            .order_by(AIArtifact.created_at.desc())
        )
        if any(ref.get("id") == str(source.id) for ref in a.source_references)
    ]
    if not artifacts:
        return result

    latest_by_operation: dict[str, AIArtifact] = {}
    for artifact in artifacts:
        latest_by_operation.setdefault(artifact.artifact_type, artifact)

    for operation, artifact in latest_by_operation.items():
        result.runs.append(
            RunInfo(
                operation=operation, provider=artifact.provider, model=artifact.model,
                prompt_version=artifact.prompt_version, status=artifact.status.value,
                latency_ms=artifact.latency_ms, input_tokens=artifact.input_tokens,
                output_tokens=artifact.output_tokens, estimated_cost_usd=artifact.estimated_cost_usd,
                artifact_id=artifact.id, created_at=artifact.created_at,
            )
        )

    detection = latest_by_operation.get(AIOperation.LANGUAGE_DETECTION.value)
    normalization = latest_by_operation.get(AIOperation.NORMALIZATION.value)
    extraction = latest_by_operation.get(AIOperation.EXTRACTION.value)
    failed = [a for a in latest_by_operation.values() if a.status == AIArtifactStatus.FAILED]

    if detection and detection.content.get("language"):
        result.detected_language = LanguageCode(detection.content["language"])
        result.language_confidence = detection.content.get("confidence")
    if normalization:
        result.normalized_english = normalization.content.get("normalized_english")
        result.unparsed = normalization.content.get("unparsed", [])
    if extraction and extraction.status == AIArtifactStatus.SUCCEEDED:
        result.needs_review = extraction.content.get("needs_review", [])
        result.normalization_check = extraction.content.get("normalization_check")
    result.facts = existing_facts(db, patient.id, source.id)
    latest = extraction or normalization or detection
    if latest is not None:
        result.provider = latest.provider
        result.model = latest.model
    result.generated_at = max((a.created_at for a in latest_by_operation.values()), default=None)
    if extraction and extraction.status == AIArtifactStatus.SUCCEEDED:
        result.status = "ok"
    elif failed:
        result.status = "unavailable"
        result.error_code = failed[0].error_code
    return result


def get_record_state(db: Session, patient: PatientProfile, record: MedicalRecord) -> PipelineResult:
    """Stored AI view for a record, without calling any provider."""
    return get_source_state(db, patient, AISource.for_record(record), record=record)


def get_own_record(db: Session, patient: PatientProfile, record_id: uuid.UUID) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if record is None or record.patient_id != patient.id:
        raise NotFound("Record not found")
    return record


def set_consent(
    db: Session, patient: PatientProfile, actor: User, granted: bool, ctx: RequestContext | None = None
) -> PatientProfile:
    patient.ai_processing_consent = granted
    patient.ai_consent_updated_at = datetime.now().astimezone()
    audit.record(
        db, actor=actor,
        action="ai.consent_granted" if granted else "ai.consent_withdrawn",
        resource_type="patient", resource_id=patient.id, patient_id=patient.id, ctx=ctx,
    )
    db.commit()
    db.refresh(patient)
    return patient
