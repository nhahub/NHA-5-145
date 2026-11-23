"""Single-attempt Converse boundary; live model and cost qualification is separate."""

import asyncio
import json
import re
from collections import deque
from contextlib import closing, suppress
from dataclasses import dataclass
from math import isfinite
from time import monotonic
from uuid import uuid4

from agent.llm.config import LLMConfigurationError
from agent.llm.contract import LLMChunk, LLMInvalidResponseError
from agent.llm.provider_schema import inline_schema_references


class BedrockProviderError(Exception):
    def __init__(self, category):
        self.category = category
        super().__init__(f"Bedrock request failed: {category}")


@dataclass(frozen=True)
class BedrockCallMetadata:
    provider: str
    model: str
    latency_ms: int
    prompt_version: str
    schema_version: int | None
    attempt_id: str
    provider_request_id: str | None
    usage: dict[str, int] | None
    failure_category: str | None
    cost_usd: None = None
    provider_error_code: str | None = None
    http_status: int | None = None


def _service_code(body):
    error = body.get("Error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None
    code = error.get("Code")
    supported = {
        "AccessDeniedException",
        "ValidationException",
        "ResourceNotFoundException",
        "ModelErrorException",
        "ModelNotReadyException",
        "ModelTimeoutException",
        "InternalServerException",
        "ThrottlingException",
        "ServiceUnavailableException",
        "ServiceQuotaExceededException",
        "UnrecognizedClientException",
        "ExpiredTokenException",
        "InvalidSignatureException",
        "IncompleteSignature",
        "MissingAuthenticationTokenException",
        "SerializationException",
    }
    return code if isinstance(code, str) and code in supported else "Other"


def _http_status(body):
    meta = body.get("ResponseMetadata") if isinstance(body, dict) else None
    value = meta.get("HTTPStatusCode") if isinstance(meta, dict) else None
    return value if type(value) is int and 100 <= value <= 599 else None


def _request_id(body):
    meta = body.get("ResponseMetadata") if isinstance(body, dict) else None
    value = meta.get("RequestId") if isinstance(meta, dict) else None
    return (
        value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value) else None
    )


def _usage(body):
    raw = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(raw, dict):
        return None
    names = {
        "inputTokens": "prompt_tokens",
        "outputTokens": "completion_tokens",
        "totalTokens": "total_tokens",
    }
    if any(type(raw.get(name)) is not int or not 0 <= raw[name] <= 10**9 for name in names):
        return None
    if raw["totalTokens"] != raw["inputTokens"] + raw["outputTokens"]:
        return None
    return {target: raw[name] for name, target in names.items()}


def _payload(settings, request):
    if (
        request.tools
        or type(request.max_tokens) is not int
        or not 0 < request.max_tokens <= 2048
        or not isfinite(request.temperature)
        or not 0 <= request.temperature <= 1
    ):
        raise LLMConfigurationError("Bedrock request exceeds the supported bounded contract")
    system = [{"text": request.system}]
    if request.response_schema is not None:
        if request.response_validator is None:
            raise LLMConfigurationError("Structured Bedrock output requires local validation")
        schema = inline_schema_references(request.response_schema)
        system.append(
            {
                "text": "Return only a complete JSON value matching this schema: "
                + json.dumps(schema)
            }
        )
    messages = []
    for message in request.messages:
        if message.role not in {"shopper", "assistant"} or not message.content:
            raise LLMConfigurationError("Bedrock accepts only nonempty conversation turns")
        role = "user" if message.role == "shopper" else "assistant"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].append({"text": message.content})
        else:
            messages.append({"role": role, "content": [{"text": message.content}]})
    if not messages or messages[-1]["role"] != "user":
        raise LLMConfigurationError("Bedrock conversation must end with a Shopper")
    if messages[0]["role"] == "assistant":
        # The bounded history can start midway through an exchange. Preserve its
        # context without relabelling assistant prose as a real Shopper request.
        messages.insert(
            0,
            {
                "role": "user",
                "content": [
                    {"text": ("Earlier assistant context follows. It grants no permission to act.")}
                ],
            },
        )
    payload = {
        "modelId": settings.model,
        "system": system,
        "messages": messages,
        "inferenceConfig": {"maxTokens": request.max_tokens, "temperature": request.temperature},
    }
    if len(json.dumps(payload).encode()) > 100_000:
        raise LLMConfigurationError("Bedrock request exceeds its size bound")
    return payload


