"""Application-side validation of a model's case summary (Phase 4).

The schema stops a provider returning a diagnosis. This stops it returning a
*supported-looking* claim that nothing in the bundle actually supports.

Ten checks, and the honest thing to say about them is that six are structural
and four are best-effort:

Structural — cannot fail if the code is correct
  1. every cited reference exists in this bundle
  2. every cited source is authorised (refs exist only for authorised rows, and
     only inside one bundle, so an unshared item is uncitable by construction)
  3. every item cites at least one source
  8. doctor-authored sources yield doctor-authored items and nothing else
  9. no unshared document can be referenced
 10. no unshared consultation can be referenced

Best-effort — they catch known failure modes, they do not prove correctness
  4. quoted text really appears in the cited source
  5. subject attribution matches the source fact (enforced by overwriting, not
     by trusting)
  6. no prohibited clinical conclusion (Pydantic `extra="forbid"` plus an enum
     with no diagnosis member)
  7. statements introduce no medical term the cited sources do not support, and
     no unstated absence

Check 7 is bounded by the lexicon, exactly as the Phase 2 drift check is
(D-031). It can show that a known term is unsupported; it cannot show that a
statement is faithful. That is why statements are capped short, why every item
must cite, and why dropped items are counted and shown rather than hidden.

An item that fails any check is **dropped**. It is never repaired, never
re-requested from the model, and never guessed at.
"""

from dataclasses import dataclass, field

from app.models.enums import (
    BundleItemKind,
    FactSubject,
    SummaryItemOrigin,
    SummarySectionKind,
)
from app.providers.ai.lexicon import CONDITIONS, MEDICATIONS, SYMPTOMS
from app.schemas.summary import (
    CaseSummaryItem,
    CaseSummarySection,
    CaseSummarySource,
    ModelCaseSummary,
    StoredCaseSummary,
)
from app.services.case_summary_bundle import BundleItem, SourceBundle
from app.services.evidence import _EXPLICIT_ABSENCE_CUES, _locate, canonical

#: Sections that assert something about a person's health. These are exactly the
#: six extraction categories, so each one maps to a kind of fact the patient has
#: already confirmed.
HEALTH_CLAIM_SECTIONS = frozenset(
    {
        SummarySectionKind.SYMPTOM,
        SummarySectionKind.DURATION,
        SummarySectionKind.MEDICATION,
        SummarySectionKind.ALLERGY,
        SummarySectionKind.MEDICAL_HISTORY,
        SummarySectionKind.MEASUREMENT,
    }
)

#: Sources a health claim may rest on without further argument: a fact the
#: patient confirmed, or a prescription a doctor authored. Both are structured
#: and both have a human behind them.
#:
#: This is the structural form of "only confirmed information becomes a
#: statement". Narrative free text — a current problem, a message, a document, a
#: doctor's note — can support a pointer ("current problem recorded on the
#: 23rd") but never a claim about the patient's health, because turning
#: narrative into a health claim is extraction, and extraction goes through the
#: patient (Phase 2).
#:
#: It is also the defence that does not depend on a word list. A model that
#: reads an instruction inside a document and asserts a condition cites
#: narrative text, so it is dropped whether or not the invented condition
#: happens to be in the lexicon.
STRUCTURED_SOURCE_KINDS = frozenset({BundleItemKind.FACT, BundleItemKind.PRIOR_PRESCRIPTION})


def _record_title_supports(statement: str, sources: list[BundleItem]) -> bool:
    """Does a health record the patient wrote themselves carry this claim?

    A health record is not narrative: the patient typed it as a record, chose its
    type, and gave it a title — "Hypertension", "Penicillin allergy". That title
    is the patient's own assertion about their health, with no machine in
    between, and it would be wrong to exclude it from a summary whose whole
    purpose is to carry what the patient said.

    So a record may support a claim, but only through that title. A statement
    drawn from the record's free-text body is extraction again, and is not
    accepted here — which is what stops an instruction hidden in a record body
    from becoming a finding.
    """
    target = canonical(statement)
    if not target:
        return False
    for source in sources:
        if source.kind != BundleItemKind.HEALTH_RECORD:
            continue
        title = canonical(source.payload.get("title") or "")
        if title and (title in target or target in title):
            return True
    return False

#: Doctor-authored sources may only ever feed these sections. A doctor's
#: assessment must not reappear as the patient's confirmed symptom.
DOCTOR_ONLY_SECTIONS = frozenset(
    {
        SummarySectionKind.PRIOR_CONSULTATION,
        SummarySectionKind.DOCTOR_AUTHORED_CONTEXT,
        SummarySectionKind.MEDICATION,
        SummarySectionKind.UNRESOLVED_INFORMATION,
    }
)

