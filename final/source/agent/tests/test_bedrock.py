import asyncio
import json
from dataclasses import replace

import pytest

from agent.llm import build_llm_client
from agent.llm.config import LLMConfigurationError, load_llm_settings
from agent.llm.contract import LLMInvalidResponseError, LLMMessage, LLMRequest, ToolSpec


def settings(**overrides):
    return load_llm_settings(
        {
            "LLM_PROVIDER": "bedrock",
            "LLM_MODEL": "openai.gpt-oss-20b-1:0",
            "AWS_REGION": "eu-north-1",
            **overrides,
        }
    )


def request(**overrides):
    return LLMRequest(
        system="Interpret the shopping request",
        messages=(LLMMessage("shopper", "عايز كوتشي"),),
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        response_validator=json.loads,
        **overrides,
    )


def response(**overrides):
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": '{"ok":true}'}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 100, "outputTokens": 10, "totalTokens": 110},
        "ResponseMetadata": {"RequestId": "safe-request-id", "HTTPStatusCode": 200},
        **overrides,
    }


class SDK:
    def __init__(self, body=None, error=None):
        self.body = response() if body is None else body
        self.error = error
        self.calls = []

    def converse(self, **payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.body


def client(sdk=None):
    from agent.llm.bedrock import BedrockClient

    return BedrockClient(settings(), sdk_client=sdk or SDK())


async def collect(adapter, value=None):
    return [chunk.text async for chunk in adapter.complete(value or request())]


def test_factory_is_lazy_and_does_not_resolve_credentials(monkeypatch):
    import boto3

    monkeypatch.setattr(boto3, "client", lambda *a, **k: pytest.fail("unexpected SDK creation"))
    assert type(build_llm_client(settings())).__name__ == "BedrockClient"
    assert settings(NVIDIA_API_KEY="unrelated-secret").api_key is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"AWS_REGION": ""},
        {"AWS_REGION": "us-east-1"},
        {"LLM_MODEL": "arn:aws:bedrock:profile"},
        {"LLM_TIMEOUT_SECONDS": "nan"},
        {"LLM_TIMEOUT_SECONDS": "0"},
        {"LLM_TIMEOUT_SECONDS": "61"},
    ],
)
def test_explicit_bounded_configuration(overrides):
    with pytest.raises(LLMConfigurationError):
        settings(**overrides)


def test_converse_maps_existing_contract_and_validates_before_output():
    sdk = SDK()
    adapter = client(sdk)
    validated = []
    value = replace(request(), response_validator=lambda s: validated.append(json.loads(s)))
    assert asyncio.run(collect(adapter, value)) == ['{"ok":true}']
    assert validated == [{"ok": True}]
    payload = sdk.calls[0]
    assert payload["modelId"] == settings().model
    assert payload["messages"] == [{"role": "user", "content": [{"text": "عايز كوتشي"}]}]
    assert "schema" in payload["system"][-1]["text"].lower()
    assert payload["inferenceConfig"] == {"maxTokens": 512, "temperature": 0}
    assert "attempt" not in json.dumps(payload)
    record = adapter.call_metadata[-1]
    assert record.provider_request_id == "safe-request-id"
    assert record.usage == {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
    assert record.cost_usd is None
    assert record.failure_category is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        response(stopReason="max_tokens"),
        response(stopReason="guardrail_intervened"),
        response(output={"message": {"role": "user", "content": [{"text": "{}"}]}}),
        response(output={"message": {"role": "assistant", "content": [{"text": ""}]}}),
        response(output={"message": {"role": "assistant", "content": [{"text": "bad"}]}}),
        response(output={"message": {"role": "assistant", "content": [{"toolUse": {}}]}}),
    ],
)
def test_invalid_or_incomplete_output_never_emits_or_retries(body):
    sdk = SDK(body)
    adapter = client(sdk)
    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(collect(adapter))
    assert len(sdk.calls) == 1
    assert adapter.call_metadata[-1].failure_category == "invalid_response"


def test_unsupported_tool_request_refuses_before_provider():
    sdk = SDK()
    with pytest.raises(LLMConfigurationError):
        asyncio.run(collect(client(sdk), request(tools=(ToolSpec("x", "x", {}),))))
    assert not sdk.calls


