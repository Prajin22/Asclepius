"""Run the synthetic evaluation set through one or more AI providers.

    uv run python -m evaluation.run_eval                       # mock provider
    uv run python -m evaluation.run_eval --provider anthropic  # needs a key
    uv run python -m evaluation.run_eval --compare mock,openai,anthropic,gemini

Reports language accuracy, per-category precision/recall/F1, evidence validity,
unsupported-fact rate, normalisation keyword coverage, latency and estimated
cost. Numbers describe *this* dataset only — never quote them as clinical
accuracy. No real patient data is used.
"""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactSubject, FactValidation
from app.providers.ai import build_ai_provider
from app.providers.ai.base import AIProvider
from app.providers.ai.errors import AIError
from app.services.evidence import canonical, validate_fact

DATASET = Path(__file__).with_name("dataset.json")
CATEGORIES = [c.value for c in FactCategory]


def matches(expected: str, predicted: str) -> bool:
    """Substring-tolerant match: 'penicillin' matches 'allergy: penicillin'."""
    e, p = canonical(expected), canonical(predicted)
    return bool(e) and (e in p or p in e)


@dataclass
class CaseResult:
    case_id: str
    language_expected: str | None
    language_predicted: str | None
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    per_category: dict[str, dict[str, int]] = field(default_factory=dict)
    evidence_checked: int = 0
    evidence_valid: int = 0
    unsupported_facts: int = 0
    predicted_facts: int = 0
    family_tp: int = 0
    family_fp: int = 0
    family_fn: int = 0
    keyword_hits: int = 0
    keyword_total: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    failed: bool = False
    error: str | None = None
    notes: str = ""


async def run_case(provider: AIProvider, case: dict[str, Any]) -> CaseResult:
    source = case["source"]
    expected = case["expected"]
    result = CaseResult(
        case_id=case["id"],
        language_expected=expected.get("language"),
        language_predicted=None,
        notes=case.get("notes", ""),
    )
    started = time.perf_counter()
    try:
        detection = await provider.detect_language(source)
        language = detection.language or LanguageCode(case["input_language"])
        normalization = await provider.normalize_to_english(source, language)
        extraction = await provider.extract_medical_information(source, language)
    except AIError as exc:
        result.failed = True
        result.error = exc.code
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    result.latency_ms = int((time.perf_counter() - started) * 1000)
    result.language_predicted = detection.language.value if detection.language else None
    for res in (detection, normalization, extraction):
        result.cost_usd += res.usage.estimated_cost_usd or 0.0

    # --- extraction quality, per category ---
    # Only facts about the patient count towards their record; a relative's
    # condition is scored separately as family attribution.
    predicted_by_category: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    predicted_family: list[str] = []
    for fact in extraction.facts:
        if fact.subject == FactSubject.FAMILY:
            predicted_family.append(fact.value)
        elif fact.subject == FactSubject.SELF:
            predicted_by_category[fact.category.value].append(fact.value)
    result.predicted_facts = len(extraction.facts)

    expected_family = list(expected.get("family", []) or [])
    remaining_family = expected_family.copy()
    for value in predicted_family:
        hit = next((g for g in remaining_family if matches(g, value)), None)
        if hit is None:
            result.family_fp += 1
        else:
            remaining_family.remove(hit)
            result.family_tp += 1
    result.family_fn = len(remaining_family)

    for category in CATEGORIES:
        gold = list(expected.get(category, []) or [])
        predicted = list(predicted_by_category[category])
        tp = 0
        unmatched_pred = []
        remaining_gold = gold.copy()
        for value in predicted:
            hit = next((g for g in remaining_gold if matches(g, value)), None)
            if hit is None:
                unmatched_pred.append(value)
            else:
                remaining_gold.remove(hit)
                tp += 1
        fp, fn = len(unmatched_pred), len(remaining_gold)
        result.per_category[category] = {"tp": tp, "fp": fp, "fn": fn}
        result.true_positives += tp
        result.false_positives += fp
        result.false_negatives += fn

    # --- evidence validity (does the quote exist in the source?) ---
    for fact in extraction.facts:
        result.evidence_checked += 1
        outcome = validate_fact(fact, source)
        if outcome.status == FactValidation.VALIDATED:
            result.evidence_valid += 1
        elif outcome.status == FactValidation.UNSUPPORTED:
            result.unsupported_facts += 1

    # --- normalisation coverage ---
    keywords = case.get("expected_keywords", [])
    normalized = canonical(normalization.normalized_text_en)
    result.keyword_total = len(keywords)
    result.keyword_hits = sum(1 for k in keywords if canonical(k) in normalized)
    return result


