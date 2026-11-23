"""Ticket 03: an Undo reading with no Undo button, and an honest "can't do that".

Driven through the Agent's HTTP API with a scripted model, on the plain and the retrieval
execution paths. Expected strings are written out literally.
"""

import json

import pytest

from agent.cart import UNDO_EXPIRED
from agent.event_log import REJECTION_CODES
from agent.tests.test_cart_replace import (
    actions as event_actions,
)
from agent.tests.test_cart_replace import (
    kinds,
    replace_intent,
    swap,
)
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_source_evidence_and_undo import payload, retrieval, undo_snapshot

assert retrieval  # the plain/retrieval fixture, imported for its parametrisation

CLEAR_ALL = "امسح السلة كلها"
UNDONE = {"id": 31, "role": "status", "name": "تم التراجع", "visible": True}
CLEAR_BUTTON = {
    "id": 7,
    "role": "button",
    "name": "إفراغ السلة",
    "visible": True,
    "form_action": "/cart/clear",
    "mutation_state": "cart:3",
}
EXPIRED_AR = UNDO_EXPIRED[0]
NOT_UNDERSTOOD_AR = "ما قدرتش أفهم الطلب ده كعملية في المتجر. تقدر تقولها بطريقة تانية؟"
NOT_UNDERSTOOD_EN = (
    "I couldn't match that to something I can do in the shop. Could you say it another way?"
)
GENERIC_AR = "أقدر أساعدك في التسوق داخل المتجر."


def after_undo_page():
    return snapshot_at("/cart", UNDONE, CLEAR_BUTTON)


def clear_reading(source=CLEAR_ALL):
    return dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="mutate",
        constraints={},
        missing_fields=[],
        needs_clarification=False,
        mutation_kind="clear_cart",
        mutation_source=source,
    )


def reading(kind, **changes):
    return {
        "v": 8,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": kind,
        "constraints": {},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        **changes,
    }


def feedback(session, index=1):
    system = session.model.requests[index].system
    return system.split("Runtime validation feedback:", 1)[-1].split("Validation feedback:", 1)[-1]


# --- Undo with no Undo button ----------------------------------------------------------------


def test_undo_with_no_button_is_repaired_to_clear_cart_and_offers_the_confirmation(retrieval):
    """Capture #151."""
    wrong = payload("undo", "امسح", cart_target_id=31)
    session = retrieval(wrong, clear_reading())
    session.send(CLEAR_ALL, after_undo_page())
    action = session.actions()[-1]
    assert action["type"] == "ask_shopper" and action["kind"] == "confirmation"
    assert EXPIRED_AR not in session.summaries()
    assert [a["type"] for a in session.actions()] == ["ask_shopper"]
    assert len(session.model.requests) == 2
    repair = feedback(session)
    assert "إفراغ السلة" in repair and "mutate/clear_cart" in repair
    assert "only possible while an enabled Undo control is visible" in repair
    if retrieval.enabled:
        assert session.rejections() == ["undo_without_button"]


def test_the_repair_lists_the_visible_checkout_control_too(retrieval):
    checkout = {
        "id": 3,
        "role": "button",
        "name": "Place order",
        "visible": True,
        "form_action": "/checkout/submit",
        "mutation_state": "cart:3",
    }
    session = retrieval(payload("undo", "تراجع"), payload("undo", "تراجع"))
    session.send("تراجع", snapshot_at("/checkout", checkout))
    assert "mutate/submit_checkout" in feedback(session)


def test_a_repeated_undo_with_no_button_gets_the_honest_expired_text_and_nothing_clicked(retrieval):
    undo = payload("undo", "تراجع", cart_target_id=20)
    session = retrieval(undo, undo, undo)
    session.send("تراجع عن آخر تعديل", snapshot_at("/cart"))
    assert session.actions() == []
    assert session.summaries() == [EXPIRED_AR]
    assert len(session.model.requests) == 2
    assert session.store.get(session.sid).last_task.status == "completed"
    if retrieval.enabled:
        assert session.rejections() == ["undo_without_button"]


def test_an_undo_with_its_button_visible_works_in_one_call(retrieval):
    session = retrieval(payload("undo", "تراجع", cart_target_id=20))
    session.send("تراجع لو سمحت", undo_snapshot())
    actions = session.actions()
    assert [a["type"] for a in actions] == ["click"] and actions[0]["id"] == 20
    assert len(session.model.requests) == 1


# --- Unsupported -----------------------------------------------------------------------------


def test_unsupported_is_repaired_once_and_a_colour_change_succeeds(retrieval):
    """Capture #162 shape: the repaired reading is a replace and runs."""
    client, model, session_id, events = swap(
        None,
        reading("unsupported"),
        replace_intent(),
        text="خليها صفرا بدل الأحمر",
        retrieval=retrieval.enabled,
    )
    assert len(model.requests) == 2
    assert kinds(events) == ["navigate"]
    repair = model.requests[1].system
    for word in ("search", "open a product", "undo", "empty the whole cart", "check out"):
        assert word in repair
    assert "cart_edit/replace" in repair
    assert event_actions(events)[0]["url"].startswith("/p/")


def test_a_second_unsupported_gets_the_honest_arabic_text(retrieval):
    session = retrieval(reading("unsupported"), reading("unsupported"), reading("unsupported"))
    session.send("خليها صفرا بدل الأحمر", snapshot_at("/cart"))
    assert session.actions() == []
    assert session.summaries() == [NOT_UNDERSTOOD_AR]
    assert len(session.model.requests) == 2
    assert session.store.get(session.sid).last_task.status == "completed"
    if retrieval.enabled:
        assert session.rejections() == ["unsupported_reading"]


def test_a_second_unsupported_gets_the_honest_english_text(retrieval):
    english = reading("unsupported", language="en", dialect="english")
    session = retrieval(english, english)
    session.send("do the thing", snapshot_at("/cart"))
    assert session.summaries() == [NOT_UNDERSTOOD_EN]


@pytest.mark.parametrize("kind", ["off_topic", "help"])
def test_off_topic_and_help_answers_are_unchanged_and_not_repaired(retrieval, kind):
    session = retrieval(reading(kind))
    session.send("مين كسب الماتش؟", snapshot_at("/cart"))
    assert session.summaries() == [GENERIC_AR]
    assert len(session.model.requests) == 1


# --- Records ---------------------------------------------------------------------------------


def test_the_new_rejection_codes_are_in_the_allow_list_and_no_shopper_text_is_recorded(retrieval):
    assert {"undo_without_button", "unsupported_reading"} <= REJECTION_CODES
    session = retrieval(reading("unsupported"), reading("unsupported"))
    session.send("كلام سري للمتسوق", snapshot_at("/cart"))
    if retrieval.enabled:
        record = json.dumps(session.rejections())
        assert "كلام" not in record
        assert set(session.rejections()) <= REJECTION_CODES
