import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from agent.llm.config import load_llm_settings
from agent.llm.contract import LLMMessage, LLMRequest
from agent.llm.openrouter import OpenRouterClient


def collect(client):
    async def run():
        return [
            c.text
            async for c in client.complete(
                LLMRequest(
                    system="Extract intent",
                    messages=(LLMMessage("shopper", "add"),),
                    response_schema={"type": "object"},
                    response_validator=json.loads,
                )
            )
        ]

    return asyncio.run(run())


def settings():
    return load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "google/gemini-2.5-flash",
            "OPENROUTER_API_KEY": "test-secret",
        }
    )


def test_schema_translation_preserves_keyword_named_properties_and_literal_metadata():
    literal = {"$ref": "literal", "pattern": "unchanged"}
    schema = {
        "type": "object",
        "properties": {
            "maximum": {"type": "integer", "maximum": 5},
            "$ref": {"type": "string"},
            "pattern": {"const": literal, "default": literal, "enum": [literal]},
        },
        "required": ["maximum", "$ref", "pattern"],
    }

    def handler(request):
        if request.method == "GET":
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
        sent = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        assert set(sent["properties"]) == set(sent["required"])
        assert sent["properties"]["maximum"] == {"type": "integer"}
        assert sent["properties"]["pattern"] == {"default": literal}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{}"},
                    }
                ]
            },
        )

    async def run():
        client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
        request = LLMRequest(system="fixture", messages=(), response_schema=schema)
        return [chunk async for chunk in client.complete(request)]

    assert asyncio.run(run())


def test_operation_union_reaches_provider_and_runtime_validates_the_decision():
    from agent.llm.intent_wire import wire_intent_adapter

    decision = dict(
        v=10,
        intent="cart_edit",
        language="en",
        dialect="english",
        constraints={"size": "43", "color": "blue"},
        missing_fields=[],
        needs_clarification=False,
        cart_operation="add",
        product_id="shoe-12",
    )

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        assert schema["anyOf"]
        assert "enum" not in schema["anyOf"][0]["properties"]["v"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(decision)},
                    }
                ]
            },
        )

    async def run():
        client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
        request = LLMRequest(
            system="fixture",
            messages=(),
            response_schema=wire_intent_adapter.json_schema(),
            response_validator=wire_intent_adapter.validate_json,
        )
        return "".join([c.text async for c in client.complete(request)])

    assert json.loads(asyncio.run(run())) == decision


@pytest.mark.parametrize("cap", ["1.00", "2.00", "2.01", "nan", "inf", "0"])
def test_explicit_total_cap_is_bounded_by_owner_authorized_two_dollars(cap):
    environment = {
        "LLM_PROVIDER": "openrouter",
        "LLM_MODEL": "google/gemini-2.5-flash",
        "OPENROUTER_API_KEY": "test-secret",
        "OPENROUTER_TOTAL_CAP_DOLLARS": cap,
    }
    if cap in {"1.00", "2.00"}:
        assert load_llm_settings(environment).openrouter_total_limit == float(cap)
    else:
        with pytest.raises(ValueError):
            load_llm_settings(environment)


@pytest.mark.parametrize("has_usage", [True, False])
def test_error_stream_retains_identity_and_received_usage_without_emitting(has_usage):
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        event = {"id": "gen-failed-attempt", "error": {"message": "private provider detail"}}
        if has_usage:
            event["usage"] = {"cost": 0.0001, "prompt_tokens": 12, "completion_tokens": 2}
        return httpx.Response(200, text="data: " + json.dumps(event) + "\n\n")

    client = OpenRouterClient(
        replace(settings(), stream=True), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ValueError):
        collect(client)
    metadata = client.call_metadata[-1]
    assert metadata.generation_id == "gen-failed-attempt"
    assert metadata.attempt_id
    assert metadata.started_at.endswith("+00:00")
    assert metadata.usage == (
        {"cost": 0.0001, "prompt_tokens": 12, "completion_tokens": 2} if has_usage else None
    )
    assert "private provider detail" not in repr(metadata)
    assert calls == ["GET", "POST"]


@pytest.mark.parametrize("terminal", ["stop", "length", "error", None])
def test_stream_is_buffered_until_complete_validation_and_records_first_content(terminal):
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
        assert json.loads(request.content)["stream"] is True
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": '{"ok":'}}]},
            {"choices": [{"delta": {"content": "true}"}, "finish_reason": terminal}]},
            {"choices": [], "usage": {"cost": 0.001, "prompt_tokens": 2, "completion_tokens": 3}},
        ]
        content = ": keepalive\n\n" + "".join("data: " + json.dumps(c) + "\n\n" for c in chunks)
        content += "data: [DONE]\n\n"
        return httpx.Response(200, text=content)

    client = OpenRouterClient(
        replace(settings(), stream=True), transport=httpx.MockTransport(handler)
    )
    if terminal == "stop":
        assert collect(client) == ['{"ok":true}']
        assert client.call_metadata[-1].ttft_ms is not None
        assert client.call_metadata[-1].usage["cost"] == 0.001
    else:
        with pytest.raises(ValueError):
            collect(client)
        assert client.call_metadata[-1].ttft_ms is not None
        assert client.call_metadata[-1].usage["cost"] == 0.001


