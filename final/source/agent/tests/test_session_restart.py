"""Ticket 03 (shopper-state): the Copilot session survives an Agent restart.

A restart is simulated by building a second app on the same State Store file (the Storefront
link is a shared fake that always hands back the same Shopper binding, as the stable Storefront
generation does). Driven through the Agent's HTTP API with a scripted model; what is asserted is
visible: the state view, the stream, the actions sent, the model's requests and log records.
Expected strings are written out literally.
"""

import json
import secrets

import pytest

from agent.app import create_app
from agent.event_log import MemorySink
from agent.llm import LLMSettings
from agent.schemas import Snapshot
from agent.session_registry import SESSION_TTL_SECONDS
from agent.sessions import SessionNotFound, SessionStore, StateSaveFailed
from agent.shopper_access import ShopperBinding
from agent.state_store import SqliteStateStore, StateStoreError
from agent.tests import test_remembered_sizes
from agent.tests.http_client import FakeStorefrontService, TestClient
from agent.tests.test_advice import RecordingModel
from agent.tests.test_guarded_task import cart_snapshot as clear_cart_snapshot
from agent.tests.test_multi_step_plan import intent, last_action, stream
from agent.tests.test_plan_failure import (
    MESSAGE,
    begin,
    finished,
    open_page,
    post,
    send,
    state,
    steps,
)
from agent.tests.test_remembered_sizes import world_with_size
from agent.tests.test_step import home_snapshot
from agent.tests.test_this_resolution import (
    ADD_THIS,
    NILE,
    NamedReads,
    request_context,
    suggest,
    suggestion_reply,
    this_intent,
)

INTERRUPTED_AR = "انقطعت المهمة بسبب إعادة تشغيل. اطلبها تاني."
INTERRUPTED_EN = "This task was interrupted by a restart. Please ask again."
SHOPPER = ShopperBinding(secrets.token_hex(32), "b" * 64)
STRANGER = ShopperBinding(secrets.token_hex(32), "c" * 64)
WEEK = 7 * 24 * 60 * 60


class SameShopper(FakeStorefrontService):
    """A Storefront whose link always names one Shopper, as after a real restart."""

    def __init__(self, binding: ShopperBinding = SHOPPER) -> None:
        super().__init__()
        self.binding = binding
        self.bindings.add(binding)

    def issue(self) -> str:
        ticket = secrets.token_hex(32)
        self.tickets[ticket] = self.binding
        return ticket


def boot(path, *replies, sink=None, shopper=SHOPPER, **options):
    """One Agent process on the state file `path`; returns its client and scripted model."""
    model = RecordingModel(*replies)
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test", api_key=None),
        llm_client=model,
        environment={"AGENT_STATE_FILE": str(path)},
        **({"event_sink": sink} if sink is not None else {}),
        **options,
    )
    app.state.storefront_service = SameShopper(shopper)
    return TestClient(app), model


@pytest.fixture
def path(tmp_path):
    return tmp_path / "agent-state.db"


def home_page() -> Snapshot:
    return Snapshot.model_validate(home_snapshot())


def error_messages(events):
    return [e["data"]["message"] for e in events if e["event"] == "error"]


def stored(path, session_id):
    return SqliteStateStore(path).read(f"agent#session#{session_id}")


# --- The session continues ---------------------------------------------------------------


