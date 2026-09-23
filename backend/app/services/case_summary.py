"""Case summarisation for one consultation (Phase 4).

    consultation
        → authorization check (doctor owns it, status visible)
        → patient consent
        → budget (patient spend + this consultation's generation cap)
        → authorised source bundle, opaque refs      ← the boundary closes here
        → hash + cache lookup
        → provider (organisation only, never a conclusion)
        → schema validation
        → source and safety validation
        → store artifact + summary
        → audit

Everything before the provider call is an authorization or budget gate, so a
request that should not happen sends nothing anywhere. Nothing here interprets
medical meaning: the summary reorganises information the doctor may already
read, every item points back at its source, and the originals are untouched.

Failure never invents content. A provider error, malformed output or an empty
result after validation all end the same way — a recorded failure, a stable
error code, and the case view still showing everything it showed before.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.languages import DEFAULT_LANGUAGE, LanguageCode
from app.models import AIArtifact, Consultation, ConsultationSummary, DoctorProfile, User
from app.models.enums import AIArtifactStatus, AIOperation, SummaryStatus
from app.providers.ai import get_ai_provider, get_circuit_breaker
from app.providers.ai.base import AIProvider
from app.providers.ai.runtime import call_with_resilience
from app.providers.ai.errors import AIError, AIMalformedOutput
from app.schemas.summary import CaseSummaryOut, ModelCaseSummary, StoredCaseSummary
from app.services import ai_limits, audit, case_summary_bundle, consultation_service, summary_validation
from app.services.audit import RequestContext
from app.services.case_summary_bundle import SourceBundle
from app.services.errors import AIRateLimited, AIUnavailable

SUMMARY_OPERATION = AIOperation.CASE_SUMMARY.value


class Summarizer(Protocol):
    """How the pipeline reaches a provider.

    Normally `_provider_summarizer` binds the configured `AIProvider`. Tests and
    the evaluation harness inject their own, so the gates, the caching and the
    validation can be exercised against a known organisation without a network.
    """

    async def __call__(self, bundle: SourceBundle, language: LanguageCode) -> "SummarizerResult": ...


@dataclass
class SummarizerResult:
    """What a provider returns, before anything of ours is attached to it."""

    summary: ModelCaseSummary
    provider: str
    model: str
    prompt_version: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    #: None means unknown, and stays unknown. Pricing is never invented.
    estimated_cost_usd: float | None = None


def _provider_summarizer(provider: AIProvider) -> Summarizer:
    """Bind a provider into the `Summarizer` seam, with the usual resilience.

    The provider is handed `bundle.canonical()` — byte for byte the same text the
    bundle hash is taken over. What was sent and what was hashed are therefore
    provably the same thing, so a cached summary can never correspond to a
    different set of words than the one that produced it.
    """

    async def call(bundle: SourceBundle, language: LanguageCode) -> SummarizerResult:
        settings = get_settings()
        organisation = await call_with_resilience(
            lambda: provider.summarize_case(bundle.canonical()),
            timeout_seconds=settings.ai_timeout_seconds,
            max_attempts=settings.ai_max_attempts,
            breaker=get_circuit_breaker(),
        )
        try:
            model_summary = ModelCaseSummary.model_validate(organisation.payload)
        except ValidationError as exc:
            # A provider that invents a field or a section fails here, as
            # malformed output — never as a stored summary.
            raise AIMalformedOutput(str(exc), provider=provider.name) from exc
        usage = organisation.usage
        return SummarizerResult(
            summary=model_summary,
            provider=organisation.provider,
            model=organisation.model,
            prompt_version=organisation.prompt_version,
            latency_ms=usage.latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
        )

    return call


@dataclass
class SummaryState:
    """A stored summary judged against the information as it stands right now."""

    consultation_id: uuid.UUID
    status: str  # not_generated | generating | ready | stale | failed
    is_stale: bool
    current_bundle_hash: str
    summary: ConsultationSummary | None = None
    generations_remaining: int | None = None


def _latest(db: Session, consultation_id: uuid.UUID) -> ConsultationSummary | None:
    return db.scalar(
        select(ConsultationSummary)
        .where(ConsultationSummary.consultation_id == consultation_id)
        .order_by(ConsultationSummary.created_at.desc(), ConsultationSummary.id.desc())
        .limit(1)
    )


def _cached(
    db: Session, consultation_id: uuid.UUID, bundle_hash: str, provider: AIProvider, prompt_version: str | None
) -> ConsultationSummary | None:
    """A ready summary of exactly this information, by this provider and prompt.

    Same provider, same model, same prompt version, same bundle content — the
    answer cannot differ, so reuse it and spend nothing. Change any one of them
    and this misses, which is what stops a changed prompt silently serving output
    produced by the old wording.
    """
    if not get_settings().ai_cache_enabled:
        return None
    return db.scalar(
        select(ConsultationSummary)
        .where(
            ConsultationSummary.consultation_id == consultation_id,
            ConsultationSummary.source_bundle_hash == bundle_hash,
            ConsultationSummary.status == SummaryStatus.READY,
            ConsultationSummary.provider == provider.name,
            ConsultationSummary.model == provider.model,
            ConsultationSummary.prompt_version == prompt_version,
        )
        .order_by(ConsultationSummary.created_at.desc())
        .limit(1)
    )


def _authorized(db: Session, doctor: DoctorProfile, consultation_id: uuid.UUID):
    """Gates 1-3: this doctor's consultation, in a status they may still read."""
    c = consultation_service.get_doctor_consultation(db, doctor, consultation_id)
    return c, consultation_service.resolve_authorized_context(db, c)