@pytest.mark.parametrize("model", ["google/gemini-2.5-flash", "google/gemini-3.5-flash-lite"])
def test_bounded_openrouter_request_validates_output_and_records_cost(model):
    def handler(request):
        assert request.headers["authorization"] == "Bearer test-secret"
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "limit": 0.25,
                        "limit_remaining": 0.25,
                        "limit_reset": None,
                        "usage": 0,
                    }
                },
            )
        payload = json.loads(request.content)
        assert payload["model"] == model
        assert payload["reasoning"] == (
            {"effort": "minimal", "exclude": True}
            if model == "google/gemini-3.5-flash-lite"
            else {"enabled": False}
        )
        assert payload["provider"]["max_price"] == {"prompt": 0.3, "completion": 2.5}
        assert payload["provider"]["require_parameters"] is True
        assert payload["provider"]["sort"] == "latency"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
                "usage": {"cost": 0.001},
            },
        )

    client = OpenRouterClient(
        replace(settings(), model=model), transport=httpx.MockTransport(handler)
    )
    assert collect(client) == ['{"ok":true}']
    assert client.call_metadata[-1].usage["cost"] == 0.001


def test_unevaluated_model_cannot_bypass_the_bounded_model_policy():
    with pytest.raises(ValueError, match="model"):
        OpenRouterClient(replace(settings(), model="google/gemini-flash-latest"))


@pytest.mark.parametrize(
    "limit,remaining,reset", [(100, 100, None), (0.25, 0, None), (0.25, 0.25, "daily")]
)
def test_budget_check_blocks_paid_calls(limit, remaining, reset):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "data": {
                    "limit": limit,
                    "limit_remaining": remaining,
                    "limit_reset": reset,
                    "usage": 0,
                }
            },
        )

    with pytest.raises(ValueError, match="budget"):
        collect(OpenRouterClient(settings(), transport=httpx.MockTransport(handler)))
    assert calls == ["/api/v1/key"]


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "invalid-json"}}]},
        None,
        "malformed-envelope",
    ],
)
def test_invalid_completion_never_retries_or_emits_an_action(body):
    paid_calls = []

    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        paid_calls.append(request)
        if body == "malformed-envelope":
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(200, content=json.dumps(body))

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError):
        collect(client)
    assert len(paid_calls) == 1


def test_real_intent_request_fits_the_paid_budget_bound():
    from agent.llm import build_intent_request
    from agent.storefront import load_storefront_definition

    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "v": 9,
                                    "language": "ar",
                                    "dialect": "egyptian_arabic",
                                    "intent": "cart_edit",
                                    "cart_operation": "add",
                                    "cart_source": "ضيفه للسلة",
                                    "constraints": {},
                                    "missing_fields": [],
                                    "needs_clarification": False,
                                }
                            )
                        },
                    }
                ]
            },
        )

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    request = build_intent_request(
        "ضيفه للسلة",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )

    async def run():
        return [c async for c in client.complete(request)]

    assert len(asyncio.run(run())) == 1


def _key_or(body):
    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        return body(request)

    return handler


@pytest.mark.parametrize(
    ("provider", "route"),
    [
        ("Google AI Studio", "Google_AI_Studio"),
        ("Google", "Google"),
        ('evil"}\n{"x', None),
        ("a" * 41, None),
        (None, None),
        (7, None),
    ],
)
def test_the_serving_provider_is_kept_only_as_a_short_token(provider, route):
    def respond(request):
        body = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        if provider is not None:
            body["provider"] = provider
        return httpx.Response(200, json=body)

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(_key_or(respond)))
    collect(client)
    assert client.call_metadata[-1].route == route


@pytest.mark.parametrize("fails", [False, True])
def test_a_streamed_response_names_its_provider_even_when_the_stream_then_fails(fails):
    def respond(request):
        chunks = [
            {"provider": "Google AI Studio", "choices": [{"delta": {"content": "{}"}}]},
            {
                "provider": "Other",
                "choices": [{"delta": {}, "finish_reason": "length" if fails else "stop"}],
            },
        ]
        text = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text)

    client = OpenRouterClient(
        replace(settings(), stream=True), transport=httpx.MockTransport(_key_or(respond))
    )
    if fails:
        with pytest.raises(ValueError):
            collect(client)
    else:
        collect(client)
    assert client.call_metadata[-1].route == "Google_AI_Studio"
