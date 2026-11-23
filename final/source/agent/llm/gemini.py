"""Native Gemini structured output adapter; local validation remains authoritative."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from math import ceil, isfinite
from time import monotonic
from urllib.parse import quote

import httpx

from agent.llm.config import LLMConfigurationError, LLMSettings
from agent.llm.contract import LLMChunk, LLMInvalidResponseError, LLMRequest


@dataclass(frozen=True)
class GeminiCallMetadata:
    provider: str
    model: str
    latency_ms: int
    prompt_version: str
    schema_version: int | None
    usage: dict[str, int] | None
    failure_category: str | None


class GeminiRateLimitError(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Model rate limit: retry after {retry_after_seconds} seconds")


class GeminiClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
    ):
        if settings.provider != "gemini" or not settings.api_key or not settings.endpoint:
            raise LLMConfigurationError("Gemini settings require a key and endpoint")
        self._settings = settings
        self._transport = transport
        self._clock = clock
        self._retry_at = 0.0
        self.call_metadata: list[GeminiCallMetadata] = []

    async def complete(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        started = monotonic()
        usage = None
        failure = None
        try:
            if self._clock() < self._retry_at:
                raise GeminiRateLimitError(ceil(self._retry_at - self._clock()))
            config = {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}
            if self._settings.model == "gemini-2.5-flash":
                config["thinkingConfig"] = {"thinkingBudget": 0}
            if request.response_schema is not None:
                config["responseMimeType"] = "application/json"
                config["responseJsonSchema"] = dict(request.response_schema)
            if request.tools or any(
                m.role not in {"shopper", "assistant"} for m in request.messages
            ):
                raise ValueError("Gemini intent adapter accepts shopper and assistant text only")
            payload = {
                "systemInstruction": {"parts": [{"text": request.system}]},
                "contents": [
                    {
                        "role": "user" if m.role == "shopper" else "model",
                        "parts": [{"text": m.content}],
                    }
                    for m in request.messages
                ],
                "generationConfig": config,
            }
            model = quote(self._settings.model, safe="")
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._settings.timeout_seconds
            ) as client:
                await request.authorize()
                response = await client.post(
                    f"{self._settings.endpoint}/models/{model}:generateContent",
                    headers={"x-goog-api-key": self._settings.api_key.get_secret_value()},
                    json=payload,
                )
            if response.status_code == 429:
                try:
                    delay = float(response.headers.get("retry-after", "60"))
                except ValueError:
                    delay = 60.0
                if not isfinite(delay) or delay <= 0:
                    delay = 60.0
                self._retry_at = self._clock() + delay
                raise GeminiRateLimitError(ceil(delay))
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError as error:
                raise LLMInvalidResponseError("Gemini response body is not JSON") from error
            if not isinstance(body, dict):
                raise LLMInvalidResponseError("Gemini response must be an object")
            raw_usage = body.get("usageMetadata", {})
            if not isinstance(raw_usage, dict):
                raise LLMInvalidResponseError("Gemini response contains invalid usage metadata")
            usage = {
                target: raw_usage[source]
                for source, target in (
                    ("promptTokenCount", "prompt_tokens"),
                    ("candidatesTokenCount", "completion_tokens"),
                    ("totalTokenCount", "total_tokens"),
                )
                if isinstance(raw_usage.get(source), int)
            }
            try:
                candidate = body["candidates"][0]
                if candidate.get("finishReason") != "STOP":
                    raise LLMInvalidResponseError("Gemini response did not finish successfully")
                text = "".join(
                    p["text"]
                    for p in candidate["content"]["parts"]
                    if not p.get("thought") and isinstance(p.get("text"), str)
                )
            except (KeyError, IndexError, TypeError, AttributeError) as error:
                raise LLMInvalidResponseError(
                    "Gemini response contains no valid text completion"
                ) from error
            if not text:
                raise LLMInvalidResponseError("Gemini response contains no valid text completion")
            if request.response_validator is not None:
                request.response_validator(text)
            yield LLMChunk(text=text)
        except Exception as error:
            failure = (
                "throttled"
                if isinstance(error, GeminiRateLimitError)
                else "timeout"
                if isinstance(error, httpx.TimeoutException)
                else "network"
                if isinstance(error, httpx.TransportError)
                else "http"
                if isinstance(error, httpx.HTTPStatusError)
                else "invalid_response"
            )
            raise
        finally:
            self.call_metadata.append(
                GeminiCallMetadata(
                    "gemini",
                    self._settings.model,
                    int((monotonic() - started) * 1000),
                    request.prompt_version,
                    request.schema_version,
                    usage,
                    failure,
                )
            )