@pytest.mark.parametrize(
    "code,category",
    [
        ("ThrottlingException", "throttled"),
        ("AccessDeniedException", "provider_http"),
        ("ModelTimeoutException", "timeout"),
        ("ServiceUnavailableException", "provider_http"),
    ],
)
def test_sdk_errors_have_safe_categories_and_no_retry(code, category):
    from botocore.exceptions import ClientError

    from agent.app import interpretation_pause_reason
    from agent.llm.bedrock import BedrockProviderError

    sdk = SDK(
        error=ClientError(
            {
                "Error": {"Code": code, "Message": "secret provider body"},
                "ResponseMetadata": {"RequestId": "safe-id"},
            },
            "Converse",
        )
    )
    adapter = client(sdk)
    with pytest.raises(BedrockProviderError) as captured:
        asyncio.run(collect(adapter))
    assert interpretation_pause_reason(captured.value) == category
    assert len(sdk.calls) == 1
    assert "secret" not in str(captured.value) + repr(adapter.call_metadata)
    assert adapter.call_metadata[-1].provider_request_id == "safe-id"


def test_reasoning_and_invalid_usage_are_never_exposed_or_settled():
    body = response(
        usage={"inputTokens": True, "outputTokens": 10, "totalTokens": 11},
        ResponseMetadata={"RequestId": "secret/raw header"},
    )
    body["output"]["message"]["content"].insert(
        0, {"reasoningContent": {"reasoningText": {"text": "private reasoning"}}}
    )
    adapter = client(SDK(body))
    assert asyncio.run(collect(adapter)) == ['{"ok":true}']
    assert adapter.call_metadata[-1].usage is None
    assert adapter.call_metadata[-1].provider_request_id is None
    assert "private reasoning" not in repr(adapter.call_metadata)


def test_metadata_history_is_bounded():
    adapter = client()

    async def run():
        for _ in range(260):
            await collect(adapter)

    asyncio.run(run())
    assert len(adapter.call_metadata) == 256


def test_denied_and_late_authority_do_not_deliver():
    calls = 0

    async def authority():
        nonlocal calls
        calls += 1
        raise PermissionError("not authorized")

    sdk = SDK()
    with pytest.raises(PermissionError):
        asyncio.run(collect(client(sdk), request(authorization_check=authority)))
    assert not sdk.calls

    async def late_authority():
        nonlocal calls
        calls += 1
        if calls > 2:
            raise PermissionError("revoked")

    adapter = client(sdk)
    with pytest.raises(PermissionError):
        asyncio.run(collect(adapter, request(authorization_check=late_authority)))
    assert len(sdk.calls) == 1


def test_sdk_settings_and_payload_match_botocore_contract(monkeypatch):
    import boto3
    from botocore.config import Config
    from botocore.stub import Stubber

    from agent.llm.bedrock import BedrockClient

    sdk = boto3.client(
        "bedrock-runtime",
        region_name="eu-north-1",
        aws_access_key_id="offline-test",
        aws_secret_access_key="offline-test",
        config=Config(retries={"total_max_attempts": 1}),
    )
    seen = []

    def create(*args, **kwargs):
        seen.append((args, kwargs))
        return sdk

    monkeypatch.setattr(boto3, "client", create)
    body = response()
    body["metrics"] = {"latencyMs": 3}
    with Stubber(sdk) as stub:
        stub.add_response("converse", body)
        assert asyncio.run(collect(BedrockClient(settings()))) == ['{"ok":true}']
        stub.assert_no_pending_responses()
    config = seen[0][1]["config"]
    assert config.retries["total_max_attempts"] == 1
    assert config.read_timeout == 20
    assert config.connect_timeout <= 5
    assert config.ignore_configured_endpoint_urls is True


