"""Stub providers for failure-path tests. They implement the same contract."""

import asyncio

from app.core.languages import LanguageCode
from app.providers.ai.base import (
    AIProvider,
    AIUsage,
    Evidence,
    ExtractedFact,
    ExtractionResult,
    LanguageDetection,
    NormalizationResult,
)
from app.providers.ai.errors import AIMalformedOutput, AIProviderUnavailable
from app.models.enums import FactCategory


class RecordingProvider(AIProvider):
    """Deterministic provider that records how often it was called."""

    name = "stub"
    model = "stub-1"
    is_external = True

    def __init__(self, facts: list[ExtractedFact] | None = None, language: LanguageCode | None = LanguageCode.EN):
        self.model = "stub-1"
        self.calls: list[str] = []
        self._facts = facts or []
        self._language = language

    async def detect_language(self, text: str) -> LanguageDetection:
        self.calls.append("detect")
        return LanguageDetection(provider=self.name, model=self.model, language=self._language, usage=AIUsage())

    async def normalize_to_english(self, text: str, source_language: LanguageCode) -> NormalizationResult:
        self.calls.append("normalize")
        return NormalizationResult(
            provider=self.name, model=self.model, original_text=text, source_language=source_language,
            normalized_text_en=f"EN: {text}", usage=AIUsage(input_tokens=10, output_tokens=5),
        )

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        self.calls.append("extract")
        return ExtractionResult(provider=self.name, model=self.model, facts=list(self._facts), usage=AIUsage())


class FailingProvider(RecordingProvider):
    """Always unavailable (network/5xx equivalent)."""

    name = "failing"

    def __init__(self, error: Exception | None = None):
        super().__init__()
        self._error = error or AIProviderUnavailable("boom", provider=self.name)

    async def detect_language(self, text: str) -> LanguageDetection:
        self.calls.append("detect")
        raise self._error


class SlowProvider(RecordingProvider):
    """Exceeds any sensible timeout."""

    name = "slow"

    async def detect_language(self, text: str) -> LanguageDetection:
        self.calls.append("detect")
        await asyncio.sleep(5)
        return await super().detect_language(text)


class MalformedProvider(RecordingProvider):
    """Returns output that does not satisfy the schema."""

    name = "malformed"

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        self.calls.append("extract")
        raise AIMalformedOutput("not JSON", provider=self.name)


class FabricatingProvider(RecordingProvider):
    """Claims a fact whose evidence is nowhere in the source."""

    name = "fabricating"

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        self.calls.append("extract")
        return ExtractionResult(
            provider=self.name,
            model=self.model,
            facts=[
                ExtractedFact(
                    category=FactCategory.MEDICATION,
                    value="insulin 10 units",
                    evidence=Evidence(quote="I inject insulin every night"),
                ),
                ExtractedFact(
                    category=FactCategory.SYMPTOM,
                    value="headache",
                    evidence=Evidence(quote="headache"),
                ),
            ],
            usage=AIUsage(),
        )
