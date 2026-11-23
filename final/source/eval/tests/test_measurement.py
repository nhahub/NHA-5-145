import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from agent.llm.config import load_llm_settings
from agent.llm.contract import LLMRequest
from agent.llm.intent import StructuredIntent
from agent.llm.openrouter import OpenRouterClient
from eval.measurement import MeasuredClient, pipeline_error_diagnostic


def test_pipeline_error_diagnostic_never_contains_rejected_input():
    with pytest.raises(ValueError) as caught:
        StructuredIntent.model_validate({"v": "private-rejected-model-value"})
    assert "private-rejected-model-value" in str(caught.value)
    assert pipeline_error_diagnostic(caught.value) == {"category": "ValidationError"}
    assert pipeline_error_diagnostic(ValueError("private-provider-detail")) == {
        "category": "ValueError"
    }


def test_failed_attempt_is_durably_recorded_and_kept_separate_from_next_attempt(tmp_path):
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "google/gemini-2.5-flash",
            "OPENROUTER_API_KEY": "never-log-this-key",
        }
    )

    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "limit": 0.25,
                        "limit_remaining": 0.25,
                        "limit_reset": None,
                    }
                },
            )
        return httpx.Response(
            200, text='data: {"id":"gen-failure","error":{"message":"private"}}\n\n'
        )

    journal = tmp_path / "attempts.jsonl"
    client = MeasuredClient(
        OpenRouterClient(replace(settings, stream=True), transport=httpx.MockTransport(handler)),
        journal=journal,
    )

    async def run():
        for _ in range(2):
            with pytest.raises(ValueError):
                async for _ in client.complete(LLMRequest(system="secret prompt", messages=())):
                    pytest.fail("Failed output reached the Agent")

    asyncio.run(run())
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(records) == 2
    assert records == client.calls
    assert records[0]["attempt_id"] != records[1]["attempt_id"]
    assert all(r["generation_id"] == "gen-failure" and r["usage"] is None for r in records)
    assert all(r["failure_category"] == "invalid_response" for r in records)
    text = journal.read_text()
    assert all(secret not in text for secret in ("never-log-this-key", "secret prompt", "private"))


@pytest.mark.parametrize("extra_field", [True, False])
def test_journal_excludes_extra_property_names_and_free_text_model_fields(tmp_path, extra_field):
    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "google/gemini-2.5-flash",
            "OPENROUTER_API_KEY": "test-key",
        }
    )
    draft = {
        "v": 8,
        "language": "en",
        "dialect": "english",
        "intent": "find_products",
        "constraints": {"category": "private-model-text", "product_type": "private-model-text"},
        "missing_fields": [],
        "needs_clarification": False,
    }
    if extra_field:
        draft["private-extra-field"] = "private-value"

    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "limit": 0.25,
                        "limit_remaining": 0.25,
                        "limit_reset": None,
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps(draft)},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    journal = tmp_path / "redacted.jsonl"
    client = MeasuredClient(
        OpenRouterClient(settings, transport=httpx.MockTransport(handler)), journal=journal
    )
    request = LLMRequest(
        system="Shopping Copilot intent context: {}",
        messages=(),
        response_schema=StructuredIntent.model_json_schema(),
        response_validator=StructuredIntent.model_validate_json,
    )

    async def run():
        return [chunk async for chunk in client.complete(request)]

    if extra_field:
        with pytest.raises(ValueError):
            asyncio.run(run())
    else:
        assert len(asyncio.run(run())) == 1
    assert "private-" not in journal.read_text()


def test_cancel_during_held_response_closes_provider_before_journaling(tmp_path):
    async def run():
        responded = asyncio.Event()
        settings = load_llm_settings(
            {
                "LLM_PROVIDER": "openrouter",
                "LLM_MODEL": "google/gemini-2.5-flash",
                "OPENROUTER_API_KEY": "test-key",
            }
        )

        def handler(request):
            if request.url.path.endswith("/key"):
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "limit": 0.25,
                            "limit_remaining": 0.25,
                            "limit_reset": None,
                        }
                    },
                )
            responded.set()
            return httpx.Response(
                200,
                json={
                    "id": "gen-held",
                    "usage": {"cost": 0.001, "prompt_tokens": 5, "completion_tokens": 2},
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                },
            )

        client = MeasuredClient(
            OpenRouterClient(settings, transport=httpx.MockTransport(handler)),
            journal=tmp_path / "held.jsonl",
        )
        client.release.clear()

        async def consume():
            return [chunk async for chunk in client.complete(LLMRequest(system="", messages=()))]

        task = asyncio.create_task(consume())
        await responded.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.calls[-1]["generation_id"] == "gen-held"
        assert client.calls[-1]["usage"]["cost"] == 0.001
        assert client.calls[-1]["failure"] == "CancelledError"

    asyncio.run(run())
