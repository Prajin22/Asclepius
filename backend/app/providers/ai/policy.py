"""Holding a provider to its product's AI policy (D-079).

`build_ai_provider` hands back the provider itself when the product's policy
permits every capability (CareBridge), and this wrapper when it does not
(IP-SAKTI). The wrapper refuses any capability the policy does not name before
anything reaches the provider, so no text is sent and nothing is spent.
"""

from app.core.ai_policy import AIPolicy
from app.core.languages import LanguageCode
from app.providers.ai.base import (
    AIProvider,
    DocumentTranscription,
    ExtractionResult,
    LanguageDetection,
    NormalizationResult,
    SummaryOrganisation,
)
from app.services.errors import AICapabilityNotPermitted


class PolicyRestrictedProvider(AIProvider):
    def __init__(self, inner: AIProvider, policy: AIPolicy):
        self._inner = inner
        self._policy = policy
        self.name = inner.name
        self.model = inner.model
        self.is_external = inner.is_external
        self.supports_vision = inner.supports_vision and policy.permits("transcribe_document_image")

    @property
    def policy(self) -> AIPolicy:
        return self._policy

    def _require(self, capability: str) -> None:
        if not self._policy.permits(capability):
            raise AICapabilityNotPermitted(f"AI policy {self._policy.id} does not permit {capability}")

    async def detect_language(self, text: str) -> LanguageDetection:
        self._require("detect_language")
        return await self._inner.detect_language(text)

    async def normalize_to_english(self, text: str, source_language: LanguageCode) -> NormalizationResult:
        self._require("normalize_to_english")
        return await self._inner.normalize_to_english(text, source_language)

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        self._require("extract_medical_information")
        return await self._inner.extract_medical_information(text, language)

    async def transcribe_document_image(self, image_png: bytes, page_number: int) -> DocumentTranscription:
        self._require("transcribe_document_image")
        return await self._inner.transcribe_document_image(image_png, page_number)

    async def summarize_case(self, bundle_text: str) -> SummaryOrganisation:
        self._require("summarize_case")
        return await self._inner.summarize_case(bundle_text)

    async def aclose(self) -> None:
        await self._inner.aclose()


def restrict_to_policy(provider: AIProvider, policy: AIPolicy) -> AIProvider:
    """The provider unchanged if the policy permits everything; otherwise wrapped."""
    return provider if policy.permits_everything else PolicyRestrictedProvider(provider, policy)
