"""Shared plumbing for HTTP providers.

Responsibilities kept in one place so each vendor adapter is only request
shaping and response unwrapping:
* render the versioned prompt,
* validate the provider's JSON against our schema (never string-scrape),
* convert transport failures into structured `AIError`s,
* record latency, tokens and estimated cost.
"""

import base64
import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.languages import LANGUAGES, LanguageCode
from app.models.enums import FactCategory, FactSubject
from app.providers.ai.base import (
    AIProvider,
    AIUsage,
    DocumentTranscription,
    Evidence,
    ExtractedFact,
    ExtractionResult,
    LanguageDetection,
    NormalizationResult,
    SummaryOrganisation,
)
from app.providers.ai.errors import (
    AICapabilityUnsupported,
    AICredentialsMissing,
    AIMalformedOutput,
    AIProviderUnavailable,
    AITimeout,
)
from app.providers.ai.pricing import Price, estimate_cost_usd
from app.providers.ai.prompts import (
    CASE_SUMMARY,
    DOCUMENT_TRANSCRIPTION,
    EXTRACTION,
    LANGUAGE_DETECTION,
    NORMALIZATION,
    Prompt,
)
from app.schemas.summary import ModelCaseSummary


class _LanguagePayload(BaseModel):
    language: str | None = None
    # Bounds live here, not only in the request schema: some providers cannot
    # express them in a strict schema (see anthropic_provider).
    confidence: float | None = Field(default=None, ge=0, le=1)


class _NormalizationPayload(BaseModel):
    normalized_english: str
    unparsed: list[str] = []


class _EvidencePayload(BaseModel):
    quote: str
    start: int | None = None
    end: int | None = None


class _FactPayload(BaseModel):
    category: FactCategory
    value: str
    original_text: str | None = None
    evidence: _EvidencePayload
    subject: FactSubject = FactSubject.SELF
    subject_evidence: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class _ExtractionPayload(BaseModel):
    facts: list[_FactPayload] = []
    needs_review: list[str] = []
    unparsed: list[str] = []


class _TranscriptionPayload(BaseModel):
    text: str
    language: str | None = None
    unreadable: list[str] = []


