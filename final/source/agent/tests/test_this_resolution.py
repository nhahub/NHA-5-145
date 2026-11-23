"""Ticket 08: "this" / "ديه" / "it" mean what code decides, never what the model picks.

Driven through the Agent's HTTP API with a scripted model. The model only sets the marker
`refers_to_this`; the candidates are the open product page, else the products the Copilot last
suggested, added or opened. Everything asserted is visible: stream events, the actions sent, the
model's request and event-log records. Expected strings are written out literally.
"""

import json

from agent.event_log import MemorySink
from agent.tests.test_catalogue_retrieval import Reads, candidate
from agent.tests.test_multi_step_plan import (
    advice,
    intent,
    last_action,
    make_client,
    names,
    stream,
)
from agent.tests.test_plan_failure import begin, finished, post, report_result, send, state
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_step import home_snapshot

QUESTION_AR = "تقصد أنهي منتج؟"
QUESTION_EN = "Which product do you mean?"
NILE, PYRAMID, ALEX = "ممشى النيل", "عداء الأهرام", "حذاء الإسكندرية"
NAMES = {"p-1": NILE, "p-2": PYRAMID, "p-3": ALEX}
ADD_THIS = "ضيفلي ديه للسلة"
REMOVE_IT = "شيلها من العربية"
ADD_OK = {"id": 90, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
REMOVE_OK = {"id": 91, "role": "status", "name": "تم حذف المنتج من السلة", "visible": True}


class NamedReads(Reads):
    """The catalogue fixture with distinct, verified product names."""

    @staticmethod
    def _named(key, status=None):
        item = candidate(key, status)
        product = item.product.model_copy(
            update={"nameAr": NAMES.get(key, "قطعة"), "nameEn": NAMES.get(key, "Piece")}
        )
        return item.model_copy(update={"product": product})

    async def search(self, query):
        result = await super().search(query)
        return result.model_copy(
            update={"candidates": [self._named(c.product.id) for c in result.candidates]}
        )

    async def details(self, query):
        result = await super().details(query)
        return result.model_copy(
            update={"products": [self._named(p.product.id) for p in result.products]}
        )


def retrieval_client(*replies, sink=None):
    return make_client(
        *replies, sink=sink, catalogue_client=NamedReads(), catalogue_retrieval_enabled=True
    )


def this_intent(operation="add", **overrides) -> dict:
    """What the scripted model says for "this": only the marker, never a target of its own."""
    body = {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "cart_edit",
        "constraints": {},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        "cart_operation": operation,
        "cart_source": ADD_THIS if operation == "add" else REMOVE_IT,
        "refers_to_this": True,
        **({"cart_quantity": 1, "cart_quantity_mode": "set"} if operation == "add" else {}),
        **overrides,
    }
    return body


def open_this(**overrides) -> dict:
    return intent(
        "cart", intent="open_product", constraints={}, refers_to_this=True, **overrides
    ) | {"navigation_source": "افتحها"}


def element(i, role, name, **extra):
    return {"id": i, "role": role, "name": name, "visible": True, **extra}


def product_page(slug="shoe-09", name=NILE, status=None) -> dict:
    elements = [
        element(1, "heading", name, level=1),
        element(2, "combobox", "المقاس", value="43", options=["43"]),
        element(3, "combobox", "اللون", value="blue", options=["blue"]),
        element(4, "textbox", "الكمية", value="1"),
        element(5, "button", "أضف إلى السلة", form_action="/cart/items"),
    ]
    if status:
        elements.append(status)
    return snapshot_at(f"/p/{slug}", *elements)


def home_with_links(*slugs) -> dict:
    links = [
        element(10 + i, "link", f"منتج {slug}", href=f"/p/{slug}") for i, slug in enumerate(slugs)
    ]
    return {**home_snapshot(), "elements": links}


def cart_page(*lines, status=None) -> dict:
    """Cart lines as (name, quantity-button id, remove-button id)."""
    elements = []
    for name, update_id, remove_id in lines:
        group = f"{name} — 43 — أسود"
        elements += [
            element(update_id - 1, "textbox", f"الكمية — {group}", value="1", group=group),
            element(
                update_id,
                "button",
                f"تحديث الكمية — {group}",
                form_action="/cart/quantity",
                group=group,
            ),
            element(remove_id, "button", f"حذف — {group}", form_action="/cart/remove", group=group),
        ]
    if status:
        elements.append(status)
    return snapshot_at("/cart", *elements)


def request_context(request) -> dict:
    prefix = "Shopping Copilot intent context: "
    body = request.system[len(prefix) :].split("\nInterpret", 1)[0]
    return json.loads(body)


def actions(events):
    return [e["data"]["action"] for e in events if e["event"] == "action"]


def question_of(events):
    action = last_action(events)
    assert action["type"] == "ask_shopper", action
    return action


def pick(client, session_id):
    """Ask for two or three suggestion cards, as the catalogue turn publishes them."""
    events = stream(client, session_id)
    assert [e["data"]["suggestions"] for e in events if e["event"] == "suggestions"]
    return events


def suggestion_reply(*ids):
    return [
        {"kind": "search", "query": {"query": "running shoes"}},
        {"kind": "recommend", "language": "ar", "selected_ids": list(ids)},
        advice("دي ترشيحاتي", list(ids)),
    ]


def suggest(client, text="دورلي على جزمة"):
    session_id = begin(client, text, home_snapshot())
    pick(client, session_id)
    return session_id


def add_via_page(client, session_id, events, slug="shoe-09", name=NILE):
    """Carry an add through its page: every step succeeds, the click shows the confirmation."""
    page, done = product_page(slug, name), product_page(slug, name, ADD_OK)
    for _ in range(8):
        action = last_action(events)
        if action["type"] == "navigate":
            report_result(client, session_id, events, page)
        elif action["type"] == "click":
            report_result(client, session_id, events, done, status="ok")
            return stream(client, session_id)
        else:
            report_result(client, session_id, events, page, status="ok")
        events = stream(client, session_id)
    raise AssertionError("the add never reached its click")


# --- Level 1: the product page that is open ------------------------------------------------


def test_with_a_product_page_open_add_this_targets_that_product_and_the_model_sees_it():
    client, model = make_client(this_intent())
    session_id = begin(client, ADD_THIS, product_page())
    events = stream(client, session_id)

    assert [a["type"] for a in actions(events)][-1] != "ask_shopper"
    assert not [e for e in events if e["event"] == "error"]
    candidates = request_context(model.requests[0])["resolved_state"]["_this_candidates"]
    assert candidates == [{"id": "shoe-09", "name": NILE}]
    assert len(model.requests) == 1


def test_a_model_naming_another_product_is_rejected_then_the_repair_succeeds():
    wrong = this_intent(product_id="shoe-12")
    client, model = make_client(wrong, this_intent())
    page = product_page()
    page["elements"].append(element(20, "link", "عداء الأهرام", href="/p/shoe-12"))
    session_id = begin(client, ADD_THIS, page)
    events = stream(client, session_id)

    assert len(model.requests) == 2
    feedback = model.requests[1].system.split("Runtime validation feedback: ", 1)[1]
    assert json.loads(feedback)["allowed_this_product"] == {"id": "shoe-09", "name": NILE}
    assert not [e for e in events if e["event"] == "error"]
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert all(a.get("url") != "/p/shoe-12" for a in actions(events))


def test_a_second_miss_pauses_the_task_and_never_adds_the_other_product():
    wrong = this_intent(product_id="shoe-12")
    client, model = make_client(wrong, wrong)
    page = product_page()
    page["elements"].append(element(20, "link", "عداء الأهرام", href="/p/shoe-12"))
    session_id = begin(client, ADD_THIS, page)
    events = stream(client, session_id)

    assert len(model.requests) == 2
    assert [e["data"]["message"] for e in events if e["event"] == "error"] == [
        "استجابة النموذج غير صالحة للتحقق، فتوقفت قبل أي إجراء. جرّب تاني أو أوقف المهمة."
    ]
    assert not actions(events)


def test_a_page_product_wins_over_what_was_suggested_before():
    client, model = retrieval_client(*suggestion_reply("p-2", "p-3"), this_intent())
    session_id = suggest(client)
    assert send(client, session_id, ADD_THIS, product_page("shoe-09")).status_code == 202
    stream(client, session_id)
    context = request_context(model.requests[-1])["resolved_state"]
    assert context["_this_candidates"] == [{"id": "shoe-09", "name": NILE}]


# --- Level 2: what the Copilot just suggested, added or opened -----------------------------


def test_after_one_suggestion_add_this_opens_that_product_for_the_add():
    client, model = retrieval_client(*suggestion_reply("p-1"), this_intent())
    session_id = suggest(client)
    assert send(client, session_id, ADD_THIS, home_snapshot()).status_code == 202
    events = stream(client, session_id)

    assert request_context(model.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "p-1", "name": NILE}
    ]
    assert last_action(events) == {**last_action(events), "type": "navigate", "url": "/p/p-1"}


