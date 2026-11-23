"""Event log records observed through the Agent's HTTP API (seam 1)."""

import json

import pytest

from agent.app import create_app
from agent.event_log import EventLog, MemorySink
from agent.llm import LLMChunk, LLMSettings, ScriptedLLMClient
from agent.tests.http_client import TestClient
from agent.tests.test_real_task import navigation_intent
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def records(sink, event):
    return [record for record in sink.records if record["event"] == event]


def test_each_request_is_recorded_with_its_route_template_status_and_duration() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))

    session_id = client.post("/sessions").json()["session_id"]
    client.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    requests = records(sink, "http_request")
    state = [r for r in requests if r["route"] == "/sessions/{session_id}/state"]
    assert len(state) == 1
    assert state[0]["method"] == "GET"
    assert state[0]["status"] == 200
    assert isinstance(state[0]["duration_ms"], int) and state[0]["duration_ms"] >= 0
    assert all(session_id not in r["route"] for r in requests)


def test_health_checks_and_activity_pings_are_not_recorded() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))

    client.get("/health")
    client.post("/shopper/activity")

    routes = [r["route"] for r in records(sink, "http_request")]
    assert "/health" not in routes
    assert "/shopper/activity" not in routes


def test_what_the_shopper_typed_appears_in_no_record() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))
    session_id = client.post("/sessions").json()["session_id"]
    typed = "عاوز كوتشي للجري بأقل من ٢٠٠٠ secret-phrase-7731"

    submitted = client.post(
        f"/sessions/{session_id}/messages", json={"text": typed, "snapshot": home_snapshot()}
    )

    assert submitted.status_code == 202
    assert any(
        r["route"] == "/sessions/{session_id}/messages" for r in records(sink, "http_request")
    )
    dumped = json.dumps(sink.records, ensure_ascii=False)
    assert "secret-phrase-7731" not in dumped
    assert "كوتشي" not in dumped


def test_a_record_refuses_unknown_fields_and_free_text() -> None:
    log = EventLog(MemorySink())

    with pytest.raises(ValueError):
        log.emit("http_request", method="GET", message="hello")
    with pytest.raises(ValueError):
        log.emit("http_request", method="GET", route="عاوز كوتشي")
    with pytest.raises(ValueError):
        log.emit("http_request", method="GET", route="a sentence with spaces")
    with pytest.raises(ValueError):
        log.emit("no_such_event")
    assert log.sink.records == []


def test_without_a_sink_records_print_to_the_terminal_as_json_lines(capsys) -> None:
    client = TestClient(create_app())

    client.post("/sessions")

    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    parsed = [json.loads(line) for line in lines]
    assert any(r["event"] == "http_request" and r["route"] == "/sessions" for r in parsed)
    assert all(r["release"] == "local" for r in parsed)


class BrokenSink:
    def write(self, record):
        raise OSError("disk full")


def test_logging_never_breaks_a_request() -> None:
    client = TestClient(create_app(event_sink=BrokenSink()))

    assert client.post("/sessions").status_code == 201

    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))
    unusual = client.request("PROPFIND", "/sessions")

    assert unusual.status_code == 405
    assert any(r["method"] == "OTHER" for r in records(sink, "http_request"))


def test_a_rejected_request_keeps_its_route_template() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))
    unknown = "session-" + "0" * 32

    response = client.get(f"/sessions/{unknown}/state?tab_id=tab-1")

    assert response.status_code == 404
    record = records(sink, "http_request")[-1]
    assert record["route"] == "/sessions/{session_id}/state"
    assert record["status"] == 404
    assert record["session_id"] == unknown


def test_a_session_id_that_is_not_one_the_agent_issues_is_not_recorded() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))

    client.get("/sessions/sneakers-under-2000/state?tab_id=tab-1")

    record = records(sink, "http_request")[-1]
    assert "session_id" not in record
    assert "sneakers" not in json.dumps(sink.records)