class HttpJSONProvider(AIProvider):
    """Base for vendor adapters that return JSON validated against our schemas."""

    is_external = True
    #: Page images are sent only for pages without an exact text layer, and never in DEMO_MODE.
    supports_vision = True

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
        price: Price | None = None,
    ):
        if not api_key:
            raise AICredentialsMissing(
                f"No API key configured for AI provider {self.name!r}", provider=self.name
            )
        self.model = model
        self._api_key = api_key  # never logged, never serialised
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client
        self._owns_client = client is None
        self._price = price

    # ---------- transport ----------

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _post(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http().post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeout(str(exc), provider=self.name) from exc
        except httpx.HTTPError as exc:  # connection, DNS, TLS…
            raise AIProviderUnavailable(str(exc), provider=self.name) from exc

        if response.status_code in (401, 403):
            raise AICredentialsMissing("AI provider rejected the credentials", provider=self.name)
        if response.status_code == 429 or response.status_code >= 500:
            raise AIProviderUnavailable(
                f"AI provider returned {response.status_code}", provider=self.name
            )
        if response.status_code >= 400:
            # 4xx other than auth/limits means our request was wrong.
            raise AIMalformedOutput(
                f"AI provider rejected the request ({response.status_code})", provider=self.name
            )
        try:
            return response.json()
        except ValueError as exc:
            raise AIMalformedOutput("AI provider returned non-JSON", provider=self.name) from exc

    # ---------- vendor hooks ----------

    def _build_request(self, prompt: Prompt, user_text: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        raise NotImplementedError

    def _parse_response(self, body: dict[str, Any]) -> tuple[dict[str, Any], AIUsage]:
        raise NotImplementedError

    def _build_image_request(
        self, prompt: Prompt, user_text: str, image_png_b64: str
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """The same structured request, with one PNG page image attached."""
        raise AICapabilityUnsupported(f"{self.name} adapter has no image input", provider=self.name)

    async def _complete(self, prompt: Prompt, user_text: str) -> tuple[dict[str, Any], AIUsage]:
        return await self._send(*self._build_request(prompt, user_text))

    async def _send(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> tuple[dict[str, Any], AIUsage]:
        started = time.perf_counter()
        body = await self._post(url, headers=headers, payload=payload)
        data, usage = self._parse_response(body)
        usage.latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        usage.estimated_cost_usd = estimate_cost_usd(
            self.name, self.model, usage.input_tokens, usage.output_tokens, self._price
        )
        return data, usage

    @staticmethod
    def _loads(text: str, provider: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise AIMalformedOutput("AI provider did not return valid JSON", provider=provider) from exc
        if not isinstance(data, dict):
            raise AIMalformedOutput("AI provider returned a non-object JSON value", provider=provider)
        return data

    # ---------- capabilities ----------

    async def detect_language(self, text: str) -> LanguageDetection:
        data, usage = await self._complete(LANGUAGE_DETECTION, LANGUAGE_DETECTION.render_user(text=text))
        try:
            payload = _LanguagePayload.model_validate(data)
        except ValidationError as exc:
            raise AIMalformedOutput(str(exc), provider=self.name) from exc
        code = payload.language
        language = LanguageCode(code) if code in {c.value for c in LANGUAGES} else None
        return LanguageDetection(
            provider=self.name,
            model=self.model,
            prompt_version=LANGUAGE_DETECTION.version,
            language=language,
            confidence=payload.confidence,
            usage=usage,
        )

    async def normalize_to_english(self, text: str, source_language: LanguageCode) -> NormalizationResult:
        data, usage = await self._complete(
            NORMALIZATION, NORMALIZATION.render_user(text=text, language=source_language.value)
        )
        try:
            payload = _NormalizationPayload.model_validate(data)
        except ValidationError as exc:
            raise AIMalformedOutput(str(exc), provider=self.name) from exc
        return NormalizationResult(
            provider=self.name,
            model=self.model,
            prompt_version=NORMALIZATION.version,
            original_text=text,
            source_language=source_language,
            normalized_text_en=payload.normalized_english,
            unparsed=payload.unparsed,
            usage=usage,
        )

    async def transcribe_document_image(self, image_png: bytes, page_number: int) -> DocumentTranscription:
        """Machine transcription of one page. Used only for pages without an exact text layer."""
        if not self.supports_vision:
            return await super().transcribe_document_image(image_png, page_number)
        request = self._build_image_request(
            DOCUMENT_TRANSCRIPTION,
            DOCUMENT_TRANSCRIPTION.render_user(page=str(page_number)),
            base64.b64encode(image_png).decode("ascii"),
        )
        data, usage = await self._send(*request)
        try:
            payload = _TranscriptionPayload.model_validate(data)
        except ValidationError as exc:
            raise AIMalformedOutput(str(exc), provider=self.name) from exc
        code = payload.language
        return DocumentTranscription(
            provider=self.name,
            model=self.model,
            prompt_version=DOCUMENT_TRANSCRIPTION.version,
            text=payload.text,
            language=LanguageCode(code) if code in {c.value for c in LANGUAGES} else None,
            unreadable=payload.unreadable,
            usage=usage,
        )

    async def summarize_case(self, bundle_text: str) -> SummaryOrganisation:
        """One request per consultation. Same structured-output path as everything else.

        The vendor adapters need nothing new: `_build_request` is generic over any
        `Prompt`, so OpenAI's strict json_schema, Anthropic's strict tool and
        Gemini's responseSchema all constrain this response exactly as they
        constrain extraction.
        """
        data, usage = await self._complete(CASE_SUMMARY, CASE_SUMMARY.render_user(bundle=bundle_text))
        try:
            # Validated here against the same strict model the application uses,
            # so a provider that invents a field or a section fails at the
            # boundary instead of reaching the validator.
            payload = ModelCaseSummary.model_validate(data)
        except ValidationError as exc:
            raise AIMalformedOutput(str(exc), provider=self.name) from exc
        return SummaryOrganisation(
            provider=self.name,
            model=self.model,
            prompt_version=CASE_SUMMARY.version,
            payload=payload.model_dump(mode="json"),
            usage=usage,
        )

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        data, usage = await self._complete(
            EXTRACTION, EXTRACTION.render_user(text=text, language=language.value)
        )
        try:
            payload = _ExtractionPayload.model_validate(data)
        except ValidationError as exc:
            raise AIMalformedOutput(str(exc), provider=self.name) from exc
        return ExtractionResult(
            provider=self.name,
            model=self.model,
            prompt_version=EXTRACTION.version,
            facts=[
                ExtractedFact(
                    category=f.category,
                    value=f.value,
                    original_text=f.original_text,
                    evidence=Evidence(quote=f.evidence.quote, start=f.evidence.start, end=f.evidence.end),
                    subject=f.subject,
                    subject_evidence=f.subject_evidence,
                    confidence=f.confidence,
                )
                for f in payload.facts
            ],
            needs_review=payload.needs_review,
            unparsed=payload.unparsed,
            usage=usage,
        )


def strip_unsupported_schema_keys(schema: dict[str, Any], drop: tuple[str, ...]) -> dict[str, Any]:
    """Copy of a JSON schema without keys a provider rejects."""
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in drop:
            continue
        if isinstance(value, dict):
            out[key] = strip_unsupported_schema_keys(value, drop)
        elif isinstance(value, list):
            out[key] = [strip_unsupported_schema_keys(v, drop) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    return out
