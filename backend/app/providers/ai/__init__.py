"""Provider selection. Business logic never names a vendor."""

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.ai.anthropic_provider import DEFAULT_MODEL as ANTHROPIC_MODEL
from app.providers.ai.anthropic_provider import AnthropicProvider
from app.providers.ai.base import AIProvider
from app.providers.ai.errors import (
    AICircuitOpen,
    AIConfigurationError,
    AICredentialsMissing,
    AIError,
    AIMalformedOutput,
    AIProviderUnavailable,
    AITimeout,
)
from app.providers.ai.gemini_provider import DEFAULT_MODEL as GEMINI_MODEL
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.mock import MOCK_MODEL, MockAIProvider
from app.providers.ai.openai_provider import DEFAULT_MODEL as OPENAI_MODEL
from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.ai.pricing import Price
from app.providers.ai.runtime import CircuitBreaker

EXTERNAL_PROVIDERS = {
    "openai": (OpenAIProvider, OPENAI_MODEL),
    "anthropic": (AnthropicProvider, ANTHROPIC_MODEL),
    "gemini": (GeminiProvider, GEMINI_MODEL),
}


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    """Instantiate the configured provider. DEMO_MODE always yields the mock."""
    settings = settings or get_settings()
    name = settings.effective_ai_provider

    if name == "mock":
        return MockAIProvider(settings.ai_model or MOCK_MODEL)

    entry = EXTERNAL_PROVIDERS.get(name)
    if entry is None:
        raise AIConfigurationError(f"Unknown AI_PROVIDER={name!r}")
    provider_cls, default_model = entry

    price = None
    if settings.ai_price_input_per_mtok is not None and settings.ai_price_output_per_mtok is not None:
        price = Price(settings.ai_price_input_per_mtok, settings.ai_price_output_per_mtok)

    base_url = {
        "openai": settings.openai_base_url,
        "anthropic": settings.anthropic_base_url,
        "gemini": settings.gemini_base_url,
    }[name]

    return provider_cls(
        model=settings.ai_model or default_model,
        api_key=settings.api_key_for(name),
        base_url=base_url,
        timeout_seconds=settings.ai_timeout_seconds,
        price=price,
    )


@lru_cache
def get_ai_provider() -> AIProvider:
    return build_ai_provider()


@lru_cache
def get_circuit_breaker() -> CircuitBreaker:
    settings = get_settings()
    return CircuitBreaker(settings.ai_circuit_failure_threshold, settings.ai_circuit_reset_seconds)


def reset_ai_provider_cache() -> None:
    """Used by tests and by configuration changes."""
    get_ai_provider.cache_clear()
    get_circuit_breaker.cache_clear()


__all__ = [
    "AICircuitOpen",
    "AIConfigurationError",
    "AICredentialsMissing",
    "AIError",
    "AIMalformedOutput",
    "AIProvider",
    "AIProviderUnavailable",
    "AITimeout",
    "AnthropicProvider",
    "GeminiProvider",
    "MockAIProvider",
    "OpenAIProvider",
    "build_ai_provider",
    "get_ai_provider",
    "get_circuit_breaker",
    "reset_ai_provider_cache",
]
