"""Ticket 06: a plan never runs on after something goes wrong, and it says what happened.

Driven through the Agent's HTTP API with a scripted model (the template is
`test_multi_step_plan.py`). Everything asserted is visible: stream events, the actions sent,
`/state`, event-log records and the report text. Expected strings are written out literally.
"""

import json

from agent.event_log import MemorySink
from agent.tests.test_cart_conversation_repair import cart_snapshot, quantity_payload
from agent.tests.test_cart_task import intent as cart_add_intent
from agent.tests.test_cart_task import snapshot as product_snapshot
from agent.tests.test_guarded_task import cart_snapshot as clear_cart_snapshot
from agent.tests.test_multi_step_plan import (
    PLAN_EVENTS,
    intent,
    last_action,
    make_client,
    names,
    retrieval_client,
    stream,
)
from agent.tests.test_real_task import action_result, snapshot_at
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

S1, S2, S3 = "افتح السلة", "افتح الدفع", "افتح الحساب"
MESSAGE = "افتح السلة وبعدين الدفع وبعدين الحساب"
INVALID_RESPONSE_AR = (
    "استجابة النموذج غير صالحة للتحقق، فتوقفت قبل أي إجراء. جرّب تاني أو أوقف المهمة."
)
INVALID_RESPONSE_EN = (
    "The model response could not be validated, so no action was taken. Retry or stop."
)


def steps(*words, target="cart", **overrides) -> dict:
    return intent(target, first_step=words[0], remaining_steps=list(words[1:]), **overrides)


def post(client, session_id, path, **kwargs):
    return client.post(f"/sessions/{session_id}{path}", **kwargs)


def send(client, session_id, text, snapshot=None, headers=None):
    return post(
        client,
        session_id,
        "/messages",
        json={"text": text, "snapshot": snapshot or home_snapshot()},
        headers=headers or {},
    )


def begin(client, text=MESSAGE, snapshot=None, tab_id=None):
    created = client.post("/sessions", json={"tab_id": tab_id} if tab_id else None)
    session_id = created.json()["session_id"]
    headers = {"X-Tab-Id": tab_id} if tab_id else {}
    assert send(client, session_id, text, snapshot, headers).status_code == 202
    return session_id


def report_result(client, session_id, events, snapshot, status="navigated", tab_id=None):
    body = {**action_result(last_action(events), snapshot), "status": status}
    headers = {"X-Tab-Id": tab_id} if tab_id else {}
    response = post(client, session_id, "/action-results", json=body, headers=headers)
    assert response.status_code == 202, response.text


def open_page(client, session_id, events, url):
    report_result(client, session_id, events, snapshot_at(url))


def stream_as(client, session_id, tab_id):
    url = f"/sessions/{session_id}/events?once=true&tab_id={tab_id}"
    return parse_sse(client.get(url).text)


def state(client, session_id, tab_id="tab-a"):
    response = client.get(f"/sessions/{session_id}/state", params={"tab_id": tab_id})
    assert response.status_code == 200
    return response.json()


def flat(events, wanted):
    return [
        (e["event"], e["data"].get("position"), e["data"].get("outcome"))
        for e in events
        if e["event"] in wanted
    ]


def finished(events):
    return next(e["data"] for e in events if e["event"] == "plan_finished")


def after_second_task_started(events):
    """Event names, minus narration and actions, from the second step's task on."""
    kinds = [e["event"] for e in events if e["event"] not in {"narration", "action"}]
    start = [i for i, kind in enumerate(kinds) if kind == "task_started"][1]
    return kinds[start:]


# --- Every failure kind ends the plan as failed ------------------------------------------