def test_conversation_stream_and_cursor_continue_after_a_restart(path):
    client, _ = boot(path, intent("cart"))
    session_id = begin(client, "افتح السلة")
    open_page(client, session_id, stream(client, session_id), "/cart")
    before_events = stream(client, session_id)
    before = state(client, session_id)
    assert before["conversation"] and before["task"]["status"] == "completed"

    client2, model2 = boot(path, intent("checkout"))
    after = state(client2, session_id)

    assert after["conversation"] == before["conversation"]
    assert after["event_cursor"] == before["event_cursor"]
    assert after["task"]["status"] == "completed"
    assert stream(client2, session_id) == before_events
    resumed = client2.get(f"/sessions/{session_id}/events?once=true&after={after['event_cursor']}")
    assert resumed.text == ""  # a reconnecting Panel resumes from its cursor: nothing is new

    assert send(client2, session_id, "افتح الدفع").status_code == 202
    fresh = stream(client2, session_id)
    assert [e["id"] for e in fresh][: len(before_events)] == [e["id"] for e in before_events]
    assert fresh[-1]["id"] > after["event_cursor"]
    assert last_action(fresh)["url"] == "/checkout"
    assert len(model2.requests) == 1


def test_the_page_snapshot_is_never_stored(path):
    client, _ = boot(path, intent("cart"))
    session_id = begin(client, "افتح السلة")

    record = stored(path, session_id)

    assert record is not None
    assert "last_snapshot" not in record.value
    text = json.dumps(record.value, ensure_ascii=False)
    assert '"elements"' not in text and '"viewport"' not in text


def test_remembered_sizes_and_the_selected_size_survive_a_restart(path, monkeypatch):
    monkeypatch.setattr(
        test_remembered_sizes, "SessionStore", lambda: SessionStore(store=SqliteStateStore(path))
    )
    world = world_with_size(True, "43")
    world.add("shoe-1")
    assert world.remembered() == {("me", "shoe"): "43"}
    before = world.store.get(world.sid)
    assert before.copilot_selected_size and before.product_kinds

    after = SessionStore(store=SqliteStateStore(path)).get(world.sid)

    assert after.remembered_sizes == {("me", "shoe"): "43"}
    assert after.copilot_selected_size == before.copilot_selected_size
    assert after.product_kinds == before.product_kinds


def test_this_still_means_the_product_just_touched_after_a_restart(path):
    options = {"catalogue_client": NamedReads(), "catalogue_retrieval_enabled": True}
    client, _ = boot(path, *suggestion_reply("p-1"), **options)
    session_id = suggest(client)

    client2, model2 = boot(path, this_intent(), **options)
    assert send(client2, session_id, ADD_THIS, home_snapshot()).status_code == 202
    events = stream(client2, session_id)

    assert request_context(model2.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "p-1", "name": NILE}
    ]
    assert last_action(events)["url"] == "/p/p-1"


def test_the_last_plan_report_is_still_there_after_a_restart(path):
    client, _ = boot(path, steps("افتح السلة", "افتح الدفع"), "no", "no")
    session_id = begin(client, "افتح السلة وبعدين افتح الدفع")
    open_page(client, session_id, stream(client, session_id), "/cart")
    before = state(client, session_id)["plan"]
    report = finished(stream(client, session_id))["report"]
    assert before["active"] is False

    client2, _ = boot(path)

    assert state(client2, session_id)["plan"] == before
    assert finished(stream(client2, session_id))["report"] == report


# --- Nothing re-runs ----------------------------------------------------------------------


def test_a_task_awaiting_an_action_result_is_ended_as_interrupted_and_the_shopper_asks_again(path):
    client, _ = boot(path, intent("cart"))
    session_id = begin(client, "افتح السلة")
    sent = [e for e in stream(client, session_id) if e["event"] == "action"]
    assert len(sent) == 1
    task_id = sent[0]["data"]["task_id"] if "data" in sent[0] else sent[0]["task_id"]

    sink = MemorySink()
    client2, model2 = boot(path, intent("checkout"), sink=sink)
    view = state(client2, session_id)

    assert view["task"]["status"] == "cancelled"
    assert INTERRUPTED_AR in [turn["text"] for turn in view["conversation"]]
    events = stream(client2, session_id)
    assert error_messages(events) == [INTERRUPTED_AR]
    assert [e for e in events if e["event"] == "action"] == sent  # nothing was sent again
    assert model2.requests == []
    assert [r["reason"] for r in sink.records if r["event"] == "task_paused"] == ["interrupted"]
    retry = post(
        client2,
        session_id,
        f"/tasks/{task_id}/retry",
        json={"snapshot": home_snapshot()},
    )
    assert 400 <= retry.status_code < 500, retry.text
    accepted = send(client2, session_id, "افتح الدفع")
    assert accepted.status_code == 202, accepted.text
    assert last_action(stream(client2, session_id))["url"] == "/checkout"


