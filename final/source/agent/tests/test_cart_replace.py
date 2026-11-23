"""Ticket 10 (revised): "blue instead of yellow" is an add of the new colour, then a removal.

Driven through the Agent's HTTP API with a scripted model. The model only proposes the cart
operation, the NEW colour and the observed remove button of the line to change. Code reads the
old line from the cart Snapshot (size, old colour, quantity, product link), checks the
catalogue, adds the new colour on the product page with the old quantity and, only after the
add is verified, removes exactly the old line. Expected strings are written out literally.
"""

import copy
import json

import pytest

from agent.app import create_app
from agent.event_log import MemorySink
from agent.llm import LLMSettings
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel
from agent.tests.test_conditions import PRODUCT, Shelf, Snapshots, world
from agent.tests.test_multi_step_plan import intent, last_action, stream
from agent.tests.test_plan_failure import begin, finished, report_result, send, state
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_step import home_snapshot
from agent.tests.test_this_resolution import (
    NILE,
    PYRAMID,
    NamedReads,
    suggest,
    suggestion_reply,
)

SOURCE = "خليها صفرا"
SOURCE_EN = "make it yellow"
NILE_EN = "Nile walker"
SIZE = "XXL"
ADD_OK = {"id": 90, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
REMOVE_OK = {"id": 91, "role": "status", "name": "تم حذف المنتج من السلة", "visible": True}
COULD_NOT_CHECK_AR = "ما قدرتش أتأكد من الشرط ده من بيانات المنتج. تحب أعمل إيه؟"
REMOVE_FAILED_AR = (
    "ضفت اللون الجديد، بس ما قدرتش أشيل القديم، فالسلة فيها الاتنين دلوقتي. تقدر تطلب مني أشيله."
)
REMOVE_FAILED_EN = (
    "I added the new colour but couldn't remove the old one, so your cart has both now. "
    "You can ask me to remove it."
)
DONE_AR = "غيّرت اللون: ضفت ممشى النيل مقاس XXL باللون الأصفر وشلت اللي باللون الأزرق."
DONE_EN = "Changed the colour: added Nile walker in size XXL in yellow and removed the blue one."


def element(i, role, name, **extra):
    return {"id": i, "role": role, "name": name, "visible": True, **extra}


def line_group(ar, en, size, colour):
    return f"{ar} / {en} — {size} / {colour}"


def cart(*lines, status=None):
    """Cart lines as (ar, en, size, colour, quantity, product id, first element id).

    Each line has the Storefront's markup: a `/p/<id>` link, the quantity textbox, the
    quantity button and the remove button "حذف المنتج — <name>"; there is no colour control.
    """
    elements = []
    for ar, en, size, colour, quantity, product, base in lines:
        group = line_group(ar, en, size, colour)
        elements += [
            element(base, "link", ar, href=f"/p/{product}", group=group),
            element(base + 1, "textbox", f"الكمية — {ar}", value=str(quantity), group=group),
            element(
                base + 2,
                "button",
                f"تحديث الكمية — {ar}",
                form_action="/cart/quantity",
                group=group,
            ),
            element(
                base + 3, "button", f"حذف المنتج — {ar}", form_action="/cart/remove", group=group
            ),
        ]
    if status:
        elements.append(status)
    return snapshot_at("/cart", *elements)


def blue_line(quantity=2, size=SIZE, colour="blue", base=10):
    return (NILE, NILE_EN, size, colour, quantity, PRODUCT, base)


def old_cart(status=None, **kwargs):
    return cart(blue_line(**kwargs), status=status)


def both_cart(status=None):
    """After the add: the old line and the new one, which has its own label."""
    return cart(blue_line(), blue_line(colour="yellow", base=20), status=status)


def product_page(size="42", colour="blue", colours=("blue", "yellow"), sizes=("42", SIZE), **kw):
    elements = [
        element(1, "heading", NILE, level=1),
        element(2, "combobox", "المقاس", value=size, options=list(sizes)),
        element(3, "combobox", "اللون", value=colour, options=list(colours)),
        element(4, "textbox", "الكمية", value="1"),
        element(5, "button", "أضف إلى السلة", form_action="/cart/items"),
    ]
    if kw.get("status"):
        elements.append(kw["status"])
    return snapshot_at(f"/p/{PRODUCT}", *elements)


def replace_intent(**overrides) -> dict:
    return {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "cart_edit",
        "constraints": {"color": "yellow"},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        "cart_operation": "replace",
        "cart_source": SOURCE,
        "cart_target_id": 13,
        **overrides,
    }


def english(**overrides) -> dict:
    return replace_intent(language="en", dialect="english", cart_source=SOURCE_EN, **overrides)


def actions(events):
    return [e["data"]["action"] for e in events if e["event"] == "action"]


def kinds(events):
    return [a["type"] for a in actions(events)]


def done_summaries(events):
    return [e["data"]["summary"] for e in events if e["event"] == "done"]


def errors(events):
    return [e["data"]["message"] for e in events if e["event"] == "error"]


def go(client, session_id, events, snapshot, status="ok"):
    report_result(client, session_id, events, snapshot, status=status)
    return stream(client, session_id)


def to_the_add_click(client, session_id, events):
    """Carry the product page through its select, select and type steps to the click."""
    assert (last_action(events)["type"], last_action(events)["url"]) == (
        "navigate",
        f"/p/{PRODUCT}",
    )
    events = go(client, session_id, events, product_page(), "navigated")
    seen = []
    while last_action(events)["type"] != "click":
        seen.append(last_action(events))
        events = go(client, session_id, events, product_page())
    return events, seen


def to_the_cart_after_the_add(client, session_id, events):
    events, seen = to_the_add_click(client, session_id, events)
    events = go(client, session_id, events, product_page(status=ADD_OK))
    return events, seen


def swap(shelf=None, *replies, text=SOURCE, snapshot=None, sink=None, retrieval=False):
    client, model = world(
        retrieval,
        shelf or Shelf(colors=("blue", "yellow"), sizes=("42", SIZE)),
        *(replies or (replace_intent(),)),
        sink=sink,
    )
    session_id = begin(client, text, snapshot or old_cart())
    return client, model, session_id, stream(client, session_id)


# --- The swap: add the new colour, then remove exactly the old line ----------------------------


def test_a_swap_on_the_cart_page_adds_the_new_colour_then_removes_the_old_line():
    client, model, session_id, events = swap()
    events, seen = to_the_cart_after_the_add(client, session_id, events)
    assert [(a["type"], a.get("id"), a.get("option") or a.get("text")) for a in seen] == [
        ("select", 2, SIZE),
        ("select", 3, "yellow"),
        ("type", 4, "2"),
    ]
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")

    events = go(client, session_id, events, both_cart(), "navigated")
    click = last_action(events)
    assert (click["type"], click["id"]) == ("click", 13)  # the OLD line's remove button
    assert not done_summaries(events)

    events = go(client, session_id, events, old_cart_after_remove())
    assert done_summaries(events) == [DONE_AR]
    assert state(client, session_id)["task"]["status"] == "completed"
    assert not errors(events)
    assert len(model.requests) == 1  # code did the rest; the model chose only the line


def old_cart_after_remove():
    return cart(blue_line(colour="yellow", base=20), status=REMOVE_OK)


def test_the_done_summary_exists_in_english():
    client, _, session_id, events = swap(None, english(), text="make it yellow instead of blue")
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    events = go(client, session_id, events, both_cart(), "navigated")
    events = go(client, session_id, events, old_cart_after_remove())
    assert done_summaries(events) == [DONE_EN]


def test_nothing_is_removed_before_the_add_is_verified():
    client, _, session_id, events = swap()
    events, _ = to_the_add_click(client, session_id, events)
    # The add click comes back with no success status: the uncertain-mutation stop, no remove.
    events = go(client, session_id, events, product_page())
    assert last_action(events)["type"] == "ask_shopper"
    assert not [a for a in actions(events) if a["type"] == "navigate" and a["url"] == "/cart"]


def test_with_retrieval_on_the_catalogue_check_works_the_same():
    client, _, session_id, events = swap(retrieval=True)
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    assert last_action(events)["url"] == "/cart"


def test_from_a_product_page_the_cart_opens_first_then_the_swap_runs():
    foreign = replace_intent(cart_target_id=7)  # a button of the product page, not a cart line
    client, model, session_id, events = swap(
        None, foreign, replace_intent(), snapshot=product_page()
    )
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")
    assert len(model.requests) == 1  # the foreign id is dropped, never rejected
    events = go(client, session_id, events, old_cart(), "navigated")
    assert len(model.requests) == 2  # the fresh cart Snapshot is interpreted
    assert (last_action(events)["type"], last_action(events)["url"]) == (
        "navigate",
        f"/p/{PRODUCT}",
    )


# --- Questions and no-ops: nothing on the page is touched -------------------------------------


def test_a_colour_the_product_does_not_offer_asks_and_touches_nothing():
    shelf = Shelf(colors=("blue", "black"), sizes=("42", SIZE))
    client, _, session_id, events = swap(shelf)
    assert kinds(events) == ["ask_shopper"]
    question = last_action(events)
    assert question["question"] == (
        "اللون الأصفر مش متاح للمنتج ده في المقاس XXL. الألوان المتاحة: أسود. تحب أغيّره لأنهي لون؟"
    )
    assert question["options"] == []
    assert state(client, session_id)["task"]["status"] == "awaiting_answer"


def test_a_size_the_product_does_not_have_asks_in_english():
    shelf = Shelf(colors=("blue", "yellow", "black"), sizes=("42",))
    _, _, _, events = swap(shelf, english(), text="make it yellow")
    assert kinds(events) == ["ask_shopper"]
    assert last_action(events)["question"] == (
        "yellow isn't available for this product in size XXL. Available colours: yellow, black. "
        "Which colour would you like?"
    )


def test_an_unavailable_product_asks_and_changes_nothing():
    _, _, _, events = swap(Shelf(colors=("blue", "yellow"), sizes=("42", SIZE), available=False))
    assert kinds(events) == ["ask_shopper"]


def test_a_catalogue_read_failure_asks_the_could_not_check_question():
    shelf = Shelf(colors=("blue", "yellow"), sizes=("42", SIZE))
    shelf.fail = True
    _, _, _, events = swap(shelf)
    assert kinds(events) == ["ask_shopper"]
    assert last_action(events)["question"] == COULD_NOT_CHECK_AR
    assert last_action(events)["options"] == []


def test_no_colour_asks_which_colour_and_lists_the_others():
    shelf = Shelf(colors=("blue", "yellow", "black"), sizes=("42", SIZE))
    _, _, _, events = swap(shelf, replace_intent(constraints={}))
    assert kinds(events) == ["ask_shopper"]
    assert last_action(events)["question"] == ("تحب تغيّره للون إيه؟ الألوان المتاحة: أصفر, أسود.")
    _, _, _, events = swap(shelf, english(constraints={}), text=SOURCE_EN)
    assert last_action(events)["question"] == (
        "Which colour would you like instead? Available colours: yellow, black."
    )


def test_the_same_colour_asks_which_colour_and_changes_nothing():
    # A "new" colour equal to the line's colour is a misread request: ask, never claim done.
    shelf = Shelf(colors=("blue", "yellow", "black"), sizes=("42", SIZE))
    client, _, session_id, events = swap(shelf, replace_intent(constraints={"color": "blue"}))
    assert kinds(events) == ["ask_shopper"]
    assert done_summaries(events) == []
    assert last_action(events)["question"] == (
        "اللون الأزرق هو اللي في السلة أصلاً. تحب تغيّره للون إيه؟ الألوان المتاحة: أصفر, أسود."
    )
    assert last_action(events)["options"] == []
    _, _, _, events = swap(shelf, english(constraints={"color": "blue"}), text=SOURCE_EN)
    assert last_action(events)["question"] == (
        "blue is already the colour in your cart. Which colour would you like instead? "
        "Available colours: yellow, black."
    )


def test_an_unreadable_line_asks_which_item_and_changes_nothing():
    for broken in (
        # no product link
        [e for e in old_cart()["elements"] if e["role"] != "link"],
        # no quantity textbox
        [e for e in old_cart()["elements"] if e["role"] != "textbox"],
    ):
        page = {**old_cart(), "elements": broken}
        _, _, _, events = swap(None, snapshot=page)
        assert kinds(events) == ["ask_shopper"]
        assert last_action(events)["question"].startswith("لم أقدر أحدد منتجًا واحدًا")


def test_a_target_that_is_not_a_remove_button_is_rejected():
    for button in (12, 11, 99):  # the quantity button, the textbox, an unobserved id
        client, model, session_id, events = swap(
            None, replace_intent(cart_target_id=button), replace_intent(cart_target_id=button)
        )
        assert not [a for a in actions(events) if a["type"] in {"click", "select", "navigate"}]
        assert len(model.requests) == 2


# --- The add cannot be done, or the removal cannot ---------------------------------------------


def test_a_product_page_without_the_option_asks_and_removes_nothing():
    client, _, session_id, events = swap()
    events = go(client, session_id, events, product_page(colours=("blue",)), "navigated")
    assert last_action(events)["type"] == "ask_shopper"
    assert state(client, session_id)["task"]["status"] == "awaiting_answer"
    assert not [a for a in actions(events) if a["type"] == "click"]
    # The Shopper answers; the old line is never removed by the swap.
    assert not [a for a in actions(events) if a.get("url") == "/cart"]


def test_when_the_removal_cannot_be_done_the_task_pauses_with_both_lines_in_the_cart():
    sink = MemorySink()
    client, _, session_id, events = swap(sink=sink)
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    gone = cart(blue_line(colour="yellow", base=20))  # the old line is not on the cart page
    events = go(client, session_id, events, gone, "navigated")
    assert errors(events) == [REMOVE_FAILED_AR]
    assert state(client, session_id)["task"]["status"] == "paused"
    reasons = [r["reason"] for r in sink.records if r["event"] == "task_paused"]
    assert reasons == ["swap_remove_failed"]
    assert not [a for a in actions(events) if a["type"] == "click" and a["id"] == 23]


def test_a_failed_removal_click_pauses_and_the_text_exists_in_english():
    client, _, session_id, events = swap(None, english(), text=SOURCE_EN)
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    events = go(client, session_id, events, both_cart(), "navigated")
    events = go(client, session_id, events, both_cart(), "not_found")
    assert errors(events) == [REMOVE_FAILED_EN]


def test_a_removal_with_no_status_is_the_uncertain_mutation_stop():
    client, _, session_id, events = swap()
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    events = go(client, session_id, events, both_cart(), "navigated")
    events = go(client, session_id, events, both_cart())
    question = last_action(events)
    assert question["type"] == "ask_shopper" and question["options"] == ["إيقاف"]


# --- In a plan ---------------------------------------------------------------------------------


def planned():
    return replace_intent(first_step=SOURCE, remaining_steps=["وبعدين افتح الدفع"])


def test_a_swap_step_succeeds_and_the_next_step_runs():
    client, _, session_id, events = swap(None, planned(), intent("checkout"))
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    events = go(client, session_id, events, both_cart(), "navigated")
    events = go(client, session_id, events, old_cart_after_remove())
    assert [e["data"]["outcome"] for e in events if e["event"] == "plan_step_finished"] == ["done"]
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/checkout")


def test_a_failed_swap_fails_the_step_and_skips_the_rest():
    client, model, session_id, events = swap(None, planned(), intent("checkout"))
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    gone = cart(blue_line(colour="yellow", base=20))
    events = go(client, session_id, events, gone, "navigated")
    assert finished(events)["outcome"] == "failed"
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✕ {SOURCE} — {REMOVE_FAILED_AR}\n– وبعدين افتح الدفع (اتخطّت)"
    )
    assert len(model.requests) == 1  # the next step was never interpreted


