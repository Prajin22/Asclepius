"""Phase 4: the evaluation harness itself must be able to fail.

A metric that reads 1.0 is only worth something if it can read less. These tests
feed the harness providers that deliberately misbehave and assert the hard gates
trip — so a clean evaluation report means the providers behaved, not that the
harness was looking the other way.
"""

import json
from pathlib import Path

import pytest

from app.providers.ai.base import AIUsage, SummaryOrganisation
from evaluation.run_summary_eval import run_case, report, to_bundle
from tests.conftest import run_async

DATASET = Path(__file__).resolve().parents[1] / "evaluation" / "summary_dataset.json"


def _cases() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))["cases"]


def _case(case_id: str) -> dict:
    return next(c for c in _cases() if c["id"] == case_id)


class _Provider:
    """Returns a fixed organisation, whatever the bundle says."""

    name = "adversarial"
    model = "adversarial-1"
    is_external = False

    def __init__(self, payload):
        self._payload = payload

    async def summarize_case(self, bundle_text: str) -> SummaryOrganisation:
        payload = self._payload(json.loads(bundle_text)) if callable(self._payload) else self._payload
        return SummaryOrganisation(
            provider=self.name, model=self.model, prompt_version="adversarial",
            payload=payload, usage=AIUsage(latency_ms=1),
        )

    async def aclose(self) -> None:
        return None


def _item(section, statement, refs, contradiction=False):
    return {"section": section, "statement": statement, "source_refs": refs,
            "is_contradiction": contradiction}


def _organisation(items):
    return {"items": items, "section_order": [], "unresolved_notes": []}


# ---------- the dataset itself ----------


def test_the_dataset_covers_what_the_brief_asks_for():
    cases = _cases()
    assert len(cases) >= 50

    kinds = {i["kind"] for c in cases for i in c["items"]}
    assert kinds >= {
        "current_problem", "health_record", "fact", "document",
        "prior_consultation", "prior_prescription", "patient_statement",
    }

    languages = {i["payload"].get("language") for c in cases for i in c["items"]}
    assert {"en", "hi", "ta"} <= languages

    assert any(c["decoys"] for c in cases), "no unauthorised decoys to measure leakage against"
    assert sum(1 for c in cases if c["id"].startswith("injection")) >= 5
    assert any(c["expected"].get("expect_contradiction") for c in cases)
    assert any(i["payload"].get("subject") == "family" for c in cases for i in c["items"])
    assert any(c["expected"].get("expect_empty") for c in cases)


# ---------- the gates trip ----------


def test_the_harness_detects_an_unsupported_clinical_claim():
    case = _case("injection-45-patient-text")
    provider = _Provider(
        lambda bundle: _organisation(
            [_item("current_problem", "Patient has cancer and needs chemotherapy", ["S1"])]
        )
    )
    result = run_async(run_case(provider, case))
    assert result.unsupported_claims, "a forbidden claim slipped past the harness"
    assert report("adversarial", [result])["passes_hard_gates"] is False


def test_the_harness_detects_leaked_unauthorised_content():
    """Content that was never in the bundle, attached to a citation that is.

    The item cites a real confirmed fact, so reference resolution and the
    structured-source rule both pass and it reaches the stored summary. Only the
    leak detector can catch it — which is the point of measuring leakage
    separately from validation.
    """
    case = _case("leakage-51-unshared")
    decoy_text = case["decoys"][0]["support_text"]
    provider = _Provider(
        lambda bundle: _organisation([_item("symptom", "Patient is being treated for depression", ["S2"])])
    )
    result = run_async(run_case(provider, case))

    assert result.kept_items == 1, "the leak must survive validation for this test to mean anything"
    assert result.leaked_sources, "leaked decoy text was not detected"
    assert "depression" in decoy_text
    assert report("adversarial", [result])["passes_hard_gates"] is False


def test_the_harness_detects_an_invented_summary_from_nothing():
    case = _case("missing-41-identity-only")
    provider = _Provider(_organisation([_item("symptom", "headache", ["S1"])]))
    result = run_async(run_case(provider, case))
    # The bundle is empty, so S1 does not resolve and the item is dropped —
    # and the case expected nothing at all, which is separately asserted.
    assert result.kept_items == 0


def test_the_harness_detects_lost_family_attribution():
    case = _case("family-07")
    provider = _Provider(
        lambda bundle: _organisation([_item("medical_history", "diabetes", ["S2"])])
    )
    result = run_async(run_case(provider, case))
    # S3 (the relative's fact) was never cited, so attribution could not survive.
    assert result.subject_correct < result.subject_checked
    assert "S3" in result.omissions


def test_the_harness_detects_a_resolved_contradiction():
    case = _case("contradiction-20-two-doctors")
    provider = _Provider(
        lambda bundle: _organisation(
            [_item("prior_consultation", "Omeprazole was the correct choice", ["S2"])]
        )
    )
    result = run_async(run_case(provider, case))
    assert result.contradiction_expected
    assert result.contradiction_preserved is False
    assert result.unsupported_claims  # "correct" is a forbidden statement here


def test_the_harness_detects_doctor_authored_recast_as_a_patient_claim():
    case = _case("doctor-25")
    provider = _Provider(
        lambda bundle: _organisation([_item("symptom", "follow-up advised", ["S2"])])
    )
    result = run_async(run_case(provider, case))
    # Dropped by the validator, so the doctor's words never became a symptom.
    assert result.kept_items == 0
    assert result.dropped_items == 1


def test_the_harness_detects_a_fabricated_reference():
    case = _case("base-01-confirmed")
    provider = _Provider(_organisation([_item("symptom", "headache", ["S77"])]))
    result = run_async(run_case(provider, case))
    assert result.fabricated_refs == 1
    assert result.kept_items == 0


@pytest.mark.parametrize("bad", [{"items": [{"section": "diagnosis"}]}, {"nope": 1}])
def test_the_harness_detects_invalid_schema(bad):
    result = run_async(run_case(_Provider(bad), _case("base-01-confirmed")))
    assert result.schema_valid is False
    assert report("adversarial", [result])["schema_validity"] == 0.0
