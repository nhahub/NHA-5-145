"""Bounded speech transcription for the Controlled Storefront demo."""

import base64
from math import isfinite
from typing import Protocol

import httpx

from agent.llm.config import LLMSettings
from agent.llm.openrouter import OpenRouterBudgetError

MAX_AUDIO_BYTES = 750_000
MIN_REMAINING_DOLLARS = 0.50


class SpeechTranscriber(Protocol):
    async def available(self) -> bool: ...

    async def transcribe(self, audio: bytes, language: str) -> str: ...


class OpenRouterSpeechTranscriber:
    def __init__(self, settings: LLMSettings, *, transport: httpx.AsyncBaseTransport | None = None):
        if settings.provider != "openrouter" or not settings.api_key:
            raise ValueError("Speech transcription requires the configured OpenRouter key")
        self._settings = settings
        self._transport = transport

    async def transcribe(self, audio: bytes, language: str) -> str:
        if not 4 <= len(audio) <= MAX_AUDIO_BYTES or not audio.startswith(b"\x1a\x45\xdf\xa3"):
            raise ValueError("A bounded WebM recording is required")
        if language not in {"ar", "en"}:
            raise ValueError("Unsupported speech language")
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=30,
            headers={"Authorization": f"Bearer {self._settings.api_key.get_secret_value()}"},
        ) as client:
            if not await self._has_budget(client):
                raise OpenRouterBudgetError(
                    "Speech transcription requires at least $0.50 available"
                )
            response = await client.post(
                "https://openrouter.ai/api/v1/audio/transcriptions",
                json={
                    "model": "openai/whisper-large-v3-turbo",
                    "input_audio": {
                        "data": base64.b64encode(audio).decode("ascii"),
                        "format": "webm",
                    },
                    "language": language,
                },
            )
            response.raise_for_status()
        text = response.json().get("text")
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 500:
            raise ValueError("Speech provider returned no bounded transcript")
        return text.strip()

    async def available(self) -> bool:
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=10,
            headers={"Authorization": f"Bearer {self._settings.api_key.get_secret_value()}"},
        ) as client:
            return await self._has_budget(client)

    async def _has_budget(self, client: httpx.AsyncClient) -> bool:
        response = await client.get("https://openrouter.ai/api/v1/key")
        response.raise_for_status()
        key = response.json().get("data", {})
        limit, remaining = key.get("limit"), key.get("limit_remaining")
        return (
            all(
                isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value)
                for value in (limit, remaining)
            )
            and 0 < limit <= self._settings.openrouter_total_limit
            and remaining >= MIN_REMAINING_DOLLARS
            and key.get("limit_reset") is None
        )
