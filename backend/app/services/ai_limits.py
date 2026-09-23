"""Per-patient AI budget.

Bounds both abuse and provider spend before any external API is enabled. The
counters come from stored artifacts, so they survive a restart and need no
extra infrastructure. A cache hit writes no artifact and therefore costs
nothing against the budget.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AIArtifact, ConsultationSummary
from app.models.enums import AIOperation
from app.services.errors import AIRateLimited


def _runs_since(db: Session, patient_id: uuid.UUID, since: datetime) -> int:
    """One extraction artifact is written per real pipeline run (success or failure)."""
    return (
        db.scalar(
            select(func.count(AIArtifact.id)).where(
                AIArtifact.patient_id == patient_id,
                AIArtifact.artifact_type == AIOperation.EXTRACTION.value,
                AIArtifact.created_at >= since,
            )
        )
        or 0
    )


def _spend_since(db: Session, patient_id: uuid.UUID, since: datetime) -> float:
    return (
        db.scalar(
            select(func.coalesce(func.sum(AIArtifact.estimated_cost_usd), 0.0)).where(
                AIArtifact.patient_id == patient_id,
                AIArtifact.created_at >= since,
            )
        )
        or 0.0
    )


def usage_snapshot(db: Session, patient_id: uuid.UUID, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    return {
        "runs_last_hour": _runs_since(db, patient_id, now - timedelta(hours=1)),
        "runs_last_day": _runs_since(db, patient_id, now - timedelta(days=1)),
        "spend_last_day_usd": round(_spend_since(db, patient_id, now - timedelta(days=1)), 6),
        "limit_per_hour": settings.ai_rate_limit_per_hour,
        "limit_per_day": settings.ai_rate_limit_per_day,
        "daily_cost_limit_usd": settings.ai_daily_cost_limit_usd,
    }


def enforce_rate_limit(
    db: Session, patient_id: uuid.UUID, settings: Settings | None = None, runs_needed: int = 1
) -> None:
    """Raise `AIRateLimited` when this patient cannot afford `runs_needed` more runs.

    Checked before any provider work, so an over-budget request sends nothing.
    A document needs one run per page that has text.
    """
    settings = settings or get_settings()
    now = datetime.now(UTC)
    runs_needed = max(1, runs_needed)

    if settings.ai_rate_limit_per_hour > 0:
        used = _runs_since(db, patient_id, now - timedelta(hours=1))
        if used + runs_needed > settings.ai_rate_limit_per_hour:
            raise AIRateLimited(
                f"AI processing limit reached ({settings.ai_rate_limit_per_hour} per hour). "
                "Please try again later — your information is unaffected."
            )

    if settings.ai_rate_limit_per_day > 0:
        used = _runs_since(db, patient_id, now - timedelta(days=1))
        if used + runs_needed > settings.ai_rate_limit_per_day:
            raise AIRateLimited(
                f"Daily AI processing limit reached ({settings.ai_rate_limit_per_day} per day). "
                "Please try again tomorrow — your information is unaffected."
            )

    enforce_cost_limit(db, patient_id, settings)


def enforce_cost_limit(db: Session, patient_id: uuid.UUID, settings: Settings | None = None) -> None:
    """The 24-hour estimated-spend cap alone, without the run counters.

    Split out so case summarisation can be bound by provider spend — which is
    about protecting the patient's budget — without consuming the hourly and
    daily run allowance, which is reserved for work the patient starts
    themselves. A doctor regenerating a summary must not use up the runs a
    patient needs for their own record.
    """
    settings = settings or get_settings()
    if settings.ai_daily_cost_limit_usd <= 0:
        return
    spend = _spend_since(db, patient_id, datetime.now(UTC) - timedelta(days=1))
    if spend >= settings.ai_daily_cost_limit_usd:
        raise AIRateLimited(
            "Daily AI processing budget reached. Please try again tomorrow — "
            "your information is unaffected."
        )


def summary_generations(db: Session, consultation_id: uuid.UUID) -> int:
    """Real generations so far for one consultation.

    Cache hits create no row and so cost nothing. Failures do count: they spent
    a provider call, and a failing provider should not be an unlimited one.
    """
    return (
        db.scalar(
            select(func.count(ConsultationSummary.id)).where(
                ConsultationSummary.consultation_id == consultation_id
            )
        )
        or 0
    )


def summary_generations_remaining(
    db: Session, consultation_id: uuid.UUID, settings: Settings | None = None
) -> int | None:
    """How many more times this summary may be generated. None when unlimited."""
    settings = settings or get_settings()
    if settings.summary_per_consultation_limit <= 0:
        return None
    used = summary_generations(db, consultation_id)
    return max(0, settings.summary_per_consultation_limit - used)


def enforce_summary_limit(
    db: Session, consultation_id: uuid.UUID, settings: Settings | None = None
) -> None:
    """Bound how many times one consultation's summary may be regenerated.

    A separate counter from the patient's, because this spends on the doctor's
    initiative. Set 0 to disable, as with every other limit here.
    """
    settings = settings or get_settings()
    if settings.summary_per_consultation_limit <= 0:
        return
    if summary_generations(db, consultation_id) >= settings.summary_per_consultation_limit:
        raise AIRateLimited(
            f"This case summary has been generated {settings.summary_per_consultation_limit} times. "
            "The shared information itself is unaffected and remains available."
        )
