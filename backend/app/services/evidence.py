"""Evidence validation — the safety gate between an AI claim and stored data.

A fact is only as good as the quote backing it. The provider supplies a
verbatim quote; this module finds it in the authoritative source text and is the
only authority on where it is (D-049). Character offsets reported by a provider
are never used: models quote reliably but count characters badly.

A quote is verbatim when it matches the source character for character, allowing
only layout differences — runs of whitespace, line breaks, zero-width marks. A
quote that matches only when letter case or Unicode character forms are ignored
is kept for review. A quote that cannot be found is not evidence. The quote is
never rewritten to make it match.
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


PROVIDER_POSITION_IGNORED = "provider position ignored; quote located by the application"
NOT_VERBATIM = "quote matches the source only when letter case or character forms are ignored"


@dataclass(frozen=True)
class ValidationOutcome:
    status: FactValidation
    note: str | None = None
    # Where the application found the quote in the source — never the provider's offsets.
    start: int | None = None
    end: int | None = None


def _comparable_with_offsets(source: str, *, fold: bool) -> tuple[str, list[int]]:
    """Comparison form of `source` plus, for each character, its index in the
    original string — so a match can be reported as original offsets.

    Zero-width marks are dropped and whitespace runs collapse to one space.
    With `fold`, letter case and Unicode compatibility forms are ignored too.
    """
    buf: list[str] = []
    mapping: list[int] = []
    previous_space = True
    for index, ch in enumerate(source):
        if ord(ch) in _ZERO_WIDTH:
            continue
        normalised = unicodedata.normalize("NFKC", ch) if fold else ch
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
        for piece in normalised.casefold() if fold else normalised:
            buf.append(piece)
            mapping.append(index)
    while buf and buf[-1] == " ":
        buf.pop()
        mapping.pop()
    return "".join(buf), mapping


def _locate(source: str, quote: str) -> tuple[int, int, bool] | None:
    """Find the quote in the source: exactly, then allowing layout differences,
    then ignoring case and character forms. Returns (start, end, verbatim).

    The first occurrence wins, so the same input always yields the same position.
    """
    if not quote:
        return None
    direct = source.find(quote)
    if direct >= 0:
        return direct, direct + len(quote), True

    for fold in (False, True):
        needle = canonical(quote) if fold else _comparable_with_offsets(quote, fold=False)[0]
        if not needle:
            continue
        haystack, mapping = _comparable_with_offsets(source, fold=fold)
        pos = haystack.find(needle)
        if pos >= 0:
            end_index = min(pos + len(needle) - 1, len(mapping) - 1)
            return mapping[pos], mapping[end_index] + 1, not fold
    return None


def validate_fact(fact: ExtractedFact, source_text: str) -> ValidationOutcome:
    """Check one fact's evidence against the source it claims to come from."""
    quote = (fact.evidence.quote or "").strip()
    if not quote:
        # A position without a quote is not evidence.
        return ValidationOutcome(FactValidation.UNSUPPORTED, "no evidence quote")

    location = _locate(source_text, quote)
    if location is None:
        # The model produced a quote that is not in the source: reject it, whatever position it claims.
        return ValidationOutcome(FactValidation.UNSUPPORTED, "evidence not found in source")
    start, end, verbatim = location

    if fact.category == FactCategory.ALLERGY and _claims_absence(fact.value):
        if not any(cue in canonical(source_text) for cue in map(canonical, _EXPLICIT_ABSENCE_CUES)):
            return ValidationOutcome(
                FactValidation.UNSUPPORTED, "absence of allergy not explicitly stated", start, end
            )

    if not verbatim:
        return ValidationOutcome(FactValidation.NEEDS_REVIEW, NOT_VERBATIM, start, end)

    if fact.confidence is not None and fact.confidence < 0.5:
        return ValidationOutcome(FactValidation.NEEDS_REVIEW, "low provider confidence", start, end)

    claimed = (fact.evidence.start, fact.evidence.end)
    note = PROVIDER_POSITION_IGNORED if claimed != (None, None) and claimed != (start, end) else None
    return ValidationOutcome(FactValidation.VALIDATED, note, start, end)


def _claims_absence(value: str) -> bool:
    v = canonical(value)
    return any(marker in v for marker in ("no known", "none", "no allerg", "not allergic", "denies"))


def validate_all(facts: list[ExtractedFact], source_text: str) -> list[tuple[ExtractedFact, ValidationOutcome]]:
    return [(fact, validate_fact(fact, source_text)) for fact in facts]