def aggregate(results: list[CaseResult]) -> dict[str, Any]:
    def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}

    ok = [r for r in results if not r.failed]
    language_scored = [r for r in ok if r.language_expected is not None or r.language_predicted is not None]
    language_correct = sum(1 for r in language_scored if r.language_expected == r.language_predicted)

    totals = {"tp": 0, "fp": 0, "fn": 0}
    per_category: dict[str, dict[str, int]] = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES}
    for r in ok:
        totals["tp"] += r.true_positives
        totals["fp"] += r.false_positives
        totals["fn"] += r.false_negatives
        for category, counts in r.per_category.items():
            for key in ("tp", "fp", "fn"):
                per_category[category][key] += counts[key]

    evidence_checked = sum(r.evidence_checked for r in ok)
    evidence_valid = sum(r.evidence_valid for r in ok)
    unsupported = sum(r.unsupported_facts for r in ok)
    predicted = sum(r.predicted_facts for r in ok)
    keyword_total = sum(r.keyword_total for r in ok)
    keyword_hits = sum(r.keyword_hits for r in ok)
    latencies = sorted(r.latency_ms for r in ok) or [0]

    return {
        "cases": len(results),
        "failures": sum(1 for r in results if r.failed),
        "failure_rate": round(sum(1 for r in results if r.failed) / max(1, len(results)), 3),
        "language_accuracy": round(language_correct / max(1, len(language_scored)), 3),
        "extraction_overall": prf(totals["tp"], totals["fp"], totals["fn"]),
        "extraction_by_category": {c: prf(v["tp"], v["fp"], v["fn"]) for c, v in per_category.items()},
        "family_attribution": prf(
            sum(r.family_tp for r in ok), sum(r.family_fp for r in ok), sum(r.family_fn for r in ok)
        ),
        "evidence_validity": round(evidence_valid / evidence_checked, 3) if evidence_checked else None,
        "unsupported_fact_rate": round(unsupported / predicted, 3) if predicted else 0.0,
        "normalization_keyword_coverage": round(keyword_hits / keyword_total, 3) if keyword_total else None,
        "latency_ms_p50": latencies[len(latencies) // 2],
        "latency_ms_p95": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        "estimated_cost_usd": round(sum(r.cost_usd for r in ok), 6),
        "mean_facts_per_case": round(statistics.mean([r.predicted_facts for r in ok]), 2) if ok else 0.0,
    }


async def evaluate(provider_name: str, model: str | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    settings = get_settings().model_copy(
        update={"demo_mode": provider_name == "mock", "ai_provider": provider_name, "ai_model": model or ""}
    )
    provider = build_ai_provider(settings)
    try:
        results = [await run_case(provider, case) for case in cases]
    finally:
        await provider.aclose()
    summary = aggregate(results)
    summary["provider"] = provider.name
    summary["model"] = provider.model
    summary["dataset"] = DATASET.name
    return {"summary": summary, "cases": [vars(r) for r in results]}


def render_markdown(reports: list[dict[str, Any]]) -> str:
    head = (
        "| provider | model | lang acc | extract P | extract R | extract F1 | family F1 | evidence valid | "
        "unsupported | norm coverage | p50 ms | cost $ | failures |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for report in reports:
        s = report["summary"]
        e = s["extraction_overall"]
        rows.append(
            f"| {s['provider']} | {s['model']} | {s['language_accuracy']} | {e['precision']} | {e['recall']} | "
            f"{e['f1']} | {s['family_attribution']['f1']} | {s['evidence_validity']} | "
            f"{s['unsupported_fact_rate']} | "
            f"{s['normalization_keyword_coverage']} | {s['latency_ms_p50']} | {s['estimated_cost_usd']} | "
            f"{s['failures']} |"
        )
    return head + "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--compare", help="comma-separated providers to benchmark against each other")
    parser.add_argument("--limit", type=int, default=None, help="only the first N cases")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = data["cases"][: args.limit] if args.limit else data["cases"]
    providers = [p.strip() for p in args.compare.split(",")] if args.compare else [args.provider]

    reports: list[dict[str, Any]] = []
    for name in providers:
        try:
            reports.append(asyncio.run(evaluate(name, args.model, cases)))
        except AIError as exc:
            print(f"{name}: skipped ({exc.code}: {exc.message})")

    if not reports:
        print("No provider could be evaluated.")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for report in reports:
        s = report["summary"]
        path = args.out / f"{s['provider']}-{s['model']}.json".replace("/", "_")
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n=== {s['provider']} / {s['model']} ===")
        print(json.dumps(s, indent=2))
        print(f"(written to {path})")

    table = render_markdown(reports)
    (args.out / "benchmark.md").write_text(table, encoding="utf-8")
    print("\n" + table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
