"""Extraction safety: no invention, negation handled, absence stays absence."""

import pytest

from app.core.languages import LanguageCode
from app.models.enums import FactCategory
from app.providers.ai import MockAIProvider
from tests.conftest import run_async


def extract(text: str, language: LanguageCode):
    return run_async(MockAIProvider().extract_medical_information(text, language))


def values(result, category: FactCategory | None = None) -> set[str]:
    return {f.value for f in result.facts if category is None or f.category == category}


@pytest.mark.parametrize(
    ("text", "language", "expected"),
    [
        ("I have had a headache for two days.", LanguageCode.EN, {"headache", "2 days"}),
        ("எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது", LanguageCode.TA, {"headache", "2 days"}),
        ("मुझे दो दिन से सिरदर्द है।", LanguageCode.HI, {"headache", "2 days"}),
    ],
)
def test_supported_facts_are_extracted_in_each_language(text, language, expected):
    assert expected <= values(extract(text, language))


def test_nothing_is_invented_from_a_vague_statement():
    result = extract("I am not feeling well.", LanguageCode.EN)
    assert result.facts == []


def test_absence_of_a_topic_never_becomes_a_fact():
    """The patient said nothing about allergies, so there is no allergy fact."""
    result = extract("I have a headache.", LanguageCode.EN)
    assert values(result, FactCategory.ALLERGY) == set()


def test_explicitly_stated_absence_is_recorded_as_stated():
    result = extract("I have no known allergies.", LanguageCode.EN)
    allergies = values(result, FactCategory.ALLERGY)
    assert allergies and all("no known allergies" in a for a in allergies)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("I have a cough but no fever.", LanguageCode.EN),
        ("எனக்கு காய்ச்சல் இல்லை, ஆனால் இருமல் உள்ளது.", LanguageCode.TA),
        ("खांसी है लेकिन बुखार नहीं है।", LanguageCode.HI),
    ],
)
def test_negated_symptoms_are_not_extracted(text, language):
    result = extract(text, language)
    assert "cough" in values(result)
    assert "fever" not in values(result)


def test_medication_keeps_its_dose():
    result = extract("I take amlodipine 5 mg every morning.", LanguageCode.EN)
    assert any(v.startswith("amlodipine 5 mg") for v in values(result, FactCategory.MEDICATION))


def test_measurements_are_read_as_reported_numbers():
    result = extract("BP was 150/95 yesterday.", LanguageCode.EN)
    assert "blood pressure 150/95" in values(result, FactCategory.MEASUREMENT)


def test_symptoms_never_become_a_diagnosis():
    result = extract("I have fever and cough.", LanguageCode.EN)
    assert values(result) == {"fever", "cough"}
    assert all(f.category != FactCategory.MEDICAL_HISTORY for f in result.facts)
    assert not any("pneumonia" in f.value.lower() for f in result.facts)


def test_every_fact_carries_evidence_from_the_source():
    source = "Fever and cough since 3 days, and I am very tired."
    result = extract(source, LanguageCode.EN)
    assert result.facts
    for fact in result.facts:
        assert fact.evidence.quote
        assert fact.evidence.quote in source
        assert source[fact.evidence.start : fact.evidence.end] == fact.evidence.quote


def test_unparsed_text_is_reported_rather_than_guessed():
    result = extract("எனக்கு ஏதோ ஒரு விசித்திரமான உணர்வு உள்ளது.", LanguageCode.TA)
    assert result.facts == []
    assert result.unparsed  # surfaced as "not understood", not invented