def get_state(db: Session, doctor: DoctorProfile, consultation_id: uuid.UUID) -> SummaryState:
    """The current summary, and whether it still describes the shared information.

    Staleness is computed here rather than stored (D-054): shared records are
    live references (D-006), so the only honest answer is a fresh comparison.
    """
    c, context = _authorized(db, doctor, consultation_id)
    bundle = case_summary_bundle.build_source_bundle(db, context)
    current_hash = bundle.hash()
    latest = _latest(db, c.id)
    remaining = ai_limits.summary_generations_remaining(db, c.id)

    if latest is None:
        return SummaryState(c.id, "not_generated", False, current_hash, None, remaining)
    if latest.status == SummaryStatus.GENERATING:
        return SummaryState(c.id, "generating", False, current_hash, latest, remaining)
    if latest.status == SummaryStatus.FAILED:
        return SummaryState(c.id, "failed", False, current_hash, latest, remaining)

    stale = latest.source_bundle_hash != current_hash
    return SummaryState(c.id, "stale" if stale else "ready", stale, current_hash, latest, remaining)


def _store_artifact(
    db: Session,
    *,
    c: Consultation,
    bundle: SourceBundle,
    result: SummarizerResult | None,
    status: AIArtifactStatus,
    error_code: str | None = None,
    provider_name: str = "",
    model_name: str = "",
) -> AIArtifact:
    """Provenance for one summarisation run, in the existing artifact table.

    `content` holds counts and the bundle's shape, never the summary text and
    never patient content: the summary itself lives in its own row, and the
    artifact is the receipt.
    """
    artifact = AIArtifact(
        patient_id=c.patient_id,
        consultation_id=c.id,
        artifact_type=SUMMARY_OPERATION,
        provider=result.provider if result else provider_name,
        model=result.model if result else model_name,
        prompt_version=result.prompt_version if result else None,
        source_references=[{"type": "consultation", "id": str(c.id)}],
        source_hash=bundle.hash(),
        cache_key=None,
        input_language=None,
        output_language=LanguageCode.EN,
        content={
            "source_items": len(bundle.items),
            "pending_facts": bundle.pending_fact_count,
            "truncated": bundle.truncated,
            **({"error": error_code} if error_code else {}),
        },
        status=status,
        error_code=error_code,
        latency_ms=result.latency_ms if result else None,
        input_tokens=result.input_tokens if result else None,
        output_tokens=result.output_tokens if result else None,
        estimated_cost_usd=result.estimated_cost_usd if result else None,
    )
    db.add(artifact)
    db.flush()
    return artifact