# --- "This" ------------------------------------------------------------------------------------


class ColourReads(NamedReads):
    """Named products that come in 43 / blue / yellow."""

    async def details(self, query):
        result = await super().details(query)
        products = [
            p.model_copy(
                update={
                    "product": p.product.model_copy(
                        update={"sizes": ["43"], "colors": ["blue", "yellow"]}
                    )
                }
            )
            for p in result.products
        ]
        return result.model_copy(update={"products": products})


def this_cart():
    return cart(
        (NILE, NILE_EN, "43", "blue", 1, "p-1", 10),
        (PYRAMID, "Pyramid runner", "43", "blue", 1, "p-2", 20),
    )


def this_replace(button_id):
    return replace_intent(cart_target_id=button_id, refers_to_this=True)


def test_replace_with_this_targets_the_single_candidates_line_and_rejects_another():
    from agent.tests.test_multi_step_plan import make_client

    sink = MemorySink()
    client, model = make_client(
        *suggestion_reply("p-1"),
        this_replace(23),  # the other product's remove button: rejected
        this_replace(13),
        sink=sink,
        catalogue_client=ColourReads(),
        catalogue_retrieval_enabled=True,
    )
    session_id = suggest(client)
    before = len(model.requests)
    assert send(client, session_id, SOURCE, this_cart()).status_code == 202
    events = stream(client, session_id)

    assert len(model.requests) - before == 2
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/p/p-1")
    turns = [r for r in sink.records if r["event"] == "retrieval_turn"]
    assert turns[-1]["rejections"] == ["this_mismatch"]


