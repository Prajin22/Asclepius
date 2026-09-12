"""Evidence validation: a claim without a matching quote is not stored."""

import pytest
from sqlalchemy import select

from app.models import AIExtractedFact
from app.models.enums import FactCategory, FactValidation
from app.providers.ai.base import Evidence, ExtractedFact
from app.services.evidence import canonical, validate_fact
from tests.ai_stubs import FabricatingProvider
from tests.conftest import create_problem, process_record

SOURCE = "I have had a headache for two days. BP was 150/95."


def fact(quote: str, *, category=FactCategory.SYMPTOM, value="headache", start=None, end=None, confidence=None):
    return ExtractedFact(
        category=category,
        value=value,
        evidence=Evidence(quote=quote, start=start, end=end),
        confidence=confidence,
    )


def test_exact_quote_is_validated():
    outcome = validate_fact(fact("headache"), SOURCE)
    assert outcome.status == FactValidation.VALIDATED
    assert SOURCE[outcome.start : outcome.end] == "headache"


@pytest.mark.parametrize("quote", ["  headache ", "HEADACHE", "head​ache", "a  headache   for two days"])
def test_harmless_differences_are_tolerated(quote):
    assert validate_fact(fact(quote), SOURCE).status in (FactValidation.VALIDATED, FactValidation.NEEDS_REVIEW)


def test_quote_absent_from_the_source_is_unsupported():
    assert validate_fact(fact("I inject insulin every night"), SOURCE).status == FactValidation.UNSUPPORTED


def test_empty_evidence_is_unsupported():
    assert validate_fact(fact(""), SOURCE).status == FactValidation.UNSUPPORTED


def test_wrong_offsets_need_review():
    outcome = validate_fact(fact("headache", start=0, end=4), SOURCE)
    assert outcome.status == FactValidation.NEEDS_REVIEW
    assert "offset" in outcome.note


def test_low_confidence_needs_review():
    assert validate_fact(fact("headache", confidence=0.2), SOURCE).status == FactValidation.NEEDS_REVIEW


def test_allergy_absence_requires_an_explicit_statement():
    claimed = fact("headache", category=FactCategory.ALLERGY, value="no known allergies")
    assert validate_fact(claimed, SOURCE).status == FactValidation.UNSUPPORTED

    stated = "I have a headache. I have no known allergies."
    supported = fact("no known allergies", category=FactCategory.ALLERGY, value="no known allergies")
    assert validate_fact(supported, stated).status == FactValidation.VALIDATED


def test_canonical_form_ignores_whitespace_and_case():
    assert canonical("  Head   ACHE\n") == "head ache"


def test_fabricated_facts_are_dropped_by_the_pipeline(client, db, consented_patient, monkeypatch):
    """A provider that invents evidence gets that fact rejected, not stored."""
    provider = FabricatingProvider()
    monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: provider)

    record = create_problem(client, consented_patient, "I have a headache.", "en")
    body = process_record(client, consented_patient, record["id"]).json()

    values = {f["value"] for f in body["facts"]}
    assert "headache" in values
    assert "insulin 10 units" not in values  # evidence was not in the source
    stored = list(db.scalars(select(AIExtractedFact)))
    assert all(f.value != "insulin 10 units" for f in stored)
    assert all(f.validation_status != FactValidation.UNSUPPORTED for f in stored)