async def generate(
    db: Session,
    doctor: DoctorProfile,
    actor: User,
    consultation_id: uuid.UUID,
    ctx: RequestContext | None = None,
    summarize: Summarizer | None = None,
    provider: AIProvider | None = None,
) -> SummaryState:
    """Generate (or reuse) the case summary for one consultation."""
    c, context = _authorized(db, doctor, consultation_id)

    # Gate 4: the patient's consent covers all AI processing of their
    # information (D-020), including a summary another party asked for.
    from app.services.ai_pipeline import require_consent

    require_consent(c.patient)

    provider = provider or get_ai_provider()
    bundle = case_summary_bundle.build_source_bundle(db, context)
    bundle_hash = bundle.hash()

    audit.record(
        db, actor=actor, action="consultation.summary_requested", resource_type="consultation",
        resource_id=c.id, patient_id=c.patient_id,
        details={
            "provider": provider.name,
            "model": provider.model,
            "external": provider.is_external,
            "source_items": len(bundle.items),
        },
        ctx=ctx,
    )

    prompt_version = _prompt_version()
    reuse = _cached(db, c.id, bundle_hash, provider, prompt_version)
    if reuse is not None:
        db.commit()
        return get_state(db, doctor, consultation_id)

    # Gate 5: budget, before anything is sent. Patient spend stays bounded, and
    # this consultation has its own generation cap (Stage A decision 3).
    try:
        ai_limits.enforce_cost_limit(db, c.patient_id)
        ai_limits.enforce_summary_limit(db, c.id)
    except AIRateLimited:
        # Only a budget refusal is audited as one. A broader catch here would
        # file a programming error under "rate limited" and make the audit trail
        # say something untrue about why a doctor was turned away.
        audit.record(
            db, actor=actor, action="consultation.summary_rate_limited", resource_type="consultation",
            resource_id=c.id, patient_id=c.patient_id, ctx=ctx,
        )
        db.commit()
        raise

    regenerating = _latest(db, c.id) is not None
    row = ConsultationSummary(
        consultation_id=c.id,
        patient_id=c.patient_id,
        doctor_id=doctor.id,
        source_bundle_hash=bundle_hash,
        prompt_version=prompt_version,
        provider=provider.name,
        model=provider.model,
        status=SummaryStatus.GENERATING,
        language=DEFAULT_LANGUAGE,
        summary={},
        warnings=[],
    )
    db.add(row)
    db.flush()

    call = summarize or _provider_summarizer(provider)
    try:
        result = await call(bundle, DEFAULT_LANGUAGE)
    except AIError as exc:
        return _fail(db, c, row, bundle, actor, ctx, exc.code, provider)

    outcome = summary_validation.validate_summary(result.summary, bundle)
    stored = summary_validation.assemble(result.summary, bundle, outcome)

    if not stored.sections and not stored.unresolved_notes:
        # Everything the model produced failed validation. Say so plainly rather
        # than presenting an empty summary as a complete one.
        return _fail(
            db, c, row, bundle, actor, ctx, "summary_unsupported", provider,
            result, outcome.dropped, outcome.warnings,
        )

    artifact = _store_artifact(db, c=c, bundle=bundle, result=result, status=AIArtifactStatus.SUCCEEDED)
    # The row keeps the identity the cache key was computed from — the provider,
    # model and prompt version we were about to call. The artifact keeps what
    # actually answered. They agree in normal operation; when they do not, the
    # artifact shows it rather than the cache silently never hitting again.
    row.artifact_id = artifact.id
    row.status = SummaryStatus.READY
    row.summary = stored.model_dump(mode="json")
    row.dropped_item_count = outcome.dropped
    row.warnings = outcome.warnings
    row.generated_at = datetime.now(UTC)

    audit.record(
        db, actor=actor,
        action="consultation.summary_regenerated" if regenerating else "consultation.summary_generated",
        resource_type="consultation", resource_id=c.id, patient_id=c.patient_id,
        details={
            "summary_id": str(row.id),
            "provider": result.provider,
            "model": result.model,
            "sections": len(stored.sections),
            "items": sum(len(s.items) for s in stored.sections),
            "dropped": outcome.dropped,
            "pending_facts": stored.pending_fact_count,
        },
        ctx=ctx,
    )
    db.commit()
    return get_state(db, doctor, consultation_id)


