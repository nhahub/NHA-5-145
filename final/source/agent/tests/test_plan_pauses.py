"""Ticket 07: a plan that reaches a guarded step or a question waits for the Shopper.

Driven through the Agent's HTTP API with a scripted model (templates: `test_plan_failure.py`,
`test_multi_step_plan.py`, `test_guarded_task.py`). Everything asserted is visible: stream
events, the actions sent, status codes, `/state` and event-log records. Expected strings are
written out literally.
"""

import json

from agent.event_log import MemorySink
from agent.sessions import SessionStore
from agent.tests.test_cart_task import intent as cart_add_intent
from agent.tests.test_guarded_task import cart_snapshot as clear_cart_snapshot
from agent.tests.test_multi_step_plan import (
    PLAN_EVENTS,
    advice,
    intent,
    last_action,
    make_client,
    names,
    retrieval_client,
    stream,
)
from agent.tests.test_plan_failure import (
    begin,
    finished,
    flat,
    open_page,
    post,
    product_page,
    report_result,
    send,
    state,
    steps,
)
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_step import home_snapshot

CONFIRMATION_FAILED_AR = "انتهى التأكيد أو اتغيّرت السلة، فما نفّذتش الخطوة دي. تقدر تطلبها تاني."
ADD, CLEAR, ACCOUNT = "ضيفلي الجزمة", "امسح العربية", "افتح الحساب"
ADD_AND_CLEAR = "ضيفلي الجزمة بعدها امسح العربية"
PAUSE_EVENTS = {"plan_paused", "plan_resumed", "plan_step_finished", "plan_finished"}


def dump(page) -> dict:
    return page.model_dump(mode="json", by_alias=True, exclude_none=True)


def clear_page(revision="3") -> dict:
    return dump(clear_cart_snapshot(revision))


def empty_cart_page() -> dict:
    return snapshot_at("/cart", {"id": 1, "role": "status", "name": "السلة فارغة", "visible": True})


def add_intent(source=ADD, **overrides) -> dict:
    return {
        **cart_add_intent(source).model_dump(mode="json"),
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "cart_target_id": 4,
        "cart_source": source,
        **overrides,
    }


def clear_intent(**overrides) -> dict:
    return {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "mutate",
        "mutation_kind": "clear_cart",
        "mutation_source": CLEAR,
        "constraints": {},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        **overrides,
    }


class Guarded:
    """A client whose Confirmation clock the test controls, and what the Storefront registered."""

    def __init__(self, *replies, sink=None, register=True):
        self.clock = [100.0]
        self.registered: list[tuple] = []

        def registrar(*parts):
            self.registered.append(parts)
            return register

        store = SessionStore(clock=lambda: self.clock[0], confirmation_registrar=registrar)
        self.client, self.model = make_client(*replies, sink=sink, session_store=store)

    def confirm(self, session_id, question, text=None, page=None):
        text = text or question["options"][0]  # the card's first option is "Confirm"
        return post(
            self.client,
            session_id,
            f"/tasks/{question['task_id']}/answers",
            json={
                "question_id": question["action_id"],
                "text": text,
                "snapshot": page if page is not None else clear_page(),
            },
        )


def add_then_clear(sink=None, **options) -> Guarded:
    first = add_intent(first_step=ADD, remaining_steps=[CLEAR])
    return Guarded(first, clear_intent(), sink=sink, **options)


def reach_clear_card(guarded: Guarded, revision="3"):
    """Run "add this, then clear the cart" up to the open Confirmation card of step 2."""
    client = guarded.client
    session_id = begin(client, ADD_AND_CLEAR, product_page())
    events = stream(client, session_id)
    assert last_action(events)["type"] == "click"
    report_result(client, session_id, events, product_page(added=True), status="ok")
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/cart"
    report_result(client, session_id, events, clear_page(revision))
    events = stream(client, session_id)
    question = last_action(events)
    assert question["kind"] == "confirmation"
    return session_id, question, events


# --- A guarded step: the card appears only at its own turn --------------------------------


