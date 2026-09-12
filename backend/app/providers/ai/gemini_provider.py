"""Gemini adapter — generateContent with a response schema.

Verified against https://ai.google.dev/api/generate-content
(POST /v1beta/models/{model}:generateContent, `generationConfig.responseMimeType`
+ `responseSchema`, usage in `usageMetadata`).

The API key is sent in the `x-goog-api-key` header rather than the documented
`?key=` query parameter: query strings end up in proxy and server logs, and
credentials must never be logged (docs/SECURITY.md).
"""

from typing import Any

from app.providers.ai.http_base import HttpJSONProvider, strip_unsupported_schema_keys
from app.providers.ai.prompts import Prompt

DEFAULT_MODEL = "gemini-3.8-flash"
# Gemini's schema dialect does not accept these JSON-Schema keywords.
_UNSUPPORTED_SCHEMA_KEYS = ("additionalProperties", "$schema")


class GeminiProvider(HttpJSONProvider):
    name = "gemini"

    def _build_request(self, prompt: Prompt, user_text: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        return (
            f"{self._base_url}/models/{self.model}:generateContent",
            {"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            {
                "systemInstruction": {"parts": [{"text": prompt.system}]},
                "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": strip_unsupported_schema_keys(prompt.schema, _UNSUPPORTED_SCHEMA_KEYS),
                },
            },
        )

    def _build_image_request(self, prompt: Prompt, user_text: str, image_png_b64: str):
        # generateContent inline image part (inline_data: mime_type + base64 data), then the text.
        url, headers, payload = self._build_request(prompt, user_text)
        payload["contents"][0]["parts"] = [
            {"inline_data": {"mime_type": "image/png", "data": image_png_b64}},
            {"text": user_text},
        ]
        return url, headers, payload

    def _parse_response(self, body: dict[str, Any]):
        from app.providers.ai.base import AIUsage
        from app.providers.ai.errors import AIMalformedOutput

        candidates = body.get("candidates") or []
        text: str | None = None
        for candidate in candidates:
            for part in (candidate.get("content") or {}).get("parts", []) or []:
                if isinstance(part.get("text"), str):
                    text = part["text"]
                    break
            if text is not None:
                break
        if text is None:
            raise AIMalformedOutput("Gemini response contained no text part", provider=self.name)
        meta = body.get("usageMetadata") or {}
        usage = AIUsage(
            input_tokens=meta.get("promptTokenCount"),
            output_tokens=meta.get("candidatesTokenCount"),
        )
        return self._loads(text, self.name), usage
