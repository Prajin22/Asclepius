"""Evidence validation — the safety gate between an AI claim and stored data.

A fact is only as good as the quote backing it. This module checks that the
quote really occurs in the original source, tolerating harmless differences
(whitespace, case, Unicode normalisation form, zero-width marks) and nothing
else. Anything unverifiable is marked, never silently accepted.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.models.enums import FactCategory, FactValidation
from app.providers.ai.base import ExtractedFact

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿"))
_WS = re.compile(r"\s+")

# An "absence" claim must be explicitly stated by the patient, in any of the
# demonstrated languages, or it is not a fact at all (AI_POLICY rule 2).
_EXPLICIT_ABSENCE_CUES = (
    "no known",
    "no allerg",
    "not allergic",
    "none",
    "no drug allerg",
    "ஒவ்வாமை இல்லை",
    "இல்லை",
    "एलर्जी नहीं",
    "नहीं है",
    "कोई एलर्जी नहीं",
)


def canonical(text: str) -> str:
    """Comparison form: NFKC, no zero-width, collapsed whitespace, casefolded."""
    text = unicodedata.normalize("NFKC", text or "").translate(_ZERO_WIDTH)
    return _WS.sub(" ", text).strip().casefold()


@dataclass(frozen=True)
class ValidationOutcome:
    status: FactValidation
    note: str | None = None
    start: int | None = None
    end: int | None = None


def _canonical_with_offsets(source: str) -> tuple[str, list[int]]:
    """Canonical form of `source` plus, for each canonical character, its index
    in the original string — so a match can be reported as original offsets."""
    buf: list[str] = []
    mapping: list[int] = []
    previous_space = True
    for index, ch in enumerate(source):
        if ord(ch) in _ZERO_WIDTH:
            continue
        normalised = unicodedata.normalize("NFKC", ch)
        if not normalised:
            continue
        if normalised.isspace():
            if previous_space:
                continue
            buf.append(" ")
            mapping.append(index)
            previous_space = True
            continue
        previous_space = False
        for piece in normalised.casefold():
            buf.append(piece)
            mapping.append(index)
    while buf and buf[-1] == " ":
        buf.pop()
        mapping.pop()
    return "".join(buf), mapping


def _locate(source: str, quote: str) -> tuple[int, int] | None:
    """Find the quote in the source, first exactly then in canonical form."""
    if not quote:
        return None
    direct = source.find(quote)
    if direct >= 0:
        return direct, direct + len(quote)

    canon_quote = canonical(quote)
    if not canon_quote:
        return None
    canon_source, mapping = _canonical_with_offsets(source)
    pos = canon_source.find(canon_quote)
    if pos < 0:
        return None
    start = mapping[pos]
    end_index = min(pos + len(canon_quote) - 1, len(mapping) - 1)
    return start, mapping[end_index] + 1


def validate_fact(fact: ExtractedFact, source_text: str) -> ValidationOutcome:
    """Check one fact's evidence against the source it claims to come from."""
    quote = (fact.evidence.quote or "").strip()
    if not quote:
        return ValidationOutcome(FactValidation.UNSUPPORTED, "no evidence quote")

    location = _locate(source_text, quote)
    if location is None:
        # The model produced a quote that is not in the source: reject it.
        return ValidationOutcome(FactValidation.UNSUPPORTED, "evidence not found in source")

    start, end = location
    if fact.evidence.start is not None and fact.evidence.end is not None:
        claimed = source_text[fact.evidence.start : fact.evidence.end]
        if canonical(claimed) != canonical(quote):
            return ValidationOutcome(FactValidation.NEEDS_REVIEW, "evidence offsets do not match", start, end)

    if fact.category == FactCategory.ALLERGY and _claims_absence(fact.value):
        if not any(cue in canonical(source_text) for cue in map(canonical, _EXPLICIT_ABSENCE_CUES)):
            return ValidationOutcome(
                FactValidation.UNSUPPORTED, "absence of allergy not explicitly stated", start, end
            )

    if fact.confidence is not None and fact.confidence < 0.5:
        return ValidationOutcome(FactValidation.NEEDS_REVIEW, "low provider confidence", start, end)

    return ValidationOutcome(FactValidation.VALIDATED, None, start, end)


def _claims_absence(value: str) -> bool:
    v = canonical(value)
    return any(marker in v for marker in ("no known", "none", "no allerg", "not allergic", "denies"))


def validate_all(facts: list[ExtractedFact], source_text: str) -> list[tuple[ExtractedFact, ValidationOutcome]]:
    return [(fact, validate_fact(fact, source_text)) for fact in facts]