def test_add_then_clear_offers_the_confirmation_only_at_step_two_and_runs_it_once_confirmed():
    sink = MemorySink()
    guarded = add_then_clear(sink)
    client = guarded.client
    session_id = begin(client, ADD_AND_CLEAR, product_page())
    events = stream(client, session_id)
    report_result(client, session_id, events, product_page(added=True), status="ok")
    events = stream(client, session_id)
    # Step 2 first opens the cart; no Confirmation exists yet and nothing was registered.
    kinds = [e["data"]["action"].get("kind") for e in events if e["event"] == "action"]
    assert kinds == [None, None]
    assert guarded.registered == []
    report_result(client, session_id, events, clear_page("7"))
    events = stream(client, session_id)
    question = last_action(events)
    assert question["kind"] == "confirmation" and question["options"] == ["تأكيد", "إيقاف"]
    assert "إزالة كل المنتجات من السلة الحالية" in question["question"]
    assert flat(events, PAUSE_EVENTS)[-1:] == [("plan_paused", 2, None)]
    paused = [e["data"] for e in events if e["event"] == "plan_paused"][-1]
    assert paused["reason"] == "confirmation" and paused["position"] == 2
    assert guarded.registered == []  # offering a card consumes nothing

    assert guarded.confirm(session_id, question, page=clear_page("7")).status_code == 202
    # The Confirmation was bound to the cart as it was at that moment (revision 7).
    assert [parts[1:] for parts in guarded.registered] == [
        ("http://localhost:4000/cart", question["action_id"], question["task_id"], "clear_cart", 7)
    ]
    events = stream(client, session_id)
    assert last_action(events)["type"] == "guarded_click"
    report_result(client, session_id, events, empty_cart_page())
    events = stream(client, session_id)
    order = flat(events, PAUSE_EVENTS)
    assert [item[0] for item in order[-4:]] == [
        "plan_paused",
        "plan_resumed",
        "plan_step_finished",
        "plan_finished",
    ]
    assert finished(events)["report"] == "خلصت طلبك:\n✓ ضيفلي الجزمة\n✓ امسح العربية"
    step = [r for r in sink.records if r["event"] == "plan_step"][-1]
    assert (step["position"], step["outcome"], step["guarded"]) == (2, "done", True)
    assert state(client, session_id)["plan"]["active"] is False


def test_a_guarded_step_in_the_middle_lets_step_three_run_after_the_confirmation():
    guarded = Guarded(
        steps("افتح السلة", CLEAR, ACCOUNT),
        clear_intent(),
        intent("account"),
    )
    client = guarded.client
    session_id = begin(client, "افتح السلة وبعدين امسح العربية وبعدين افتح الحساب")
    report_result(client, session_id, stream(client, session_id), clear_page())
    events = stream(client, session_id)
    question = last_action(events)
    assert question["kind"] == "confirmation"
    assert flat(events, PAUSE_EVENTS)[-1] == ("plan_paused", 2, None)
    assert "plan_finished" not in names(events)

    assert guarded.confirm(session_id, question).status_code == 202
    events = stream(client, session_id)
    report_result(client, session_id, events, empty_cart_page())
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/account"  # step 3 runs only after the confirm
    open_page(client, session_id, events, "/account")
    events = stream(client, session_id)
    assert [item[:3] for item in flat(events, PLAN_EVENTS | {"plan_paused", "plan_resumed"})][
        -6:
    ] == [
        ("plan_paused", 2, None),
        ("plan_resumed", 2, None),
        ("plan_step_finished", 2, "done"),
        ("plan_step_started", 3, None),
        ("plan_step_finished", 3, "done"),
        ("plan_finished", None, "done"),
    ]


def test_stop_on_a_step_confirmation_cancels_the_plan_with_no_resume():
    guarded = add_then_clear()
    session_id, question, _ = reach_clear_card(guarded)
    assert guarded.confirm(session_id, question, "إيقاف").status_code == 202
    events = stream(guarded.client, session_id)
    assert "plan_resumed" not in names(events)
    assert flat(events, PAUSE_EVENTS)[-3:] == [
        ("plan_paused", 2, None),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert guarded.registered == []


# --- An expired, stale or unregistered Confirmation inside a plan fails the step --------------


def assert_step_failed_on_confirmation(guarded, session_id, events):
    assert [e for e in events if e["event"] == "action"][-1]["data"]["action"]["type"] != (
        "guarded_click"
    )
    assert flat(events, PAUSE_EVENTS)[-4:] == [
        ("plan_paused", 2, None),
        ("plan_resumed", 2, None),
        ("plan_step_finished", 2, "failed"),
        ("plan_finished", None, "failed"),
    ]
    assert names(events)[-3:] == ["plan_step_finished", "cancelled", "plan_finished"]
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✓ ضيفلي الجزمة\n✕ امسح العربية — {CONFIRMATION_FAILED_AR}"
    )
    view = state(guarded.client, session_id)
    assert view["task"]["status"] == "cancelled" and view["plan"]["active"] is False
    # The Session is free at once and the Shopper can ask again.
    assert send(guarded.client, session_id, "افتح السلة").status_code == 202


