"""Deterministic case-summary organisation for the local provider (Phase 4).

Same contract as the real providers, same schema, same validation afterwards —
but rule-based, so a demo cannot fail on an outage, a quota or latency, and the
same bundle always produces byte-identical output. `DEMO_MODE` pins the whole
system to this, so the public deployment never calls anyone.

It groups. It does not interpret: every statement is a value, a title or a
label already present in the bundle, and each one cites the item it came from.
Nothing here decides what anything means, and its quality is measured by the
same evaluation harness as any other provider (D-028).
"""

from typing import Any

from app.models.enums import BundleItemKind, FactCategory, SummarySectionKind
from app.services.evidence import canonical

#: Which section a confirmed fact of each category belongs in.
#: Where a health record the patient wrote belongs, by the type they chose.
_RECORD_SECTION: dict[str, str] = {
    "allergy": SummarySectionKind.ALLERGY.value,
    "medication": SummarySectionKind.MEDICATION.value,
    "condition": SummarySectionKind.MEDICAL_HISTORY.value,
    "history_note": SummarySectionKind.MEDICAL_HISTORY.value,
    "family_history": SummarySectionKind.MEDICAL_HISTORY.value,
}

_FACT_SECTION: dict[str, str] = {
    FactCategory.SYMPTOM.value: SummarySectionKind.SYMPTOM.value,
    FactCategory.DURATION.value: SummarySectionKind.DURATION.value,
    FactCategory.MEDICATION.value: SummarySectionKind.MEDICATION.value,
    FactCategory.ALLERGY.value: SummarySectionKind.ALLERGY.value,
    FactCategory.MEDICAL_HISTORY.value: SummarySectionKind.MEDICAL_HISTORY.value,
    FactCategory.MEASUREMENT.value: SummarySectionKind.MEASUREMENT.value,
}

#: The order sections are emitted in. Matches the validator's canonical order,
#: so the two cannot disagree about how a case reads.
_ORDER: tuple[str, ...] = (
    SummarySectionKind.CURRENT_PROBLEM.value,
    SummarySectionKind.PATIENT_STATEMENT.value,
    SummarySectionKind.SYMPTOM.value,
    SummarySectionKind.DURATION.value,
    SummarySectionKind.MEASUREMENT.value,
    SummarySectionKind.MEDICATION.value,
    SummarySectionKind.ALLERGY.value,
    SummarySectionKind.MEDICAL_HISTORY.value,
    SummarySectionKind.DOCUMENT.value,
    SummarySectionKind.PRIOR_CONSULTATION.value,
)

#: Wording that marks a statement as denying something, in the languages the
#: extractor understands. Used only to notice that two sources disagree — never
#: to decide which of them is right.
_DENIAL_CUES = (
    "no medication", "no medicine", "no tablets", "not taking",
    "do not take", "don't take", "dont take", "take no",
    "மருந்து இல்லை", "दवा नहीं",
)

MAX_STATEMENT = 200


def _clip(text: str) -> str:
    text = " ".join((text or "").split())
    return text[:MAX_STATEMENT]


#: Longest patient-supplied label allowed inside a statement. Titles and file
#: names are label fields, not free text, but they are still the patient's words:
#: clipped here so nothing long can be smuggled into a summary line.
MAX_LABEL = 60


def _clip_label(text: str | None) -> str:
    return " ".join((text or "").split())[:MAX_LABEL]


def _label(what: str) -> str:
    """An application-written line naming what kind of source this is.

    Statements are never built from a source's free text. A patient's words, a
    document's contents and a doctor's note reach the reader through the source
    block, labelled as theirs; a statement that copied them would let anything
    written inside one read as the summary's own line — including text shaped
    like an instruction.

    Deliberately carries no date and no language code. The interface shows both
    on the source itself, formatted for the reader's locale — a raw "2026-09-23"
    or "(in ta)" inside a statement is a server string leaking into a screen.
    """
    return what


def _item(section: str, statement: str, refs: list[str], contradiction: bool = False) -> dict[str, Any]:
    return {
        "section": section,
        "statement": _clip(statement),
        "source_refs": refs,
        "is_contradiction": contradiction,
    }