def test_a_completed_task_leaves_its_whole_trail_in_order() -> None:
    sink = MemorySink()
    client = TestClient(create_app(event_sink=sink))
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)[-1][
        "data"
    ]["action"]

    client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": "navigated",
            "snapshot": {
                **home_snapshot(),
                "url": "http://localhost:4000/c/shoes?type=running&max_price=2000",
            },
        },
    )

    trail = [r for r in sink.records if r["event"] in {"task", "action_result"}]
    assert [(r["event"], r.get("kind") or r.get("status")) for r in trail] == [
        ("task", "task_started"),
        ("task", "narration"),
        ("task", "action"),
        ("action_result", "navigated"),
        ("task", "done"),
    ]
    assert all(r["session_id"] == session_id for r in trail)
    assert all(r["task_id"] == action["task_id"] for r in trail)
    sent = trail[2]
    assert (sent["action_type"], sent["sequence"]) == ("navigate", 1)
    assert trail[3]["action_type"] == "navigate"
    assert "كوتشي" not in json.dumps(sink.records, ensure_ascii=False)


def test_a_paused_task_records_why_it_paused() -> None:
    import httpx

    class TimeoutClient:
        async def complete(self, request):
            del request
            raise httpx.ReadTimeout("private timeout detail")
            yield LLMChunk(text="unused")

    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b"),
            llm_client=TimeoutClient(),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Find running shoes", "snapshot": home_snapshot()},
    )

    paused = records(sink, "task_paused")
    assert [r["reason"] for r in paused] == ["timeout"]
    assert paused[0]["session_id"] == session_id
    assert "private timeout detail" not in json.dumps(sink.records)


def test_the_intent_the_model_chose_is_recorded() -> None:
    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=ScriptedLLMClient(
                [[LLMChunk(text=navigation_intent("navigate", "orders"))]]
            ),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Open order history", "snapshot": home_snapshot()},
    )

    intents = records(sink, "intent")
    assert len(intents) == 1
    assert (intents[0]["intent"], intents[0]["language"], intents[0]["dialect"]) == (
        "navigate",
        "en",
        "english",
    )
    assert intents[0]["needs_clarification"] is False
    assert "order history" not in json.dumps(sink.records)


def _clear_cart_client(sink, clock):
    from agent.sessions import SessionStore
    from agent.tests.test_guarded_task import clear_intent

    return TestClient(
        create_app(
            session_store=SessionStore(
                clock=lambda: clock[0], confirmation_registrar=lambda *_: True
            ),
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=ScriptedLLMClient(
                [[LLMChunk(text=json.dumps({**clear_intent().model_dump(mode="json"), "v": 9}))]]
            ),
            event_sink=sink,
        )
    )


def _offer(client, snapshot):
    session_id = client.post("/sessions").json()["session_id"]
    task_id = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Please empty my cart", "snapshot": snapshot},
    ).json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)
    question = next(e["data"]["action"] for e in events if e["event"] == "action")
    return f"/sessions/{session_id}/tasks/{task_id}/answers", question["action_id"]


def test_each_confirmation_outcome_is_recorded() -> None:
    from agent.tests.test_guarded_task import cart_snapshot

    def wire(revision="3"):
        return cart_snapshot(revision).model_dump(mode="json", by_alias=True, exclude_none=True)

    sink, clock = MemorySink(), [100.0]
    client = _clear_cart_client(sink, clock)
    answers, question_id = _offer(client, wire())
    changed = client.post(
        answers, json={"question_id": question_id, "text": "Confirm", "snapshot": wire("4")}
    )
    clock[0] = 160.0
    late = client.post(
        answers, json={"question_id": question_id, "text": "Confirm", "snapshot": wire()}
    )

    other, clock2 = MemorySink(), [100.0]
    client2 = _clear_cart_client(other, clock2)
    answers2, question_id2 = _offer(client2, wire())
    confirmed = client2.post(
        answers2, json={"question_id": question_id2, "text": "Confirm", "snapshot": wire()}
    )

    assert (changed.status_code, late.status_code, confirmed.status_code) == (409, 409, 202)
    assert [r["outcome"] for r in records(sink, "confirmation")] == ["stale", "expired"]
    assert [(r["outcome"], r["mutation_kind"]) for r in records(other, "confirmation")] == [
        ("consumed", "clear_cart")
    ]


