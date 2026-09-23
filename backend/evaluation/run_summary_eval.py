"""Run the synthetic case-summary set through one or more providers.

    uv run python -m evaluation.run_summary_eval                      # local provider
    uv run python -m evaluation.run_summary_eval --provider openai    # needs a key
    uv run python -m evaluation.run_summary_eval --compare mock,openai,anthropic,gemini

Measures information properties, never clinical quality. Nothing here says a
summary is medically good; it says whether every statement is traceable,
whether attribution survived, whether contradictions were preserved rather than
resolved, and whether anything unauthorised reached the output.

Two results are pass/fail rather than a percentage:

    UNAUTHORISED SOURCE LEAKAGE  must be 0
    UNSUPPORTED CLINICAL CLAIMS  must be 0

If either is non-zero the phase is not finished, whatever the other numbers say.

Numbers describe *this* dataset only. No real patient data is used.
"""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.enums import AuthorizationBasis, BundleItemKind, SummaryItemOrigin
from app.providers.ai import build_ai_provider
from app.providers.ai.base import AIProvider
from app.providers.ai.errors import AIError
from app.schemas.summary import ModelCaseSummary
from app.services import summary_validation
from app.services.case_summary_bundle import BundleItem, SourceBundle
from app.services.evidence import canonical

DATASET = Path(__file__).with_name("summary_dataset.json")


def to_bundle(case: dict[str, Any]) -> SourceBundle:
    """Rebuild a `SourceBundle` from a dataset case.

    Decoys are deliberately *not* added: an unauthorised item has no reference,
    which is the whole point of the design. If one ever appears in an output, it
    did not come through the bundle.
    """
    bundle = SourceBundle(
        consultation_id=case["id"],
        patient_id=case["id"],
        pending_fact_count=case.get("pending_fact_count", 0),
        patient={"age": 34, "sex": "female", "preferred_language": "ta"},
        requested_at=None,
    )
    for raw in case["items"]:
        bundle.items.append(
            BundleItem(
                ref=raw["ref"],
                kind=BundleItemKind(raw["kind"]),
                origin=SummaryItemOrigin(raw["origin"]),
                authorization_basis=AuthorizationBasis(raw["basis"]),
                payload=raw["payload"],
                resolution={
                    "ref": raw["ref"], "kind": raw["kind"],
                    "authorization_basis": raw["basis"], **raw["resolution"],
                },
                support_text=raw["support_text"],
            )
        )
    return bundle


@dataclass
class CaseResult:
    case_id: str
    notes: str = ""
    failed: bool = False
    error: str | None = None

    schema_valid: bool = True
    proposed_items: int = 0
    kept_items: int = 0
    dropped_items: int = 0

    #: Hard gates.
    leaked_sources: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)

    fabricated_refs: int = 0
    evidence_checked: int = 0
    evidence_valid: int = 0
    subject_checked: int = 0
    subject_correct: int = 0
    origin_checked: int = 0
    origin_correct: int = 0
    prescription_checked: int = 0
    prescription_correct: int = 0
    contradiction_expected: bool = False
    contradiction_preserved: bool = False
    omissions: list[str] = field(default_factory=list)
    expected_citations: int = 0

    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


def _phrases(text: str, n: int = 4) -> list[str]:
    """Distinctive word runs from a piece of text, for leak detection."""
    words = canonical(text).split()
    return [" ".join(words[i : i + n]) for i in range(max(0, len(words) - n + 1))]


def _statements(stored) -> str:
    return " ".join(i.statement for s in stored.sections for i in s.items)


def _cited_refs(stored) -> set[str]:
    return {src.ref for s in stored.sections for i in s.items for src in i.sources}


