"""Provider contract tests (Phase 2 async interface)."""

import asyncio

import pytest

from app.core.config import Settings
from app.core.languages import LANGUAGES, LanguageCode
from app.providers.ai import (
    AIConfigurationError,
    AICredentialsMissing,
    AnthropicProvider,
    GeminiProvider,
    MockAIProvider,
    OpenAIProvider,
    build_ai_provider,
)
from app.providers.ai.base import AIProvider
from app.providers.ai.prompts import PROMPTS
from app.providers.storage import LocalStorageProvider, ObjectNotFound, StorageError


def run(coro):
    return asyncio.run(coro)


def test_mock_provider_implements_the_contract():
    provider = MockAIProvider()
    assert isinstance(provider, AIProvider)
    assert provider.is_external is False  # nothing leaves the process


def test_interface_offers_no_clinical_decision_capability():
    forbidden = {"diagnose", "prescribe", "generate_prescription", "recommend_treatment", "select_medication"}
    assert not forbidden & set(dir(AIProvider))


def test_mock_detects_scripts():
    p = MockAIProvider()
    assert run(p.detect_language("தலைவலி")).language == LanguageCode.TA
    assert run(p.detect_language("सिरदर्द")).language == LanguageCode.HI
    assert run(p.detect_language("headache")).language == LanguageCode.EN
    assert run(p.detect_language("12345")).language is None  # no signal: never guess


def test_mock_detects_dominant_language_in_mixed_text():
    p = MockAIProvider()
    detection = run(p.detect_language("எனக்கு fever மற்றும் headache உள்ளது"))
    assert detection.language == LanguageCode.TA
    assert 0 < detection.confidence <= 1


def test_mock_normalisation_preserves_the_original():
    p = MockAIProvider()
    source = "மூன்று நாட்களாக தலைவலி உள்ளது"
    result = run(p.normalize_to_english(source, LanguageCode.TA))
    assert result.original_text == source  # unchanged
    assert "headache" in result.normalized_text_en
    assert result.normalized_text_en != source
    assert result.prompt_version == PROMPTS["normalization"].version


def test_mock_normalisation_of_english_is_the_source_itself():
    p = MockAIProvider()
    result = run(p.normalize_to_english("I have a headache.", LanguageCode.EN))
    assert result.normalized_text_en == "I have a headache."


def test_mock_extraction_returns_evidence_that_exists_in_the_source():
    p = MockAIProvider()
    source = "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது"
    result = run(p.extract_medical_information(source, LanguageCode.TA))
    values = {f.value for f in result.facts}
    assert "headache" in values and "2 days" in values
    for fact in result.facts:
        assert fact.evidence.quote in source
        assert source[fact.evidence.start : fact.evidence.end] == fact.evidence.quote


def test_provider_factory_selects_by_configuration():
    base = Settings(demo_mode=False, app_env="test")
    assert build_ai_provider(base.model_copy(update={"ai_provider": "mock"})).name == "mock"
    assert isinstance(
        build_ai_provider(base.model_copy(update={"ai_provider": "openai", "openai_api_key": "k"})), OpenAIProvider
    )
    assert isinstance(
        build_ai_provider(base.model_copy(update={"ai_provider": "anthropic", "anthropic_api_key": "k"})),
        AnthropicProvider,
    )
    assert isinstance(
        build_ai_provider(base.model_copy(update={"ai_provider": "gemini", "gemini_api_key": "k"})), GeminiProvider
    )


def test_demo_mode_pins_the_local_provider():
    settings = Settings(app_env="test", demo_mode=True, ai_provider="openai", openai_api_key="k")
    provider = build_ai_provider(settings)
    assert provider.name == "mock" and provider.is_external is False


def test_invalid_provider_configuration_fails_safely():
    with pytest.raises(AIConfigurationError):
        build_ai_provider(Settings(app_env="test", demo_mode=False, ai_provider="nonsense"))
    with pytest.raises(AICredentialsMissing):
        build_ai_provider(Settings(app_env="test", demo_mode=False, ai_provider="openai", openai_api_key=None))


def test_default_models_come_from_configuration():
    settings = Settings(app_env="test", demo_mode=False, ai_provider="anthropic", anthropic_api_key="k",
                        ai_model="claude-sonnet-5")
    assert build_ai_provider(settings).model == "claude-sonnet-5"


# ---------- storage (unchanged from Phase 1) ----------


def test_local_storage_roundtrip(tmp_path):
    s = LocalStorageProvider(tmp_path)
    ref = s.put("patients/p1/documents/abc.pdf", b"%PDF-data", "application/pdf")
    assert s.exists(ref)
    assert s.get(ref) == b"%PDF-data"
    s.delete(ref)
    assert not s.exists(ref)
    with pytest.raises(ObjectNotFound):
        s.get(ref)


@pytest.mark.parametrize("key", ["../escape.pdf", "patients/../../escape", "/abs/path", "C:/windows/x", ""])
def test_local_storage_rejects_traversal(tmp_path, key):
    s = LocalStorageProvider(tmp_path)
    with pytest.raises(StorageError):
        s.put(key, b"x", "application/pdf")


def test_language_registry_is_honest():
    assert len(LANGUAGES) == 12
    ui = {c for c, i in LANGUAGES.items() if i.ui_available}
    assert ui == {LanguageCode.EN, LanguageCode.HI, LanguageCode.TA}


def test_meta_ai_endpoint_describes_configuration_without_secrets(client):
    body = client.get("/api/v1/meta/ai").json()
    assert body["provider"] == "mock"
    assert body["demo_mode"] is True
    assert body["is_external"] is False
    # Every capability that has a versioned prompt, derived rather than listed.
    assert set(body["enabled_features"]) == {
        "language_detection", "normalization", "extraction",
        "document_transcription", "case_summary",
    }
    assert body["prompt_versions"]["extraction"] == PROMPTS["extraction"].version
    serialised = str(body).lower()
    for leak in ("api_key", "sk-", "secret", "authorization"):
        assert leak not in serialised


def test_meta_languages(client):
    langs = client.get("/api/v1/meta/languages").json()
    assert {l["code"] for l in langs if l["ui_available"]} == {"en", "hi", "ta"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
