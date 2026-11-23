"""Expand local schema references for providers that lose definition scopes."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from agent.llm.config import LLMConfigurationError


def _map_subschemas(node, visit):
    """Visit schema positions only, preserving property names and literal metadata."""
    result = {}
    for key, value in node.items():
        if key in {"properties", "patternProperties", "dependentSchemas", "$defs"}:
            result[key] = {name: visit(child) for name, child in value.items()}
        elif key in {"allOf", "anyOf", "oneOf", "prefixItems"}:
            result[key] = [visit(child) for child in value]
        elif key in {
            "items",
            "additionalProperties",
            "contains",
            "not",
            "if",
            "then",
            "else",
            "propertyNames",
            "unevaluatedProperties",
            "unevaluatedItems",
        }:
            result[key] = visit(value)
        else:
            result[key] = deepcopy(value)
    return result


def openrouter_response_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Keep decoding structural; apply value/resource bounds in the local validator.

    Gemini rejected the expanded catalogue schema with 'too many states for serving'.
    Array/string bounds and value matchers multiply the provider grammar's states.
    Types, required fields, alternatives and enums still guide model generation.
    """
    local_constraints = {
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    }

    def structural(value):
        if not isinstance(value, dict):
            return value
        # The pinned Gemini route supports string enums. Numeric enums caused
        # empty decisions in live probes; their values remain locally validated.
        if "const" in value:
            if "enum" in value and value["const"] not in value["enum"]:
                raise LLMConfigurationError("Provider schema has contradictory literals")
            value = {**value, "enum": [value["const"]]}
            value.pop("const")
        if "enum" in value and any(not isinstance(item, str) for item in value["enum"]):
            value = {key: item for key, item in value.items() if key != "enum"}
        result = _map_subschemas(
            {key: item for key, item in value.items() if key not in local_constraints}, structural
        )
        # A property's title only repeats its name. The schema is copied into every
        # branch, and the request must stay inside the evaluation budget size bound.
        for child in result.get("properties", {}).values():
            if isinstance(child, dict):
                child.pop("title", None)
        return result

    return structural(inline_schema_references(schema))


def inline_schema_references(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the wire schema without changing the application's response validator.

    OpenRouter's Gemini route rejected the catalogue union's definition references.
    Keep constraints inline and omit discriminator annotations whose mappings would
    otherwise still reference removed definitions. Cycles/remote refs fail locally.
    """
    visited = 0

    def expand(value, refs=()):
        nonlocal visited
        visited += 1
        if visited > 10000 or len(refs) > 32:
            raise LLMConfigurationError("Provider schema expansion exceeds its bound")
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/$defs/") or ref in refs:
                raise LLMConfigurationError("Provider schema requires acyclic local definitions")
            target = schema
            try:
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            except (KeyError, TypeError) as error:
                raise LLMConfigurationError(
                    "Provider schema contains an unresolved reference"
                ) from error
            resolved = expand(target, (*refs, ref))
            siblings = {key: item for key, item in value.items() if key != "$ref"}
            # JSON Schema siblings intersect with the referenced schema; never overwrite it.
            return {"allOf": [resolved, expand(siblings, refs)]} if siblings else resolved
        return _map_subschemas(
            {key: item for key, item in value.items() if key not in {"$defs", "discriminator"}},
            lambda child: expand(child, refs),
        )

    return expand(dict(schema))