def _fail(
    db: Session,
    c: Consultation,
    row: ConsultationSummary,
    bundle: SourceBundle,
    actor: User,
    ctx: RequestContext | None,
    error_code: str,
    provider: AIProvider,
    result: SummarizerResult | None = None,
    dropped: int = 0,
    warnings: list[str] | None = None,
) -> SummaryState:
    """Record the failure, keep the original information, invent nothing.

    Why it failed is kept too. A doctor told only "unavailable" cannot tell an
    outage from a summary whose every line was rejected, and those mean very
    different things about the case in front of them.
    """
    artifact = _store_artifact(
        db, c=c, bundle=bundle, result=result, status=AIArtifactStatus.FAILED,
        error_code=error_code, provider_name=provider.name, model_name=provider.model,
    )
    row.artifact_id = artifact.id
    row.status = SummaryStatus.FAILED
    row.error_code = error_code
    row.dropped_item_count = dropped
    row.warnings = list(warnings or [])
    audit.record(
        db, actor=actor, action="consultation.summary_failed", resource_type="consultation",
        resource_id=c.id, patient_id=c.patient_id,
        details={
            "summary_id": str(row.id), "error": error_code, "dropped": dropped,
            "reasons": list(warnings or []),
        },
        ctx=ctx,
    )
    db.commit()
    db.refresh(row)
    return SummaryState(
        consultation_id=c.id,
        status="failed",
        is_stale=False,
        current_bundle_hash=bundle.hash(),
        summary=row,
        generations_remaining=ai_limits.summary_generations_remaining(db, c.id),
    )


def _prompt_version() -> str | None:
    """The case-summary prompt version, once Stage C adds one."""
    from app.providers.ai.prompts import PROMPTS

    prompt = PROMPTS.get("case_summary")
    return prompt.version if prompt else None


def record_view(
    db: Session, actor: User, c: Consultation, summary: ConsultationSummary, ctx: RequestContext | None = None
) -> None:
    audit.record(
        db, actor=actor, action="consultation.summary_viewed", resource_type="consultation",
        resource_id=c.id, patient_id=c.patient_id,
        details={"summary_id": str(summary.id), "status": summary.status.value}, ctx=ctx,
    )
    db.commit()


def present(state: SummaryState, provider: AIProvider | None = None) -> CaseSummaryOut:
    """SummaryState → the doctor-facing DTO."""
    row = state.summary
    if row is None:
        return CaseSummaryOut(
            consultation_id=state.consultation_id,
            status="not_generated",
            generations_remaining=state.generations_remaining,
        )
    stored = StoredCaseSummary.model_validate(row.summary) if row.summary else None
    return CaseSummaryOut(
        consultation_id=state.consultation_id,
        status=state.status,
        is_stale=state.is_stale,
        summary=stored if row.status == SummaryStatus.READY else None,
        generated_at=row.generated_at,
        language=row.language,
        provider=row.provider,
        model=row.model,
        prompt_version=row.prompt_version,
        is_external_provider=provider.is_external if provider else None,
        dropped_item_count=row.dropped_item_count,
        warnings=list(row.warnings or []),
        error_code=row.error_code,
        generations_remaining=state.generations_remaining,
    )


__all__ = [
    "AIUnavailable",
    "SUMMARY_OPERATION",
    "SummarizerResult",
    "SummaryState",
    "generate",
    "get_state",
    "present",
    "record_view",
]