def test_a_pause_fails_the_step_skips_the_rest_cancels_its_task_and_reports():
    client, model = make_client(steps(S1, S2, S3), "no", "no", intent("cart"))
    session_id = begin(client)
    open_page(client, session_id, stream(client, session_id), "/cart")
    events = stream(client, session_id)

    assert after_second_task_started(events) == [
        "task_started",
        "plan_step_started",
        "error",
        "plan_step_finished",
        "plan_step_finished",
        "cancelled",
        "plan_finished",
    ]
    assert flat(events, {"plan_step_finished", "plan_finished"}) == [
        ("plan_step_finished", 1, "done"),
        ("plan_step_finished", 2, "failed"),
        ("plan_step_finished", 3, "skipped"),
        ("plan_finished", None, "failed"),
    ]
    assert [e["data"]["message"] for e in events if e["event"] == "error"] == [INVALID_RESPONSE_AR]
    expected = (
        "وقفت عند خطوة ماتمّتش:\n"
        "✓ افتح السلة\n"
        f"✕ افتح الدفع — {INVALID_RESPONSE_AR}\n"
        "– افتح الحساب (اتخطّت)"
    )
    assert finished(events)["report"] == expected
    assert len(model.requests) == 3  # step 3 was never interpreted

    # The Session is free at once: no Retry waits, no Stop is needed, a new message works.
    view = state(client, session_id)
    assert view["task"]["status"] == "cancelled"
    assert view["conversation"][-1] == {"role": "copilot", "text": expected}
    assert send(client, session_id, "افتح السلة").status_code == 202


def test_the_same_failure_in_english_reports_in_english():
    client, _ = make_client(
        steps("open the cart", "open checkout", language="en", dialect="english"),
        "no",
        "no",
    )
    session_id = begin(client, "open the cart then open checkout")
    open_page(client, session_id, stream(client, session_id), "/cart")
    events = stream(client, session_id)
    assert finished(events)["report"] == (
        "I stopped at a step that didn't work:\n"
        "✓ open the cart\n"
        f"✕ open checkout — {INVALID_RESPONSE_EN}"
    )


def quantity_plan_client(**options):
    return make_client(
        steps("افتح السلة", "زوّد الكمية"),
        quantity_payload("زوّد الكمية", target_id=11),
        **options,
    )


def reach_quantity_step(client):
    session_id = begin(client, "افتح السلة وبعدين زوّد الكمية")
    report_result(client, session_id, stream(client, session_id), cart_snapshot(2))
    events = stream(client, session_id)
    assert last_action(events)["type"] == "type"
    return session_id, events


def test_a_cart_edit_the_storefront_cannot_prepare_pauses_and_fails_the_step():
    client, _ = quantity_plan_client()
    session_id, events = reach_quantity_step(client)
    report_result(client, session_id, events, cart_snapshot(2), status="blocked")
    events = stream(client, session_id)
    message = "تعذر تجهيز تعديل السلة. حاول تاني من الحالة الحالية."
    assert after_second_task_started(events) == [
        "task_started",
        "plan_step_started",
        "error",
        "plan_step_finished",
        "cancelled",
        "plan_finished",
    ]
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✓ افتح السلة\n✕ زوّد الكمية — {message}"
    )


def test_a_refresh_pause_fails_the_step_and_the_reconcile_view_shows_it():
    client, _ = quantity_plan_client()
    session_id, _ = reach_quantity_step(client)
    state(client, session_id)  # the Panel reloaded: the pending action cannot be replayed
    response = post(
        client,
        session_id,
        "/reconcile",
        json={"snapshot": cart_snapshot(2)},
        headers={"X-Tab-Id": "tab-a"},
    )
    assert response.status_code == 200
    view = response.json()
    assert view["plan"]["active"] is False
    assert [s["status"] for s in view["plan"]["steps"]] == ["done", "failed"]
    events = stream(client, session_id)
    message = "اتحدثت الصفحة قبل تعديل السلة أو الطلب. حاول تاني من الحالة الحالية."
    assert [e["data"]["message"] for e in events if e["event"] == "error"] == [message]
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✓ افتح السلة\n✕ زوّد الكمية — {message}"
    )


def adding_client(second="ضيفها تاني", **options):
    add = {
        **cart_add_intent("ضيفلي الجزمة").model_dump(mode="json"),
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "cart_target_id": 4,
    }
    first = {**add, "cart_source": "ضيفلي الجزمة", "first_step": "ضيفلي الجزمة"}
    first["remaining_steps"] = [second]
    return make_client(first, {**add, "cart_source": second}, **options)