def test_task_records_name_the_invitation_and_a_scrambled_shopper_never_the_code(tmp_path):
    from time import time

    from agent.admission.runtime import AdmissionPolicy
    from agent.admission.store import InvitationStore

    path = tmp_path / "admission.sqlite"
    store = InvitationStore(path, InvitationStore.initialize(path))
    invitation, code = store.issue(time() - 1, time() + 100, redemptions=2, sessions=4)
    sink = MemorySink()
    client = TestClient(
        create_app(
            admission=AdmissionPolicy(store),
            llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
            event_sink=sink,
        )
    )
    assert client.post("/shopper/admission", json={"code": code}).status_code == 200
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Open my cart", "snapshot": home_snapshot()},
    )

    trail = records(sink, "task")
    assert trail and all(r["invitation_id"] == invitation for r in trail)
    assert len({r["shopper"] for r in trail}) == 1
    assert code not in json.dumps(sink.records)


def _wire_cart(revision="3"):
    from agent.tests.test_guarded_task import cart_snapshot

    return cart_snapshot(revision).model_dump(mode="json", by_alias=True, exclude_none=True)


def test_stopping_or_refreshing_a_confirmation_is_recorded() -> None:
    sink = MemorySink()
    client = _clear_cart_client(sink, [100.0])
    answers, question_id = _offer(client, _wire_cart())
    client.post(
        answers, json={"question_id": question_id, "text": "Stop", "snapshot": _wire_cart()}
    )

    refreshed = MemorySink()
    client2 = _clear_cart_client(refreshed, [100.0])
    answers2, _ = _offer(client2, _wire_cart())
    session_id = answers2.split("/")[2]
    client2.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    assert [r["outcome"] for r in records(sink, "confirmation")] == ["stopped"]
    assert [r["outcome"] for r in records(refreshed, "confirmation")] == ["invalidated"]
    assert [r["reason"] for r in records(refreshed, "task_paused")] == ["refresh"]


def test_an_offered_confirmation_and_a_clarifying_question_are_told_apart() -> None:
    sink = MemorySink()
    client = _clear_cart_client(sink, [100.0])
    _offer(client, _wire_cart())

    asked = [r for r in records(sink, "task") if r.get("action_type") == "ask_shopper"]
    assert [r["question_kind"] for r in asked] == ["confirmation"]

    other = MemorySink()
    which_category = {
        "v": 9,
        "language": "en",
        "dialect": "english",
        "intent": "find_products",
        "constraints": {},
        "missing_fields": ["category"],
        "conflicting_fields": [],
        "needs_clarification": True,
    }
    clarifying = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=ScriptedLLMClient([[LLMChunk(text=json.dumps(which_category))]]),
            event_sink=other,
        )
    )
    session_id = clarifying.post("/sessions").json()["session_id"]
    clarifying.post(
        f"/sessions/{session_id}/messages",
        json={"text": "I want something nice", "snapshot": home_snapshot()},
    )
    kinds = [r.get("question_kind") for r in records(other, "task") if r["kind"] == "action"]
    assert "question" in kinds


def test_a_broken_log_never_stops_a_task() -> None:
    client = _clear_cart_client(BrokenSink(), [100.0])

    answers, question_id = _offer(client, _wire_cart())
    confirmed = client.post(
        answers, json={"question_id": question_id, "text": "Confirm", "snapshot": _wire_cart()}
    )

    assert confirmed.status_code == 202


class MeteredClient:
    """A model double that reports usage the way the production adapters do."""

    def __init__(self, text):
        self.text = text
        self.call_metadata = []

    async def complete(self, request):
        from types import SimpleNamespace

        self.call_metadata.append(
            SimpleNamespace(
                usage={"prompt_tokens": 1200, "completion_tokens": 85, "cost": 0.0011298},
                attempt_id=request.attempt_id,
            )
        )
        yield LLMChunk(text=self.text)


def test_each_model_call_is_recorded_with_its_tokens_and_cost() -> None:
    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=MeteredClient(navigation_intent("navigate", "orders")),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    task_id = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Open order history", "snapshot": home_snapshot()},
    ).json()["task_id"]

    calls = records(sink, "model_call")
    assert len(calls) == 1
    call = calls[0]
    assert (call["session_id"], call["task_id"]) == (session_id, task_id)
    assert (call["provider"], call["model"], call["outcome"]) == (
        "groq",
        "openai/gpt-oss-120b",
        "ok",
    )
    assert call["prompt_version"].startswith("intent-")
    assert (call["prompt_tokens"], call["completion_tokens"]) == (1200, 85)
    assert call["cost_usd"] == 0.0011298
    assert isinstance(call["latency_ms"], int)
    assert "navigate" not in json.dumps(call)