def test_the_interrupted_message_is_in_english_for_an_english_shopper(path):
    client, _ = boot(path, intent("cart", language="en", dialect="english"))
    session_id = begin(client, "open the cart")

    client2, _ = boot(path)

    view = state(client2, session_id)
    assert INTERRUPTED_EN in [turn["text"] for turn in view["conversation"]]
    assert error_messages(stream(client2, session_id)) == [INTERRUPTED_EN]


def test_a_task_that_was_interpreting_comes_back_ended_as_interrupted(path):
    store = SessionStore(store=SqliteStateStore(path))
    session = store.create()
    session.shopper = SHOPPER
    store.begin_interpretation(session.session_id, "افتح السلة", home_page())
    store.flush()
    assert store.get(session.session_id).active_task.status == "interpreting"

    client2, model2 = boot(path, intent("cart"))
    # The Shopper's new browser authority owns the session again through its stored owner.
    view = state(client2, session.session_id)

    assert view["task"]["status"] == "cancelled"
    assert INTERRUPTED_AR in [turn["text"] for turn in view["conversation"]]
    assert model2.requests == []


def test_a_task_waiting_on_a_question_is_ended_as_interrupted_too(path):
    store = SessionStore(store=SqliteStateStore(path), confirmation_registrar=lambda *_: True)
    session = store.create()
    session.shopper = SHOPPER
    task = store.submit_message(session.session_id, "Empty my cart", clear_cart_snapshot())
    store.flush()
    assert task.status == "awaiting_answer"

    client2, _ = boot(path)

    assert state(client2, session.session_id)["task"]["status"] == "cancelled"


def test_a_plan_in_progress_fails_at_its_running_step_with_the_report(path):
    client, _ = boot(path, steps("افتح السلة", "افتح الدفع", "افتح الحساب"))
    session_id = begin(client, MESSAGE)
    first = [e for e in stream(client, session_id) if e["event"] == "action"]

    client2, model2 = boot(path)
    events = stream(client2, session_id)

    expected = (
        "وقفت عند خطوة ماتمّتش:\n"
        f"✕ افتح السلة — {INTERRUPTED_AR}\n"
        "– افتح الدفع (اتخطّت)\n"
        "– افتح الحساب (اتخطّت)"
    )
    assert finished(events)["report"] == expected
    assert [e for e in events if e["event"] == "action"] == first
    assert model2.requests == []
    view = state(client2, session_id)
    assert view["plan"]["active"] is False
    assert [s["status"] for s in view["plan"]["steps"]] == ["failed", "skipped", "skipped"]
    assert view["task"]["status"] == "cancelled"


def test_the_session_is_free_for_a_new_request_after_an_interrupted_plan(path):
    client, _ = boot(path, steps("افتح السلة", "افتح الدفع"))
    session_id = begin(client, "افتح السلة وبعدين افتح الدفع")

    client2, model2 = boot(path, intent("checkout"))
    assert send(client2, session_id, "افتح الدفع").status_code == 202

    assert last_action(stream(client2, session_id))["url"] == "/checkout"
    assert len(model2.requests) == 1


