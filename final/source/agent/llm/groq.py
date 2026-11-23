import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from math import ceil, isfinite
from time import monotonic
from typing import Any

import httpx

from agent.llm.config import LLMConfigurationError, LLMSettings
from agent.llm.contract import LLMChunk, LLMInvalidResponseError, LLMRequest


@dataclass(frozen=True)
class GroqCallMetadata:
    provider: str
    model: str
    endpoint: str
    latency_ms: int
    parameters: dict[str, object]
    prompt_version: str
    schema_version: int | None
    usage: dict[str, int] | None
    failure_category: str | None


class GroqRateLimitError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Model rate limit: retry after {retry_after_seconds} seconds")


class GroqClient:
    """Groq adapter with strict structured output for the Intent Interpreter."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if settings.provider != "groq" or settings.api_key is None or settings.endpoint is None:
            raise LLMConfigurationError("Groq settings require a key and endpoint")
        self._clock = clock
        self._retry_at = 0.0
        self._settings = settings
        self._transport = transport
        self.call_metadata: list[GroqCallMetadata] = []

    async def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        started = monotonic()
        try:
            if self._clock() < self._retry_at:
                raise GroqRateLimitError(ceil(self._retry_at - self._clock()))
            chunks, usage = await self._complete_with_retry(request)
        except Exception as error:
            self._record(request, started, usage=None, failure_category=_failure_category(error))
            raise
        self._record(request, started, usage=usage, failure_category=None)
        for chunk in chunks:
            yield chunk

    async def _complete_with_retry(
        self, request: LLMRequest
    ) -> tuple[list[LLMChunk], dict[str, int] | None]:
        for attempt in range(request.provider_attempt_limit):
            try:
                return await self._complete(request)
            except (
                httpx.HTTPStatusError,
                httpx.TimeoutException,
                httpx.TransportError,
                ValueError,
            ) as error:
                if attempt + 1 >= request.provider_attempt_limit or not _is_retryable(error):
                    raise
                await asyncio.sleep(0.25)
        raise AssertionError("unreachable")

    async def _complete(self, request: LLMRequest) -> tuple[list[LLMChunk], dict[str, int] | None]:
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": request.system},
                *[
                    {
                        "role": "user" if message.role == "shopper" else message.role,
                        "content": message.content,
                    }
                    for message in request.messages
                ],
            ],
            "stream": False,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "reasoning_effort": self._settings.reasoning_effort,
        }
        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"structured_intent_v{request.schema_version or 1}",
                    "strict": True,
                    "schema": _strict_schema(request.response_schema),
                },
            }
        endpoint = f"{self._settings.endpoint.rstrip('/')}/chat/completions"
        headers = {
            "authorization": f"Bearer {self._settings.api_key.get_secret_value()}",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._settings.timeout_seconds,
        ) as client:
            await request.authorize()
            response = await client.post(endpoint, headers=headers, json=payload)
            if response.status_code == 429:
                try:
                    delay = float(response.headers.get("retry-after", "60"))
                except ValueError:
                    delay = 60
                if not isfinite(delay) or delay <= 0:
                    delay = 60
                self._retry_at = self._clock() + delay
                raise GroqRateLimitError(ceil(delay))
            response.raise_for_status()
        try:
            body = response.json()
        except ValueError as error:
            raise LLMInvalidResponseError("Groq response body is not JSON") from error
        chunks, usage = _parse_completion(body)
        if request.response_validator is not None:
            request.response_validator("".join(chunk.text or "" for chunk in chunks))
        return chunks, usage

    def _record(
        self,
        request: LLMRequest,
        started: float,
        *,
        usage: dict[str, int] | None,
        failure_category: str | None,
    ) -> None:
        self.call_metadata.append(
            GroqCallMetadata(
                provider="groq",
                model=self._settings.model,
                endpoint=self._settings.endpoint or "",
                latency_ms=int((monotonic() - started) * 1000),
                parameters={
                    "stream": False,
                    "timeout_seconds": self._settings.timeout_seconds,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "reasoning_effort": self._settings.reasoning_effort,
                    "strict_schema": request.response_schema is not None,
                },
                prompt_version=request.prompt_version,
                schema_version=request.schema_version,
                usage=usage,
                failure_category=failure_category,
            )
        )


def _strict_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    strict = deepcopy(dict(schema))

    def visit(value: object) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            value.pop("title", None)
            value.pop("description", None)
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["additionalProperties"] = False
                value["required"] = list(properties)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(strict)
    return strict


def _parse_completion(payload: object) -> tuple[list[LLMChunk], dict[str, int] | None]:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (IndexError, KeyError, TypeError) as error:
        raise LLMInvalidResponseError("Groq response contains an invalid completion") from error
    if not isinstance(content, str) or not content:
        raise LLMInvalidResponseError("Groq response contains empty non-text content")
    raw_usage = payload.get("usage") if isinstance(payload, dict) else None
    usage = (
        {
            key: value
            for key, value in raw_usage.items()
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and isinstance(value, int)
        }
        if isinstance(raw_usage, dict)
        else None
    )
    return [LLMChunk(text=content)], usage


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    return isinstance(error, httpx.TimeoutException | httpx.TransportError)


def _failure_category(error: Exception) -> str:
    if isinstance(error, GroqRateLimitError):
        return "throttled"
    if isinstance(error, httpx.HTTPStatusError):
        return "throttled" if error.response.status_code == 429 else "http"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "network"
    return "invalid_response"