def test_a_failed_model_call_records_why_without_the_provider_message() -> None:
    import httpx

    class TimeoutClient:
        async def complete(self, request):
            del request
            raise httpx.ReadTimeout("private timeout detail")
            yield LLMChunk(text="unused")

    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b"),
            llm_client=TimeoutClient(),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Find running shoes", "snapshot": home_snapshot()},
    )

    calls = records(sink, "model_call")
    assert [(c["outcome"], c["failure"]) for c in calls] == [("failed", "timeout")]
    assert "prompt_tokens" not in calls[0] and "cost_usd" not in calls[0]
    assert "private timeout detail" not in json.dumps(sink.records)


def _retrieval_client(sink, *answers):
    from agent.tests.test_advice import RecordingModel
    from agent.tests.test_catalogue_retrieval import Reads

    model, reads = RecordingModel(*answers), Reads()
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=reads,
        catalogue_retrieval_enabled=True,
        event_sink=sink,
    )
    return TestClient(app), model, reads


def _ask(client, text):
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages", json={"text": text, "snapshot": home_snapshot()}
    )
    return session_id


def test_each_catalogue_turn_records_the_budget_it_used_and_how_it_ended() -> None:
    from agent.tests.test_advice import advice, decision

    sink = MemorySink()
    client, model, reads = _retrieval_client(
        sink,
        {"kind": "search", "query": {"query": "running shoes"}},
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
        advice("A light running shoe.", ["p-4"]),
    )
    session_id = _ask(client, "عايز كوتشي للجري")

    turns = records(sink, "retrieval_turn")
    assert len(turns) == 1
    turn = turns[0]
    assert turn["session_id"] == session_id
    assert (turn["outcome"], turn["decisions"], turn["advice"]) == ("recommend", 2, 1)
    assert turn["rejections"] == []
    assert turn["reads"] == len(reads.calls)
    assert [c["prompt_version"].split("-")[0] for c in records(sink, "model_call")] == [
        "catalogue",
        "catalogue",
        "advice",
    ]

    exhausted = MemorySink()
    client2, _, _ = _retrieval_client(exhausted, {}, {}, {})
    _ask(client2, "anything messy")
    assert [t["outcome"] for t in records(exhausted, "retrieval_turn")] == ["exhausted"]


class SharedAdapterClient:
    """Keeps call details in a bounded deque, like Bedrock, and another call lands after ours."""

    def __init__(self, text):
        from collections import deque

        self.text = text
        self.call_metadata = deque(maxlen=256)

    async def complete(self, request):
        from types import SimpleNamespace

        self.call_metadata.append(
            SimpleNamespace(
                attempt_id=request.attempt_id,
                usage={"prompt_tokens": 900, "completion_tokens": 40, "cost": 0.0007},
            )
        )
        self.call_metadata.append(
            SimpleNamespace(
                attempt_id="someone-else",
                usage={"prompt_tokens": 5, "completion_tokens": 5, "cost": 0.5},
            )
        )
        yield LLMChunk(text=self.text)


def test_usage_is_matched_to_its_own_call_by_attempt_id() -> None:
    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=SharedAdapterClient(navigation_intent("navigate", "orders")),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Open order history", "snapshot": home_snapshot()},
    )

    (call,) = records(sink, "model_call")
    assert (call["prompt_tokens"], call["completion_tokens"], call["cost_usd"]) == (900, 40, 0.0007)
    assert call["attempt_id"]


def test_a_catalogue_turn_that_fails_still_records_what_it_used() -> None:
    from agent.catalogue_client import CatalogueReadError

    class UnreachableCatalogue:
        calls = []

        async def search(self, query):
            raise CatalogueReadError("unavailable")

        async def details(self, query):
            raise CatalogueReadError("unavailable")

    from agent.tests.test_advice import RecordingModel

    sink = MemorySink()
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=RecordingModel({"kind": "search", "query": {"query": "running shoes"}}),
        catalogue_client=UnreachableCatalogue(),
        catalogue_retrieval_enabled=True,
        event_sink=sink,
    )
    _ask(TestClient(app), "عايز كوتشي للجري")

    turns = records(sink, "retrieval_turn")
    assert [(t["outcome"], t["decisions"]) for t in turns] == [("failed", 1)]
    assert [r["reason"] for r in records(sink, "task_paused")] == ["catalogue_unavailable"]