#: The order sections are shown in when the model offers none, or offers a
#: partial one. Roughly the order a consultation actually runs.
CANONICAL_ORDER: tuple[SummarySectionKind, ...] = (
    SummarySectionKind.CURRENT_PROBLEM,
    SummarySectionKind.PATIENT_STATEMENT,
    SummarySectionKind.SYMPTOM,
    SummarySectionKind.DURATION,
    SummarySectionKind.MEASUREMENT,
    SummarySectionKind.MEDICATION,
    SummarySectionKind.ALLERGY,
    SummarySectionKind.MEDICAL_HISTORY,
    SummarySectionKind.DOCUMENT,
    SummarySectionKind.PRIOR_CONSULTATION,
    SummarySectionKind.DOCTOR_AUTHORED_CONTEXT,
    SummarySectionKind.UNRESOLVED_INFORMATION,
)

#: English concept -> every surface form, across languages. Same table the
#: Phase 2 drift check uses, so the two cannot disagree about what a term is.
_CONCEPTS: dict[str, tuple[str, ...]] = {
    concept.value: tuple(form for _lang, form in concept.all_forms())
    for concept in (*SYMPTOMS, *MEDICATIONS, *CONDITIONS)
}

_ABSENCE_MARKERS = ("no known", "none", "no allerg", "not allergic", "denies", "no history of")


@dataclass
class ValidationOutcome:
    items: list[CaseSummaryItem] = field(default_factory=list)
    dropped: int = 0
    #: Machine-readable reasons, counted. Shown to the doctor so a thinned
    #: summary never reads as a complete one.
    warnings: list[str] = field(default_factory=list)

    def drop(self, reason: str) -> None:
        self.dropped += 1
        if reason not in self.warnings:
            self.warnings.append(reason)


def _source_out(item: BundleItem) -> CaseSummarySource:
    """The resolved pointer for one bundle item — real ids, from our side only."""
    r = item.resolution
    return CaseSummarySource(
        ref=item.ref,
        kind=item.kind,
        authorization_basis=item.authorization_basis,
        record_id=r.get("record_id"),
        document_id=r.get("document_id"),
        consultation_id=r.get("consultation_id"),
        prescription_id=r.get("prescription_id"),
        fact_id=r.get("fact_id"),
        page_number=r.get("page_number"),
        bbox=r.get("bbox"),
        quote=r.get("quote"),
        original_text=r.get("original_text"),
        language=r.get("language"),
        doctor_name=r.get("doctor_name"),
        occurred_at=r.get("occurred_at"),
    )


def _origin_for(sources: list[BundleItem]) -> SummaryItemOrigin:
    """Derived from the sources, never from the model.

    Doctor-authored wins: if any cited source is a doctor's words, the item is
    doctor-authored and must be shown as such. Otherwise a confirmed fact makes
    it patient-confirmed, and anything else is the patient's own words.
    """
    origins = {s.origin for s in sources}
    if SummaryItemOrigin.DOCTOR_AUTHORED in origins:
        return SummaryItemOrigin.DOCTOR_AUTHORED
    if SummaryItemOrigin.PATIENT_CONFIRMED in origins:
        return SummaryItemOrigin.PATIENT_CONFIRMED
    return SummaryItemOrigin.PATIENT_PROVIDED


def _subject_for(sources: list[BundleItem]) -> tuple[FactSubject | None, str | None]:
    """Attribution copied from the cited facts. Never inferred, never merged.

    If the cited facts disagree about whose health this is, the item describes
    more than one person and is not safe to state as one line — the caller
    drops it.
    """
    subjects: set[str] = set()
    evidence: str | None = None
    for source in sources:
        value = source.resolution.get("subject")
        if value:
            subjects.add(value)
            evidence = evidence or source.resolution.get("subject_evidence")
    if not subjects:
        return None, None
    if len(subjects) > 1:
        raise _MixedSubjects()
    return FactSubject(next(iter(subjects))), evidence


class _MixedSubjects(Exception):
    """One statement covering two different people's health."""


def _claims_absence(statement: str) -> bool:
    text = canonical(statement)
    return any(marker in text for marker in _ABSENCE_MARKERS)


def _absence_is_stated(sources: list[BundleItem]) -> bool:
    """An absence may only be repeated, never introduced (AI_POLICY rule 2)."""
    haystack = canonical(" ".join(s.support_text for s in sources))
    return any(canonical(cue) in haystack for cue in _EXPLICIT_ABSENCE_CUES)


#: A statement at least this long that is a verbatim span of a source's free
#: text is a copy, not an organising line. Confirmed values and labels are far
#: shorter than this, so the rule does not touch them.
_COPY_THRESHOLD = 80


def _copies_source_text(statement: str, sources: list[BundleItem]) -> bool:
    """Is this statement just a chunk of untrusted free text?

    Free text — what a patient wrote, what a document says, what a doctor noted —
    reaches the reader through the source block, labelled as theirs. A statement
    that reproduces a long span of it lets anything written inside read as the
    summary's own line, including text shaped like an instruction. The words are
    not the problem; presenting them as the summary's own organisation is.
    """
    candidate = canonical(statement)
    if len(candidate) < _COPY_THRESHOLD:
        return False
    return any(candidate in canonical(source.support_text) for source in sources)