def test_guard_retains_unknown_cost_and_rejects_low_prices(tmp_path):
    from decimal import Decimal

    from agent.inference.config import configured_guard
    from agent.inference.ledger import AllowanceLedger

    path = tmp_path / "ledger.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.10"))
    environment = {
        "INFERENCE_LEDGER_PATH": str(path),
        "INFERENCE_LEDGER_ID": identity,
        "INFERENCE_PROVIDER": "bedrock",
        "INFERENCE_MODEL": settings().model,
        "INFERENCE_INPUT_USD_PER_MILLION": "0.07",
        "INFERENCE_OUTPUT_USD_PER_MILLION": "0.30",
        "INFERENCE_MAX_ACTIVE": "1",
        "INFERENCE_MAX_WAITING": "0",
        "INFERENCE_WAIT_SECONDS": "1",
        "INFERENCE_MAXIMUM_PAGES": "1024",
        "COPILOT_ENV": "production",
    }
    adapter = client()
    guarded = configured_guard(adapter, settings(), environment)
    assert asyncio.run(collect(guarded)) == ['{"ok":true}']
    status = AllowanceLedger(path, identity).status()
    assert status["uncertain"] == 1
    assert Decimal(status["accounted_usd"]) > 0
    with pytest.raises(ValueError):
        configured_guard(
            adapter, settings(), {**environment, "INFERENCE_INPUT_USD_PER_MILLION": "0.01"}
        )


def test_cancellation_holds_guard_slot_until_worker_ends_and_discards_late_output(tmp_path):
    import threading
    from decimal import Decimal

    from agent.inference.client import GuardedClient, InferencePrices
    from agent.inference.ledger import AllowanceLedger, InferenceRefused

    entered, release = threading.Event(), threading.Event()

    class BlockingSDK(SDK):
        def converse(self, **payload):
            entered.set()
            assert release.wait(5), "test did not release provider"
            return super().converse(**payload)

    path = tmp_path / "ledger.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.10"))
    ledger = AllowanceLedger(path, identity)
    adapter = client(BlockingSDK())
    guarded = GuardedClient(
        adapter,
        ledger,
        InferencePrices(Decimal("0.07"), Decimal("0.30")),
        maximum_active=1,
        maximum_waiting=0,
        wait_seconds=1,
    )

    async def run():
        task = asyncio.create_task(collect(guarded))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(0.02)
            task.cancel()
            await asyncio.sleep(0.02)
            assert not task.done()
            with pytest.raises(InferenceRefused, match="busy"):
                await collect(guarded)
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert ledger.status()["uncertain"] == 1
    assert adapter.call_metadata[-1].failure_category == "canceled"
    assert adapter.call_metadata[-1].usage is None


@pytest.mark.parametrize("kind,expected", [("read", "timeout"), ("connect", "network")])
def test_transport_failure_is_safe_and_single_attempt(kind, expected):
    from botocore.exceptions import EndpointConnectionError, ReadTimeoutError

    from agent.llm.bedrock import BedrockProviderError

    error = (
        ReadTimeoutError(endpoint_url="https://offline.invalid")
        if kind == "read"
        else EndpointConnectionError(endpoint_url="https://offline.invalid")
    )
    sdk = SDK(error=error)
    adapter = client(sdk)
    with pytest.raises(BedrockProviderError) as captured:
        asyncio.run(collect(adapter, request(provider_attempt_limit=2)))
    assert captured.value.category == expected
    assert len(sdk.calls) == 1
    assert "offline.invalid" not in str(captured.value) + repr(adapter.call_metadata)
    assert adapter.call_metadata[-1].usage is None


@pytest.mark.parametrize(
    "change",
    [
        {"max_tokens": 0},
        {"max_tokens": True},
        {"max_tokens": 2049},
        {"temperature": float("nan")},
        {"messages": (LLMMessage("tool", "unsafe"),)},
        {"system": "x" * 110_000},
        {"response_schema": {"$ref": "https://offline.invalid/schema"}},
        {"response_validator": None},
    ],
)
def test_unsupported_requests_never_enter_sdk(change):
    sdk = SDK()
    with pytest.raises(LLMConfigurationError):
        asyncio.run(collect(client(sdk), replace(request(), **change)))
    assert not sdk.calls