def test_after_an_add_this_means_the_added_product():
    client, model = make_client(this_intent(), open_this())
    session_id = begin(client, ADD_THIS, product_page())
    events = add_via_page(client, session_id, stream(client, session_id))
    assert "done" in names(events)

    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    events = stream(client, session_id)
    assert request_context(model.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "shoe-09", "name": NILE}
    ]
    assert last_action(events)["url"] == "/p/shoe-09"


def test_after_opening_a_product_this_means_the_opened_product():
    opening = intent("cart", intent="open_product", constraints={}, product_id="shoe-09")
    opening["navigation_source"] = "افتح ممشى النيل"
    client, model = make_client(opening, open_this())
    named = {**home_snapshot(), "elements": [element(10, "link", NILE, href="/p/shoe-09")]}
    session_id = begin(client, "افتح ممشى النيل", named)
    report_result(client, session_id, stream(client, session_id), product_page())
    assert "done" in names(stream(client, session_id))

    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    events = stream(client, session_id)
    assert request_context(model.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "shoe-09", "name": NILE}
    ]
    assert last_action(events)["url"] == "/p/shoe-09"


def test_a_completed_task_of_another_kind_leaves_what_this_means_unchanged():
    client, model = retrieval_client(*suggestion_reply("p-1"), intent("cart"), open_this())
    session_id = suggest(client)
    assert send(client, session_id, "افتح السلة", home_snapshot()).status_code == 202
    report_result(client, session_id, stream(client, session_id), snapshot_at("/cart"))
    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    stream(client, session_id)
    assert request_context(model.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "p-1", "name": NILE}
    ]


