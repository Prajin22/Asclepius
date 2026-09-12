"""A local server that speaks the real OpenAI Responses wire format.

It lets the actual `OpenAIProvider` be exercised over a real socket — real
HTTP, real JSON, real parsing, real token accounting — without credentials or
spend. Used by `tests/test_ai_openai_smoke.py` and by
`scripts/ai_smoke_test.py --emulate`.

It is a test double for the *transport*, not for CareBridge: the pipeline,
evidence gate and storage are the production ones.
"""

import json
import re
import threading
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import sleep
from typing import Any

INPUT_TOKENS = 123
OUTPUT_TOKENS = 45

# What the emulated vision model "reads" from a synthetic page image.
TRANSCRIBED_PAGE = "Hemoglobin: 13.5 g/dL\nBlood pressure: 150/95 mmHg"


class EmulatorMode(StrEnum):
    OK = "ok"
    ERROR_500 = "error_500"
    AUTH_401 = "auth_401"
    RATE_429 = "rate_429"
    MALFORMED = "malformed"  # 200 with text that is not JSON
    WRONG_SCHEMA = "wrong_schema"  # 200 with JSON that violates the schema
    FABRICATED = "fabricated"  # valid shape, evidence that is not in the source
    SLOW = "slow"


_SOURCE = re.compile(r"<<<\n(.*)\n>>>", re.DOTALL)


def _source_text(user_content: str) -> str:
    """The patient text the prompt wrapped, as a real model would see it."""
    match = _SOURCE.search(user_content or "")
    return match.group(1) if match else (user_content or "")


def _user_text(content: Any) -> str:
    """Text of a user message; multimodal content is a list of input_text / input_image parts."""
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if part.get("type") == "input_text")
    return content or ""


def _payload_for(schema_name: str, user_content: str) -> dict[str, Any]:
    source = _source_text(user_content)
    if schema_name.startswith("document_transcription"):
        return {"text": TRANSCRIBED_PAGE, "language": "en", "unreadable": []}
    if schema_name.startswith("language_detection"):
        return {"language": "ta", "confidence": 0.95}
    if schema_name.startswith("normalization"):
        return {"normalized_english": "Patient reports headache. Reported duration: 2 days.", "unparsed": []}
    # Extraction: quote a real substring so the evidence gate can validate it.
    quote = source.strip()[:12]
    return {
        "facts": [
            {
                "category": "symptom",
                "value": "headache",
                "original_text": quote,
                "evidence": {"quote": quote, "start": None, "end": None},
                "subject": "self",
                "subject_evidence": None,
                "confidence": 0.9,
            }
        ],
        "needs_review": [],
        "unparsed": [],
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "OpenAIEmulator/1.0"

    def log_message(self, *args):  # keep test output clean
        return

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        # Header names are case-insensitive on the wire (httpx sends lowercase).
        headers = {name.lower(): value for name, value in self.headers.items()}
        self.server.requests.append({"path": self.path, "headers": headers, "body": body})

        mode = self.server.mode
        if mode is EmulatorMode.AUTH_401:
            return self._send(401, {"error": {"message": "invalid api key"}})
        if mode is EmulatorMode.RATE_429:
            return self._send(429, {"error": {"message": "rate limit"}})
        if mode is EmulatorMode.ERROR_500:
            return self._send(500, {"error": {"message": "server error"}})
        if mode is EmulatorMode.SLOW:
            sleep(self.server.slow_seconds)

        fmt = ((body.get("text") or {}).get("format") or {})
        schema_name = fmt.get("name", "")
        user_content = ""
        for message in body.get("input", []):
            if message.get("role") == "user":
                user_content = _user_text(message.get("content"))

        if mode is EmulatorMode.MALFORMED:
            text = "Sorry, I cannot help with that."
        elif mode is EmulatorMode.WRONG_SCHEMA:
            text = json.dumps({"facts": [{"category": "diagnosis", "value": "pneumonia"}],
                               "needs_review": [], "unparsed": []})
        elif mode is EmulatorMode.FABRICATED and schema_name.startswith("medical_extraction"):
            text = json.dumps({
                "facts": [{
                    "category": "medication",
                    "value": "insulin 10 units",
                    "original_text": None,
                    "evidence": {"quote": "I inject insulin every night", "start": None, "end": None},
                    "subject": "self",
                    "subject_evidence": None,
                    "confidence": 0.9,
                }],
                "needs_review": [], "unparsed": [],
            })
        else:
            text = json.dumps(_payload_for(schema_name, user_content), ensure_ascii=False)

        self._send(200, {
            "id": "resp_emulated",
            "model": body.get("model", "emulated"),
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": INPUT_TOKENS, "output_tokens": OUTPUT_TOKENS,
                      "total_tokens": INPUT_TOKENS + OUTPUT_TOKENS},
        })


class EmulatorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, mode: EmulatorMode = EmulatorMode.OK, slow_seconds: float = 5.0):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.mode = mode
        self.slow_seconds = slow_seconds
        self.requests: list[dict[str, Any]] = []

    @property
    def base_url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/v1"


def start(mode: EmulatorMode = EmulatorMode.OK, slow_seconds: float = 5.0) -> EmulatorServer:
    server = EmulatorServer(mode, slow_seconds)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