def test_guard_exhaustion_never_reaches_bedrock(tmp_path):
    from decimal import Decimal

    from agent.inference.client import GuardedClient, InferencePrices
    from agent.inference.ledger import AllowanceLedger, InferenceRefused

    path = tmp_path / "ledger.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.000001"))
    sdk = SDK()
    guarded = GuardedClient(
        client(sdk),
        AllowanceLedger(path, identity),
        InferencePrices(Decimal("0.07"), Decimal("0.30")),
        maximum_active=1,
        maximum_waiting=0,
        wait_seconds=1,
    )
    with pytest.raises(InferenceRefused, match="budget"):
        asyncio.run(collect(guarded))
    assert not sdk.calls


def test_ref_siblings_cannot_hide_provider_input_from_reservation(tmp_path):
    from decimal import Decimal

    from agent.inference.client import GuardedClient, InferencePrices
    from agent.inference.ledger import AllowanceLedger, InferenceRefused

    schema = {
        "$defs": {"large": {"type": "object", "description": "q9Z_" * 8000}},
        "$ref": "#/$defs/large",
        "description": "short",
    }
    path = tmp_path / "ledger.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.001"))
    sdk = SDK()
    guarded = GuardedClient(
        client(sdk),
        AllowanceLedger(path, identity),
        InferencePrices(Decimal("0.07"), Decimal("0.30")),
        maximum_active=1,
        maximum_waiting=0,
        wait_seconds=1,
    )
    with pytest.raises(InferenceRefused, match="budget"):
        asyncio.run(collect(guarded, replace(request(), response_schema=schema)))
    assert not sdk.calls


def test_real_rolling_conversation_keeps_leading_assistant_context():
    from agent.llm.intent_pipeline import build_intent_request
    from agent.product_context import ProductContext
    from agent.storefront import load_storefront_definition
    from agent.tests.test_real_task import snapshot_at

    conversation = []
    for i in range(7):
        conversation.extend(
            [{"role": "shopper", "text": f"request {i}"}, {"role": "copilot", "text": f"reply {i}"}]
        )
    conversation.append({"role": "copilot", "text": "Added the chosen item"})
    storefront = load_storefront_definition()
    from agent.schemas import Snapshot

    snapshot = Snapshot.model_validate(snapshot_at("/"))
    context = ProductContext()
    context.prepare(snapshot, storefront, [])
    state = context.prepare(snapshot, storefront, conversation)
    value = build_intent_request(
        "what next?",
        storefront=storefront,
        resolved_state=state,
        pending_clarification=None,
        snapshot=snapshot,
    )
    assert value.messages[0].role == "assistant"
    sdk = SDK()
    assert asyncio.run(collect(client(sdk), replace(value, response_validator=json.loads)))
    messages = sdk.calls[0]["messages"]
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"][0]["text"] == value.messages[0].content
    assert messages[-1] == {"role": "user", "content": [{"text": "what next?"}]}


def test_safe_service_code_is_retained_without_raw_error_body():
    from botocore.exceptions import ClientError

    from agent.llm.bedrock import BedrockProviderError

    sdk = SDK(
        error=ClientError(
            {
                "Error": {"Code": "ValidationException", "Message": "private diagnostic details"},
                "ResponseMetadata": {"HTTPStatusCode": 400, "RequestId": "safe-correlation"},
            },
            "Converse",
        )
    )
    adapter = client(sdk)
    with pytest.raises(BedrockProviderError):
        asyncio.run(collect(adapter))
    record = adapter.call_metadata[-1]
    assert record.provider_error_code == "ValidationException"
    assert record.http_status == 400
    assert "private diagnostic details" not in repr(record)


def test_unknown_service_code_is_not_a_secret_metadata_channel():
    from botocore.exceptions import ClientError

    from agent.llm.bedrock import BedrockProviderError

    sdk = SDK(
        error=ClientError(
            {
                "Error": {"Code": "privateCredentialValue", "Message": "private body"},
                "ResponseMetadata": {"HTTPStatusCode": True},
            },
            "Converse",
        )
    )
    adapter = client(sdk)
    with pytest.raises(BedrockProviderError):
        asyncio.run(collect(adapter))
    record = adapter.call_metadata[-1]
    assert record.provider_error_code == "Other"
    assert record.http_status is None
    assert "private" not in repr(record)
