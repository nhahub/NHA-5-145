"""Every Shopping Task end reaches one observable point (seam 1: the Agent HTTP API)."""

import json
import re

import httpx

from agent.app import create_app
from agent.event_log import MemorySink
from agent.llm import LLMChunk, LLMSettings, ScriptedLLMClient
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_guarded_task import cart_snapshot, clear_intent
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

CLEAR_SETTINGS = LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None)


RANDOM = re.compile(r"(task|action|session)-[0-9a-f]{32}|\"shopper\": \"[0-9a-f]{16}\"")


def mask(text: str) -> str:
    return RANDOM.sub("id", text)


def watched(store: SessionStore) -> list[tuple[str, str, str | None]]:
    ends: list[tuple[str, str, str | None]] = []
    store.on_task_end(lambda end: ends.append((end.task.task_id, end.kind, end.reason)))
    return ends


def wire(revision: str = "3") -> dict:
    return cart_snapshot(revision).model_dump(mode="json", by_alias=True, exclude_none=True)


def sent_action(client: TestClient, session_id: str) -> dict:
    events = parse_sse(client.get(f"/sessions/{session_id}/events?after=0&once=true").text)
    return [e for e in events if e["event"] == "action"][-1]["data"]["action"]


def navigated(action: dict, url: str) -> dict:
    return {
        "v": 1,
        "task_id": action["task_id"],
        "action_id": action["action_id"],
        "sequence_number": action["sequence_number"],
        "status": "navigated",
        "snapshot": {**home_snapshot(), "url": url},
    }


def journey_completed(client: TestClient) -> str:
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    action = sent_action(client, session_id)
    client.post(
        f"/sessions/{session_id}/action-results",
        json=navigated(action, "http://localhost:4000/c/shoes?type=running&max_price=2000"),
    )
    return session_id


def journey_stop(client: TestClient) -> str:
    session_id = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري بأقل من ٢٠٠٠", "snapshot": home_snapshot()},
    )
    assert client.post(f"/sessions/{session_id}/stop").status_code == 202
    return session_id


def clear_client(store: SessionStore, sink: MemorySink | None = None) -> TestClient:
    return TestClient(
        create_app(
            session_store=store,
            llm_settings=CLEAR_SETTINGS,
            llm_client=ScriptedLLMClient(
                [[LLMChunk(text=json.dumps({**clear_intent().model_dump(mode="json"), "v": 9}))]]
            ),
            event_sink=sink,
        )
    )


def offer(client: TestClient) -> tuple[str, str, str]:
    session_id = client.post("/sessions").json()["session_id"]
    task_id = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Please empty my cart", "snapshot": wire()},
    ).json()["task_id"]
    question = sent_action(client, session_id)
    return session_id, task_id, question["action_id"]


def answer(client: TestClient, session_id: str, task_id: str, question_id: str, text: str, snap):
    return client.post(
        f"/sessions/{session_id}/tasks/{task_id}/answers",
        json={"question_id": question_id, "text": text, "snapshot": snap},
    )


def test_a_completed_task_ends_once_as_completed() -> None:
    store = SessionStore()
    ends = watched(store)
    client = TestClient(create_app(session_store=store))

    session_id = journey_completed(client)

    task = store.get(session_id).last_task
    assert task is not None and task.status == "completed"
    assert store.get(session_id).active_task is None
    assert ends == [(task.task_id, "completed", None)]


def test_stop_mid_task_ends_once_as_cancelled() -> None:
    store = SessionStore()
    ends = watched(store)
    client = TestClient(create_app(session_store=store))

    session_id = journey_stop(client)

    task = store.get(session_id).last_task
    assert task is not None and task.status == "cancelled"
    assert store.get(session_id).active_task is None
    assert ends == [(task.task_id, "cancelled", None)]


def test_a_replaced_task_ends_as_cancelled_before_the_new_one_begins() -> None:
    store = SessionStore()
    ends = watched(store)
    client = TestClient(create_app(session_store=store))
    session_id = client.post("/sessions").json()["session_id"]
    first = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "عاوز كوتشي للجري", "snapshot": home_snapshot()},
    ).json()["task_id"]

    second = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "افتح السلة", "snapshot": home_snapshot(), "replace_active": True},
    ).json()["task_id"]

    assert ends == [(first, "cancelled", None)]
    assert store.get(session_id).active_task.task_id == second


