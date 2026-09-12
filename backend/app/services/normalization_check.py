"""Guard against English normalisation silently changing medical meaning.

The three layers — original text, normalised English, structured facts — must
say the same thing. This service compares them and reports drift:

* **added**  a medical term appears in the English that nothing in the source
  supports (the normaliser invented or "clarified" something);
* **dropped** an extracted fact is missing from the English (the normaliser
  lost information the extractor found);
* **subject drift** a relative's condition was rendered as the patient's.

It is a signal, not a gate: the result is stored with the artifacts and shown
to both patient and doctor, so a human can see exactly where the layers
disagree. It cannot prove a translation is correct — only that these specific
kinds of drift are absent.
"""

from dataclasses import dataclass, field

from app.models.enums import FactCategory, FactSubject
from app.providers.ai.base import ExtractedFact
from app.providers.ai.lexicon import CONDITIONS, MEDICATIONS, SYMPTOMS
from app.services.evidence import canonical

# Categories whose values should be visible in the English rendering.
_CONTENT_CATEGORIES = (
    FactCategory.SYMPTOM,
    FactCategory.MEDICATION,
    FactCategory.MEDICAL_HISTORY,
    FactCategory.ALLERGY,
)

# English canonical value -> every surface form in every language.
_CONCEPTS = {
    concept.value: tuple(form for _lang, form in concept.all_forms())
    for concept in (*SYMPTOMS, *MEDICATIONS, *CONDITIONS)
}

_FAMILY_MARKERS = ("family", "father", "mother", "brother", "sister", "relative", "parent")


@dataclass
class NormalizationCheck:
    status: str = "ok"  # "ok" | "review"
    added_terms: list[str] = field(default_factory=list)
    dropped_facts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "added_terms": self.added_terms,
            "dropped_facts": self.dropped_facts,
            "notes": self.notes,
        }


def check_normalization(
    source_text: str, normalized_english: str | None, facts: list[ExtractedFact]
) -> NormalizationCheck:
    check = NormalizationCheck()
    if not normalized_english:
        return check

    english = canonical(normalized_english)
    source = canonical(source_text)
    fact_values = {canonical(f.value) for f in facts}

    # 1. Terms the English asserts that the source does not support.
    for concept, surface_forms in _CONCEPTS.items():
        term = canonical(concept)
        if term not in english:
            continue
        supported_by_fact = any(term in value or value in term for value in fact_values)
        supported_by_source = any(canonical(form) in source for form in surface_forms)
        if not supported_by_fact and not supported_by_source:
            check.added_terms.append(concept)

    # 2. Facts the English dropped.
    for fact in facts:
        if fact.category not in _CONTENT_CATEGORIES:
            continue
        value = canonical(fact.value)
        # Compare on the concept word, not the whole phrase ("allergy: penicillin").
        core = value.split(":")[-1].strip()
        if core and core not in english:
            check.dropped_facts.append(fact.value)

    # 3. Attribution drift: a relative's fact must stay attributed in the English.
    family_facts = [f for f in facts if f.subject == FactSubject.FAMILY]
    if family_facts and not any(marker in english for marker in _FAMILY_MARKERS):
        check.notes.append("attribution_lost")

    if check.added_terms or check.dropped_facts or check.notes:
        check.status = "review"
    return check
