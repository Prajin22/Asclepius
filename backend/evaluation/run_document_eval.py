"""Evaluate document reading and extraction on synthetic documents.

    uv run python -m evaluation.run_document_eval                 # local reader + local provider
    uv run python -m evaluation.run_document_eval --reader none   # text layers only, no OCR

For every synthetic document (its exact text is known):

* reading     — character accuracy of the text read against the known text
                (whitespace ignored, because OCR drops spaces) and the share of
                lines read exactly, by reading method;
* extraction  — precision / recall / F1 of the patient's own facts, and family
                attribution, scored like evaluation/run_eval.py;
* provenance  — a matched fact must come from the page the document states it
                on; every quote must be found on its page; where the reader
                reports positions, the outlined region must cover the line the
                quote is on;
* safety      — no fact may contain a value listed as forbidden (for example
                an instruction embedded in the document).

Numbers describe these synthetic documents and this configuration only. They are
not a clinical accuracy claim. No real patient data is used.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app import synthetic_documents as sd
from app.core.config import get_settings
from app.core.languages import LanguageCode
from app.models.enums import FactSubject, FactValidation
from app.providers.ai import build_ai_provider
from app.providers.ai.base import AIProvider
from app.providers.ai.errors import AIError
from app.providers.documents import ReadOptions, local_ocr_engine, read_document
from app.providers.documents.base import PageText
from app.services.evidence import canonical, validate_fact
from evaluation.run_eval import matches

DATASET = Path(__file__).with_name("document_dataset.json")


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def squash(text: str) -> str:
    return "".join(text.split()).casefold()


def character_accuracy(expected: str, read: str) -> float:
    e, r = squash(expected), squash(read)
    return max(0.0, 1 - levenshtein(e, r) / max(1, len(e)))


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def _covers(bbox: tuple[float, float, float, float], target: tuple[float, float, float, float]) -> bool:
    cx, cy = (target[0] + target[2]) / 2, (target[1] + target[3]) / 2
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


async def run_document(provider: AIProvider, spec: dict[str, Any], reader: str) -> dict[str, Any]:
    name = spec["file"]
    data, mime = sd.all_samples()[name]
    truth_pages = sd.SAMPLE_TEXT[name]
    row: dict[str, Any] = {"file": name, "notes": spec.get("notes", ""), "pages": [], "facts": []}

    ocr = local_ocr_engine() if reader == "local" else None
    started = time.perf_counter()
    try:
        read = read_document(data, mime, ReadOptions(), ocr)
    except Exception as exc:  # reported, not raised: an unreadable document is a result
        row["error"] = getattr(exc, "code", type(exc).__name__)
        return row
    row["read_ms"] = int((time.perf_counter() - started) * 1000)

    predictions: list[dict[str, Any]] = []
    for page in read.pages:
        truth = "\n".join(truth_pages[page.page_number - 1])
        read_lines = {squash(block.text) for block in page.blocks} or {squash(line) for line in page.text.split("\n")}
        truth_lines = [line for line in truth_pages[page.page_number - 1] if line.strip()]
        row["pages"].append(
            {
                "page": page.page_number,
                "method": page.method,
                "confidence": page.confidence,
                "character_accuracy": round(character_accuracy(truth, page.text), 4),
                "exact_line_rate": round(sum(squash(line) in read_lines for line in truth_lines) / len(truth_lines), 4),
                "warnings": page.warnings,
            }
        )
        if not page.text.strip():
            continue
        try:
            detection = await provider.detect_language(page.text)
            extraction = await provider.extract_medical_information(page.text, detection.language or LanguageCode.EN)
        except AIError as exc:
            row["error"] = exc.code
            continue
        for fact in extraction.facts:
            predictions.append(_score_fact(fact, page, truth_pages))
    row["facts"] = predictions
    return row


def _score_fact(fact, page: PageText, truth_pages: list[list[str]]) -> dict[str, Any]:
    outcome = validate_fact(fact, page.text)
    start, end = outcome.start, outcome.end  # the application's position, never the provider's
    quote = squash(fact.evidence.quote)
    stated_on = [i + 1 for i, lines in enumerate(truth_pages) if quote and quote in squash(" ".join(lines))]
    bbox = page.bbox_for_span(start, end)
    line = next((b for b in page.blocks if quote and quote in squash(b.text)), None)
    return {
        "page": page.page_number,
        "category": fact.category.value,
        "subject": fact.subject.value,
        "value": fact.value,
        "quote": fact.evidence.quote,
        "validation": outcome.status.value,
        "quote_on_stated_page": page.page_number in stated_on,
        "has_positions": bool(page.blocks),
        "bbox": list(bbox) if bbox else None,
        "bbox_covers_line": bool(bbox and line and _covers(bbox, line.bbox)),
    }


def score(rows: list[dict[str, Any]], specs: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = 0
    family = {"tp": 0, "fp": 0, "fn": 0}
    page_correct = 0
    forbidden_hits: list[str] = []
    for row, spec in zip(rows, specs, strict=True):
        own_expected = [e for e in spec["expected"] if e.get("subject", "self") == "self"]
        family_expected = [e for e in spec["expected"] if e.get("subject") == "family"]
        for fact in row["facts"]:
            if any(canonical(bad) in canonical(fact["value"]) for bad in spec.get("forbidden", [])):
                forbidden_hits.append(f"{row['file']}: {fact['value']}")
            pool = family_expected if fact["subject"] == FactSubject.FAMILY.value else own_expected
            hit = next(
                (e for e in pool if e["category"] == fact["category"] and matches(e["value"], fact["value"])),
                None,
            )
            counts = family if pool is family_expected else None
            if hit is None:
                if counts is not None:
                    counts["fp"] += 1
                elif fact["subject"] == FactSubject.SELF.value:
                    fp += 1
                continue
            pool.remove(hit)
            if counts is not None:
                counts["tp"] += 1
            else:
                tp += 1
            page_correct += int(hit["page"] == fact["page"])
        fn += len(own_expected)
        family["fn"] += len(family_expected)

    facts = [f for row in rows for f in row["facts"]]
    with_positions = [f for f in facts if f["has_positions"] and f["validation"] != FactValidation.UNSUPPORTED.value]
    pages = [p for row in rows for p in row["pages"]]
    by_method: dict[str, dict[str, Any]] = {}
    for method in sorted({p["method"] for p in pages}):
        chosen = [p for p in pages if p["method"] == method]
        by_method[method] = {
            "pages": len(chosen),
            "character_accuracy": round(statistics.mean(p["character_accuracy"] for p in chosen), 4),
            "exact_line_rate": round(statistics.mean(p["exact_line_rate"] for p in chosen), 4),
        }
    return {
        "documents": len(rows),
        "pages_read": len(pages),
        "reading_errors": [f"{r['file']}: {r['error']}" for r in rows if r.get("error")],
        "reading_by_method": by_method,
        "extraction_overall": prf(tp, fp, fn),
        "family_attribution": prf(family["tp"], family["fp"], family["fn"]),
        "page_provenance_accuracy": round(page_correct / (tp + family["tp"]), 3) if tp + family["tp"] else None,
        "evidence_validity": round(sum(f["validation"] == "validated" for f in facts) / len(facts), 3) if facts else None,
        "unsupported_fact_rate": round(sum(f["validation"] == "unsupported" for f in facts) / len(facts), 3) if facts else 0.0,
        "quote_on_stated_page_rate": round(sum(f["quote_on_stated_page"] for f in facts) / len(facts), 3) if facts else None,
        "bbox_coverage": round(sum(bool(f["bbox"]) for f in with_positions) / len(with_positions), 3) if with_positions else None,
        "bbox_line_agreement": round(sum(f["bbox_covers_line"] for f in with_positions) / len(with_positions), 3)
        if with_positions
        else None,
        "forbidden_facts": forbidden_hits,
    }


async def evaluate(provider_name: str, model: str | None, reader: str) -> dict[str, Any]:
    specs = json.loads(DATASET.read_text(encoding="utf-8"))["documents"]
    settings = get_settings().model_copy(
        update={"demo_mode": provider_name == "mock", "ai_provider": provider_name, "ai_model": model or ""}
    )
    provider = build_ai_provider(settings)
    try:
        rows = [await run_document(provider, spec, reader) for spec in specs]
    finally:
        await provider.aclose()
    summary = score(rows, [json.loads(json.dumps(s)) for s in specs])
    summary |= {"provider": provider.name, "model": provider.model, "reader": reader, "dataset": DATASET.name}
    return {"summary": summary, "documents": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reader", choices=["local", "none"], default="local")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()

    report = asyncio.run(evaluate(args.provider, args.model, args.reader))
    args.out.mkdir(parents=True, exist_ok=True)
    s = report["summary"]
    path = args.out / f"documents-{s['provider']}-{s['model']}-{s['reader']}.json".replace("/", "_")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(s, indent=2, ensure_ascii=False))
    print(f"(written to {path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