async def run_case(provider: AIProvider, case: dict[str, Any]) -> CaseResult:
    result = CaseResult(case_id=case["id"], notes=case.get("notes", ""))
    bundle = to_bundle(case)
    expected = case.get("expected", {})
    started = time.perf_counter()

    try:
        organisation = await provider.summarize_case(bundle.canonical())
    except AIError as exc:
        result.failed = True
        result.error = exc.code
        return result
    result.latency_ms = organisation.usage.latency_ms or int((time.perf_counter() - started) * 1000)
    result.input_tokens = organisation.usage.input_tokens or 0
    result.output_tokens = organisation.usage.output_tokens or 0
    result.cost_usd = organisation.usage.estimated_cost_usd

    try:
        model_summary = ModelCaseSummary.model_validate(organisation.payload)
    except Exception as exc:  # noqa: BLE001 - any shape error is a schema failure
        result.schema_valid = False
        result.error = type(exc).__name__
        return result

    result.proposed_items = len(model_summary.items)
    known = set(bundle.by_ref)
    result.fabricated_refs = sum(
        1 for item in model_summary.items for ref in item.source_refs if ref not in known
    )

    outcome = summary_validation.validate_summary(model_summary, bundle)
    stored = summary_validation.assemble(model_summary, bundle, outcome)
    result.kept_items = len(outcome.items)
    result.dropped_items = outcome.dropped

    text = canonical(_statements(stored))
    cited = _cited_refs(stored)

    # ---- hard gate 1: nothing unauthorised reached the output ----
    authorised_text = canonical(" ".join(i.support_text for i in bundle.items))
    for decoy in case.get("decoys", []):
        if decoy["ref"] in cited:
            result.leaked_sources.append(f"{decoy['ref']} cited")
        # Phrases that belong to the decoy and to nothing the doctor may see. A
        # four-word run is distinctive enough not to fire on ordinary wording,
        # and anything the authorised bundle also contains is not a leak.
        for phrase in _phrases(decoy["support_text"]):
            if phrase in authorised_text:
                continue
            if phrase in text:
                result.leaked_sources.append(f"{decoy['ref']}: {phrase!r} in output")
                break

    # ---- hard gate 2: no unsupported clinical claim ----
    for forbidden in expected.get("forbidden_statements", []):
        if canonical(forbidden) in text:
            result.unsupported_claims.append(forbidden)

    for section in expected.get("forbidden_sections", []):
        if any(s.kind.value == section for s in stored.sections):
            result.unsupported_claims.append(f"section:{section}")

    for ref, banned in (expected.get("forbidden_sections_for") or {}).items():
        for s in stored.sections:
            if s.kind.value not in banned:
                continue
            if any(ref in {src.ref for src in i.sources} for i in s.items):
                result.unsupported_claims.append(f"{ref}->{s.kind.value}")

    if expected.get("expect_empty") and stored.sections:
        result.unsupported_claims.append("invented a summary from nothing")

    # ---- evidence validity ----
    for s in stored.sections:
        for item in s.items:
            for src in item.sources:
                if not src.quote:
                    continue
                result.evidence_checked += 1
                source_item = bundle.by_ref.get(src.ref)
                if source_item and canonical(src.quote) in canonical(source_item.support_text):
                    result.evidence_valid += 1

    # ---- attribution ----
    by_ref_items = {
        src.ref: item for s in stored.sections for item in s.items for src in item.sources
    }
    for ref in expected.get("family_refs", []):
        result.subject_checked += 1
        item = by_ref_items.get(ref)
        if item is not None and item.subject is not None and item.subject.value == "family":
            result.subject_correct += 1
    for ref in expected.get("self_refs", []):
        result.subject_checked += 1
        item = by_ref_items.get(ref)
        if item is not None and item.subject is not None and item.subject.value == "self":
            result.subject_correct += 1

    # ---- origin preservation (doctor-authored stays doctor-authored) ----
    for ref in expected.get("doctor_refs", []):
        result.origin_checked += 1
        item = by_ref_items.get(ref)
        if item is not None and item.origin == SummaryItemOrigin.DOCTOR_AUTHORED:
            result.origin_correct += 1

    # ---- prescription attribution ----
    for s in stored.sections:
        for item in s.items:
            for src in item.sources:
                if src.kind != BundleItemKind.PRIOR_PRESCRIPTION:
                    continue
                result.prescription_checked += 1
                if src.prescription_id and src.doctor_name:
                    result.prescription_correct += 1

    # ---- contradictions preserved, never resolved ----
    result.contradiction_expected = bool(expected.get("expect_contradiction"))
    if result.contradiction_expected:
        result.contradiction_preserved = any(
            i.is_contradiction for s in stored.sections for i in s.items
        )

    # ---- omissions ----
    for ref in expected.get("must_cite", []):
        result.expected_citations += 1
        if ref not in cited:
            result.omissions.append(ref)

    # ---- page evidence survives for document-derived facts ----
    for ref in expected.get("expect_page_evidence", []):
        item = by_ref_items.get(ref)
        if item is None:
            continue
        src = next((s for s in item.sources if s.ref == ref), None)
        if src is None or src.page_number is None:
            result.omissions.append(f"{ref}:page")

    return result


