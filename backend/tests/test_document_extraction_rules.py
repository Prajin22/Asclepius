"""Extraction rules that document text exercises: lab values, dates, intervals, allergy lines.

Found while running the Phase 2 extractor over Phase 3 documents. Each case is a
meaning error a doctor would otherwise have been shown.
"""

import pytest

from app import synthetic_documents as sd
from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactSubject
from app.providers.ai import MockAIProvider
from tests.conftest import run_async


def facts(text: str, language: LanguageCode = LanguageCode.EN):
    return run_async(MockAIProvider().extract_medical_information(text, language)).facts


def values(text: str, category: FactCategory | None = None) -> list[str]:
    return [f.value for f in facts(text) if category is None or f.category == category]


def test_lab_values_keep_the_label_the_document_uses():
    got = values("Total cholesterol: 212 mg/dL\nLDL cholesterol: 138 mg/dL", FactCategory.MEASUREMENT)
    assert got == ["total cholesterol 212 mg/dL", "ldl cholesterol 138 mg/dL"]


def test_a_cholesterol_value_is_never_called_blood_sugar():
    assert not any("sugar" in v for v in values("Total cholesterol: 212 mg/dL"))


def test_sugar_statements_still_read_as_blood_sugar():
    """Phase 2 behaviour preserved."""
    assert "blood sugar 210 mg/dL" in values("Sugar was 210 mg/dL last week.", FactCategory.MEASUREMENT)


def test_ocr_spacing_is_tolerated():
    assert "hemoglobin 13.5 g/dL" in values("Hemoglobin:13.5g/dL", FactCategory.MEASUREMENT)


def test_dotted_leader_lab_lines_keep_their_label_and_ignore_reference_ranges():
    got = values("Total cholesterol ........ 212 mg/dL   (ref < 200)\nHDL cholesterol ..........  42 mg/dL", FactCategory.MEASUREMENT)
    assert got == ["total cholesterol 212 mg/dL", "hdl cholesterol 42 mg/dL"]


def test_an_unlabelled_number_is_not_given_a_label():
    assert values("212 mg/dL", FactCategory.MEASUREMENT) == []


@pytest.mark.parametrize("text", ["Report date: 12/05/2026", "Ref 300/20", "Room 12/10"])
def test_dates_and_implausible_pairs_are_not_blood_pressure(text):
    assert values(text, FactCategory.MEASUREMENT) == []


def test_blood_pressure_is_still_read():
    assert values("Blood pressure: 148/94 mmHg", FactCategory.MEASUREMENT) == ["blood pressure 148/94"]


def test_follow_up_intervals_are_not_symptom_durations():
    assert values("Follow up with physician in 4 weeks.", FactCategory.DURATION) == []
    assert values("Cough for 4 weeks.", FactCategory.DURATION) == ["4 weeks"]


def test_document_style_allergy_line():
    assert values("Allergies: Penicillin", FactCategory.ALLERGY) == ["allergy: Penicillin"]


@pytest.mark.parametrize("text", ["Allergies: None", "Allergies: NKDA", "No known drug allergies"])
def test_document_style_no_allergy_line(text):
    got = values(text, FactCategory.ALLERGY)
    assert got and all("no known allergies" in v for v in got)


def test_discharge_summary_keeps_family_history_separate():
    by_value = {f.value: f for f in facts("\n".join(sd.DISCHARGE_SUMMARY[0]))}
    assert by_value["hypertension"].subject == FactSubject.SELF
    assert by_value["diabetes"].subject == FactSubject.FAMILY
    assert any(v.startswith("amlodipine 5 mg") for v in by_value)
    assert not any(f.category == FactCategory.DURATION for f in by_value.values())  # "in 4 weeks"


def test_instructions_inside_a_document_are_treated_as_data():
    got = facts("\n".join(sd.INJECTION_ATTEMPT[0]))
    assert {f.value for f in got} >= {"headache", "2 days"}
    assert not any("tumour" in f.value.lower() or "tumor" in f.value.lower() for f in got)
