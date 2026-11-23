"""Bounded paid Gemini evaluation through OpenRouter, with no automatic retries."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from time import monotonic
from uuid import uuid4

import httpx

from agent.llm.config import LLMConfigurationError, LLMSettings
from agent.llm.contract import LLMChunk, LLMInvalidResponseError, LLMRequest
from agent.llm.provider_schema import openrouter_response_schema


@dataclass(frozen=True)
class OpenRouterCallMetadata:
    provider: str
    model: str
    latency_ms: int
    prompt_version: str
    schema_version: int | None
    usage: dict[str, int | float] | None
    failure_category: str | None
    ttft_ms: float | None = None
    attempt_id: str | None = None
    started_at: str | None = None
    generation_id: str | None = None
    route: str | None = None


class OpenRouterBudgetError(ValueError):
    """No paid request may proceed under the current key allowance."""


@dataclass
class StreamMetrics:
    ttft_ms: float | None = None
    usage: dict[str, int | float] | None = None
    generation_id: str | None = None
    route: str | None = None


def route_name(value):
    """The upstream provider as a short token, or nothing if it is not one."""
    if not isinstance(value, str):
        return None
    name = value.replace(" ", "_")
    return name if re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", name) else None


def _usage_metadata(raw):
    if not isinstance(raw, dict):
        return None
    return {
        key: value
        for key, value in raw.items()
        if key in {"prompt_tokens", "completion_tokens", "total_tokens", "cost"}
        and isinstance(value, int | float)
        and not isinstance(value, bool)
        and isfinite(value)
        and value >= 0
    }


def generation_id(value):
    """Retain only bounded protocol identifiers, never arbitrary provider text."""
    return (
        value
        if isinstance(value, str)
        and 0 < len(value) <= 200
        and value.isascii()
        and all(c.isalnum() or c in "-_" for c in value)
        else None
    )


class OpenRouterClient:
    price_ceiling = ("0.3", "2.5")

    def __init__(self, settings: LLMSettings, *, transport: httpx.AsyncBaseTransport | None = None):
        if settings.provider != "openrouter" or not settings.api_key:
            raise LLMConfigurationError("OpenRouter requires its own API key")
        if settings.model not in {"google/gemini-2.5-flash", "google/gemini-3.5-flash-lite"}:
            raise LLMConfigurationError(
                "OpenRouter model is outside the bounded qualification policy"
            )
        self._settings = settings
        self._transport = transport
        self._lock = asyncio.Lock()
        self.call_metadata: list[OpenRouterCallMetadata] = []

    async def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        started = monotonic()
        started_at = datetime.now(UTC).isoformat()
        attempt_id = request.attempt_id or str(uuid4())
        usage = None
        ttft_ms = None
        stream_metrics = StreamMetrics()
        completed_at = None
        failure = None
        try:
            payload = {
                "model": self._settings.model,
                "messages": [
                    {"role": "system", "content": request.system},
                    *[
                        {"role": "user" if m.role == "shopper" else m.role, "content": m.content}
                        for m in request.messages
                    ],
                ],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": self._settings.stream,
                "reasoning": (
                    {"effort": "minimal", "exclude": True}
                    if self._settings.model == "google/gemini-3.5-flash-lite"
                    else {"enabled": False}
                ),
                "provider": {
                    "sort": "latency",
                    "require_parameters": True,
                    "max_price": {
                        "prompt": float(self.price_ceiling[0]),
                        "completion": float(self.price_ceiling[1]),
                    },
                },
            }
            if request.tools:
                raise ValueError("Paid intent evaluation does not use tools")
            if request.response_schema is not None:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "shopping_intent",
                        "strict": True,
                        "schema": openrouter_response_schema(request.response_schema),
                    },
                }
            # Conservative byte-based reservation, including schema and protocol overhead.
            reserve = (
                (len(json.dumps(payload).encode()) + 4096) * 0.3 + request.max_tokens * 2.5
            ) / 1_000_000
            if request.max_tokens <= 0 or request.max_tokens > 2048 or reserve > 0.02:
                raise OpenRouterBudgetError("Request exceeds the evaluation budget size bound")
            async with (
                self._lock,
                httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self._settings.timeout_seconds,
                    headers={
                        "Authorization": f"Bearer {self._settings.api_key.get_secret_value()}"
                    },
                ) as client,
            ):
                key_response = await client.get("https://openrouter.ai/api/v1/key")
                key_response.raise_for_status()
                key = key_response.json().get("data", {})
                limit, remaining = key.get("limit"), key.get("limit_remaining")
                if (
                    not all(
                        isinstance(v, int | float) and not isinstance(v, bool) and isfinite(v)
                        for v in (limit, remaining)
                    )
                    or not 0 < limit <= self._settings.openrouter_total_limit
                    or remaining < reserve
                    or key.get("limit_reset") is not None
                ):
                    raise OpenRouterBudgetError(
                        "OpenRouter evaluation budget requires a non-resetting key limit "
                        "within the configured total cap and sufficient remaining credit"
                    )
                await request.authorize()
                if self._settings.stream:
                    async with client.stream(
                        "POST", "https://openrouter.ai/api/v1/chat/completions", json=payload
                    ) as response:
                        response.raise_for_status()
                        body, ttft_ms = await _collect_stream(response, started, stream_metrics)
                else:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions", json=payload
                    )
                    response.raise_for_status()
                    try:
                        body = response.json()
                    except ValueError as error:
                        raise LLMInvalidResponseError(
                            "OpenRouter response body is not JSON"
                        ) from error
            try:
                stream_metrics.generation_id = generation_id(body.get("id")) or (
                    stream_metrics.generation_id
                )
                stream_metrics.route = route_name(body.get("provider")) or stream_metrics.route
                raw_usage = body.get("usage", {})
                usage = _usage_metadata(raw_usage)
                choice = body["choices"][0]
                text = choice["message"]["content"]
                if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text:
                    raise LLMInvalidResponseError(
                        "OpenRouter returned incomplete or non-text output"
                    )
            except (KeyError, IndexError, TypeError, AttributeError) as error:
                raise LLMInvalidResponseError("OpenRouter returned invalid output") from error
            if request.response_validator:
                request.response_validator(text)
            completed_at = monotonic()
            yield LLMChunk(text=text)
        except Exception as error:
            failure = (
                "budget"
                if isinstance(error, OpenRouterBudgetError)
                else "throttled"
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429
                else "http"
                if isinstance(error, httpx.HTTPStatusError)
                else "timeout"
                if isinstance(error, httpx.TimeoutException)
                else "network"
                if isinstance(error, httpx.TransportError)
                else "invalid_response"
            )
            raise
        finally:
            self.call_metadata.append(
                OpenRouterCallMetadata(
                    "openrouter",
                    self._settings.model,
                    int(
                        ((completed_at if completed_at is not None else monotonic()) - started)
                        * 1000
                    ),
                    request.prompt_version,
                    request.schema_version,
                    usage if usage is not None else stream_metrics.usage,
                    failure,
                    ttft_ms if ttft_ms is not None else stream_metrics.ttft_ms,
                    attempt_id,
                    started_at,
                    stream_metrics.generation_id,
                    stream_metrics.route,
                )
            )


async def _collect_stream(response: httpx.Response, started: float, metrics: StreamMetrics):
    """Measure first content but expose nothing until the entire response is validated."""
    parts = []
    usage = {}
    finish = None
    ttft = None
    data = []
    completed = False
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            continue
        if line or not data:
            continue
        event = "\n".join(data)
        data = []
        if event == "[DONE]":
            completed = True
            break
        try:
            chunk = json.loads(event)
            received_id = generation_id(chunk.get("id"))
            if received_id:
                if metrics.generation_id not in (None, received_id):
                    metrics.generation_id = None
                    raise LLMInvalidResponseError("OpenRouter stream changed generation identity")
                metrics.generation_id = received_id
            metrics.route = metrics.route or route_name(chunk.get("provider"))
            if "usage" in chunk:
                usage = chunk["usage"]
                received_usage = _usage_metadata(usage)
                if received_usage:
                    metrics.usage = {**(metrics.usage or {}), **received_usage}
            if chunk.get("error"):
                raise LLMInvalidResponseError("OpenRouter stream failed")
            for choice in chunk.get("choices", []):
                content = choice.get("delta", {}).get("content")
                if content:
                    if not isinstance(content, str):
                        raise LLMInvalidResponseError("OpenRouter stream contains invalid content")
                    if ttft is None:
                        ttft = (monotonic() - started) * 1000
                        metrics.ttft_ms = ttft
                    parts.append(content)
                if choice.get("finish_reason") is not None:
                    finish = choice["finish_reason"]
        except (ValueError, AttributeError, TypeError) as error:
            raise LLMInvalidResponseError("OpenRouter stream contains invalid data") from error
    if not completed or finish != "stop":
        raise LLMInvalidResponseError("OpenRouter stream did not complete successfully")
    return {
        "choices": [{"finish_reason": finish, "message": {"content": "".join(parts)}}],
        "usage": metrics.usage,
    }, ttft