def test_an_expired_confirmation_fails_the_step_and_the_report_says_so():
    sink = MemorySink()
    guarded = add_then_clear(sink)
    session_id, question, _ = reach_clear_card(guarded)
    guarded.clock[0] += 61
    response = guarded.confirm(session_id, question)
    assert response.status_code == 202
    events = stream(guarded.client, session_id)
    assert_step_failed_on_confirmation(guarded, session_id, events)
    assert guarded.registered == []
    outcomes = [r["outcome"] for r in sink.records if r["event"] == "confirmation"]
    assert outcomes == ["expired"]


def test_a_confirmation_whose_cart_changed_fails_the_step():
    sink = MemorySink()
    guarded = add_then_clear(sink)
    session_id, question, _ = reach_clear_card(guarded, revision="3")
    assert guarded.confirm(session_id, question, page=clear_page("4")).status_code == 202
    events = stream(guarded.client, session_id)
    assert_step_failed_on_confirmation(guarded, session_id, events)
    assert [r["outcome"] for r in sink.records if r["event"] == "confirmation"] == ["stale"]


def test_a_confirmation_the_storefront_cannot_register_fails_the_step():
    sink = MemorySink()
    guarded = add_then_clear(sink, register=False)
    session_id, question, _ = reach_clear_card(guarded)
    assert guarded.confirm(session_id, question).status_code == 202
    events = stream(guarded.client, session_id)
    assert_step_failed_on_confirmation(guarded, session_id, events)
    assert [r["outcome"] for r in sink.records if r["event"] == "confirmation"] == ["unregistered"]


def test_a_reply_that_is_not_a_confirm_is_still_refused_and_the_step_keeps_waiting():
    guarded = add_then_clear()
    session_id, question, _ = reach_clear_card(guarded)
    assert guarded.confirm(session_id, question, "yes").status_code == 409
    events = stream(guarded.client, session_id)
    assert "plan_finished" not in names(events) and "plan_resumed" not in names(events)
    assert guarded.confirm(session_id, question).status_code == 202  # the card is still live


def test_refreshing_while_a_step_confirmation_is_open_fails_the_step():
    guarded = add_then_clear()
    session_id, _, _ = reach_clear_card(guarded)
    view = state(guarded.client, session_id)  # the Panel reloaded: the Confirmation is void
    assert view["plan"]["active"] is False
    assert [s["status"] for s in view["plan"]["steps"]] == ["done", "failed"]
    events = stream(guarded.client, session_id)
    message = "انتهى التأكيد بعد تحديث الصفحة. حاول تاني لتأكيد الحالة الحالية."
    assert [e["data"]["message"] for e in events if e["event"] == "error"] == [message]
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✓ ضيفلي الجزمة\n✕ امسح العربية — {message}"
    )
    assert names(events)[-3:] == ["plan_step_finished", "cancelled", "plan_finished"]


def test_without_a_plan_an_expired_or_stale_confirmation_is_still_a_409():
    for stale in (False, True):
        guarded = Guarded(clear_intent())
        client = guarded.client
        session_id = begin(client, CLEAR, clear_page())
        question = last_action(stream(client, session_id))
        assert question["kind"] == "confirmation"
        if stale:
            response = guarded.confirm(session_id, question, page=clear_page("9"))
        else:
            guarded.clock[0] += 61
            response = guarded.confirm(session_id, question)
        assert response.status_code == 409
        events = stream(client, session_id)
        assert not (PLAN_EVENTS | {"plan_paused", "plan_resumed", "cancelled"}) & set(names(events))


# --- A question inside a plan -----------------------------------------------------------------


