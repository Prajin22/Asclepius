"""End-to-end smoke test for a real AI provider adapter. Synthetic data only.

    # against a local server speaking the real OpenAI wire format (no key, no spend)
    uv run python scripts/ai_smoke_test.py --emulate

    # against the real API (requires OPENAI_API_KEY in the environment or .env)
    uv run python scripts/ai_smoke_test.py --provider openai
    uv run python scripts/ai_smoke_test.py --provider anthropic --model claude-opus-5

    # also read one synthetic scanned page with the provider's vision input (Phase 3)
    uv run python scripts/ai_smoke_test.py --provider openai --document

Checks, in order: credentials resolve, language detection, English
normalisation, structured extraction, every fact's evidence against the source,
three-layer meaning drift, token accounting and estimated cost, and the error
mapping for a deliberate bad request. With --document: vision transcription of
a synthetic page image, reading accuracy against its known text, and extraction
with evidence over what was read. Never sends anything but the synthetic
sentence and the synthetic page below.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for openai_emulator
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for app

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.languages import LanguageCode  # noqa: E402
from app.models.enums import FactValidation  # noqa: E402
from app.providers.ai import build_ai_provider  # noqa: E402
from app.providers.ai.errors import AIError  # noqa: E402
from app.services.evidence import validate_fact  # noqa: E402
from app.services.normalization_check import check_normalization  # noqa: E402

# Synthetic sentence. Not from any real person.
SYNTHETIC_TA = "எனக்கு இரண்டு நாட்களாக தலைவலி மற்றும் காய்ச்சல் உள்ளது."

PASS, FAIL, INFO = "PASS", "FAIL", "····"
failures = 0


def _why(fact, outcome) -> str:
    """The validator's reason, the provider's claimed offsets and where the quote really is."""
    if outcome.status == FactValidation.VALIDATED:
        return ""
    return (f" ({outcome.note}; claimed offsets={fact.evidence.start},{fact.evidence.end}; "
            f"found at={outcome.start},{outcome.end}; confidence={fact.confidence})")


def line(status: str, label: str, detail: str = "") -> None:
    global failures
    if status == FAIL:
        failures += 1
    print(f"{status}  {label}" + (f" — {detail}" if detail else ""))


async def run(settings: Settings, text: str, language: LanguageCode) -> None:
    provider = build_ai_provider(settings)
    print(f"\nprovider={provider.name} model={provider.model} external={provider.is_external}")
    print(f"base_url={getattr(provider, '_base_url', 'n/a')}\n")
    try:
        detection = await provider.detect_language(text)
        line(PASS if detection.language else FAIL, "language detection",
             f"{detection.language} (confidence={detection.confidence})")

        used_language = detection.language or language
        normalization = await provider.normalize_to_english(text, used_language)
        ok = bool(normalization.normalized_text_en.strip())
        line(PASS if ok else FAIL, "english normalisation", normalization.normalized_text_en[:90])
        line(PASS if normalization.original_text == text else FAIL, "original text preserved unchanged")

        extraction = await provider.extract_medical_information(text, used_language)
        line(PASS if extraction.facts else FAIL, "structured extraction", f"{len(extraction.facts)} fact(s)")

        for fact in extraction.facts:
            outcome = validate_fact(fact, text)
            status = PASS if outcome.status == FactValidation.VALIDATED else FAIL
            line(status, f"evidence · {fact.category.value}: {fact.value}",
                 f"subject={fact.subject.value} quote={fact.evidence.quote!r} → {outcome.status.value}"
                 + _why(fact, outcome))

        check = check_normalization(text, normalization.normalized_text_en, extraction.facts)
        line(PASS if check.status == "ok" else INFO, "three-layer meaning check",
             json.dumps(check.as_dict(), ensure_ascii=False))

        results = (detection, normalization, extraction)
        totals = {"input": 0, "output": 0, "cost": 0.0, "latency": 0}
        for result in results:
            totals["input"] += result.usage.input_tokens or 0
            totals["output"] += result.usage.output_tokens or 0
            totals["cost"] += result.usage.estimated_cost_usd or 0.0
            totals["latency"] += result.usage.latency_ms or 0
        has_tokens = totals["input"] > 0 or provider.name == "mock"
        # Never report an unknown price as $0 — that would be an invented number.
        cost_known = all(r.usage.estimated_cost_usd is not None for r in results)
        cost = (
            f"cost=${totals['cost']:.6f}"
            if cost_known
            else "cost=unknown (model not in pricing table; set AI_PRICE_INPUT/OUTPUT_PER_MTOK)"
        )
        line(PASS if has_tokens else FAIL, "token accounting", f"in={totals['input']} out={totals['output']} {cost}")
        line(PASS, "latency", f"{totals['latency']} ms total for 3 calls")

    except AIError as exc:
        line(FAIL, "provider call", f"{exc.code}: {exc.message}")
    finally:
        await provider.aclose()


async def run_document(settings: Settings, server=None) -> None:
    """Vision transcription of one synthetic scanned page, then extraction over what was read."""
    from app import synthetic_documents as sd
    from app.providers.documents.render import png_bytes
    from evaluation.run_document_eval import character_accuracy

    provider = build_ai_provider(settings)
    lines = sd.SCANNED_LAB[0]
    print(f"\n--- document page · provider={provider.name} model={provider.model} vision={provider.supports_vision}")
    try:
        if not provider.supports_vision:
            line(FAIL, "vision transcription", f"{provider.name} has no image input")
            return
        page = await provider.transcribe_document_image(png_bytes(sd.image_of_lines(lines)), 1)
        line(PASS if page.text.strip() else FAIL, "vision transcription", page.text.replace("\n", " | ")[:120])
        if server is not None:
            parts = server.requests[-1]["body"]["input"][1]["content"]
            line(PASS if any(p.get("type") == "input_image" for p in parts) else FAIL, "page sent as input_image")
        accuracy = character_accuracy("\n".join(lines), page.text)
        line(PASS if accuracy >= 0.9 else INFO, "reading accuracy vs known text", f"{accuracy:.3f} (whitespace ignored)")
        if page.unreadable:
            line(INFO, "reported unreadable", "; ".join(page.unreadable))

        extraction = await provider.extract_medical_information(page.text, page.language or LanguageCode.EN)
        line(PASS if extraction.facts else FAIL, "extraction over transcribed page", f"{len(extraction.facts)} fact(s)")
        for fact in extraction.facts:
            outcome = validate_fact(fact, page.text)
            line(PASS if outcome.status == FactValidation.VALIDATED else FAIL,
                 f"evidence on page · {fact.category.value}: {fact.value}",
                 f"quote={fact.evidence.quote!r} → {outcome.status.value}" + _why(fact, outcome))

        results = (page, extraction)
        tokens_in = sum(r.usage.input_tokens or 0 for r in results)
        tokens_out = sum(r.usage.output_tokens or 0 for r in results)
        cost_known = all(r.usage.estimated_cost_usd is not None for r in results)
        cost = f"cost=${sum(r.usage.estimated_cost_usd or 0.0 for r in results):.6f}" if cost_known else "cost=unknown"
        line(PASS if tokens_in > 0 else FAIL, "token accounting (page)", f"in={tokens_in} out={tokens_out} {cost}")
        line(PASS, "latency (page)", f"{sum(r.usage.latency_ms or 0 for r in results)} ms for 2 calls")
    except AIError as exc:
        line(FAIL, "document call", f"{exc.code}: {exc.message}")
    finally:
        await provider.aclose()


async def error_paths(settings: Settings) -> None:
    """The adapter must map transport failures to structured errors, not crashes."""
    from openai_emulator import EmulatorMode, start

    for mode, expected in (
        (EmulatorMode.AUTH_401, "ai_credentials_missing"),
        (EmulatorMode.RATE_429, "ai_provider_unavailable"),
        (EmulatorMode.ERROR_500, "ai_provider_unavailable"),
        (EmulatorMode.MALFORMED, "ai_malformed_output"),
        (EmulatorMode.WRONG_SCHEMA, "ai_malformed_output"),
    ):
        server = start(mode)
        provider = build_ai_provider(settings.model_copy(update={"openai_base_url": server.base_url}))
        try:
            await provider.extract_medical_information(SYNTHETIC_TA, LanguageCode.TA)
            line(FAIL, f"error mapping · {mode.value}", "no error raised")
        except AIError as exc:
            line(PASS if exc.code == expected else FAIL, f"error mapping · {mode.value}",
                 f"{exc.code} (expected {expected})")
        finally:
            await provider.aclose()
            server.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic", "gemini", "mock"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--text", default=SYNTHETIC_TA)
    parser.add_argument("--language", default="ta")
    parser.add_argument("--emulate", action="store_true",
                        help="run against a local server speaking the OpenAI wire format")
    parser.add_argument("--skip-error-paths", action="store_true")
    parser.add_argument("--document", action="store_true",
                        help="also transcribe one synthetic scanned page with the provider's vision input")
    parser.add_argument("--document-only", action="store_true", help="only the document page check")
    args = parser.parse_args()

    update = {"demo_mode": False, "ai_provider": args.provider, "ai_model": args.model or ""}
    server = None
    if args.emulate:
        from openai_emulator import start

        server = start()
        update |= {"ai_provider": "openai", "openai_api_key": "emulated-key", "openai_base_url": server.base_url}
        print("Running against the local OpenAI emulator (no network, no spend).")
    elif args.base_url:
        update[f"{args.provider}_base_url"] = args.base_url

    settings = get_settings().model_copy(update=update)
    if settings.ai_provider != "mock" and not settings.api_key_for(settings.ai_provider):
        print(f"\nFAIL  no API key configured for {settings.ai_provider}.")
        print(f"      Set {settings.ai_provider.upper()}_API_KEY in your environment or .env,")
        print("      or run with --emulate to exercise the adapter without one.")
        return 1

    try:
        if not args.document_only:
            asyncio.run(run(settings, args.text, LanguageCode(args.language)))
        if args.document or args.document_only:
            asyncio.run(run_document(settings, server))
        if args.emulate and not args.skip_error_paths and not args.document_only:
            asyncio.run(error_paths(settings))
    finally:
        if server is not None:
            server.shutdown()

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