def test_a_cancelled_model_call_is_recorded_as_interrupted_not_ok() -> None:
    import asyncio

    from agent.event_log import bind
    from agent.inference.recorded import RecordedClient
    from agent.llm.contract import LLMRequest

    class Hanging:
        async def complete(self, request):
            await asyncio.sleep(60)
            yield LLMChunk(text="never")

    sink = MemorySink()
    recorded = RecordedClient(
        Hanging(), provider="groq", model="m", classify=lambda e: "unexpected"
    )

    async def call():
        with bind(EventLog(sink)):
            async for _ in recorded.complete(LLMRequest(system="s", messages=())):
                pass

    async def main():
        work = asyncio.create_task(call())
        await asyncio.sleep(0.01)
        work.cancel()
        with pytest.raises(asyncio.CancelledError):
            await work

    asyncio.run(main())

    assert [(r["outcome"], r["failure"]) for r in records(sink, "model_call")] == [
        ("failed", "interrupted")
    ]


class ExplodingClient:
    async def complete(self, request):
        del request
        raise RuntimeError("secret detail: عايز كوتشي")
        yield LLMChunk(text="unused")


def test_an_unexpected_error_is_recorded_by_type_and_place_never_its_message() -> None:
    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b"),
            llm_client=ExplodingClient(),
            event_sink=sink,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Find running shoes", "snapshot": home_snapshot()},
    )

    errors = records(sink, "error")
    assert len(errors) == 1
    assert errors[0]["error_type"] == "RuntimeError"
    assert errors[0]["location"] == "agent/tests/test_event_log.py:complete"
    assert errors[0]["session_id"] == session_id
    assert "secret detail" not in json.dumps(sink.records, ensure_ascii=False)


def _debug_client(sink, marker, llm_client):
    from agent.event_log import DebugSwitch

    return TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=llm_client,
            event_sink=sink,
            debug_switch=DebugSwitch(marker, owner=None),
        )
    )


def _send(client, text):
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages", json={"text": text, "snapshot": home_snapshot()}
    )
    return session_id


def test_without_the_marker_no_debug_record_is_written(tmp_path) -> None:
    sink = MemorySink()
    client = _debug_client(
        sink,
        tmp_path / "debug-logging",
        ScriptedLLMClient([[LLMChunk(text=navigation_intent("navigate", "orders"))]]),
    )

    _send(client, "افتح طلباتي")

    assert records(sink, "debug") == []
    assert "افتح" not in json.dumps(sink.records, ensure_ascii=False)


def test_a_fresh_marker_records_the_message_model_output_and_error_text(tmp_path) -> None:
    marker = tmp_path / "debug-logging"
    marker.write_text("")
    sink = MemorySink()
    _send(
        _debug_client(
            sink,
            marker,
            ScriptedLLMClient([[LLMChunk(text=navigation_intent("navigate", "orders"))]]),
        ),
        "افتح طلباتي",
    )
    failing = MemorySink()
    _send(_debug_client(failing, marker, ExplodingClient()), "Find running shoes")

    debug = {r["kind"]: r for r in records(sink, "debug")}
    assert debug["shopper_message"]["text"] == "افتح طلباتي"
    assert '"intent": "navigate"' in debug["model_output"]["text"]
    assert all(r["debug"] is True for r in debug.values())
    detail = [r for r in records(failing, "debug") if r["kind"] == "error_detail"]
    assert "secret detail" in detail[0]["text"]
    # Debug text never leaks into the ordinary records.
    ordinary = [r for r in sink.records if r["event"] != "debug"]
    assert "افتح" not in json.dumps(ordinary, ensure_ascii=False)


