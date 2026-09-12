"""Token pricing used only to *estimate* cost for provenance and evaluation.

USD per million tokens. Verify against the provider's current pricing page
before relying on these numbers for anything financial; an unknown model
yields `None` rather than a guess.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float


# Checked against provider documentation on 2026-09-12.
PRICING: dict[tuple[str, str], Price] = {
    ("anthropic", "claude-opus-5"): Price(5.00, 25.00),
    ("anthropic", "claude-sonnet-5"): Price(2.00, 10.00),
    ("anthropic", "claude-haiku-4-5"): Price(1.00, 5.00),
    # Populate from the current OpenAI/Google pricing pages before use.
    ("mock", "mock-0"): Price(0.0, 0.0),
}


def estimate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    override: Price | None = None,
) -> float | None:
    """None when the price is unknown — we never invent a number."""
    if input_tokens is None and output_tokens is None:
        return None
    price = override or PRICING.get((provider, model))
    if price is None:
        return None
    return round(
        (input_tokens or 0) / 1_000_000 * price.input_per_mtok
        + (output_tokens or 0) / 1_000_000 * price.output_per_mtok,
        6,
    )