def answer(client, session_id, question, text, page=None):
    return post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={
            "question_id": question["action_id"],
            "text": text,
            "snapshot": page if page is not None else home_snapshot(),
        },
    )


def sizes_page(added=False) -> dict:
    page = product_page(added)
    for element in page["elements"]:
        if element["name"] == "المقاس":
            element.update(value="", options=["42", "43"])
    return page


def test_a_size_question_mid_plan_pauses_the_plan_and_the_answer_continues_that_step():
    first = add_intent(first_step=ADD, remaining_steps=["ضيفها تاني", "افتح السلة"])
    second = add_intent("ضيفها تاني", product_id="shoe-09")
    client, model = make_client(first, second, intent("cart"))
    session_id = begin(client, "ضيفلي الجزمة وبعدين ضيفها تاني وبعدين افتح السلة", product_page())
    events = stream(client, session_id)
    report_result(client, session_id, events, sizes_page(added=True), status="ok")
    events = stream(client, session_id)
    question = last_action(events)
    assert question["type"] == "ask_shopper" and question["options"] == []
    assert flat(events, PAUSE_EVENTS)[-1] == ("plan_paused", 2, None)
    paused = [e["data"] for e in events if e["event"] == "plan_paused"][-1]
    assert paused["reason"] == "question"
    assert not {"plan_resumed", "plan_finished"} & set(names(events))
    view = state(client, session_id)
    assert view["plan"]["paused"] == "question" and view["plan"]["active"] is True
    assert [s["status"] for s in view["plan"]["steps"]] == ["done", "running", "pending"]
    requests_before = len(model.requests)

    assert answer(client, session_id, question, "43", sizes_page()).status_code == 202
    events = stream(client, session_id)
    assert names(events).count("task_started") == 2  # the answer continued step 2's own task
    assert flat(events, PAUSE_EVENTS)[-2:] == [("plan_paused", 2, None), ("plan_resumed", 2, None)]
    assert last_action(events)["type"] == "select"
    assert len(model.requests) == requests_before  # an exact option needs no new model call
    report_result(client, session_id, events, product_page(), status="ok")
    events = stream(client, session_id)
    assert last_action(events)["type"] == "click"
    report_result(client, session_id, events, product_page(added=True), status="ok")
    events = stream(client, session_id)
    order = flat(events, PAUSE_EVENTS | {"plan_step_started"})
    assert [item[:2] for item in order[-3:]] == [
        ("plan_resumed", 2),
        ("plan_step_finished", 2),
        ("plan_step_started", 3),
    ]
    assert last_action(events)["url"] == "/cart"
    open_page(client, session_id, events, "/cart")
    assert finished(stream(client, session_id))["outcome"] == "done"


def test_a_failure_question_still_fails_the_step_and_never_pauses_the_plan():
    first = add_intent(first_step=ADD, remaining_steps=["ضيفها تاني"])
    client, _ = make_client(first, add_intent("ضيفها تاني"))
    session_id = begin(client, "ضيفلي الجزمة وبعدين ضيفها تاني", product_page())
    events = stream(client, session_id)
    report_result(client, session_id, events, product_page(added=True), status="ok")
    events = stream(client, session_id)
    report_result(client, session_id, events, product_page(), status="blocked")
    events = stream(client, session_id)
    assert "plan_paused" not in names(events)
    assert finished(events)["outcome"] == "failed"


# --- A catalogue clarify inside a plan --------------------------------------------------------

CLARIFY = "أي نوع جزم تحب؟"


def clarify_decision(**overrides) -> dict:
    return {"kind": "clarify", "question": CLARIFY, "language": "ar", **overrides}


def test_a_catalogue_clarify_as_a_later_step_waits_for_an_answer_instead_of_finishing():
    client, _ = retrieval_client(
        {"kind": "execute"},
        steps("افتح السلة", "دورلي على جزم"),
        clarify_decision(),
    )
    session_id = begin(client, "افتح السلة وبعدين دورلي على جزم")
    open_page(client, session_id, stream(client, session_id), "/cart")
    events = stream(client, session_id)
    question = last_action(events)
    assert question["type"] == "ask_shopper" and question["options"] == []
    assert question["question"] == CLARIFY and question["narration"] == CLARIFY
    assert flat(events, PAUSE_EVENTS)[-1] == ("plan_paused", 2, None)
    assert ("plan_step_finished", 2, "done") not in flat(events, PAUSE_EVENTS)
    assert "done" not in names(events)[names(events).index("plan_step_finished") + 1 :]
    view = state(client, session_id)
    assert view["task"]["status"] == "awaiting_answer"
    assert view["task"]["pending_question"]["question"] == CLARIFY
    assert view["plan"]["paused"] == "question"
    assert [s["status"] for s in view["plan"]["steps"]] == ["done", "running"]
    assert view["conversation"][-1] == {"role": "copilot", "text": CLARIFY}


