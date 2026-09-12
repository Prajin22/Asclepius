"""The application, not the model, locates evidence (D-049).

A provider supplies a verbatim quote. Where that quote sits in the source is
decided by the validator; character offsets reported by the provider are never
used, never override the located position, and never count as evidence.
"""

import pytest

from app.models.enums import FactCategory, FactValidation
from app.providers.ai import MockAIProvider
from app.providers.ai.base import Evidence, ExtractedFact
from app.services.evidence import NOT_VERBATIM, PROVIDER_POSITION_IGNORED, validate_fact
from tests.conftest import TAMIL_PROBLEM, create_problem, process_record

PAGE = "Demo Diagnostics Laboratory\nComplete Blood Count\nHemoglobin 12.4 g/dL\nPlatelets 250 x10^9/L"
QUOTE = "Hemoglobin 12.4 g/dL"
START = PAGE.index(QUOTE)
END = START + len(QUOTE)


def fact(
    quote: str = QUOTE,
    start: int | None = None,
    end: int | None = None,
    *,
    category: FactCategory = FactCategory.MEASUREMENT,
    value: str = "hemoglobin 12.4 g/dL",
    confidence: float | None = 0.9,
) -> ExtractedFact:
    return ExtractedFact(
        category=category, value=value, evidence=Evidence(quote=quote, start=start, end=end), confidence=confidence
    )


def assert_located(outcome, source: str = PAGE, quote: str = QUOTE) -> None:
    assert outcome.status == FactValidation.VALIDATED
    assert (outcome.start, outcome.end) == (source.index(quote), source.index(quote) + len(quote))
    assert source[outcome.start : outcome.end] == quote


# ---------- valid verbatim quote: accepted, application position used ----------


def test_exact_model_position_is_accepted():
    outcome = validate_fact(fact(start=START, end=END), PAGE)
    assert_located(outcome)
    assert outcome.note is None


def test_no_model_position_is_needed():
    outcome = validate_fact(fact(), PAGE)
    assert_located(outcome)
    assert outcome.note is None


@pytest.mark.parametrize("shift", [1, -1], ids=["plus-1", "minus-1"])
def test_position_shifted_by_one_character(shift):
    outcome = validate_fact(fact(start=START + shift, end=END + shift), PAGE)
    assert_located(outcome)
    assert outcome.note == PROVIDER_POSITION_IGNORED


@pytest.mark.parametrize("shift", [3, -4, 5], ids=["plus-3", "minus-4", "plus-5"])
def test_position_shifted_by_several_characters(shift):
    outcome = validate_fact(fact(start=START + shift, end=END + shift), PAGE)
    assert_located(outcome)
    assert outcome.note == PROVIDER_POSITION_IGNORED


@pytest.mark.parametrize(
    ("start", "end"),
    [(0, 5), (END, START), (900, 921), (-10, -1), (START, None)],
    ids=["start-of-page", "reversed", "past-the-end", "negative", "half-missing"],
)
def test_valid_quote_with_a_completely_wrong_model_position(start, end):
    outcome = validate_fact(fact(start=start, end=end), PAGE)
    assert_located(outcome)
    assert outcome.note == PROVIDER_POSITION_IGNORED


TAMIL = "எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது."
TRANSCRIBED = "Demo Diagnostics Laboratory\nComplete Blood Count\nHemoglobin: 13.5 g/dL\nBlood pressure: 150/95 mmHg"


@pytest.mark.parametrize(
    ("source", "quote", "claimed_start", "claimed_end"),
    [
        (TAMIL, "தலைவலி", 21, 28),
        (TAMIL, "காய்ச்சல்", 36, 45),
        (TAMIL, "இரண்டு நாட்களாக", 8, 23),
        (TRANSCRIBED, "Hemoglobin: 13.5 g/dL", 54, 75),
        (TRANSCRIBED, "Blood pressure: 150/95 mmHg", 76, 103),
    ],
)
def test_quotes_and_offsets_returned_by_a_live_model_now_validate(source, quote, claimed_start, claimed_end):
    """Replays what Anthropic returned in the Phase 3 live smoke test: verbatim quotes, drifted offsets."""
    outcome = validate_fact(fact(quote, claimed_start, claimed_end, confidence=0.95), source)
    assert_located(outcome, source, quote)
    assert (outcome.start, outcome.end) != (claimed_start, claimed_end)


@pytest.mark.parametrize(
    ("quote", "located"),
    [
        ("Complete Blood Count Hemoglobin 12.4 g/dL", "Complete Blood Count\nHemoglobin 12.4 g/dL"),
        ("Hemoglobin  12.4   g/dL", QUOTE),
        ("Hemo​globin 12.4 g/dL", QUOTE),
    ],
    ids=["line-break-as-space", "extra-spaces", "zero-width-mark"],
)
def test_layout_only_differences_are_still_verbatim(quote, located):
    outcome = validate_fact(fact(quote, 0, 3), PAGE)
    assert outcome.status == FactValidation.VALIDATED
    assert PAGE[outcome.start : outcome.end] == located