def test_a_pending_confirmation_is_expired_and_cannot_be_confirmed_after_a_restart(path):
    clear = {
        "v": 10,
        "language": "en",
        "dialect": "english",
        "intent": "mutate",
        "mutation_kind": "clear_cart",
        "mutation_source": "empty my cart",
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
    }
    page = clear_cart_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    client, _ = boot(path, clear, confirmation_registrar=lambda *_: True)
    session_id = begin(client, "empty my cart", page)
    question = last_action(stream(client, session_id))
    assert question["kind"] == "confirmation"

    registered = []
    sink = MemorySink()
    client2, _ = boot(
        path, sink=sink, confirmation_registrar=lambda *parts: registered.append(parts) or True
    )
    answer = post(
        client2,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "Confirm", "snapshot": page},
    )

    assert answer.status_code == 409
    assert registered == []
    assert state(client2, session_id)["task"]["status"] == "cancelled"
    assert "guarded_click" not in json.dumps(stream(client2, session_id))
    assert [r["outcome"] for r in sink.records if r["event"] == "confirmation"] == ["expired"]


def test_a_restart_logs_no_shopper_text_sizes_names_or_products(path):
    client, _ = boot(path, steps("افتح السلة", "افتح الدفع"))
    session_id = begin(client, "افتح السلة وبعدين افتح الدفع")
    sink = MemorySink()

    client2, _ = boot(path, sink=sink)
    state(client2, session_id)

    text = json.dumps(sink.records, ensure_ascii=False)
    for private in ("افتح", "السلة", "الدفع", INTERRUPTED_AR):
        assert private not in text
    assert {"task_paused", "plan_finished"} <= {r["event"] for r in sink.records}


def test_another_shopper_cannot_use_the_restored_session(path):
    client, _ = boot(path, intent("cart"))
    session_id = begin(client, "افتح السلة")

    stranger, _ = boot(path, shopper=STRANGER)

    assert stranger.get(f"/sessions/{session_id}/state?tab_id=tab-a").status_code == 404


# --- Lifetime, capacity and failure -------------------------------------------------------


def test_the_session_lifetime_is_seven_days():
    assert SESSION_TTL_SECONDS == WEEK


def test_the_stored_session_lives_seven_days_after_its_last_activity(path):
    wall = [5_000_000.0]
    store = SessionStore(
        store=SqliteStateStore(path, clock=lambda: wall[0]), wall_clock=lambda: wall[0]
    )
    session = store.create()
    store.flush()
    wall[0] += WEEK - 1

    alive = SessionStore(store=SqliteStateStore(path, clock=lambda: wall[0]))
    assert alive.get(session.session_id).session_id == session.session_id

    wall[0] += 2
    expired = SessionStore(store=SqliteStateStore(path, clock=lambda: wall[0]))
    with pytest.raises(SessionNotFound):
        expired.get(session.session_id)


def test_activity_extends_the_stored_lifetime(path):
    wall = [5_000_000.0]
    store = SessionStore(
        store=SqliteStateStore(path, clock=lambda: wall[0]), wall_clock=lambda: wall[0]
    )
    session = store.create()
    store.flush()
    for _ in range(3):
        wall[0] += WEEK - 100
        store.get(session.session_id).conversation.append({"role": "user", "text": "hi"})
        store.flush()

    later = SessionStore(store=SqliteStateStore(path, clock=lambda: wall[0]))
    assert len(later.get(session.session_id).conversation) == 3


def test_idle_sessions_leave_memory_so_capacity_counts_active_sessions(path):
    now = [100.0]
    store = SessionStore(store=SqliteStateStore(path), clock=lambda: now[0], capacity=1)
    first = store.create()
    store.flush()
    assert not store.has_capacity()

    now[0] += 31 * 60

    assert store.has_capacity()
    second = store.create()
    store.flush()
    assert store.get(first.session_id).session_id == first.session_id  # back from the store
    assert second.session_id != first.session_id


def test_a_session_with_work_in_progress_stays_in_memory_when_idle(path):
    now = [100.0]
    store = SessionStore(store=SqliteStateStore(path), clock=lambda: now[0], capacity=1)
    session = store.create()
    store.begin_interpretation(session.session_id, "افتح السلة", home_page())
    store.flush()

    now[0] += 31 * 60

    assert not store.has_capacity()
    assert store.has_pending_work()


