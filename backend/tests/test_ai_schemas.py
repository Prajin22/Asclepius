"""Static checks that our response schemas are accepted by strict structured output.

A real provider rejects a non-conforming schema with a 400 before the model
ever runs — a failure no stub transport or emulator can reveal. These rules
catch that class of bug without credentials or spend.
"""

import re
from collections.abc import Iterator
from typing import Any

import pytest

from app.providers.ai.gemini_provider import _UNSUPPORTED_SCHEMA_KEYS
from app.providers.ai.http_base import strip_unsupported_schema_keys
from app.providers.ai.prompts import PROMPTS

SCHEMAS = [pytest.param(prompt.schema, id=name) for name, prompt in PROMPTS.items()]


def objects(node: Any, path: str = "$") -> Iterator[tuple[str, dict]]:
    """Every object-typed node in a JSON schema, with its path."""
    if isinstance(node, dict):
        types = node.get("type")
        is_object = types == "object" or (isinstance(types, list) and "object" in types) or "properties" in node
        if is_object:
            yield path, node
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop, child in value.items():
                    yield from objects(child, f"{path}.{prop}")
            elif key == "items":
                yield from objects(value, f"{path}[]")


@pytest.mark.parametrize("schema", SCHEMAS)
def test_every_object_is_closed(schema):
    for path, node in objects(schema):
        assert node.get("additionalProperties") is False, f"{path} must set additionalProperties: false"


@pytest.mark.parametrize("schema", SCHEMAS)
def test_every_property_is_required(schema):
    """Strict mode: optional fields are nullable, never omitted from `required`."""
    for path, node in objects(schema):
        properties = set(node.get("properties", {}))
        required = set(node.get("required", []))
        assert properties == required, f"{path}: not required: {sorted(properties - required)}"


@pytest.mark.parametrize("schema", SCHEMAS)
def test_root_is_an_object(schema):
    assert schema["type"] == "object"


def test_optional_values_are_expressed_as_nullable_types():
    evidence = PROMPTS["extraction"].schema["properties"]["facts"]["items"]["properties"]["evidence"]
    for field in ("start", "end"):
        assert "null" in evidence["properties"][field]["type"]
    fact = PROMPTS["extraction"].schema["properties"]["facts"]["items"]["properties"]
    for field in ("original_text", "subject_evidence", "confidence"):
        assert "null" in fact[field]["type"], field


def test_extraction_schema_cannot_express_a_diagnosis():
    categories = PROMPTS["extraction"].schema["properties"]["facts"]["items"]["properties"]["category"]["enum"]
    assert "diagnosis" not in categories
    assert set(categories) == {"symptom", "duration", "medication", "allergy", "medical_history", "measurement"}


def test_prompt_versions_are_explicit():
    versions = [p.version for p in PROMPTS.values()]
    assert len(set(versions)) == len(versions)
    assert all(re.fullmatch(r"[a-z_]+_v\d+", v) for v in versions)


def test_gemini_variant_drops_keywords_it_rejects():
    for prompt in PROMPTS.values():
        stripped = strip_unsupported_schema_keys(prompt.schema, _UNSUPPORTED_SCHEMA_KEYS)
        assert "additionalProperties" not in repr(stripped)
        assert prompt.schema.get("additionalProperties") is False  # original untouched