# --- Scratch state and records -----------------------------------------------------------------


def lasting(session):
    return copy.deepcopy(
        (
            session.remembered_sizes,
            session.copilot_selected_size,
            session.last_touched,
            session.product_kinds,
        )
    )


def test_nothing_of_the_swap_is_kept_in_the_session():
    store = SessionStore(confirmation_registrar=lambda *_: True)
    app = create_app(
        session_store=store,
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=RecordingModel(replace_intent()),
        confirmation_registrar=lambda *_: True,
        catalogue_reader=Snapshots(Shelf(colors=("blue", "yellow"), sizes=("42", SIZE))),
        catalogue_retrieval_enabled=False,
    )
    with TestClient(app) as client:
        session_id = begin(client, SOURCE, old_cart())
        before = lasting(store.get(session_id))
        events = stream(client, session_id)
        events, _ = to_the_cart_after_the_add(client, session_id, events)
        events = go(client, session_id, events, both_cart(), "navigated")
        events = go(client, session_id, events, old_cart_after_remove())
        assert done_summaries(events) == [DONE_AR]
        after = lasting(store.get(session_id))
    assert after == before
    assert "yellow" not in json.dumps(after, ensure_ascii=False)


def test_no_record_carries_a_colour_a_size_a_name_or_the_shoppers_words():
    sink = MemorySink()
    client, _, session_id, events = swap(sink=sink)
    events, _ = to_the_cart_after_the_add(client, session_id, events)
    events = go(client, session_id, events, cart(blue_line(colour="yellow", base=20)), "navigated")
    assert errors(events) == [REMOVE_FAILED_AR]

    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in ("yellow", "blue", SIZE, NILE, NILE_EN, SOURCE, "صفرا", REMOVE_FAILED_AR):
        assert private not in dumped
    assert "swap_remove_failed" in dumped