# ---------- invalid quote: rejected or held for review ----------


@pytest.mark.parametrize(("start", "end"), [(None, None), (START, END)], ids=["no-position", "position-of-real-text"])
def test_quote_not_present_in_the_source_is_rejected(start, end):
    outcome = validate_fact(fact("Hemoglobin 14.1 g/dL", start, end), PAGE)
    assert outcome.status == FactValidation.UNSUPPORTED
    assert (outcome.start, outcome.end) == (None, None)


@pytest.mark.parametrize(
    "quote",
    ["Haemoglobin 12.4 g/dL", "Hemoglobin 12.4 mg/dL", "Hemoglobin 12 g/dL", "Hemoglobin 12.4 g/dL (normal)"],
    ids=["spelling", "unit", "value", "added-words"],
)
def test_modified_quote_is_rejected_and_never_rewritten(quote):
    claimed = fact(quote, START, END)
    outcome = validate_fact(claimed, PAGE)
    assert outcome.status == FactValidation.UNSUPPORTED
    assert claimed.evidence.quote == quote


def test_quote_differing_in_letter_case_needs_review_at_the_application_position():
    outcome = validate_fact(fact("HEMOGLOBIN 12.4 G/DL", START + 2, END + 2), PAGE)
    assert outcome.status == FactValidation.NEEDS_REVIEW
    assert outcome.note == NOT_VERBATIM
    assert (outcome.start, outcome.end) == (START, END)


def test_quote_differing_only_in_character_forms_needs_review():
    """'×109/L' is not what the document says ('×10⁹/L') even though the forms normalise alike."""
    source = "Platelets 250 ×10⁹/L"
    outcome = validate_fact(fact("Platelets 250 ×109/L"), source)
    assert outcome.status == FactValidation.NEEDS_REVIEW
    assert outcome.note == NOT_VERBATIM


def test_a_position_without_a_quote_is_not_evidence():
    assert validate_fact(fact("", START, END), PAGE).status == FactValidation.UNSUPPORTED


def test_an_unstated_absence_of_allergy_is_rejected_whatever_the_position():
    claimed = fact("headache", 5, 9, category=FactCategory.ALLERGY, value="no known allergies")
    assert validate_fact(claimed, "I have a headache.").status == FactValidation.UNSUPPORTED


def test_low_confidence_still_needs_review_at_the_application_position():
    outcome = validate_fact(fact(start=0, end=3, confidence=0.3), PAGE)
    assert outcome.status == FactValidation.NEEDS_REVIEW
    assert (outcome.start, outcome.end) == (START, END)


# ---------- repeated quote: deterministic first occurrence ----------


def test_repeated_quote_resolves_to_its_first_occurrence_every_time():
    source = "Blood pressure: 150/95 mmHg (morning)\nBlood pressure: 150/95 mmHg (evening)"
    quote = "Blood pressure: 150/95 mmHg"
    second = source.rindex(quote)
    outcomes = {
        (o.status, o.start, o.end)
        for o in (validate_fact(fact(quote, second, second + len(quote)), source) for _ in range(3))
    }
    assert outcomes == {(FactValidation.VALIDATED, 0, len(quote))}


# ---------- through the pipeline ----------


class DriftingProvider(MockAIProvider):
    """Quotes verbatim but reports offsets that are off, as a live model did."""

    def __init__(self, shift: int | None):
        super().__init__()
        self.shift = shift

    async def extract_medical_information(self, text, language):
        result = await super().extract_medical_information(text, language)
        for claimed in result.facts:
            if self.shift is None:  # completely wrong: every fact claims the start of the text
                claimed.evidence.start, claimed.evidence.end = 0, len(claimed.evidence.quote)
            else:
                claimed.evidence.start += self.shift
                claimed.evidence.end += self.shift
        return result


@pytest.mark.parametrize("shift", [1, 4, None], ids=["off-by-1", "off-by-4", "completely-wrong"])
def test_record_facts_store_the_application_position(client, consented_patient, monkeypatch, shift):
    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: DriftingProvider(shift))
    record = create_problem(client, consented_patient, TAMIL_PROBLEM, "ta")

    body = process_record(client, consented_patient, record["id"]).json()

    assert body["facts"]
    for stored in body["facts"]:
        assert stored["validation_status"] == "validated"
        assert record["content"][stored["evidence_start"] : stored["evidence_end"]] == stored["evidence_quote"]
        assert stored["evidence_document_id"] is None and stored["evidence_page_number"] is None
