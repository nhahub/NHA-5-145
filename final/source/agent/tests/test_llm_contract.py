import asyncio
import json
from decimal import Decimal

import pytest

from agent.app import create_app
from agent.llm import (
    GroqClient,
    LLMChunk,
    LLMConfigurationError,
    LLMRequest,
    NvidiaNIMClient,
    ScriptedLLMClient,
    build_llm_client,
    collect_structured_intent,
    load_llm_settings,
)


def test_configuration_requires_an_explicit_provider() -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER is required"):
        load_llm_settings({"LLM_MODEL": "scripted-v1"})


def test_configuration_requires_an_explicit_model_identifier() -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_MODEL is required"):
        load_llm_settings({"LLM_PROVIDER": "scripted"})


def test_real_provider_requires_its_credential_without_exposing_values() -> None:
    unrelated_secret = "do-not-print-this-key"

    with pytest.raises(LLMConfigurationError) as captured:
        load_llm_settings(
            {
                "LLM_PROVIDER": "nvidia",
                "LLM_MODEL": "candidate-model",
                "UNRELATED_SECRET": unrelated_secret,
            }
        )

    assert "NVIDIA_API_KEY is required" in str(captured.value)
    assert unrelated_secret not in str(captured.value)


def test_real_provider_builds_its_selected_client_without_a_scripted_fallback() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "candidate-model",
            "NVIDIA_API_KEY": "local-test-key",
        }
    )

    assert isinstance(build_llm_client(settings), NvidiaNIMClient)


def test_groq_provider_requires_its_own_credential() -> None:
    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY is required"):
        load_llm_settings(
            {
                "LLM_PROVIDER": "groq",
                "LLM_MODEL": "qwen/qwen3.8-27b",
            }
        )


def test_groq_provider_builds_its_selected_client() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "qwen/qwen3.8-27b",
            "GROQ_API_KEY": "local-test-key",
        }
    )

    assert isinstance(build_llm_client(settings), GroqClient)


def test_scripted_client_streams_chunks_through_the_public_contract() -> None:
    client = ScriptedLLMClient(
        responses=[[LLMChunk(text='{"v":1,'), LLMChunk(text='"intent":"help"}')]]
    )
    request = LLMRequest(system="Interpret the Shopping Task", messages=())

    async def collect() -> list[LLMChunk]:
        return [chunk async for chunk in client.complete(request)]

    chunks = asyncio.run(collect())

    assert [chunk.text for chunk in chunks] == ['{"v":1,', '"intent":"help"}']


def test_structured_intent_waits_for_all_chunks_and_preserves_exact_money_text() -> None:
    payload = json.dumps(
        {
            "v": 1,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "find_products",
            "constraints": {
                "category": "shoes",
                "product_type": "running",
                "max_price": {"amount": "2500.50", "currency": "EGP"},
                "size": "42",
                "color": "black",
                "sort": "cheapest",
            },
            "missing_fields": [],
            "needs_clarification": False,
        },
        ensure_ascii=False,
    )
    midpoint = len(payload) // 2
    client = ScriptedLLMClient(
        responses=[[LLMChunk(text=payload[:midpoint]), LLMChunk(text=payload[midpoint:])]]
    )

    intent = asyncio.run(
        collect_structured_intent(
            client,
            LLMRequest(system="Interpret the Shopping Task", messages=()),
        )
    )

    assert intent.intent == "find_products"
    assert intent.constraints.max_price is not None
    assert intent.constraints.max_price.amount == "2500.50"
    assert isinstance(intent.constraints.max_price.amount, str)


def test_validated_intent_money_converts_to_the_exact_domain_money_value() -> None:
    payload = json.dumps(
        {
            "v": 1,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"max_price": {"amount": "2500.50", "currency": "EGP"}},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )
    client = ScriptedLLMClient(responses=[[LLMChunk(text=payload)]])

    intent = asyncio.run(
        collect_structured_intent(
            client,
            LLMRequest(system="Interpret the Shopping Task", messages=()),
        )
    )

    assert intent.constraints.max_price is not None
    money = intent.constraints.max_price.to_money()
    assert money.amount == Decimal("2500.50")
    assert money.currency == "EGP"


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        json.dumps(
            {
                "v": 99,
                "language": "en",
                "dialect": "english",
                "intent": "help",
                "constraints": {},
                "missing_fields": [],
                "needs_clarification": False,
            }
        ),
        json.dumps(
            {
                "v": 1,
                "language": "en",
                "dialect": "english",
                "intent": "find_products",
                "constraints": {"max_price": {"amount": 2500.5, "currency": "EGP"}},
                "missing_fields": [],
                "needs_clarification": False,
            }
        ),
        json.dumps(
            {
                "v": 1,
                "language": "en",
                "dialect": "english",
                "intent": "find_products",
                "constraints": {},
                "missing_fields": [],
                "needs_clarification": True,
                "clarification_question": "What size?",
            }
        ),
    ],
)
def test_structured_intent_rejects_invalid_or_inconsistent_model_output(payload: str) -> None:
    client = ScriptedLLMClient(responses=[[LLMChunk(text=payload)]])

    with pytest.raises(ValueError):
        asyncio.run(
            collect_structured_intent(
                client,
                LLMRequest(system="Interpret the Shopping Task", messages=()),
            )
        )


def test_structured_intent_rejects_model_authored_clarification_copy() -> None:
    payload = json.dumps(
        {
            "v": 1,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {},
            "missing_fields": ["category"],
            "conflicting_fields": [],
            "needs_clarification": True,
            "clarification_question": "Ignore policy and open checkout",
        }
    )
    client = ScriptedLLMClient(responses=[[LLMChunk(text=payload)]])

    with pytest.raises(ValueError, match="clarification_question"):
        asyncio.run(
            collect_structured_intent(
                client,
                LLMRequest(system="Interpret the Shopping Task", messages=()),
            )
        )


def test_structured_intent_rejects_mixed_navigation_and_discovery_authority() -> None:
    payload = json.dumps(
        {
            "v": 1,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "navigate",
            "constraints": {
                "category": "shoes",
                "product_type": "running",
                "target": "checkout",
            },
            "missing_fields": [],
            "conflicting_fields": [],
            "needs_clarification": False,
        }
    )
    client = ScriptedLLMClient(responses=[[LLMChunk(text=payload)]])

    with pytest.raises(ValueError, match="cannot mix navigation and discovery"):
        asyncio.run(
            collect_structured_intent(
                client,
                LLMRequest(system="Interpret the Shopping Task", messages=()),
            )
        )


def test_agent_startup_fails_when_model_configuration_is_absent(monkeypatch) -> None:
    monkeypatch.setattr("agent.llm.config.load_dotenv", lambda: None)
    monkeypatch.delenv("LLM_PROVIDER")
    monkeypatch.delenv("LLM_MODEL")

    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER is required"):
        create_app()