def product_page(added=False):
    page = product_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    if added:
        page["elements"].append(
            {"id": 5, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
        )
    return page


def add_first_step(client):
    session_id = begin(client, "ضيفلي الجزمة وبعدين ضيفها تاني", product_page())
    events = stream(client, session_id)
    assert last_action(events)["type"] == "click"
    report_result(client, session_id, events, product_page(added=True), status="ok")
    events = stream(client, session_id)
    assert last_action(events)["type"] == "click"
    return session_id, events


def test_an_unverified_cart_click_fails_the_step_without_undoing_the_earlier_add():
    client, _ = adding_client()
    session_id, events = add_first_step(client)
    report_result(client, session_id, events, product_page(), status="blocked")
    events = stream(client, session_id)

    # The question is published first, then the step fails and its task is cancelled.
    assert names(events)[-4:] == ["action", "plan_step_finished", "cancelled", "plan_finished"]
    question = last_action(events)
    assert question["type"] == "ask_shopper" and question["options"] == ["إيقاف"]
    assert finished(events)["report"] == (
        "وقفت عند خطوة ماتمّتش:\n"
        "✓ ضيفلي الجزمة\n"
        "✕ ضيفها تاني — مش متأكد إذا تعديل السلة اكتمل. راجع السلة الحالية؛ مش هكرره تلقائيًا."
    )
    # Nothing is rolled back: the plan sent exactly the two add clicks and the question, and
    # never a remove or an Undo.
    sent = [e["data"]["action"] for e in events if e["event"] == "action"]
    assert [(a["type"], a.get("id")) for a in sent] == [
        ("click", 4),
        ("click", 4),
        ("ask_shopper", None),
    ]
    view = state(client, session_id)
    assert view["plan"]["steps"][0]["status"] == "done"
    assert view["task"]["status"] == "cancelled"


def test_a_failed_browser_action_fails_the_step_instead_of_asking_to_try_again():
    client, _ = make_client(steps(S1, S2), intent("checkout"))
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    open_page(client, session_id, stream(client, session_id), "/cart")
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/checkout"
    report_result(client, session_id, events, snapshot_at("/cart"), status="blocked")
    events = stream(client, session_id)
    question = last_action(events)
    assert question["options"] == ["حاول تاني", "إيقاف"]
    assert names(events)[-4:] == ["action", "plan_step_finished", "cancelled", "plan_finished"]
    assert finished(events)["report"] == (
        "وقفت عند خطوة ماتمّتش:\n✓ افتح السلة\n✕ افتح الدفع — تعذر تنفيذ الإجراء بأمان."
    )
    assert state(client, session_id)["task"]["status"] == "cancelled"


def test_a_step_that_ends_in_the_exhausted_fallback_is_reported_as_failed():
    client, _ = retrieval_client(
        {"kind": "execute"},
        steps("open the cart", "show me bags", "open checkout"),
        {},
        {},
        {},
    )
    session_id = begin(client, "open the cart, show me bags, then open checkout")
    open_page(client, session_id, stream(client, session_id), "/cart")
    events = stream(client, session_id)
    assert finished(events)["report"] == (
        "وقفت عند خطوة ماتمّتش:\n"
        "✓ open the cart\n"
        "✕ show me bags — ما قدرتش أكمّل البحث.\n"
        "– open checkout (اتخطّت)"
    )
    # Its task had already completed, so there is nothing to cancel.
    assert "cancelled" not in names(events)


def test_a_next_step_that_cannot_even_begin_fails_the_plan(monkeypatch):
    client, _ = make_client(steps(S1, S2))
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    events = stream(client, session_id)

    def refuse(*args, **kwargs):
        raise ValueError("cannot begin")

    monkeypatch.setattr("agent.task_interpretation.begin_interpretation", refuse)
    open_page(client, session_id, events, "/cart")
    events = stream(client, session_id)
    assert names(events).count("task_started") == 1
    assert flat(events, {"plan_step_finished", "plan_finished"}) == [
        ("plan_step_finished", 1, "done"),
        ("plan_step_finished", 2, "failed"),
        ("plan_finished", None, "failed"),
    ]
    assert finished(events)["report"] == (
        "وقفت عند خطوة ماتمّتش:\n✓ افتح السلة\n✕ افتح الدفع — ما قدرتش أبدأ الخطوة دي."
    )


def test_a_refresh_continue_or_stop_question_is_a_question_not_a_failure():
    client, _ = make_client(steps(S1, S2))
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    state(client, session_id)
    response = post(
        client,
        session_id,
        "/reconcile",
        json={"snapshot": home_snapshot()},
        headers={"X-Tab-Id": "tab-a"},
    )
    assert response.json()["plan"]["active"] is True
    events = stream_as(client, session_id, "tab-a")
    assert last_action(events)["options"] == ["كمّل", "إيقاف"]
    assert not {"plan_step_finished", "plan_finished"} & set(names(events))


def test_a_question_with_real_choices_keeps_the_plan_waiting():
    asking = steps(S1, S2, needs_clarification=True, missing_fields=["target"])
    client, _ = make_client(asking)
    session_id = begin(client)
    events = stream(client, session_id)
    assert last_action(events)["options"][0] == "افتح السلة"
    assert not {"plan_step_finished", "plan_finished"} & set(names(events))
    assert state(client, session_id)["plan"]["active"] is True


def test_a_free_text_question_keeps_the_plan_waiting():
    too_many = {
        **quantity_payload("زوّد الكمية", target_id=11),
        "v": 10,
        "cart_quantity": 99,
        "first_step": "زوّد الكمية",
        "remaining_steps": ["افتح الدفع"],
    }
    client, _ = make_client(too_many)
    session_id = begin(client, "زوّد الكمية وبعدين افتح الدفع", cart_snapshot(2))
    events = stream(client, session_id)
    assert last_action(events)["type"] == "ask_shopper"
    assert last_action(events)["options"] == []
    assert not {"plan_step_finished", "plan_finished"} & set(names(events))
    assert state(client, session_id)["plan"]["active"] is True


# --- Stop ---------------------------------------------------------------------------------


def test_stop_cancels_the_whole_plan_marks_the_current_step_skipped_and_says_so():
    sink = MemorySink()
    client, model = make_client(steps(S1, S2), sink=sink)
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    stream(client, session_id)
    assert post(client, session_id, "/stop").status_code == 202
    events = stream(client, session_id)
    assert flat(events, {"plan_step_finished", "plan_finished"}) == [
        ("plan_step_finished", 1, "skipped"),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert finished(events)["report"] == (
        "وقفت الطلب زي ما طلبت:\n– افتح السلة (اتلغت)\n– افتح الدفع (اتلغت)"
    )
    assert len(model.requests) == 1
    cancelled = [r for r in sink.records if r["event"] == "plan_cancelled"]
    assert [r["reason"] for r in cancelled] == ["stop"]
    view = state(client, session_id)
    assert view["plan"]["active"] is False and view["task"]["status"] == "cancelled"


def test_stop_on_a_step_confirmation_is_a_shopper_stop():
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
    client, _ = make_client(steps("افتح السلة", "empty my cart"), clear)
    session_id = begin(client, "افتح السلة وبعدين empty my cart")
    page = clear_cart_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    report_result(client, session_id, stream(client, session_id), page)
    events = stream(client, session_id)
    question = last_action(events)
    assert question["kind"] == "confirmation" and question["options"] == ["Confirm", "Stop"]
    assert not {"plan_finished"} & set(names(events))  # the plan waits on the question
    response = post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "Stop", "snapshot": page},
    )
    assert response.status_code == 202
    events = stream(client, session_id)
    assert flat(events, {"plan_step_finished", "plan_finished"})[-2:] == [
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert finished(events)["report"] == (
        "وقفت الطلب زي ما طلبت:\n✓ افتح السلة\n– empty my cart (اتلغت)"
    )


# --- A new unrelated message while paused for a question --------------------------------------


def ask_in_step_one(client_replies, **options):
    asking = steps(S1, S2, needs_clarification=True, missing_fields=["target"])
    client, model = make_client(asking, *client_replies, **options)
    session_id = begin(client)
    question = last_action(stream(client, session_id))
    return client, model, session_id, question


def answer(client, session_id, question, text):
    return post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": text, "snapshot": home_snapshot()},
    )


