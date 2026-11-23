import asyncio
import json

import httpx
import pytest

from agent.llm.config import load_llm_settings
from agent.llm.contract import LLMMessage, LLMRequest
from agent.llm.gemini import GeminiClient, GeminiRateLimitError


def test_gemini_returns_validated_json_through_existing_interface():
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "gemini",
            "LLM_MODEL": "gemini-2.5-flash",
            "GEMINI_API_KEY": "test-secret",
        }
    )
    validated = []

    def handler(request):
        assert request.headers["x-goog-api-key"] == "test-secret"
        assert "test-secret" not in str(request.url)
        body = json.loads(request.content)
        assert body["generationConfig"]["responseJsonSchema"]["type"] == "object"
        assert body["contents"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"thought": True, "text": "private reasoning"},
                                {"text": '{"ok":true}'},
                            ]
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 10,
                    "totalTokenCount": 110,
                },
            },
        )

    client = GeminiClient(settings, transport=httpx.MockTransport(handler))
    request = LLMRequest(
        system="Extract intent",
        messages=(LLMMessage("shopper", "add"),),
        response_schema={"type": "object"},
        response_validator=lambda text: validated.append(json.loads(text)),
    )

    async def collect():
        return [chunk.text async for chunk in client.complete(request)]

    assert asyncio.run(collect()) == ['{"ok":true}']
    assert validated == [{"ok": True}]
    assert client.call_metadata[-1].usage["total_tokens"] == 110


@pytest.mark.parametrize(
    "body",
    [
        {"candidates": []},
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]},
        {"candidates": [{"finishReason": "SAFETY"}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "bad-json"}]}}]},
    ],
)
def test_invalid_or_incomplete_outputs_are_rejected_without_retry(body):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=body)

    settings = load_llm_settings(
        {"LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-2.5-flash", "GEMINI_API_KEY": "test-secret"}
    )
    client = GeminiClient(settings, transport=httpx.MockTransport(handler))

    async def collect():
        return [
            c
            async for c in client.complete(
                LLMRequest(
                    system="Extract",
                    messages=(LLMMessage("shopper", "add"),),
                    response_validator=json.loads,
                )
            )
        ]

    with pytest.raises(ValueError):
        asyncio.run(collect())
    assert len(calls) == 1
    assert client.call_metadata[-1].failure_category == "invalid_response"


def test_cooldown_blocks_early_retries_and_does_not_expose_provider_body():
    calls = []
    now = [0.0]

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "8"}, json={"error": "test-secret"})

    settings = load_llm_settings(
        {"LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-2.5-flash", "GEMINI_API_KEY": "test-secret"}
    )
    client = GeminiClient(settings, transport=httpx.MockTransport(handler), clock=lambda: now[0])

    async def collect():
        return [c async for c in client.complete(LLMRequest(system="Extract", messages=()))]

    for timestamp, wait in [(0, 8), (2, 6), (8, 8)]:
        now[0] = timestamp
        with pytest.raises(GeminiRateLimitError) as error:
            asyncio.run(collect())
        assert error.value.retry_after_seconds == wait
        assert "test-secret" not in str(error.value)
    assert len(calls) == 2


@pytest.mark.parametrize("body", [None, [], {"usageMetadata": None}, {"candidates": [None]}])
def test_malformed_provider_envelope_is_reported_as_invalid_output(body):
    settings = load_llm_settings(
        {"LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-2.5-flash", "GEMINI_API_KEY": "test-secret"}
    )
    client = GeminiClient(
        settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=json.dumps(body))
        ),
    )

    async def collect():
        return [c async for c in client.complete(LLMRequest(system="Extract", messages=()))]

    with pytest.raises(ValueError):
        asyncio.run(collect())


def test_gemini_configuration_requires_its_own_key_and_builds_adapter():
    from agent.llm import build_llm_client
    from agent.llm.config import LLMConfigurationError

    values = {
        "LLM_PROVIDER": "gemini",
        "LLM_MODEL": "gemini-2.5-flash",
        "GROQ_API_KEY": "unrelated-key",
    }
    with pytest.raises(LLMConfigurationError, match="GEMINI_API_KEY"):
        load_llm_settings(values)
    values["GEMINI_API_KEY"] = "gemini-test-key"
    assert isinstance(build_llm_client(load_llm_settings(values)), GeminiClient)
