"""AI provider contract (Phase 2).

Business logic depends on `AIProvider` only; concrete providers are selected by
configuration. Every result carries provider, model, prompt version and usage so
it can be stored as an `AIArtifact` with full provenance.

Policy (docs/AI_POLICY.md): these capabilities detect language, normalise to
English and extract *explicitly stated* information with evidence. There is
deliberately no diagnose / prescribe / recommend capability anywhere in this
interface, and no method may infer a fact the source does not state.
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactSubject

SourceType = Literal["medical_record", "document", "document_page", "consultation_message"]


class SourceReference(BaseModel):
    type: SourceType = "medical_record"
    id: str
    span: tuple[int, int] | None = None


class AIUsage(BaseModel):
    """Provenance metrics for one provider call."""

    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


class AIResult(BaseModel):
    provider: str
    model: str
    prompt_version: str | None = None
    usage: AIUsage = Field(default_factory=AIUsage)
    confidence: float | None = Field(default=None, ge=0, le=1)


class LanguageDetection(AIResult):
    language: LanguageCode | None = None
    # Unknown stays unknown: `language=None` means "could not determine".


class NormalizationResult(AIResult):
    original_text: str
    source_language: LanguageCode
    normalized_text_en: str
    # Parts of the source the provider could not render with confidence.
    unparsed: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """A verbatim quote from the source that supports a fact."""

    quote: str
    start: int | None = None
    end: int | None = None


class ExtractedFact(BaseModel):
    category: FactCategory
    value: str  # normalised English value, e.g. "headache", "3 days"
    original_text: str | None = None  # the patient's own words for this fact
    evidence: Evidence
    #: Whose health this describes. Defaults to the patient because the source
    #: is their own health entry; an explicit cue is required to say otherwise.
    subject: FactSubject = FactSubject.SELF
    #: The words that attributed it to someone else ("my father"), when present.
    subject_evidence: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExtractionResult(AIResult):
    facts: list[ExtractedFact] = Field(default_factory=list)
    # Statements the provider could not turn into supported facts.
    needs_review: list[str] = Field(default_factory=list)
    unparsed: list[str] = Field(default_factory=list)


class DocumentTranscription(AIResult):
    """Text a vision model read from one page image. Machine transcription, not truth."""

    text: str
    language: LanguageCode | None = None
    # Parts of the page the model could not read. Never filled in by guessing.
    unreadable: list[str] = Field(default_factory=list)


class AIProvider(ABC):
    """Every method must be safe to call concurrently and must not mutate input."""

    name: str
    model: str
    #: True when calling this provider sends patient text to a third party.
    is_external: bool = True
    #: True when the provider can transcribe document page images.
    supports_vision: bool = False

    async def transcribe_document_image(self, image_png: bytes, page_number: int) -> DocumentTranscription:
        """Read the text on one page image. Only providers with vision implement this."""
        from app.providers.ai.errors import AICapabilityUnsupported

        raise AICapabilityUnsupported(f"{self.name} cannot read document images", provider=self.name)

    @abstractmethod
    async def detect_language(self, text: str) -> LanguageDetection: ...

    @abstractmethod
    async def normalize_to_english(self, text: str, source_language: LanguageCode) -> NormalizationResult: ...

    @abstractmethod
    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult: ...

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        """Release network resources, if the provider holds any."""
        return None