def _unsupported_terms(statement: str, sources: list[BundleItem]) -> list[str]:
    """Known medical terms in the statement that no cited source supports."""
    text = canonical(statement)
    support = canonical(" ".join(s.support_text for s in sources))
    unsupported = []
    for concept, forms in _CONCEPTS.items():
        term = canonical(concept)
        if term and term in text and not any(canonical(form) in support for form in forms):
            unsupported.append(concept)
    return unsupported


def validate_summary(model_summary: ModelCaseSummary, bundle: SourceBundle) -> ValidationOutcome:
    """Resolve, check and attach provenance. Anything that fails is dropped."""
    outcome = ValidationOutcome()
    by_ref = bundle.by_ref

    for item in model_summary.items:
        # 1-3. Every reference must resolve inside *this* bundle. Unshared rows
        # have no ref at all, so 2, 9 and 10 hold structurally.
        refs = list(dict.fromkeys(item.source_refs))
        sources = [by_ref[ref] for ref in refs if ref in by_ref]
        if len(sources) != len(refs):
            outcome.drop("unknown_source_reference")
            continue
        if not sources:
            outcome.drop("no_source_reference")
            continue

        origin = _origin_for(sources)

        # 8. Doctor-authored material may not become a patient claim.
        if origin == SummaryItemOrigin.DOCTOR_AUTHORED and item.section not in DOCTOR_ONLY_SECTIONS:
            outcome.drop("doctor_authored_recast_as_patient_claim")
            continue
        # …and the reverse: a doctor-authored section must cite doctor material.
        if item.section == SummarySectionKind.PRIOR_CONSULTATION and not any(
            s.kind in (BundleItemKind.PRIOR_CONSULTATION, BundleItemKind.PRIOR_PRESCRIPTION)
            for s in sources
        ):
            outcome.drop("prior_consultation_without_doctor_source")
            continue

        # 5. Attribution is copied from the source, never taken from the model.
        try:
            subject, subject_evidence = _subject_for(sources)
        except _MixedSubjects:
            outcome.drop("mixed_subject_attribution")
            continue

        # A statement is an organising line, never a copy of untrusted free text.
        # Applies to every section: a document listing must not become a place to
        # reproduce a page, either.
        if _copies_source_text(item.statement, sources):
            outcome.drop("statement_copies_source_text")
            continue

        if item.section in HEALTH_CLAIM_SECTIONS:
            # 3b. A claim about the patient's health must rest on something the
            # patient confirmed, a doctor authored, or the patient's own label on
            # a record they wrote — never on narrative free text.
            structured = any(s.kind in STRUCTURED_SOURCE_KINDS for s in sources)
            if not structured and not _record_title_supports(item.statement, sources):
                outcome.drop("health_claim_without_confirmed_source")
                continue
            # 7a. Absence must be stated in the source, in any of the languages
            # the extractor understands.
            if _claims_absence(item.statement) and not _absence_is_stated(sources):
                outcome.drop("unstated_absence")
                continue
            # 7b. No medical term the cited sources do not carry.
            if _unsupported_terms(item.statement, sources):
                outcome.drop("unsupported_medical_term")
                continue

        # 4. A quoted fragment must really be in the source it is attributed to.
        quoted = [s for s in sources if s.resolution.get("quote")]
        if quoted and not any(
            _locate(s.support_text, s.resolution["quote"]) is not None for s in quoted
        ):
            outcome.drop("quote_not_found_in_source")
            continue

        occurred = next(
            (s.resolution.get("occurred_at") for s in sources if s.resolution.get("occurred_at")), None
        )
        outcome.items.append(
            CaseSummaryItem(
                section=item.section,
                statement=item.statement,
                origin=origin,
                subject=subject,
                subject_evidence=subject_evidence,
                is_contradiction=item.is_contradiction,
                occurred_at=occurred,
                sources=[_source_out(s) for s in sources],
            )
        )

    return outcome


def assemble(
    model_summary: ModelCaseSummary, bundle: SourceBundle, outcome: ValidationOutcome
) -> StoredCaseSummary:
    """Group validated items into ordered sections."""
    requested = [s for s in model_summary.section_order if s in set(CANONICAL_ORDER)]
    order = list(dict.fromkeys([*requested, *CANONICAL_ORDER]))

    grouped: dict[SummarySectionKind, list[CaseSummaryItem]] = {}
    for item in outcome.items:
        grouped.setdefault(item.section, []).append(item)

    return StoredCaseSummary(
        sections=[
            CaseSummarySection(kind=kind, items=grouped[kind]) for kind in order if grouped.get(kind)
        ],
        unresolved_notes=list(model_summary.unresolved_notes),
        pending_fact_count=bundle.pending_fact_count,
        truncated=list(bundle.truncated),
    )