def test_a_first_message_that_clarifies_still_opens_its_plan_and_waits():
    sink = MemorySink()
    client, _ = retrieval_client(
        clarify_decision(first_step="دورلي على جزم", remaining_steps=["افتح السلة"]), sink=sink
    )
    session_id = begin(client, "دورلي على جزم وبعدين افتح السلة")
    events = stream(client, session_id)
    assert names(events, PLAN_EVENTS | {"plan_paused", "done", "task_started"}) == [
        "task_started",
        "plan_created",
        "plan_step_started",
        "plan_paused",
    ]
    created = next(e["data"] for e in events if e["event"] == "plan_created")
    assert [s["text"] for s in created["steps"]] == ["دورلي على جزم", "افتح السلة"]
    assert last_action(events)["question"] == CLARIFY
    view = state(client, session_id)
    assert [s["status"] for s in view["plan"]["steps"]] == ["running", "pending"]
    assert view["plan"]["paused"] == "question" and view["task"]["status"] == "awaiting_answer"
    assert "دورلي" not in json.dumps(sink.records, ensure_ascii=False)


def test_a_one_step_clarify_still_completes_with_the_question_as_its_summary():
    client, _ = retrieval_client(clarify_decision())
    session_id = begin(client, "عايز جزمة")
    events = stream(client, session_id)
    assert not (PLAN_EVENTS | {"plan_paused", "plan_resumed"}) & set(names(events))
    done = [e["data"] for e in events if e["event"] == "done"]
    assert [d["summary"] for d in done] == [CLARIFY]
    view = state(client, session_id)
    assert view["task"]["status"] == "completed" and view["plan"] is None


def test_a_clarify_answer_that_finds_products_finishes_the_step_and_the_plan():
    client, _ = retrieval_client(
        {"kind": "execute"},
        steps("افتح السلة", "show me running shoes", language="en", dialect="english"),
        clarify_decision(language="en", question="Which kind of shoes?"),
        # The answer is read by the action interpreter, which hands a search goal back.
        intent("cart", intent="find_products", constraints={}, language="en", dialect="english"),
        {"kind": "search", "query": {"query": "running shoes"}},
        {"kind": "recommend", "language": "en", "selected_ids": ["p-4"]},
        advice("A light running shoe.", ["p-4"]),
    )
    session_id = begin(client, "افتح السلة وبعدين show me running shoes")
    open_page(client, session_id, stream(client, session_id), "/cart")
    question = last_action(stream(client, session_id))
    assert question["question"] == "Which kind of shoes?"
    assert answer(client, session_id, question, "running shoes").status_code == 202
    events = stream(client, session_id)
    assert names(events).count("task_started") == 2
    assert flat(events, PAUSE_EVENTS)[-4:] == [
        ("plan_paused", 2, None),
        ("plan_resumed", 2, None),
        ("plan_step_finished", 2, "done"),
        ("plan_finished", None, "done"),
    ]


# --- Privacy ----------------------------------------------------------------------------------


def test_no_shopper_text_reaches_any_record_and_pauses_leave_none():
    sink = MemorySink()
    guarded = add_then_clear(sink)
    session_id, question, _ = reach_clear_card(guarded)
    guarded.confirm(session_id, question)
    kinds = {record["event"] for record in sink.records}
    assert "plan_paused" not in kinds and "plan_resumed" not in kinds
    text = json.dumps(sink.records, ensure_ascii=False)
    for secret in (ADD, CLEAR, ADD_AND_CLEAR, "إزالة كل المنتجات"):
        assert secret not in text
    guarded_flags = [r["guarded"] for r in sink.records if r["event"] == "plan_step"]
    assert guarded_flags == [False]  # step 1 ended; step 2 is still waiting on its answer
