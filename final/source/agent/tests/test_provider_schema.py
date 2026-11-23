import copy
import json

import pytest

from agent.catalogue_retrieval import DECISION
from agent.llm.config import LLMConfigurationError
from agent.llm.provider_schema import inline_schema_references, openrouter_response_schema


def test_catalogue_schema_expands_nested_references_without_losing_constraints():
    original = DECISION.json_schema()
    before = copy.deepcopy(original)
    result = inline_schema_references(original)
    assert original == before
    assert all(key not in json.dumps(result) for key in ['"$ref"', '"$defs"', '"discriminator"'])
    search = result["oneOf"][0]
    assert search["properties"]["kind"]["const"] == "search"
    assert search["additionalProperties"] is False
    query = search["properties"]["query"]
    assert query["properties"]["requirements"]["maxItems"] == 20
    money = query["properties"]["requirements"]["items"]["oneOf"][0]
    assert money["properties"]["amount"]["pattern"] == r"^(?:0|[1-9]\d*)(?:\.\d{1,2})?$"
    assert money["required"] == ["field", "op", "amount", "currency"]


@pytest.mark.parametrize("ref", ["#/$defs/missing", "#/$defs/cycle", "https://example.test/schema"])
def test_unresolvable_or_cyclic_schemas_fail_locally(ref):
    with pytest.raises(LLMConfigurationError):
        inline_schema_references({"$defs": {"cycle": {"$ref": ref}}, "$ref": ref})


def test_reference_sibling_constraints_are_intersected_instead_of_overwriting():
    result = inline_schema_references(
        {
            "$defs": {"limit": {"type": "integer", "maximum": 10}},
            "$ref": "#/$defs/limit",
            "minimum": 2,
        }
    )
    assert result == {"allOf": [{"type": "integer", "maximum": 10}, {"minimum": 2}]}


def test_provider_structural_schema_keeps_types_while_local_validator_enforces_bounds():
    schema = openrouter_response_schema(DECISION.json_schema())
    query = schema["oneOf"][0]["properties"]["query"]
    assert query["properties"]["query"]["type"] == "string"
    assert "maxLength" not in query["properties"]["query"]
    assert "maxItems" not in query["properties"]["requirements"]
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DECISION.validate_json(json.dumps({"kind": "search", "query": {"query": "x" * 1025}}))


def test_provider_literals_use_single_value_enums_including_nested_operations():
    from agent.llm.intent_wire import wire_intent_adapter

    schema = openrouter_response_schema(wire_intent_adapter.json_schema())
    cart = next(b for b in schema["anyOf"] if b["title"] == "CartDecision")
    assert cart["properties"]["intent"]["enum"] == ["cart_edit"]
    assert cart["properties"]["v"]["type"] == "integer"
    assert "enum" not in cart["properties"]["v"]
    assert "const" not in cart["properties"]["v"]
    # A property named const is application data, not a schema keyword to rewrite.
    named = openrouter_response_schema(
        {"type": "object", "properties": {"const": {"const": "value", "type": "string"}}}
    )
    assert named["properties"]["const"] == {"type": "string", "enum": ["value"]}
    with pytest.raises(LLMConfigurationError, match="contradictory literals"):
        openrouter_response_schema({"type": "string", "const": "add", "enum": ["remove"]})


@pytest.mark.parametrize("version", [7, 8, 9, 10, 11])
def test_live_validation_retains_version_policy_without_provider_numeric_enum(version):
    from agent.llm.intent_pipeline import validate_live_response

    raw = json.dumps(
        dict(
            v=version,
            intent="help",
            constraints={},
            language="en",
            dialect="english",
            missing_fields=[],
            needs_clarification=False,
        )
    )
    if version in {8, 9, 10}:
        assert validate_live_response(raw).v == version
    else:
        with pytest.raises(ValueError):
            validate_live_response(raw)