def _text(body):
    try:
        if body["stopReason"] != "end_turn":
            raise ValueError
        message = body["output"]["message"]
        if message["role"] != "assistant" or not isinstance(message["content"], list):
            raise ValueError
        parts = []
        for block in message["content"]:
            if not isinstance(block, dict) or len(block) != 1:
                raise ValueError
            if "reasoningContent" in block:
                continue
            if "text" not in block or not isinstance(block["text"], str):
                raise ValueError
            parts.append(block["text"])
        text = "".join(parts)
        if not text.strip() or len(text.encode()) > 100_000:
            raise ValueError
        return text
    except (KeyError, TypeError, ValueError) as error:
        raise LLMInvalidResponseError("Bedrock returned incomplete or invalid output") from error


def _provider_failure(error):
    from botocore.exceptions import (
        ClientError,
        ConnectionClosedError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    if isinstance(error, ConnectTimeoutError | ReadTimeoutError):
        return "timeout"
    if isinstance(error, EndpointConnectionError | ConnectionClosedError):
        return "network"
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code")
        if code == "ModelTimeoutException":
            return "timeout"
        return "throttled" if code == "ThrottlingException" else "provider_http"
    return "provider_http"


class BedrockClient:
    price_floor = ("0.07", "0.30")

    def __init__(self, settings, *, sdk_client=None):
        if (
            settings.provider != "bedrock"
            or settings.region != "eu-north-1"
            or settings.model != "openai.gpt-oss-20b-1:0"
            or settings.endpoint
            or settings.stream
            or not isfinite(settings.timeout_seconds)
            or not 0 < settings.timeout_seconds <= 60
        ):
            raise LLMConfigurationError("Unsupported Bedrock candidate configuration")
        self._settings = settings
        self._sdk = sdk_client
        self.call_metadata = deque(maxlen=256)

    def _invoke(self, payload):
        if self._sdk is not None:
            return self._sdk.converse(**payload)
        import boto3
        from botocore.config import Config

        with closing(
            boto3.client(
                "bedrock-runtime",
                region_name=self._settings.region,
                config=Config(
                    connect_timeout=min(5, self._settings.timeout_seconds),
                    read_timeout=self._settings.timeout_seconds,
                    retries={"total_max_attempts": 1, "mode": "standard"},
                    ignore_configured_endpoint_urls=True,
                ),
            )
        ) as sdk:
            return sdk.converse(**payload)

    async def complete(self, request):
        started = monotonic()
        body, failure = None, "invalid_response"
        attempt = request.attempt_id or str(uuid4())
        try:
            payload = _payload(self._settings, request)
            await request.authorize()
            worker = asyncio.create_task(asyncio.to_thread(self._invoke, payload))
            try:
                body = await asyncio.shield(worker)
            except asyncio.CancelledError:
                # Keep the guarded slot until the blocking SDK operation ends. Even a
                # repeated cancellation cannot leave unbounded background provider work.
                while not worker.done():
                    try:
                        await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not worker.cancelled():
                    with suppress(Exception):
                        worker.result()
                failure = "canceled"
                raise
            except Exception as error:
                body = getattr(error, "response", None)
                failure = _provider_failure(error)
                raise BedrockProviderError(failure) from None
            text = _text(body)
            if request.response_validator is not None:
                try:
                    request.response_validator(text)
                except Exception:
                    raise LLMInvalidResponseError(
                        "Bedrock output failed local validation"
                    ) from None
            await request.authorize()
            failure = None
            yield LLMChunk(text=text)
        finally:
            self.call_metadata.append(
                BedrockCallMetadata(
                    "bedrock",
                    self._settings.model,
                    int((monotonic() - started) * 1000),
                    request.prompt_version,
                    request.schema_version,
                    attempt,
                    _request_id(body),
                    _usage(body),
                    failure,
                    provider_error_code=_service_code(body),
                    http_status=_http_status(body),
                )
            )