def test_a_new_touched_product_replaces_the_earlier_ones_never_merges():
    opening = intent("cart", intent="open_product", constraints={}, product_id="p-2")
    opening["navigation_source"] = "افتح عداء الأهرام"
    client, model = retrieval_client(*suggestion_reply("p-1", "p-2"), opening, open_this())
    session_id = suggest(client)
    assert send(client, session_id, "افتح عداء الأهرام", home_snapshot()).status_code == 202
    report_result(client, session_id, stream(client, session_id), product_page("p-2", PYRAMID))
    assert "done" in names(stream(client, session_id))

    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    events = stream(client, session_id)
    assert request_context(model.requests[-1])["resolved_state"]["_this_candidates"] == [
        {"id": "p-2", "name": PYRAMID}
    ]
    assert last_action(events)["url"] == "/p/p-2"


# --- Ambiguous or empty: the Copilot asks "which one?" and never picks ----------------------


def test_two_suggestions_make_the_copilot_ask_with_both_names_and_do_nothing():
    client, _ = retrieval_client(*suggestion_reply("p-1", "p-2"), this_intent())
    session_id = suggest(client)
    assert send(client, session_id, ADD_THIS, home_snapshot()).status_code == 202
    events = stream(client, session_id)

    question = question_of(events)
    assert question["question"] == QUESTION_AR
    assert question["narration"] == QUESTION_AR
    assert question["options"] == [NILE, PYRAMID]
    assert [a["type"] for a in actions(events)].count("navigate") == 0
    assert [a["type"] for a in actions(events)].count("click") == 0


