"""OpenAI adapter — Responses API with strict JSON-schema structured output.

Verified against https://developers.openai.com/api/docs/guides/structured-outputs
(POST /v1/responses, `text.format` = {type: json_schema, name, schema, strict}).
The model id is configuration (`AI_MODEL`), never hard-coded into domain logic.
"""

from typing import Any

from app.providers.ai.http_base import HttpJSONProvider
from app.providers.ai.prompts import Prompt

DEFAULT_MODEL = "gpt-6-astra"


class OpenAIProvider(HttpJSONProvider):
    name = "openai"

    def _build_request(self, prompt: Prompt, user_text: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        return (
            f"{self._base_url}/responses",
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            {
                "model": self.model,
                "input": [
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": user_text},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": prompt.version,
                        "schema": prompt.schema,
                        "strict": True,
                    }
                },
            },
        )

    def _build_image_request(self, prompt: Prompt, user_text: str, image_png_b64: str):
        # Responses API image input: input_text + input_image with a base64 data URL.
        url, headers, payload = self._build_request(prompt, user_text)
        payload["input"][1]["content"] = [
            {"type": "input_text", "text": user_text},
            {"type": "input_image", "image_url": f"data:image/png;base64,{image_png_b64}", "detail": "high"},
        ]
        return url, headers, payload

    def _parse_response(self, body: dict[str, Any]):
        from app.providers.ai.base import AIUsage
        from app.providers.ai.errors import AIMalformedOutput

        text: str | None = None
        for item in body.get("output", []) or []:
            if item.get("type") != "message":
                continue
            for block in item.get("content", []) or []:
                if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                    text = block["text"]
                    break
            if text is not None:
                break
        if text is None:
            raise AIMalformedOutput("OpenAI response contained no output_text", provider=self.name)
        usage_raw = body.get("usage") or {}
        usage = AIUsage(
            input_tokens=usage_raw.get("input_tokens"),
            output_tokens=usage_raw.get("output_tokens"),
        )
        return self._loads(text, self.name), usage
