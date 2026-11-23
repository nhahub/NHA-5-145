import asyncio
import json

import httpx
import pytest

from agent.llm import build_intent_request, load_llm_settings
from agent.llm.groq import GroqClient
from agent.storefront import load_storefront_definition


def test_groq_client_uses_strict_structured_output_behind_the_llm_interface() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "qwen/qwen3.8-27b",
            "GROQ_API_KEY": "local-test-key",
            "GROQ_BASE_URL": "https://example.test/openai/v1",
            "LLM_REASONING_EFFORT": "low",
        }
    )
    seen_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "v": 8,
                                    "language": "en",
                                    "dialect": "english",
                                    "intent": "find_products",
                                    "constraints": {
                                        "category": "shoes",
                                        "query": None,
                                        "product_type": None,
                                        "min_price": None,
                                        "max_price": None,
                                        "size": None,
                                        "color": None,
                                        "availability": None,
                                        "sort": None,
                                        "target": None,
                                    },
                                    "missing_fields": [],
                                    "conflicting_fields": [],
                                    "needs_clarification": False,
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
        )

    client = GroqClient(settings, transport=httpx.MockTransport(handler))
    request = build_intent_request(
        "Find shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )

    async def collect() -> list[str]:
        return [chunk.text or "" async for chunk in client.complete(request)]

    result = asyncio.run(collect())

    assert result
    assert seen_request is not None
    assert seen_request.url == httpx.URL("https://example.test/openai/v1/chat/completions")
    payload = json.loads(seen_request.content)
    assert payload["model"] == "qwen/qwen3.8-27b"
    assert payload["stream"] is False
    assert payload["reasoning_effort"] == "low"
    assert payload["response_format"]["type"] == "json_schema"
    schema_definition = payload["response_format"]["json_schema"]
    assert schema_definition["strict"] is True
    schema = schema_definition["schema"]
    for reference in schema["anyOf"]:
        branch = schema["$defs"][reference["$ref"].split("/")[-1]]
        assert branch["additionalProperties"] is False
        assert set(branch["required"]) == set(branch["properties"])
    constraints = schema["$defs"]["DiscoveryConstraints"]
    assert constraints["additionalProperties"] is False
    assert set(constraints["required"]) == set(constraints["properties"])
    assert client.call_metadata[-1].usage == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }


def test_groq_client_does_not_repeat_invalid_output_or_expose_its_key() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "qwen/qwen3.8-27b",
            "GROQ_API_KEY": "secret-groq-test-key",
            "GROQ_BASE_URL": "https://example.test/openai/v1",
        }
    )
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = GroqClient(settings, transport=httpx.MockTransport(handler))
    request = build_intent_request(
        "Find shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )

    async def collect() -> None:
        async for _ in client.complete(request):
            pass

    with pytest.raises(ValueError) as captured:
        asyncio.run(collect())

    assert attempts == 1
    assert "secret-groq-test-key" not in str(captured.value)
    assert client.call_metadata[-1].failure_category == "invalid_response"


def test_rate_limit_stops_immediate_and_manual_retry_until_provider_cooldown():
    from agent.llm.groq import GroqRateLimitError

    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "openai/gpt-oss-120b",
            "GROQ_API_KEY": "test-key",
            "GROQ_BASE_URL": "https://example.test/openai/v1",
        }
    )
    attempts = 0
    now = [0.0]

    async def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            headers={"retry-after": "8"},
            json={"error": {"message": "private provider details"}},
        )

    client = GroqClient(settings, transport=httpx.MockTransport(handler), clock=lambda: now[0])
    request = build_intent_request(
        "Find shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )

    async def run():
        for instant in [0, 2, 8]:
            now[0] = instant
            with pytest.raises(GroqRateLimitError) as error:
                async for _ in client.complete(request):
                    pass
            assert error.value.retry_after_seconds == (6 if instant == 2 else 8)
            assert "private provider details" not in str(error.value)

    asyncio.run(run())
    assert attempts == 2