def test_stopping_a_confirmation_ends_the_task_as_cancelled() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    ends = watched(store)
    client = clear_client(store)
    session_id, task_id, question_id = offer(client)

    stopped = answer(client, session_id, task_id, question_id, "Stop", wire())

    assert stopped.status_code == 202
    assert ends == [(task_id, "cancelled", None)]
    assert store.get(session_id).active_task is None


def test_a_stale_or_expired_confirmation_leaves_the_task_open_until_it_is_stopped() -> None:
    clock = [100.0]
    store = SessionStore(clock=lambda: clock[0], confirmation_registrar=lambda *_: True)
    ends = watched(store)
    client = clear_client(store)
    session_id, task_id, question_id = offer(client)

    changed = answer(client, session_id, task_id, question_id, "Confirm", wire("4"))
    clock[0] = 160.0
    late = answer(client, session_id, task_id, question_id, "Confirm", wire())

    assert (changed.status_code, late.status_code) == (409, 409)
    assert ends == []
    assert store.get(session_id).active_task.task_id == task_id
    client.post(f"/sessions/{session_id}/stop")
    assert ends == [(task_id, "cancelled", None)]


def test_a_refresh_during_a_confirmation_pauses_the_task_with_its_reason() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    ends = watched(store)
    client = clear_client(store)
    session_id, task_id, _ = offer(client)

    client.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    assert ends == [(task_id, "paused", "refresh")]
    assert store.get(session_id).active_task.status == "paused"


def test_an_interpretation_pause_ends_the_task_with_its_reason() -> None:
    class TimeoutClient:
        async def complete(self, request):
            del request
            raise httpx.ReadTimeout("private timeout detail")
            yield LLMChunk(text="unused")

    store = SessionStore()
    ends = watched(store)
    client = TestClient(
        create_app(
            session_store=store,
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b"),
            llm_client=TimeoutClient(),
        )
    )
    session_id = client.post("/sessions").json()["session_id"]

    task_id = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Find running shoes", "snapshot": home_snapshot()},
    ).json()["task_id"]

    assert ends == [(task_id, "paused", "timeout")]


def test_a_verified_guarded_click_ends_the_task_as_completed() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    ends = watched(store)
    client = clear_client(store)
    session_id, task_id, question_id = offer(client)
    answer(client, session_id, task_id, question_id, "Confirm", wire())
    click = sent_action(client, session_id)
    empty = {
        **home_snapshot(),
        "url": "http://localhost:4000/cart",
        "elements": [{"id": 1, "role": "status", "name": "السلة فارغة", "visible": True}],
    }

    client.post(
        f"/sessions/{session_id}/action-results",
        json={
            "v": 1,
            "task_id": task_id,
            "action_id": click["action_id"],
            "sequence_number": click["sequence_number"],
            "status": "navigated",
            "snapshot": empty,
        },
    )

    assert ends == [(task_id, "completed", None)]


def test_a_listener_changes_nothing_a_single_message_journey_shows() -> None:
    def trace(journey, listen: bool):
        sink, store = MemorySink(), SessionStore()
        if listen:
            watched(store)
        client = TestClient(create_app(session_store=store, event_sink=sink))
        session_id = journey(client)
        session = store.get(session_id)
        events = [(e.id, e.event, {**e.data, "session_id": "-"}) for e in session.events]
        records = [
            {k: v for k, v in r.items() if k not in {"session_id", "task_id", "ts", "time"}}
            for r in sink.records
            if r["event"] != "http_request"
        ]
        state = (
            session.active_task is None,
            session.last_task.status if session.last_task else None,
            session.conversation,
        )
        return json.dumps([events, records, state], default=str, sort_keys=True).replace(
            session_id, "-"
        )

    for journey in (journey_completed, journey_stop):
        quiet, listened = trace(journey, False), trace(journey, True)
        # Ids and the scrambled shopper tag are random; compare with them masked.
        assert mask(quiet) == mask(listened)


def test_every_listener_hears_each_end_in_registration_order() -> None:
    store = SessionStore()
    heard: list[str] = []
    store.on_task_end(lambda end: heard.append(f"first:{end.kind}"))
    store.on_task_end(lambda end: heard.append(f"second:{end.kind}"))
    client = TestClient(create_app(session_store=store))

    journey_stop(client)

    assert heard == ["first:cancelled", "second:cancelled"]