def organise(bundle_payload: dict[str, Any]) -> dict[str, Any]:
    """Group one bundle's items. Pure function of the payload — no I/O, no clock."""
    items = bundle_payload.get("items", []) or []
    out: list[dict[str, Any]] = []
    sections_used: list[str] = []

    def emit(section: str, statement: str, refs: list[str], contradiction: bool = False) -> None:
        if not statement.strip() or not refs:
            return
        out.append(_item(section, statement, refs, contradiction))
        if section not in sections_used:
            sections_used.append(section)

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_kind.setdefault(item.get("kind", ""), []).append(item)

    # 1. Why the patient is here. A label and a date, never the text itself:
    #    free text belongs in the source block, where it is shown as the
    #    patient's own words. Copying it into a statement would let anything
    #    written in it read as the summary's own line (see `_label`).
    for problem in by_kind.get(BundleItemKind.CURRENT_PROBLEM.value, []):
        emit(
            SummarySectionKind.CURRENT_PROBLEM.value,
            _label("Current problem recorded"),
            [problem["ref"]],
        )

    # 2. That they wrote to this doctor, and when. Same rule.
    for statement in by_kind.get(BundleItemKind.PATIENT_STATEMENT.value, []):
        emit(
            SummarySectionKind.PATIENT_STATEMENT.value,
            _label("Message to the doctor"),
            [statement["ref"]],
        )

    # 3. Confirmed facts, de-duplicated within a category so the same symptom
    #    reported twice reads once — but every source it came from is kept.
    facts = by_kind.get(BundleItemKind.FACT.value, [])
    grouped: dict[tuple[str, str, str], list[str]] = {}
    order: list[tuple[str, str, str]] = []
    values: dict[tuple[str, str, str], str] = {}
    for fact in facts:
        section = _FACT_SECTION.get(fact.get("category", ""))
        if section is None:
            continue
        # Attribution is part of a fact's identity: a relative's diabetes and the
        # patient's diabetes are two different facts and must never merge.
        key = (section, fact.get("subject", "self"), canonical(fact.get("value", "")))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
            values[key] = fact.get("value", "")
        grouped[key].append(fact["ref"])
    for key in order:
        emit(key[0], values[key], grouped[key])

    # 4. Documents the patient shared: what kind and when, never read into. The
    #    file name is patient-supplied text, so it stays in the source where the
    #    interface shows it as the patient's own label.
    for doc in by_kind.get(BundleItemKind.DOCUMENT.value, []):
        kind = (doc.get("document_type") or "document").replace("_", " ")
        emit(
            SummarySectionKind.DOCUMENT.value,
            _label(kind[:1].upper() + kind[1:] + " shared"),
            [doc["ref"]],
        )

    # 5. Doctor-authored history. Attributed and dated; the assessment itself is
    #    shown from the source, not restated here as a finding.
    for prior in by_kind.get(BundleItemKind.PRIOR_CONSULTATION.value, []):
        doctor = prior.get("doctor") or "a doctor"
        when = (prior.get("completed_at") or prior.get("created_at") or "")[:10]
        has_note = bool(prior.get("doctor_assessment"))
        label = "Assessment on file" if has_note else "Consultation on record"
        emit(
            SummarySectionKind.PRIOR_CONSULTATION.value,
            f"{label} — {doctor}" + (f", {when}" if when else ""),
            [prior["ref"]],
        )
    for rx in by_kind.get(BundleItemKind.PRIOR_PRESCRIPTION.value, []):
        doctor = rx.get("doctor") or "a doctor"
        names = ", ".join(i.get("medication", "") for i in rx.get("items", []) if i.get("medication"))
        when = (rx.get("issued_at") or "")[:10]
        emit(
            SummarySectionKind.PRIOR_CONSULTATION.value,
            f"Prescription by {doctor}" + (f", {when}" if when else "") + (f": {names}" if names else ""),
            [rx["ref"]],
        )

    # 6. Two doctors prescribed. Say so; never say which one was right.
    prescriptions = by_kind.get(BundleItemKind.PRIOR_PRESCRIPTION.value, [])
    prescribers = {rx.get("doctor") for rx in prescriptions if rx.get("doctor")}
    if len(prescriptions) > 1 and len(prescribers) > 1:
        emit(
            SummarySectionKind.PRIOR_CONSULTATION.value,
            "Prescriptions from more than one doctor are present in the shared records.",
            [rx["ref"] for rx in prescriptions],
            contradiction=True,
        )

    # 7. A source denies something another source reports. Surface the
    #    disagreement with both sides cited, and leave it unresolved.
    denials = [
        item["ref"]
        for item in items
        if item.get("kind")
        in (
            BundleItemKind.CURRENT_PROBLEM.value,
            BundleItemKind.HEALTH_RECORD.value,
            BundleItemKind.PATIENT_STATEMENT.value,
        )
        and any(cue in canonical(f"{item.get('text', '')} {item.get('english') or ''}") for cue in map(canonical, _DENIAL_CUES))
    ]
    medications = [f["ref"] for f in facts if f.get("category") == FactCategory.MEDICATION.value]
    if denials and medications:
        emit(
            SummarySectionKind.MEDICATION.value,
            "Medication information differs across the shared records.",
            [*denials, *medications],
            contradiction=True,
        )

    # 8. Health records that produced no confirmed fact still belong somewhere,
    #    as the patient's own words under history.
    cited = {ref for entry in out for ref in entry["source_refs"]}
    for record in by_kind.get(BundleItemKind.HEALTH_RECORD.value, []):
        if record["ref"] in cited:
            continue
        # The patient's own short label for the record, when they gave one — a
        # title is a label field, not narrative, and it is the patient's direct
        # assertion about their own health. Otherwise say only that a record of
        # this type exists and let the doctor open it.
        record_type = record.get("record_type") or "history_note"
        section = _RECORD_SECTION.get(record_type, SummarySectionKind.MEDICAL_HISTORY.value)
        title = _clip_label(record.get("title"))
        if title:
            emit(section, title, [record["ref"]])
        else:
            kind = record_type.replace("_", " ")
            emit(
                SummarySectionKind.MEDICAL_HISTORY.value,
                _label(kind[:1].upper() + kind[1:] + " recorded"),
                [record["ref"]],
            )

    # Pending items are reported from the structured `pending_fact_count`, which
    # the interface renders in its own words. Repeating it here would say the
    # same thing twice, differently.
    notes: list[str] = []

    return {
        "items": out,
        "section_order": [s for s in _ORDER if s in sections_used],
        "unresolved_notes": notes,
    }