def test_the_prompt_teaches_replace_as_a_colour_change_of_a_cart_line():
    client, model, session_id, _ = swap()
    system = model.requests[-1].system
    assert model.requests[-1].prompt_version == "intent-v39"
    assert "is replace, never remove plus add" in system
    assert "حذف المنتج" in system
    assert "/cart/replace" not in system


# --- A button ID from another page never names a cart line -------------------------------------

PRODUCT_BUTTON = 7


def remove_intent(**overrides) -> dict:
    return replace_intent(cart_operation="remove", constraints={}, cart_source="شيلها", **overrides)


def test_a_remove_from_a_product_page_drops_the_foreign_id_and_opens_the_cart():
    client, model, session_id, events = swap(
        None,
        remove_intent(cart_target_id=PRODUCT_BUTTON),
        remove_intent(cart_target_id=13),
        text="شيلها من السلة",
        snapshot=product_page(),
    )
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")
    assert len(model.requests) == 1
    events = go(client, session_id, events, old_cart(), "navigated")
    assert (last_action(events)["type"], last_action(events)["id"]) == ("click", 13)


def test_a_quantity_edit_from_a_product_page_also_opens_the_cart():
    quantity = replace_intent(
        cart_operation="quantity",
        cart_source="خليها 2",
        constraints={},
        cart_quantity=2,
        cart_quantity_mode="set",
        cart_target_id=PRODUCT_BUTTON,
    )
    _, model, _, events = swap(None, quantity, text="خليها 2", snapshot=product_page())
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")
    assert len(model.requests) == 1