def test_three_suggestions_are_never_resolved_by_picking_one():
    client, _ = retrieval_client(*suggestion_reply("p-1", "p-2", "p-3"), open_this())
    session_id = suggest(client)
    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    events = stream(client, session_id)

    question = question_of(events)
    assert (question["question"], question["options"]) == (QUESTION_AR, [NILE, PYRAMID, ALEX])
    assert [a["type"] for a in actions(events)].count("navigate") == 0


def test_a_model_choosing_a_product_among_several_is_ignored_and_the_copilot_asks():
    client, _ = retrieval_client(*suggestion_reply("p-1", "p-2"), open_this(product_id="p-2"))
    session_id = suggest(client)
    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    events = stream(client, session_id)
    question = question_of(events)
    assert (question["question"], question["options"]) == (QUESTION_AR, [NILE, PYRAMID])
    assert [a["type"] for a in actions(events)].count("navigate") == 0


def test_nothing_touched_asks_a_free_text_question_in_the_shoppers_language():
    reply = this_intent(language="en", dialect="english", cart_source="add this")
    client, _ = make_client(reply)
    session_id = begin(client, "add this", home_snapshot())
    question = question_of(stream(client, session_id))
    assert (question["question"], question["options"]) == (QUESTION_EN, [])

    client, _ = make_client(open_this(language="en", dialect="english"))
    session_id = begin(client, "open it", home_snapshot())
    question = question_of(stream(client, session_id))
    assert (question["question"], question["options"]) == (QUESTION_EN, [])


def test_naming_one_of_the_offered_products_opens_it_without_another_model_call():
    client, model = retrieval_client(*suggestion_reply("p-1", "p-2"), open_this())
    session_id = suggest(client)
    assert send(client, session_id, "افتحها", home_snapshot()).status_code == 202
    question = question_of(stream(client, session_id))
    calls = len(model.requests)
    answer = post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={
            "question_id": question["action_id"],
            "text": PYRAMID,
            "snapshot": home_snapshot(),
        },
    )
    assert answer.status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/p-2"
    assert len(model.requests) == calls


# --- A cart line for "it" -------------------------------------------------------------------


def test_remove_it_on_the_cart_page_targets_the_touched_products_line():
    both = cart_page((NILE, 11, 12), (PYRAMID, 21, 22))
    client, model = retrieval_client(
        *suggestion_reply("p-1"), this_intent("remove", cart_target_id=12)
    )
    session_id = suggest(client)
    assert send(client, session_id, REMOVE_IT, both).status_code == 202
    events = stream(client, session_id)

    action = last_action(events)
    assert (action["type"], action["id"]) == ("click", 12)
    assert not [e for e in events if e["event"] == "error"]


def test_a_button_of_another_line_is_rejected_then_the_repair_picks_the_right_one():
    both = cart_page((NILE, 11, 12), (PYRAMID, 21, 22))
    sink = MemorySink()
    client, model = retrieval_client(
        *suggestion_reply("p-1"),
        this_intent("remove", cart_target_id=22),
        this_intent("remove", cart_target_id=12),
        sink=sink,
    )
    session_id = suggest(client)
    before = len(model.requests)
    assert send(client, session_id, REMOVE_IT, both).status_code == 202
    events = stream(client, session_id)

    assert len(model.requests) - before == 2
    action = last_action(events)
    assert (action["type"], action["id"]) == ("click", 12)
    turns = [r for r in sink.records if r["event"] == "retrieval_turn"]
    assert turns[-1]["rejections"] == ["this_mismatch"]


def test_a_remove_that_only_rejects_never_clicks_the_other_line():
    both = cart_page((NILE, 11, 12), (PYRAMID, 21, 22))
    wrong = this_intent("remove", cart_target_id=22)
    client, _ = retrieval_client(*suggestion_reply("p-1"), wrong, wrong, wrong)
    session_id = suggest(client)
    assert send(client, session_id, REMOVE_IT, both).status_code == 202
    events = stream(client, session_id)
    assert not [a for a in actions(events) if a["type"] == "click"]