def test_an_answer_that_is_a_new_request_cancels_the_plan_and_is_handled_afresh():
    sink = MemorySink()
    off_topic = intent("cart", intent="off_topic", constraints={})
    client, model, session_id, question = ask_in_step_one(
        [off_topic, intent("checkout")], sink=sink
    )
    assert answer(client, session_id, question, "ضيفلي حقيبة").status_code == 202
    events = stream(client, session_id)

    assert flat(events, {"plan_step_finished", "plan_finished"}) == [
        ("plan_step_finished", 1, "skipped"),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert finished(events)["report"] == (
        "لغيت باقي الخطوات وبدأت طلبك الجديد:\n– افتح السلة (اتلغت)\n– افتح الدفع (اتلغت)"
    )
    # The same text is interpreted again as a fresh task with its own task id.
    assert names(events).count("task_started") == 2
    assert len(model.requests) == 3
    assert model.requests[2].messages[-1].content == "ضيفلي حقيبة"
    assert last_action(events)["url"] == "/checkout"
    conversation = state(client, session_id)["conversation"]
    assert [m["text"] for m in conversation].count("ضيفلي حقيبة") == 1
    assert [r["reason"] for r in sink.records if r["event"] == "plan_cancelled"] == ["new_request"]


def test_a_fresh_request_after_the_cancel_may_make_its_own_plan():
    off_topic = intent("cart", intent="off_topic", constraints={})
    fresh = steps("افتح الحساب", "افتح الدفع", target="account")
    client, _, session_id, question = ask_in_step_one([off_topic, fresh])
    assert answer(client, session_id, question, "افتح الحساب وبعدين الدفع").status_code == 202
    events = stream(client, session_id)
    assert names(events, PLAN_EVENTS).count("plan_created") == 2
    assert names(events, {"plan_finished"}) == ["plan_finished"]
    assert last_action(events)["url"] == "/account"


def test_an_answer_of_the_same_family_continues_the_step():
    client, model, session_id, question = ask_in_step_one([intent("cart")])
    assert answer(client, session_id, question, "السلة").status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/cart"
    assert not {"plan_step_finished", "plan_finished"} & set(names(events))
    assert names(events).count("task_started") == 1
    assert len(model.requests) == 2


# --- Takeover -----------------------------------------------------------------------------


def takeover(client, session_id, tab_id="tab-b"):
    response = post(client, session_id, "/takeover", json={"tab_id": tab_id})
    assert response.status_code == 200
    return response.json()


def test_takeover_lets_the_current_step_end_then_cancels_the_rest():
    sink = MemorySink()
    client, model = make_client(steps(S1, S2), sink=sink)
    session_id = begin(client, "افتح السلة وبعدين الدفع", tab_id="tab-a")
    events = stream_as(client, session_id, "tab-a")
    assert takeover(client, session_id)["plan"]["active"] is True
    report_result(client, session_id, events, snapshot_at("/cart"), tab_id="tab-b")
    events = stream_as(client, session_id, "tab-b")
    assert flat(events, {"plan_step_finished", "plan_finished"}) == [
        ("plan_step_finished", 1, "done"),
        ("plan_step_finished", 2, "skipped"),
        ("plan_finished", None, "cancelled"),
    ]
    assert names(events).count("task_started") == 1  # nothing after the current step starts
    assert finished(events)["report"] == (
        "لغيت باقي الخطوات لأن المحادثة اتفتحت في صفحة تانية:\n✓ افتح السلة\n– افتح الدفع (اتلغت)"
    )
    assert len(model.requests) == 1
    assert [r["reason"] for r in sink.records if r["event"] == "plan_cancelled"] == ["takeover"]


def test_takeover_gives_the_current_step_its_true_outcome_when_it_pauses():
    client, _ = quantity_plan_client()
    created = client.post("/sessions", json={"tab_id": "tab-a"})
    session_id = created.json()["session_id"]
    headers = {"X-Tab-Id": "tab-a"}
    assert (
        send(client, session_id, "افتح السلة وبعدين زوّد الكمية", headers=headers).status_code == 202
    )
    first = stream_as(client, session_id, "tab-a")
    report_result(client, session_id, first, cart_snapshot(2), tab_id="tab-a")
    assert last_action(stream_as(client, session_id, "tab-a"))["type"] == "type"
    takeover(client, session_id)
    response = post(
        client,
        session_id,
        "/reconcile",
        json={"snapshot": cart_snapshot(2)},
        headers={"X-Tab-Id": "tab-b"},
    )
    assert response.status_code == 200
    events = stream_as(client, session_id, "tab-b")
    message = "اتحدثت الصفحة قبل تعديل السلة أو الطلب. حاول تاني من الحالة الحالية."
    assert finished(events)["outcome"] == "cancelled"
    assert finished(events)["report"] == (
        "لغيت باقي الخطوات لأن المحادثة اتفتحت في صفحة تانية:\n"
        "✓ افتح السلة\n"
        f"✕ زوّد الكمية — {message}"
    )


# --- More than three requests -----------------------------------------------------------


def test_a_fourth_request_is_announced_at_the_start_and_in_the_final_report():
    sink = MemorySink()
    four = steps(S1, S2, S3, target="cart", skipped_steps=["افتح الطلبات"])
    client, _ = make_client(four, intent("checkout"), intent("account"), sink=sink)
    session_id = begin(client, "افتح السلة والدفع والحساب والطلبات")
    events = stream(client, session_id)
    created = next(e["data"] for e in events if e["event"] == "plan_created")
    assert [s["text"] for s in created["steps"]] == [S1, S2, S3]
    assert created["skipped"] == ["افتح الطلبات"]
    open_page(client, session_id, events, "/cart")
    open_page(client, session_id, stream(client, session_id), "/checkout")
    open_page(client, session_id, stream(client, session_id), "/account")
    events = stream(client, session_id)
    assert finished(events)["report"] == (
        "خلصت طلبك:\n"
        "✓ افتح السلة\n"
        "✓ افتح الدفع\n"
        "✓ افتح الحساب\n"
        "مش هعمل دول دلوقتي لأن الحد ٣ طلبات في الرسالة: افتح الطلبات"
    )
    record = next(r for r in sink.records if r["event"] == "plan_created")
    assert record["skipped_count"] == 1
    assert "افتح الطلبات" not in json.dumps(sink.records, ensure_ascii=False)


def test_a_fourth_request_is_announced_in_english_too():
    four = steps(
        "open the cart",
        "open checkout",
        "open my account",
        language="en",
        dialect="english",
        skipped_steps=["show orders", "open help"],
    )
    client, _ = make_client(four, intent("checkout", language="en", dialect="english"))
    session_id = begin(client, "open the cart, checkout, my account, orders and help")
    events = stream(client, session_id)
    open_page(client, session_id, events, "/cart")
    report_result(client, session_id, stream(client, session_id), snapshot_at("/cart"), "blocked")
    events = stream(client, session_id)
    assert finished(events)["report"].splitlines()[-1] == (
        "Not done, because one message can hold at most 3 requests: show orders, open help"
    )


def test_a_contradictory_sequence_runs_literally_in_spoken_order():
    client, _ = make_client(
        steps("افتح السلة", "افتح الحساب", "افتح السلة تاني"),
        intent("account"),
        intent("cart"),
    )
    session_id = begin(client, "افتح السلة وبعدين الحساب وبعدين السلة تاني")
    urls = []
    for url in ("/cart", "/account", "/cart"):
        events = stream(client, session_id)
        urls.append(last_action(events)["url"])
        open_page(client, session_id, events, url)
    assert urls == ["/cart", "/account", "/cart"]
    assert finished(stream(client, session_id))["outcome"] == "done"


# --- /state shows the Session's truth ------------------------------------------------------


def test_state_shows_the_running_plan_and_never_marks_unrun_steps_done():
    client, _ = make_client(steps(S1, S2, S3), "no", "no")
    assert state(client, client.post("/sessions").json()["session_id"])["plan"] is None
    session_id = begin(client)
    plan = state(client, session_id)["plan"]
    assert (plan["language"], plan["active"], plan["skipped"]) == ("ar", True, [])
    assert plan["steps"] == [
        {"position": 1, "text": S1, "status": "running"},
        {"position": 2, "text": S2, "status": "pending"},
        {"position": 3, "text": S3, "status": "pending"},
    ]
    open_page(client, session_id, stream(client, session_id), "/cart")
    after = state(client, session_id)["plan"]
    assert after["active"] is False
    assert [s["status"] for s in after["steps"]] == ["done", "failed", "skipped"]


def test_state_keeps_the_finished_plan_until_the_next_one_is_created():
    client, _ = make_client(steps(S1, S2), intent("checkout"), intent("cart"))
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    open_page(client, session_id, stream(client, session_id), "/cart")
    open_page(client, session_id, stream(client, session_id), "/checkout")
    plan = state(client, session_id)["plan"]
    assert plan["active"] is False and [s["status"] for s in plan["steps"]] == ["done", "done"]
    assert send(client, session_id, "افتح السلة").status_code == 202
    assert state(client, session_id)["plan"]["steps"][0]["text"] == S1


# --- Records never carry text --------------------------------------------------------------


def test_no_record_carries_step_text_or_report_text():
    sink = MemorySink()
    client, _ = make_client(steps(S1, S2, S3), "no", "no", sink=sink)
    session_id = begin(client)
    open_page(client, session_id, stream(client, session_id), "/cart")
    post(client, session_id, "/stop")  # nothing is active any more; harmless
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (S1, S2, S3, MESSAGE, "✓", "✕", "وقفت", "خلصت", INVALID_RESPONSE_AR, "report"):
        assert private not in dumped
    cancelled = [r for r in sink.records if r["event"] == "plan_cancelled"]
    assert cancelled == []  # a failed plan is not a cancelled one


def test_a_cancelled_plan_record_has_only_the_plan_id_and_the_reason():
    sink = MemorySink()
    client, _ = make_client(steps(S1, S2), sink=sink)
    session_id = begin(client, "افتح السلة وبعدين الدفع")
    post(client, session_id, "/stop")
    record = next(r for r in sink.records if r["event"] == "plan_cancelled")
    common = {"time", "release", "event", "session_id", "shopper", "invitation_id", "task_id"}
    assert set(record) - common == {"plan_id", "reason"}
    plan_id = next(r["plan_id"] for r in sink.records if r["event"] == "plan_created")
    assert record["plan_id"] == plan_id
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (S1, S2, "وقفت", "اتلغت"):
        assert private not in dumped


# --- One-step messages are untouched ---------------------------------------------------------


def test_a_single_message_pause_still_waits_for_retry_with_no_plan_and_no_cancel():
    client, model = make_client("no", "no", intent("cart"))
    session_id = begin(client, "افتح السلة")
    events = stream(client, session_id)
    assert names(events) == ["task_started", "narration", "error"]
    assert state(client, session_id)["task"]["status"] == "paused"
    assert state(client, session_id)["plan"] is None
    task_id = events[0]["data"]["task_id"]
    retry = post(client, session_id, f"/tasks/{task_id}/retry", json={"snapshot": home_snapshot()})
    assert retry.status_code == 202
    assert last_action(stream(client, session_id))["url"] == "/cart"
    assert len(model.requests) == 3