def test_a_marker_older_than_sixty_minutes_is_ignored(tmp_path) -> None:
    import os
    import time

    marker = tmp_path / "debug-logging"
    marker.write_text("")
    stale = time.time() - 61 * 60
    os.utime(marker, (stale, stale))
    sink = MemorySink()

    _send(
        _debug_client(
            sink,
            marker,
            ScriptedLLMClient([[LLMChunk(text=navigation_intent("navigate", "orders"))]]),
        ),
        "افتح طلباتي",
    )

    assert records(sink, "debug") == []


def test_no_web_route_can_turn_debug_logging_on() -> None:
    app = create_app(event_sink=MemorySink())

    assert not [r.path for r in app.routes if "debug" in getattr(r, "path", "").lower()]


def test_an_answer_to_a_question_is_captured_as_typed(tmp_path) -> None:
    marker = tmp_path / "debug-logging"
    marker.write_text("")
    which_category = {
        "v": 9,
        "language": "en",
        "dialect": "english",
        "intent": "find_products",
        "constraints": {},
        "missing_fields": ["category"],
        "conflicting_fields": [],
        "needs_clarification": True,
    }
    sink = MemorySink()
    client = _debug_client(
        sink,
        marker,
        ScriptedLLMClient(
            [
                [LLMChunk(text=json.dumps(which_category))],
                [LLMChunk(text=navigation_intent("navigate", "orders"))],
            ]
        ),
    )
    session_id = client.post("/sessions").json()["session_id"]
    task_id = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "I want something nice", "snapshot": home_snapshot()},
    ).json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)
    question = next(e["data"]["action"] for e in events if e["event"] == "action")

    client.post(
        f"/sessions/{session_id}/tasks/{task_id}/answers",
        json={
            "question_id": question["action_id"],
            "text": "shoes please",
            "snapshot": home_snapshot(),
        },
    )

    typed = [r["text"] for r in records(sink, "debug") if r["kind"] == "shopper_message"]
    assert typed == ["I want something nice", "shoes please"]


def test_a_failed_call_keeps_its_partial_output_while_debugging(tmp_path) -> None:
    class HalfAnswer:
        async def complete(self, request):
            yield LLMChunk(text='{"v": 9, "intent"')
            raise RuntimeError("cut off")

    marker = tmp_path / "debug-logging"
    marker.write_text("")
    sink = MemorySink()

    _send(_debug_client(sink, marker, HalfAnswer()), "Find running shoes")

    outputs = [r["text"] for r in records(sink, "debug") if r["kind"] == "model_output"]
    assert outputs == ['{"v": 9, "intent"']


def test_an_error_in_a_request_handler_is_recorded() -> None:
    from agent.sessions import SessionStore

    class BrokenStore(SessionStore):
        def state(self, session_id, tab_id):
            raise RuntimeError("store exploded: private")

    sink = MemorySink()
    client = TestClient(
        create_app(session_store=BrokenStore(), event_sink=sink), raise_server_exceptions=False
    )
    session_id = client.post("/sessions").json()["session_id"]

    response = client.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    assert response.status_code == 500
    (error,) = records(sink, "error")
    assert error["error_type"] == "RuntimeError"
    assert error["location"] == "agent/tests/test_event_log.py:state"
    assert "private" not in json.dumps(sink.records)


def test_debug_text_is_never_printed_to_a_terminal(tmp_path, capsys) -> None:
    from agent.event_log import DebugSwitch, StreamSink

    marker = tmp_path / "debug-logging"
    marker.write_text("")
    log = EventLog(StreamSink(), debug=DebugSwitch(marker, owner=None))

    log.emit_debug("shopper_message", "عايز كوتشي")

    printed = capsys.readouterr().err
    assert '"event":"debug"' not in printed and "shopper_message" not in printed


@pytest.mark.parametrize("unsafe", ["missing", "directory", "symlink", "future"])
def test_an_unsafe_or_odd_marker_never_turns_debug_on(tmp_path, unsafe) -> None:
    import os
    import time

    from agent.event_log import DebugSwitch

    marker = tmp_path / "debug-logging"
    real = tmp_path / "real"
    real.write_text("")
    if unsafe == "directory":
        marker.mkdir()
    elif unsafe == "symlink":
        try:
            marker.symlink_to(real)
        except OSError:
            pytest.skip("symlinks unavailable")
    elif unsafe == "future":
        marker.write_text("")
        ahead = time.time() + 3600
        os.utime(marker, (ahead, ahead))

    assert DebugSwitch(marker, owner=None).active() is False


