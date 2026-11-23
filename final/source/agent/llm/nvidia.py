import asyncio
import json
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from agent.llm.config import LLMConfigurationError, LLMSettings
from agent.llm.contract import LLMChunk, LLMInvalidResponseError, LLMRequest


@dataclass(frozen=True)
class NvidiaCallMetadata:
    provider: str
    model: str
    endpoint: str
    latency_ms: int
    parameters: dict[str, object]
    prompt_version: str
    schema_version: int | None
    usage: dict[str, int] | None
    failure_category: str | None


class NvidiaNIMClient:
    """NVIDIA's OpenAI-compatible streaming chat-completions adapter."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if settings.provider != "nvidia" or settings.api_key is None or settings.endpoint is None:
            raise LLMConfigurationError("NVIDIA settings require a key and endpoint")
        self._settings = settings
        self._transport = transport
        self.call_metadata: list[NvidiaCallMetadata] = []

    async def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        started = monotonic()
        try:
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
                return await self._complete_stream(request)
            except (
                httpx.HTTPStatusError,
                httpx.TimeoutException,
                httpx.TransportError,
            ) as error:
                if attempt + 1 >= request.provider_attempt_limit or not _is_retryable(error):
                    raise
                await asyncio.sleep(0.25 + random.uniform(0, 0.1))
        raise AssertionError("unreachable")

    async def _complete_stream(
        self, request: LLMRequest
    ) -> tuple[list[LLMChunk], dict[str, int] | None]:
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
            "stream": self._settings.stream,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if request.response_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        endpoint = f"{self._settings.endpoint.rstrip('/')}/chat/completions"
        headers = {
            "authorization": f"Bearer {self._settings.api_key.get_secret_value()}",
            "content-type": "application/json",
        }
        chunks: list[LLMChunk] = []
        usage: dict[str, int] | None = None
        if not self._settings.stream:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self._settings.timeout_seconds,
            ) as client:
                await request.authorize()
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
            try:
                body = response.json()
            except ValueError as error:
                raise LLMInvalidResponseError("NVIDIA response body is not JSON") from error
            chunks, usage = _parse_completion(body)
            _validate_response(request, chunks)
            return chunks, usage

        saw_done = False
        await request.authorize()
        async with (
            httpx.AsyncClient(
                transport=self._transport,
                timeout=self._settings.timeout_seconds,
            ) as client,
            client.stream("POST", endpoint, headers=headers, json=payload) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    saw_done = True
                    break
                parsed_chunks, parsed_usage = _parse_stream_chunk(data)
                chunks.extend(parsed_chunks)
                usage = parsed_usage or usage
        if not saw_done:
            raise LLMInvalidResponseError("NVIDIA response ended before [DONE]")
        _validate_response(request, chunks)
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
            NvidiaCallMetadata(
                provider="nvidia",
                model=self._settings.model,
                endpoint=self._settings.endpoint or "",
                latency_ms=int((monotonic() - started) * 1000),
                parameters={
                    "stream": self._settings.stream,
                    "timeout_seconds": self._settings.timeout_seconds,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                prompt_version=request.prompt_version,
                schema_version=request.schema_version,
                usage=usage,
                failure_category=failure_category,
            )
        )


def _parse_stream_chunk(data: str) -> tuple[list[LLMChunk], dict[str, int] | None]:
    try:
        payload: dict[str, Any] = json.loads(data)
        choices = payload["choices"]
        delta = choices[0]["delta"]
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise LLMInvalidResponseError(
            "NVIDIA response contains an invalid streaming chunk"
        ) from error
    raw_usage = payload.get("usage")
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
    content = delta.get("content")
    if content is None:
        return [], usage
    if not isinstance(content, str):
        raise LLMInvalidResponseError("NVIDIA response contains non-text content")
    return [LLMChunk(text=content)], usage


def _parse_completion(payload: object) -> tuple[list[LLMChunk], dict[str, int] | None]:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (IndexError, KeyError, TypeError) as error:
        raise LLMInvalidResponseError("NVIDIA response contains an invalid completion") from error
    if not isinstance(content, str) or not content:
        raise LLMInvalidResponseError("NVIDIA response contains empty non-text content")
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


def _validate_response(request: LLMRequest, chunks: list[LLMChunk]) -> None:
    if request.response_validator is None:
        return
    request.response_validator("".join(chunk.text or "" for chunk in chunks))


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return isinstance(error, httpx.TimeoutException | httpx.TransportError)


def _failure_category(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return "throttled" if error.response.status_code == 429 else "http"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "network"
    return "invalid_response"
