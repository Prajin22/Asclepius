"""Real provider adapters: request shape and response handling, without network.

The wire formats are exercised against a stub transport so a broken adapter is
caught without credentials or spend.
"""

import json

import httpx
import pytest

from app.core.languages import LanguageCode
from app.providers.ai.anthropic_provider import AnthropicProvider
from app.providers.ai.errors import AICredentialsMissing, AIMalformedOutput, AIProviderUnavailable
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.openai_provider import OpenAIProvider
from tests.conftest import run_async

EXTRACTION_JSON = {
    "facts": [
        {
            "category": "symptom",
            "value": "headache",
            "original_text": "தலைவலி",
            "evidence": {"quote": "தலைவலி", "start": None, "end": None},
            "confidence": 0.9,
        }
    ],
    "needs_review": [],
    "unparsed": [],
}


def transport(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_openai_request_shape_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(EXTRACTION_JSON)}]}],
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
        )

    provider = OpenAIProvider("gpt-6-astra", "sk-test", "https://api.openai.test/v1", client=transport(handler))
    result = run_async(provider.extract_medical_information("தலைவலி", LanguageCode.TA))

    assert seen["url"] == "https://api.openai.test/v1/responses"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["text"]["format"]["type"] == "json_schema"
    assert seen["body"]["text"]["format"]["strict"] is True
    assert result.facts[0].value == "headache"
    assert result.usage.input_tokens == 120 and result.usage.output_tokens == 40


def test_anthropic_request_shape_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "tool_use", "name": "medical_extraction_v1", "input": EXTRACTION_JSON}],
                "usage": {"input_tokens": 200, "output_tokens": 60},
                "stop_reason": "tool_use",
            },
        )

    provider = AnthropicProvider("claude-opus-5", "key", "https://api.anthropic.test/v1", client=transport(handler))
    result = run_async(provider.extract_medical_information("தலைவலி", LanguageCode.TA))

    assert seen["url"] == "https://api.anthropic.test/v1/messages"
    assert seen["headers"]["x-api-key"] == "key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["tool_choice"]["type"] == "tool"
    assert seen["body"]["tools"][0]["strict"] is True
    assert result.facts[0].category.value == "symptom"
    assert result.usage.estimated_cost_usd is not None  # priced model


def test_gemini_request_shape_and_key_is_not_in_the_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key_header"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(EXTRACTION_JSON)}]}}],
                "usageMetadata": {"promptTokenCount": 90, "candidatesTokenCount": 25},
            },
        )

    provider = GeminiProvider("gemini-3.8-flash", "secret", "https://gemini.test/v1beta", client=transport(handler))
    result = run_async(provider.extract_medical_information("தலைவலி", LanguageCode.TA))

    assert seen["url"] == "https://gemini.test/v1beta/models/gemini-3.8-flash:generateContent"
    assert "secret" not in seen["url"]  # never in a URL that could be logged
    assert seen["key_header"] == "secret"
    config = seen["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "additionalProperties" not in json.dumps(config["responseSchema"])
    assert result.facts[0].value == "headache"


@pytest.mark.parametrize("status", [500, 503, 429])
def test_server_errors_map_to_unavailable(status):
    provider = OpenAIProvider(
        "m", "k", "https://x.test", client=transport(lambda r: httpx.Response(status, json={"error": "x"}))
    )
    with pytest.raises(AIProviderUnavailable):
        run_async(provider.detect_language("hello"))


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_are_reported_as_credentials_problems(status):
    provider = OpenAIProvider(
        "m", "k", "https://x.test", client=transport(lambda r: httpx.Response(status, json={"error": "x"}))
    )
    with pytest.raises(AICredentialsMissing):
        run_async(provider.detect_language("hello"))


def test_non_json_content_is_malformed():
    provider = OpenAIProvider(
        "m",
        "k",
        "https://x.test",
        client=transport(
            lambda r: httpx.Response(
                200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "sorry!"}]}]}
            )
        ),
    )
    with pytest.raises(AIMalformedOutput):
        run_async(provider.detect_language("hello"))


def test_schema_violation_is_malformed():
    bad = {"facts": [{"category": "diagnosis", "value": "pneumonia", "evidence": {"quote": "x"}}],
           "needs_review": [], "unparsed": []}
    provider = GeminiProvider(
        "m",
        "k",
        "https://x.test",
        client=transport(
            lambda r: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(bad)}]}}]})
        ),
    )
    with pytest.raises(AIMalformedOutput):
        run_async(provider.extract_medical_information("x", LanguageCode.EN))


def test_provider_requires_credentials():
    with pytest.raises(AICredentialsMissing):
        OpenAIProvider("m", None, "https://x.test")


def test_unknown_language_code_from_provider_becomes_unknown():
    provider = AnthropicProvider(
        "m",
        "k",
        "https://x.test",
        client=transport(
            lambda r: httpx.Response(
                200,
                json={"content": [{"type": "tool_use", "input": {"language": "elvish", "confidence": 0.9}}],
                      "usage": {}},
            )
        ),
    )
    assert run_async(provider.detect_language("mellon")).language is None


def test_anthropic_tool_schema_carries_no_numeric_bounds():
    """Found by the first live run: strict tool schemas with minimum/maximum get HTTP 400."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"content": [{"type": "tool_use", "input": {"language": "en", "confidence": 0.9}}], "usage": {}}
        )

    provider = AnthropicProvider("claude-opus-5", "key", "https://api.anthropic.test/v1", client=transport(handler))
    run_async(provider.detect_language("hello"))

    tool = seen["body"]["tools"][0]
    assert tool["strict"] is True
    assert "minimum" not in json.dumps(tool["input_schema"]) and "maximum" not in json.dumps(tool["input_schema"])


@pytest.mark.parametrize("confidence", [7, -0.5])
def test_confidence_outside_zero_to_one_is_malformed(confidence):
    """The range is enforced on the response even when the request schema cannot state it."""
    provider = AnthropicProvider(
        "m",
        "k",
        "https://x.test",
        client=transport(
            lambda r: httpx.Response(
                200,
                json={"content": [{"type": "tool_use", "input": {"language": "en", "confidence": confidence}}],
                      "usage": {}},
            )
        ),
    )
    with pytest.raises(AIMalformedOutput):
        run_async(provider.detect_language("hello"))