@pytest.mark.skipif(__import__("os").name != "posix", reason="owners and modes are POSIX")
@pytest.mark.parametrize("unsafe", ["wrong_owner", "group_writable", "hard_link"])
def test_only_the_expected_owner_can_turn_debug_on(tmp_path, unsafe) -> None:
    import os

    from agent.event_log import DebugSwitch

    marker = tmp_path / "debug-logging"
    marker.write_text("")
    marker.chmod(0o644)
    owner = os.geteuid()
    if unsafe == "wrong_owner":
        owner = os.geteuid() + 1
    elif unsafe == "group_writable":
        marker.chmod(0o664)
    else:
        os.link(marker, tmp_path / "second-name")

    assert DebugSwitch(marker, owner=owner).active() is False
    assert DebugSwitch(marker, owner=None).active() is (unsafe == "wrong_owner")


def test_a_catalogue_turn_records_why_each_decision_was_rejected_without_any_text() -> None:
    sink = MemorySink()
    client, _, _ = _retrieval_client(
        sink,
        {"kind": "teleport", "note": "سر الشوبر"},
        {},
        {"kind": "recommend", "language": "ar", "selected_ids": ["p-1"]},
    )
    _ask(client, "عايز كوتشي سري جدا")

    (turn,) = records(sink, "retrieval_turn")
    assert turn["outcome"] == "exhausted"
    assert turn["rejections"] == ["decision_schema", "decision_schema", "selection_before_read"]
    everything = json.dumps(sink.records, ensure_ascii=False)
    for text in ("سري", "سر الشوبر", "teleport", "Field required", "validation error"):
        assert text not in everything


@pytest.mark.parametrize(
    "bad",
    [
        ["not a code"],
        ["decision_schema"] * 4,
        "decision_schema",
        [{"error": "text"}],
        [None],
    ],
)
def test_the_rejection_field_refuses_anything_but_a_short_list_of_codes(bad) -> None:
    log = EventLog(MemorySink())
    with pytest.raises(ValueError):
        log.emit("retrieval_turn", rejections=bad)
    log.emit("retrieval_turn", rejections=["other", "duplicate_ids"])
    log.emit("retrieval_turn", rejections=[])


def _openrouter_model_call(provider_field):
    import asyncio

    import httpx

    from agent.event_log import bind
    from agent.inference.recorded import RecordedClient
    from agent.llm.contract import LLMRequest
    from agent.llm.openrouter import OpenRouterClient
    from agent.tests.test_openrouter import settings

    def handler(request):
        if request.url.path.endswith("/key"):
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        body = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        if provider_field is not None:
            body["provider"] = provider_field
        return httpx.Response(200, json=body)

    sink = MemorySink()
    recorded = RecordedClient(
        OpenRouterClient(settings(), transport=httpx.MockTransport(handler)),
        provider="openrouter",
        model="google/gemini-2.5-flash",
        classify=lambda error: "unexpected",
    )

    async def call():
        with bind(EventLog(sink)):
            async for _ in recorded.complete(LLMRequest(system="s", messages=())):
                pass

    asyncio.run(call())
    (call_record,) = records(sink, "model_call")
    return call_record


def test_the_model_call_names_the_upstream_provider_that_served_it() -> None:
    assert _openrouter_model_call("Google AI Studio")["route"] == "Google_AI_Studio"
    assert _openrouter_model_call("Vertex-2.0")["route"] == "Vertex-2.0"


@pytest.mark.parametrize("hostile", ['x"; DROP', "a" * 41, "", "عايز", 5, None, ["Google"]])
def test_a_provider_name_that_is_not_a_short_token_is_dropped(hostile) -> None:
    assert "route" not in _openrouter_model_call(hostile)


def test_providers_without_an_upstream_name_record_no_route() -> None:
    sink = MemorySink()
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=SharedAdapterClient(navigation_intent("navigate", "orders")),
            event_sink=sink,
        )
    )
    _send(client, "Open order history")
    (call,) = records(sink, "model_call")
    assert "route" not in call
