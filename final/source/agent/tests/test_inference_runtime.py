import json
from decimal import Decimal

import pytest

from agent.app import create_app
from agent.inference.config import configured_guard
from agent.inference.ledger import AllowanceLedger
from agent.llm import LLMChunk, LLMSettings, ScriptedLLMClient
from agent.tests.http_client import TestClient
from agent.tests.test_advice import Reader, advice, decision
from agent.tests.test_catalogue_retrieval import Reads
from agent.tests.test_real_task import navigation_intent
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def configure(monkeypatch, path, identity):
    values = {
        "INFERENCE_LEDGER_PATH": str(path),
        "INFERENCE_LEDGER_ID": identity,
        "INFERENCE_PROVIDER": "groq",
        "INFERENCE_MODEL": "test-model",
        "INFERENCE_INPUT_USD_PER_MILLION": "0.3",
        "INFERENCE_OUTPUT_USD_PER_MILLION": "2.5",
        "INFERENCE_MAX_ACTIVE": "1",
        "INFERENCE_MAX_WAITING": "1",
        "INFERENCE_WAIT_SECONDS": "0.1",
        "INFERENCE_MAXIMUM_PAGES": "1024",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_openrouter_cannot_configure_prices_below_its_route_ceiling(tmp_path, monkeypatch):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("1"))
    configure(monkeypatch, path, identity)
    monkeypatch.setenv("INFERENCE_PROVIDER", "openrouter")
    monkeypatch.setenv("INFERENCE_MODEL", "google/gemini-3.5-flash-lite")
    monkeypatch.setenv("INFERENCE_INPUT_USD_PER_MILLION", "0.1")
    with pytest.raises(ValueError, match="allowance configuration"):
        configured_guard(
            ScriptedLLMClient(),
            LLMSettings(provider="openrouter", model="google/gemini-3.5-flash-lite"),
        )


@pytest.mark.parametrize(
    "failure, expected",
    [
        ("budget", "spending allowance"),
        ("disabled", "temporarily disabled"),
        ("missing", "could not be verified safely"),
    ],
)
def test_http_refusal_does_not_call_provider_or_emit_action(
    tmp_path, monkeypatch, failure, expected
):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(
        path, Decimal("0.001") if failure == "budget" else Decimal("1")
    )
    configure(monkeypatch, path, identity)
    calls = []

    class FakeProvider:
        async def complete(self, request):
            calls.append(request)
            yield LLMChunk(text=navigation_intent("navigate", "cart"))

    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test-model"),
            llm_client=FakeProvider(),
            catalogue_retrieval_enabled=False,
        )
    )
    sid = client.post("/sessions").json()["session_id"]
    if failure == "disabled":
        AllowanceLedger(path, identity).set_enabled(False)
    elif failure == "missing":
        path.unlink()
    response = client.post(
        f"/sessions/{sid}/messages", json={"text": "Open my cart", "snapshot": home_snapshot()}
    )
    assert response.status_code == 202
    events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
    assert not calls
    assert not any(e["event"] == "action" for e in events)
    assert expected in next(e["data"]["message"] for e in events if e["event"] == "error")


def test_http_interpretation_repair_uses_same_durable_allowance(tmp_path, monkeypatch):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("1"))
    configure(monkeypatch, path, identity)
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test-model"),
            llm_client=ScriptedLLMClient(
                [
                    [LLMChunk(text="not json")],
                    [LLMChunk(text=navigation_intent("navigate", "cart"))],
                ]
            ),
            catalogue_retrieval_enabled=False,
        )
    )
    sid = client.post("/sessions").json()["session_id"]
    assert (
        client.post(
            f"/sessions/{sid}/messages", json={"text": "Open my cart", "snapshot": home_snapshot()}
        ).status_code
        == 202
    )
    events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
    assert any(e["event"] == "action" for e in events)
    status = AllowanceLedger(path, identity).status()
    assert status["attempts"] == 2
    assert status["uncertain"] == 2


def test_durable_protection_disables_unqualified_server_transcription(tmp_path, monkeypatch):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("1"))
    configure(monkeypatch, path, identity)
    calls = []

    class FakeTranscriber:
        async def available(self):
            calls.append("available")
            return True

        async def transcribe(self, audio, language):
            calls.append("paid-call")
            return "fixture"

    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test-model"),
            llm_client=ScriptedLLMClient(),
            speech_transcriber=FakeTranscriber(),
        )
    )
    assert client.get("/speech/availability").json() == {"available": False}
    response = client.post(
        "/speech/transcribe?language=ar",
        content=b"\x1a\x45\xdf\xa3audio",
        headers={"content-type": "audio/webm"},
    )
    assert response.status_code == 503
    assert calls == []


@pytest.mark.parametrize("retrieval", [False, True])
@pytest.mark.parametrize("stop", [None, "disabled", "budget"])
def test_http_advice_reserves_separately_and_refuses_after_interpretation(
    tmp_path, monkeypatch, retrieval, stop
):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("1"))
    ledger = AllowanceLedger(path, identity)
    configure(monkeypatch, path, identity)
    reference = "p-4" if retrieval else "white-shirt"
    responses = (
        [
            {"kind": "search", "query": {"query": "shirt"}},
            {"kind": "recommend", "language": "en", "selected_ids": [reference]},
        ]
        if retrieval
        else [decision()]
    )
    before_advice = len(responses)
    responses.append(advice("In my opinion, this shirt could suit the outfit.", [reference]))
    calls = []

    class Model:
        async def complete(self, request):
            calls.append(request)
            yield LLMChunk(text=json.dumps(responses[len(calls) - 1]))
            if len(calls) == before_advice:
                if stop == "disabled":
                    ledger.set_enabled(False)
                elif stop == "budget":
                    # A separate admitted caller consumes the remaining allowance
                    # while this Shopping Task is between interpretation and advice.
                    ledger.reserve("other-call", Decimal(ledger.status()["remaining_usd"]))

    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test-model"),
            llm_client=Model(),
            catalogue_reader=Reader(),
            catalogue_client=Reads(),
            catalogue_retrieval_enabled=retrieval,
        )
    )
    sid = client.post("/sessions").json()["session_id"]
    assert (
        client.post(
            f"/sessions/{sid}/messages",
            json={"text": "What shirt could go with black trousers?", "snapshot": home_snapshot()},
        ).status_code
        == 202
    )
    events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
    assert not any(e["event"] == "action" for e in events)
    if stop:
        assert len(calls) == before_advice
        assert any(e["event"] == "error" for e in events)
        assert not any(e["event"] in {"suggestions", "done"} for e in events)
    else:
        assert len(calls) == before_advice + 1
        assert calls[-1].prompt_version == "advice-v4"
        assert any(e["event"] == "done" for e in events)
        assert ledger.status()["attempts"] == len(calls)
        assert ledger.status()["uncertain"] == len(calls)