def test_no_rejection_is_recorded_when_a_product_page_id_is_dropped():
    from agent.tests.test_multi_step_plan import make_client

    sink = MemorySink()
    client, _ = make_client(
        *suggestion_reply("p-1"),
        replace_intent(cart_target_id=PRODUCT_BUTTON),
        sink=sink,
        catalogue_client=NamedReads(),
        catalogue_retrieval_enabled=True,
    )
    session_id = suggest(client)
    assert send(client, session_id, SOURCE, product_page()).status_code == 202
    events = stream(client, session_id)
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")
    turns = [r for r in sink.records if r["event"] == "retrieval_turn"]
    assert turns[-1]["rejections"] == []
    assert "cart_edit_invalid" not in json.dumps(sink.records, ensure_ascii=False)


@pytest.mark.parametrize(
    "payload", [replace_intent(cart_target_id=99), remove_intent(cart_target_id=99)]
)
def test_on_the_cart_page_an_unobserved_id_is_still_rejected(payload):
    client, model = world(False, Shelf(), payload, payload)[:2]
    session_id = begin(client, SOURCE, old_cart())
    events = stream(client, session_id)
    assert not [a for a in actions(events) if a["type"] in {"click", "select"}]
    assert len(model.requests) == 2


def test_home_is_not_the_cart():
    # A replace asked on the home page with no id opens the cart and is interpreted again.
    client, model, _, events = swap(
        None, replace_intent(cart_target_id=None), snapshot=home_snapshot()
    )
    assert (last_action(events)["type"], last_action(events)["url"]) == ("navigate", "/cart")