def test_a_failed_save_fails_the_request_visibly(path, monkeypatch):
    client, _ = boot(path)

    def refuse(*_):
        raise StateStoreError("disk full")

    monkeypatch.setattr(SqliteStateStore, "write", lambda self, *args: refuse())

    changed = client.post("/sessions")

    assert changed.status_code == 503
    assert changed.json() == {"detail": "State could not be saved"}


def test_an_oversized_session_is_refused_not_saved(path):
    store = SessionStore(store=SqliteStateStore(path))
    session = store.create()
    session.last_touched = [{"id": "p", "name": "n" * 400_000}]
    # The size guard is on the whole record: the touched list is not otherwise bounded here.
    session.product_context.products = {
        f"p-{i}": {"id": f"p-{i}", "name": "n" * 200} for i in range(24)
    }
    session.remembered_sizes = {(f"person-{i}", "shoe"): "43" for i in range(20_000)}

    with pytest.raises(StateSaveFailed):
        store.flush()

    with pytest.raises(SessionNotFound):
        SessionStore(store=SqliteStateStore(path)).get(session.session_id)


def test_conversation_and_stream_are_bounded_in_the_stored_record(path):
    store = SessionStore(store=SqliteStateStore(path))
    session = store.create()
    for i in range(500):
        session.conversation.append({"role": "user", "text": f"turn {i}"})
    for _ in range(500):
        store._runtime.append(session, "narration", {"text": "x" * 500})
    store.flush()

    restored = SessionStore(store=SqliteStateStore(path)).get(session.session_id)

    assert len(restored.conversation) == 60 and restored.conversation[-1]["text"] == "turn 499"
    assert len(restored.events) <= 200
    assert restored.events[-1].id == 500 and restored.last_event_id == 500
    assert len(json.dumps(stored(path, session.session_id).value)) < 200 * 1024


def test_a_failed_save_leaves_the_request_with_no_effect(path, monkeypatch):
    client, model = boot(path, intent("cart"), intent("checkout"))
    session_id = client.post("/sessions").json()["session_id"]
    before = state(client, session_id)
    real_write = SqliteStateStore.write
    failing = [True]

    def write(self, *args):
        if failing[0]:
            raise StateStoreError("disk full")
        return real_write(self, *args)

    monkeypatch.setattr(SqliteStateStore, "write", write)

    refused = send(client, session_id, "افتح السلة")

    assert refused.status_code == 503
    assert model.requests == []  # nothing was interpreted
    failing[0] = False
    after = state(client, session_id)
    assert after["task"] is None and after["conversation"] == before["conversation"]
    assert after["event_cursor"] == before["event_cursor"]
    assert client.get(f"/sessions/{session_id}/events?once=true").text == ""

    # The session is as before: the same request now works and is interpreted once.
    assert send(client, session_id, "افتح السلة").status_code == 202
    assert last_action(stream(client, session_id))["url"] == "/cart"
    assert len(model.requests) == 1


def test_a_failed_save_after_the_work_drops_the_change_and_its_events(path, monkeypatch):
    client, model = boot(path, intent("cart"))
    session_id = client.post("/sessions").json()["session_id"]
    real_write = SqliteStateStore.write
    calls = []

    def write(self, *args):
        calls.append(1)
        if len(calls) == 2:  # the checkpoint passes; the final save fails; the undo works
            raise StateStoreError("disk full")
        return real_write(self, *args)

    monkeypatch.setattr(SqliteStateStore, "write", write)

    assert send(client, session_id, "افتح السلة").status_code == 503

    monkeypatch.setattr(SqliteStateStore, "write", real_write)
    assert client.get(f"/sessions/{session_id}/events?once=true").text == ""
    assert state(client, session_id)["task"] is None