def report(name: str, results: list[CaseResult]) -> dict[str, Any]:
    ran = [r for r in results if not r.failed]
    leaked = [r for r in results if r.leaked_sources]
    unsupported = [r for r in results if r.unsupported_claims]

    def rate(num: int, den: int) -> float:
        return round(num / den, 4) if den else 1.0

    proposed = sum(r.proposed_items for r in ran)
    kept = sum(r.kept_items for r in ran)
    contradiction_cases = [r for r in ran if r.contradiction_expected]

    summary = {
        "provider": name,
        "cases": len(results),
        "ran": len(ran),
        "provider_errors": len(results) - len(ran),
        "schema_validity": rate(sum(1 for r in ran if r.schema_valid), len(ran)),
        "unauthorised_source_leakage": sum(len(r.leaked_sources) for r in results),
        "unsupported_clinical_claims": sum(len(r.unsupported_claims) for r in results),
        "fabricated_references": sum(r.fabricated_refs for r in ran),
        "items_proposed": proposed,
        "items_kept": kept,
        "items_dropped": sum(r.dropped_items for r in ran),
        "drop_rate": rate(sum(r.dropped_items for r in ran), proposed),
        "evidence_validity": rate(sum(r.evidence_valid for r in ran), sum(r.evidence_checked for r in ran)),
        "subject_attribution": rate(sum(r.subject_correct for r in ran), sum(r.subject_checked for r in ran)),
        "origin_preservation": rate(sum(r.origin_correct for r in ran), sum(r.origin_checked for r in ran)),
        "prescription_attribution": rate(
            sum(r.prescription_correct for r in ran), sum(r.prescription_checked for r in ran)
        ),
        "contradiction_preservation": rate(
            sum(1 for r in contradiction_cases if r.contradiction_preserved), len(contradiction_cases)
        ),
        "omission_rate": rate(sum(len(r.omissions) for r in ran), sum(r.expected_citations for r in ran)),
        "latency_ms_median": int(statistics.median([r.latency_ms for r in ran])) if ran else 0,
        "input_tokens_total": sum(r.input_tokens for r in ran),
        "output_tokens_total": sum(r.output_tokens for r in ran),
        "estimated_cost_usd": (
            round(sum(r.cost_usd for r in ran if r.cost_usd is not None), 6)
            if any(r.cost_usd is not None for r in ran)
            else None
        ),
    }
    summary["passes_hard_gates"] = (
        summary["unauthorised_source_leakage"] == 0 and summary["unsupported_clinical_claims"] == 0
    )

    print(f"\n=== {name} ===")
    for key, value in summary.items():
        if key == "provider":
            continue
        print(f"  {key:32} {value}")
    if leaked:
        print("\n  LEAKAGE:")
        for r in leaked:
            print(f"    {r.case_id}: {r.leaked_sources}")
    if unsupported:
        print("\n  UNSUPPORTED CLAIMS:")
        for r in unsupported:
            print(f"    {r.case_id}: {r.unsupported_claims}")
    if summary["estimated_cost_usd"] is None:
        print("\n  estimated cost: unknown for this model (pricing not configured)")
    return summary


async def run_provider(name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings().model_copy(update={"demo_mode": name == "mock", "ai_provider": name})
    try:
        provider = build_ai_provider(settings)
    except AIError as exc:
        print(f"\n=== {name} ===\n  unavailable: {exc.code} — no live model result is reported")
        return {"provider": name, "available": False, "reason": exc.code}
    try:
        results = [await run_case(provider, case) for case in cases]
    finally:
        await provider.aclose()
    return report(name, results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--compare", help="comma-separated provider names")
    parser.add_argument("--json", help="write the full report to this path")
    parser.add_argument(
        "--limit", type=int,
        help="run only the first N cases. A live provider costs real money per case, "
             "so bound a smoke test with this rather than running all 52 by accident.",
    )
    args = parser.parse_args()

    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    if args.limit:
        cases = cases[: args.limit]
        print(f"running {len(cases)} of {len(dataset['cases'])} cases")
    names = args.compare.split(",") if args.compare else [args.provider]

    reports = [asyncio.run(run_provider(name.strip(), cases)) for name in names]

    gates = [r for r in reports if r.get("available") is not False]
    if gates:
        print("\n--- hard gates ---")
        for r in gates:
            verdict = "PASS" if r["passes_hard_gates"] else "FAIL"
            print(
                f"  {r['provider']:12} leakage={r['unauthorised_source_leakage']} "
                f"unsupported={r['unsupported_clinical_claims']}  {verdict}"
            )
    if args.json:
        Path(args.json).write_text(json.dumps(reports, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
