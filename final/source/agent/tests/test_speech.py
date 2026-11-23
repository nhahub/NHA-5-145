import asyncio
import base64
import json

import httpx
import pytest

from agent.app import create_app
from agent.llm import ScriptedLLMClient
from agent.llm.config import load_llm_settings
from agent.speech import OpenRouterSpeechTranscriber
from agent.tests.http_client import TestClient


def settings():
    return load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "google/gemini-2.5-flash",
            "OPENROUTER_API_KEY": "test-secret",
            "OPENROUTER_TOTAL_CAP_DOLLARS": "0.75",
        }
    )


def test_audio_endpoint_returns_editable_transcript_without_creating_a_task() -> None:
    class FakeTranscriber:
        def __init__(self):
            self.calls = []

        async def transcribe(self, audio: bytes, language: str) -> str:
            self.calls.append((audio, language))
            return "عايز كوتشي جري"

        async def available(self) -> bool:
            return True

    fake = FakeTranscriber()
    app = create_app(
        llm_settings=settings(), llm_client=ScriptedLLMClient([]), speech_transcriber=fake
    )
    client = TestClient(app)
    assert client.get("/speech/availability").json() == {"available": True}
    response = client.post(
        "/speech/transcribe?language=ar",
        content=b"\x1a\x45\xdf\xa3audio",
        headers={"content-type": "audio/webm"},
    )
    assert response.status_code == 200
    assert response.json() == {"text": "عايز كوتشي جري"}
    assert fake.calls == [(b"\x1a\x45\xdf\xa3audio", "ar")]
    assert client.post("/speech/transcribe?language=ar", content=b"audio").status_code == 415
    assert (
        client.post(
            "/speech/transcribe?language=ar",
            content=b"x" * 750_001,
            headers={"content-type": "audio/webm"},
        ).status_code
        == 413
    )
    assert len(fake.calls) == 1


def test_openrouter_speech_checks_total_key_cap_before_transmitting_audio() -> None:
    audio = b"\x1a\x45\xdf\xa3audio"
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["authorization"] == "Bearer test-secret"
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200,
                json={"data": {"limit": 0.75, "limit_remaining": 0.75, "limit_reset": None}},
            )
        body = json.loads(request.content)
        assert body["model"] == "openai/whisper-large-v3-turbo"
        assert body["input_audio"] == {
            "data": base64.b64encode(audio).decode("ascii"),
            "format": "webm",
        }
        assert body["language"] == "ar"
        return httpx.Response(200, json={"text": "عايز كوتشي جري"})

    transcriber = OpenRouterSpeechTranscriber(settings(), transport=httpx.MockTransport(handler))
    assert asyncio.run(transcriber.transcribe(audio, "ar")) == "عايز كوتشي جري"
    assert calls == ["/api/v1/key", "/api/v1/audio/transcriptions"]


def test_openrouter_speech_rejects_unsafe_key_limit_without_paid_call() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={"data": {"limit": 100, "limit_remaining": 100, "limit_reset": None}},
        )

    transcriber = OpenRouterSpeechTranscriber(settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError):
        asyncio.run(transcriber.transcribe(b"\x1a\x45\xdf\xa3audio", "en"))
    assert calls == ["/api/v1/key"]


def test_speech_fallback_unavailable_below_audio_minimum() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}},
        )

    transcriber = OpenRouterSpeechTranscriber(settings(), transport=httpx.MockTransport(handler))
    assert asyncio.run(transcriber.available()) is False
    assert calls == ["/api/v1/key"]
