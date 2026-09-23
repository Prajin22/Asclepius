"""Case-summary schemas (Phase 4).

Three layers, and the split between them is the safety property:

* `ModelCaseSummary` — the *only* shape a provider may return. Organisation
  only: which authorised sources group together, under which section, in which
  order. It carries no identifiers, no provenance and no attribution, because
  the model is not the authority on any of those.
* `StoredCaseSummary` — what the application writes after resolving every
  reference and attaching provenance from the source bundle.
* `CaseSummaryOut` — what a doctor's browser receives.

No field in any of them can express a diagnosis, differential, risk score,
triage level, severity, prognosis or treatment recommendation, and `extra` is
forbidden everywhere, so a provider that invents one produces a validation
error rather than a stored summary.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.languages import LanguageCode
from app.models.enums import (
    AuthorizationBasis,
    BundleItemKind,
    FactSubject,
    SummaryItemOrigin,
    SummarySectionKind,
)

#: An organising line, not prose. Short enough that it cannot become a narrative
#: in which an unsupported clinical claim could hide.
Statement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

#: Opaque, per-bundle source handle such as "S7". Never a database identifier.
SourceRef = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^S[1-9][0-9]{0,3}$")]

MAX_ITEMS = 80
MAX_NOTES = 20


# --------------------------------------------------------------------------
# Layer 1 — what a provider may return
# --------------------------------------------------------------------------


class ModelSummaryItem(BaseModel):
    """One organised line proposed by the model.

    Deliberately absent: origin, subject, evidence, dates, identifiers. The
    application fills those in from the cited sources, so a model cannot change
    who said something, whose health it describes, or where it came from.
    """

    model_config = ConfigDict(extra="forbid")

    section: SummarySectionKind
    statement: Statement
    #: At least one authorised source. An item citing nothing is not a summary
    #: of anything, and is dropped.
    source_refs: list[SourceRef] = Field(min_length=1, max_length=12)
    #: True when the cited sources disagree. It flags the disagreement; it never
    #: resolves it, and nothing downstream picks a side.
    is_contradiction: bool = False


class ModelCaseSummary(BaseModel):
    """The whole provider response. Grouping and ordering — nothing else."""

    model_config = ConfigDict(extra="forbid")

    items: list[ModelSummaryItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    #: Preferred section order. Unknown or duplicate entries are ignored by the
    #: application, which always falls back to the canonical order.
    section_order: list[SummarySectionKind] = Field(default_factory=list, max_length=20)
    #: Things the model could not place. Free text, shown as-is, never treated
    #: as a claim about the patient.
    unresolved_notes: list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = Field(
        default_factory=list, max_length=MAX_NOTES
    )


# --------------------------------------------------------------------------
# Layer 2 — what the application stores
# --------------------------------------------------------------------------


class CaseSummarySource(BaseModel):
    """A resolved pointer back to the authorised row an item came from."""

    model_config = ConfigDict(extra="forbid")

    ref: str
    kind: BundleItemKind
    authorization_basis: AuthorizationBasis
    #: Whichever identifiers apply to this kind of source. Resolved by the
    #: application from the bundle; never supplied by a model.
    record_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    consultation_id: uuid.UUID | None = None
    prescription_id: uuid.UUID | None = None
    fact_id: uuid.UUID | None = None
    page_number: int | None = None
    #: [x0, y0, x1, y1] as fractions of the page, when the reader measured it.
    bbox: list[float] | None = None
    #: The words in the source that support the item, in their original script.
    quote: str | None = None
    #: The patient's own wording, when the source has it.
    original_text: str | None = None
    language: LanguageCode | None = None
    #: Doctor-authored sources say who authored them.
    doctor_name: str | None = None
    occurred_at: datetime | None = None


class CaseSummaryItem(BaseModel):
    """One organised line, with provenance the application attached."""

    model_config = ConfigDict(extra="forbid")

    section: SummarySectionKind
    statement: str
    #: Always a human. There is no machine origin for a claim (D-053).
    origin: SummaryItemOrigin
    #: Copied from the source fact, never inferred. A relative's condition stays
    #: a relative's condition.
    subject: FactSubject | None = None
    subject_evidence: str | None = None
    is_contradiction: bool = False
    occurred_at: datetime | None = None
    sources: list[CaseSummarySource] = Field(min_length=1)


class CaseSummarySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SummarySectionKind
    items: list[CaseSummaryItem]


class StoredCaseSummary(BaseModel):
    """The payload written to `consultation_summaries.summary`."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    sections: list[CaseSummarySection] = Field(default_factory=list)
    unresolved_notes: list[str] = Field(default_factory=list)
    #: Facts the patient has not yet confirmed. Counted, never stated
    #: (Stage A decision 2), so an unreviewed case cannot look like a complete one.
    pending_fact_count: int = 0
    #: Source kinds that were capped when the bundle was built.
    truncated: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Layer 3 — what the doctor's browser receives
# --------------------------------------------------------------------------

#: `not_generated` and `stale` are derived at read time, never stored (D-054).
SummaryViewStatus = Literal["not_generated", "generating", "ready", "stale", "failed"]


class CaseSummaryOut(BaseModel):
    """A case summary and everything needed to judge how much to trust it."""

    model_config = ConfigDict(extra="forbid")

    consultation_id: uuid.UUID
    status: SummaryViewStatus
    #: True when the shared information has changed since this was generated.
    is_stale: bool = False
    summary: StoredCaseSummary | None = None
    #: When the information it organises was read, so the doctor can say
    #: "generated from information shared on ...".
    generated_at: datetime | None = None
    language: LanguageCode | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    #: False in DEMO_MODE, where the deterministic local provider runs.
    is_external_provider: bool | None = None
    dropped_item_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    #: How many more times this consultation's summary may be generated.
    generations_remaining: int | None = None