# --- Inside a plan ---------------------------------------------------------------------------


def test_add_this_then_remove_it_removes_the_line_the_first_step_added():
    first = this_intent(first_step="ضيفلي ديه للسلة", remaining_steps=["وبعدين شيلها"])
    second = this_intent("remove", cart_source="وبعدين شيلها")
    both = cart_page((NILE, 11, 12), (PYRAMID, 21, 22))
    client, model = make_client(
        first,
        second,
        this_intent("remove", cart_source="وبعدين شيلها", cart_target_id=22),
        this_intent("remove", cart_source="وبعدين شيلها", cart_target_id=12),
    )
    session_id = begin(client, "ضيفلي ديه للسلة وبعدين شيلها", product_page())
    events = add_via_page(client, session_id, stream(client, session_id))
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_step_finished"] == ["done"]

    # Step 2 is its own task: it resolves "it" at its own turn to the product step 1 touched.
    assert last_action(events)["url"] == "/cart"
    assert request_context(model.requests[1])["resolved_state"]["_this_candidates"] == [
        {"id": "shoe-09", "name": NILE}
    ]
    report_result(client, session_id, events, both)
    events = stream(client, session_id)
    action = last_action(events)
    assert (action["type"], action["id"]) == ("click", 12)
    report_result(client, session_id, events, cart_page((PYRAMID, 21, 22), status=REMOVE_OK), "ok")
    events = stream(client, session_id)
    assert finished(events)["outcome"] == "done"
    assert finished(events)["report"] == ("خلصت طلبك:\n✓ ضيفلي ديه للسلة\n✓ وبعدين شيلها")


def test_an_ambiguous_this_inside_a_plan_pauses_the_plan_for_the_question():
    first = this_intent(first_step="ضيفلي ديه للسلة", remaining_steps=["وبعدين افتح الدفع"])
    client, _ = retrieval_client(*suggestion_reply("p-1", "p-2"), first)
    session_id = suggest(client)
    assert (
        send(client, session_id, "ضيفلي ديه للسلة وبعدين افتح الدفع", home_snapshot()).status_code
        == 202
    )
    events = stream(client, session_id)

    assert question_of(events)["question"] == QUESTION_AR
    assert "plan_paused" in names(events)
    assert state(client, session_id)["plan"]["paused"] == "question"
    assert not [e for e in events if e["event"] == "plan_step_finished"]


# --- Existing behaviour and privacy -----------------------------------------------------------


def test_a_message_that_does_not_refer_to_this_behaves_exactly_as_before():
    named = this_intent(
        product_id="shoe-12", refers_to_this=False, cart_source="ضيفلي عداء الأهرام"
    )
    client, model = make_client(named)
    page = {**home_snapshot(), "elements": [element(10, "link", PYRAMID, href="/p/shoe-12")]}
    session_id = begin(client, "ضيفلي عداء الأهرام", page)
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-12"
    assert len(model.requests) == 1


def test_no_event_record_carries_a_product_name_a_product_id_or_the_shoppers_words():
    sink = MemorySink()
    both = cart_page((NILE, 11, 12), (PYRAMID, 21, 22))
    client, _ = retrieval_client(
        *suggestion_reply("p-1"),
        this_intent(),
        this_intent("remove", cart_target_id=22),
        this_intent("remove", cart_target_id=12),
        sink=sink,
    )
    session_id = suggest(client)
    assert send(client, session_id, ADD_THIS, home_snapshot()).status_code == 202
    assert last_action(stream(client, session_id))["url"] == "/p/p-1"
    assert post(client, session_id, "/stop").status_code == 202
    assert send(client, session_id, REMOVE_IT, both).status_code == 202
    stream(client, session_id)

    # Only the closed rejection code is recorded: the rejected "this" never names a product.
    turns = [r for r in sink.records if r["event"] == "retrieval_turn"]
    assert [r["rejections"] for r in turns][-2:] == [[], ["this_mismatch"]]
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (NILE, PYRAMID, ALEX, "p-1", "p-2", "p-3", ADD_THIS, REMOVE_IT, "shoe-09"):
        assert private not in dumped
