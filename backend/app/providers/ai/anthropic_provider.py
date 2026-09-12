"""Anthropic adapter — Messages API, schema enforced through a strict tool.

Verified against the Anthropic Messages API reference (POST /v1/messages,
headers `x-api-key` + `anthropic-version: 2023-06-01`). Structured output is
obtained with a single `strict` tool plus a forced `tool_choice`, so the model
must answer with arguments matching our JSON schema.

Note for future model changes: the Fable/Mythos family rejects forced
`tool_choice`; those models need `tool_choice: {"type": "auto"}` plus an
instruction, or the `output_config.format` structured-output parameter.
Model selection stays in configuration (`AI_MODEL`).
"""

from typing import Any

from app.providers.ai.http_base import HttpJSONProvider, strip_unsupported_schema_keys
from app.providers.ai.prompts import Prompt

DEFAULT_MODEL = "claude-opus-5"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 4096
# Strict tool schemas reject numeric range keywords — the live API answers 400
# "For 'number' type, properties maximum, minimum are not supported". Ranges are
# still enforced when the response is validated (http_base payload models).
_UNSUPPORTED_SCHEMA_KEYS = ("minimum", "maximum")


class AnthropicProvider(HttpJSONProvider):
    name = "anthropic"

    def _build_request(self, prompt: Prompt, user_text: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        tool_name = prompt.version
        return (
            f"{self._base_url}/messages",
            {
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            {
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "system": prompt.system,
                "messages": [{"role": "user", "content": user_text}],
                "tools": [
                    {
                        "name": tool_name,
                        "description": "Return the structured result for this operation.",
                        "input_schema": strip_unsupported_schema_keys(prompt.schema, _UNSUPPORTED_SCHEMA_KEYS),
                        "strict": True,
                    }
                ],
                "tool_choice": {"type": "tool", "name": tool_name},
            },
        )

    def _build_image_request(self, prompt: Prompt, user_text: str, image_png_b64: str):
        # Messages API image content block (base64 source), then the instruction text.
        url, headers, payload = self._build_request(prompt, user_text)
        payload["messages"][0]["content"] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_png_b64}},
            {"type": "text", "text": user_text},
        ]
        return url, headers, payload

    def _parse_response(self, body: dict[str, Any]):
        from app.providers.ai.base import AIUsage
        from app.providers.ai.errors import AIMalformedOutput

        if body.get("stop_reason") == "refusal":
            raise AIMalformedOutput("Anthropic declined the request", provider=self.name)
        payload: dict[str, Any] | None = None
        for block in body.get("content", []) or []:
            if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
                payload = block["input"]
                break
        if payload is None:
            raise AIMalformedOutput("Anthropic response contained no tool_use block", provider=self.name)
        usage_raw = body.get("usage") or {}
        usage = AIUsage(
            input_tokens=usage_raw.get("input_tokens"),
            output_tokens=usage_raw.get("output_tokens"),
        )
        return payload, usage
