import asyncio
import json

import httpx
import pytest

from agent.llm import LLMMessage, LLMRequest, load_llm_settings
from agent.llm.nvidia import NvidiaNIMClient


def test_nvidia_client_streams_openai_compatible_completion_chunks() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )
    seen_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello shopper"}}]},
        )

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(
        system="Interpret the Shopping Task",
        messages=(LLMMessage(role="shopper", content="find shoes"),),
        prompt_version="intent-v1",
        schema_version=1,
    )

    async def collect() -> list[str]:
        return [chunk.text or "" async for chunk in client.complete(request)]

    assert asyncio.run(collect()) == ["hello shopper"]
    assert seen_request is not None
    assert seen_request.url == httpx.URL("https://example.test/v1/chat/completions")
    assert seen_request.headers["authorization"] == "Bearer local-test-key"
    assert json.loads(seen_request.content) == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "Interpret the Shopping Task"},
            {"role": "user", "content": "find shoes"},
        ],
        "stream": False,
        "temperature": 0,
        "max_tokens": 512,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    assert client.call_metadata[-1].prompt_version == "intent-v1"
    assert client.call_metadata[-1].schema_version == 1
    assert client.call_metadata[-1].parameters == {
        "stream": False,
        "timeout_seconds": 20,
        "temperature": 0,
        "max_tokens": 512,
    }


def test_nvidia_client_retries_one_throttled_response_before_streaming() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "retried"}}]},
        )

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(system="Interpret the Shopping Task", messages=())

    async def collect() -> list[str]:
        return [chunk.text or "" async for chunk in client.complete(request)]

    assert asyncio.run(collect()) == ["retried"]
    assert attempts == 2


def test_nvidia_client_does_not_retry_malformed_output_or_expose_the_secret() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: not-json\n\n",
        )

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(system="Interpret the Shopping Task", messages=())

    async def collect() -> None:
        async for _ in client.complete(request):
            pass

    with pytest.raises(ValueError) as captured:
        asyncio.run(collect())

    assert attempts == 1
    assert "local-test-key" not in str(captured.value)
    assert client.call_metadata[-1].failure_category == "invalid_response"


def test_nvidia_client_leaves_invalid_structured_output_retry_to_the_intent_pipeline() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        content = "not-json" if attempts == 1 else '{"v": 1}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(
        system="Return one JSON object",
        messages=(),
        response_validator=lambda content: json.loads(content),
    )

    async def collect() -> list[str]:
        return [chunk.text or "" async for chunk in client.complete(request)]

    with pytest.raises(ValueError):
        asyncio.run(collect())
    assert attempts == 1


def test_nvidia_client_retries_one_timeout_then_records_the_timeout_category() -> None:
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("connection timed out", request=request)

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(system="Interpret the Shopping Task", messages=())

    async def collect() -> None:
        async for _ in client.complete(request):
            pass

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(collect())

    assert attempts == 2
    assert client.call_metadata[-1].failure_category == "timeout"
