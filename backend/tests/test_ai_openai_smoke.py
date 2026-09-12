"""The real OpenAI adapter, end to end over real HTTP.

A local server speaks the documented `/v1/responses` wire format, so the
production adapter, pipeline, evidence gate and storage all run for real —
without credentials or spend. Synthetic data only.

`scripts/ai_smoke_test.py --provider openai` runs the same checks against the
real API once a key is configured.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import AIArtifact
from app.models.enums import AIArtifactStatus, AIOperation
from app.providers.ai import build_ai_provider
from tests.conftest import API, create_problem, process_record

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from openai_emulator import INPUT_TOKENS, OUTPUT_TOKENS, EmulatorMode, start  # noqa: E402

TAMIL = "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது."
# Deterministic pricing so the cost assertion is exact.
PRICE_IN, PRICE_OUT = 1.0, 2.0
EXPECTED_COST = round(INPUT_TOKENS / 1_000_000 * PRICE_IN + OUTPUT_TOKENS / 1_000_000 * PRICE_OUT, 6)


@pytest.fixture
def openai_against_emulator(monkeypatch):
    """Point the *real* OpenAI provider at a local server, per test mode."""
    servers = []

    def _use(mode: EmulatorMode = EmulatorMode.OK, **overrides):
        server = start(mode, slow_seconds=2.0)
        servers.append(server)
        settings = get_settings().model_copy(
            update={
                "demo_mode": False,
                "ai_provider": "openai",
                "ai_model": "gpt-6-astra",
                "openai_api_key": "test-key-not-real",
                "openai_base_url": server.base_url,
                "ai_price_input_per_mtok": PRICE_IN,
                "ai_price_output_per_mtok": PRICE_OUT,
                **overrides,
            }
        )
        provider = build_ai_provider(settings)
        monkeypatch.setattr("app.services.ai_pipeline.get_ai_provider", lambda: provider)
        monkeypatch.setattr("app.services.ai_pipeline.get_settings", lambda: settings)
        return server

    yield _use
    for server in servers:
        server.shutdown()


def test_happy_path_through_the_real_adapter(client, db, consented_patient, openai_against_emulator):
    server = openai_against_emulator()
    record = create_problem(client, consented_patient, TAMIL, "ta")

    body = process_record(client, consented_patient, record["id"]).json()

    assert body["status"] == "ok"
    assert body["provider"] == "openai" and body["is_external_provider"] is True
    assert body["detected_language"] == "ta"
    assert body["normalized_english"].startswith("Patient reports headache")
    assert body["facts"], "expected the extracted fact to survive the evidence gate"
    fact = body["facts"][0]
    assert fact["value"] == "headache"
    assert fact["evidence_quote"] in TAMIL
    assert fact["validation_status"] == "validated"
    assert body["original_text"] == TAMIL  # layer 1 untouched


def test_request_shape_on_the_wire(client, consented_patient, openai_against_emulator):
    server = openai_against_emulator()
    record = create_problem(client, consented_patient, TAMIL, "ta")
    process_record(client, consented_patient, record["id"])

    assert len(server.requests) == 3  # detect, normalise, extract
    first = server.requests[0]
    assert first["path"] == "/v1/responses"
    assert first["headers"]["authorization"] == "Bearer test-key-not-real"
    fmt = first["body"]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert first["body"]["model"] == "gpt-6-astra"
    # The prompt version travels with the request, so artifacts stay traceable.
    assert fmt["name"].startswith("language_detection")
    assert server.requests[2]["body"]["text"]["format"]["name"].startswith("medical_extraction")


def test_token_accounting_and_cost(client, db, consented_patient, openai_against_emulator):
    openai_against_emulator()
    record = create_problem(client, consented_patient, TAMIL, "ta")
    body = process_record(client, consented_patient, record["id"]).json()

    for run in body["runs"]:
        assert run["input_tokens"] == INPUT_TOKENS
        assert run["output_tokens"] == OUTPUT_TOKENS
        assert run["estimated_cost_usd"] == pytest.approx(EXPECTED_COST)
        assert run["latency_ms"] is not None and run["latency_ms"] >= 0
    artifacts = list(db.scalars(select(AIArtifact)))
    assert len(artifacts) == 3
    assert all(a.input_tokens == INPUT_TOKENS for a in artifacts)
    assert body["usage"]["spend_last_day_usd"] == pytest.approx(EXPECTED_COST * 3)


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        (EmulatorMode.AUTH_401, "ai_credentials_missing"),
        (EmulatorMode.RATE_429, "ai_provider_unavailable"),
        (EmulatorMode.ERROR_500, "ai_provider_unavailable"),
        (EmulatorMode.MALFORMED, "ai_malformed_output"),
        (EmulatorMode.WRONG_SCHEMA, "ai_malformed_output"),
    ],
)
def test_provider_errors_degrade_without_fabricating(
    client, db, consented_patient, openai_against_emulator, mode, expected_code
):
    openai_against_emulator(mode)
    record = create_problem(client, consented_patient, TAMIL, "ta")

    body = process_record(client, consented_patient, record["id"]).json()

    assert body["status"] == "unavailable"
    assert body["error_code"] == expected_code
    assert body["facts"] == []
    assert body["original_text"] == TAMIL  # the patient's information is intact
    failed = db.scalar(select(AIArtifact).where(AIArtifact.status == AIArtifactStatus.FAILED))
    assert failed is not None and failed.error_code == expected_code


def test_timeout_is_enforced_against_a_slow_provider(client, consented_patient, openai_against_emulator):
    openai_against_emulator(EmulatorMode.SLOW, ai_timeout_seconds=0.3, ai_max_attempts=1)
    record = create_problem(client, consented_patient, TAMIL, "ta")
    body = process_record(client, consented_patient, record["id"]).json()
    assert body["status"] == "unavailable"
    assert body["error_code"] == "ai_timeout"


def test_fabricated_evidence_is_rejected_even_from_a_real_provider(
    client, db, consented_patient, openai_against_emulator
):
    openai_against_emulator(EmulatorMode.FABRICATED)
    record = create_problem(client, consented_patient, TAMIL, "ta")
    body = process_record(client, consented_patient, record["id"]).json()

    assert body["status"] == "ok"
    assert body["facts"] == []  # the quote was not in the source
    extraction = db.scalar(
        select(AIArtifact).where(AIArtifact.artifact_type == AIOperation.EXTRACTION.value)
    )
    assert extraction.content["facts"], "the provider did return a fact"
