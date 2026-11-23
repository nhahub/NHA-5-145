"""A model-proposed cart edit or mutation must quote the Shopper's own words, and an Undo
asked after its window has closed gets an honest answer instead of a retry loop."""

import json

import pytest

from agent.app import create_app
from agent.cart import UNDO_EXPIRED
from agent.llm import LLMSettings
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel
from agent.tests.test_cart_conversation_repair import cart_snapshot, quantity_payload
from agent.tests.test_cart_task import snapshot as product_snapshot
from agent.tests.test_guarded_task import cart_snapshot as clear_snapshot
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_sessions import parse_sse

EARLIER_ADD = "ضيفها للسلة مقاس 43 لون أبيض"
REMOVE = "شيل خطوة سريعة من السلة"


def payload(operation, source, **changes):
    return {
        **dict(
            v=8,
            language="ar",
            dialect="egyptian_arabic",
            intent="cart_edit",
            constraints={},
            missing_fields=[],
            needs_clarification=False,
            cart_operation=operation,
            cart_source=source,
        ),
        **changes,
    }


def mutation(kind, source):
    return dict(
        v=8,
        language="en",
        dialect="english",
        intent="mutate",
        constraints={},
        missing_fields=[],
        needs_clarification=False,
        mutation_kind=kind,
        mutation_source=source,
    )


def remove_snapshot():
    return snapshot_at(
        "/cart",
        dict(
            id=12,
            role="button",
            name="حذف — خطوة سريعة",
            form_action="/cart/remove",
            group="خطوة سريعة — 43 / white",
            visible=True,
        ),
    )


def undo_snapshot(*, enabled=True):
    return snapshot_at(
        "/cart",
        dict(
            id=20,
            role="button",
            name="تراجع",
            form_action="/cart/undo",
            disabled=not enabled,
            visible=True,
        ),
    )


def clear_page():
    return clear_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)


def product_page():
    return product_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)


class Session:
    """A scripted-model HTTP seam in plain interpretation or catalogue-retrieval mode."""

    def __init__(self, retrieval, *responses):
        self.store = SessionStore(confirmation_registrar=lambda *_: True)
        self.model = RecordingModel(*responses)
        self.client = TestClient(
            create_app(
                session_store=self.store,
                llm_settings=LLMSettings(provider="groq", model="test"),
                llm_client=self.model,
                catalogue_client=object(),
                catalogue_retrieval_enabled=retrieval,
                confirmation_registrar=lambda *_: True,
            )
        )
        self.client.__enter__()
        self.sid = self.client.post("/sessions").json()["session_id"]
        if retrieval:
            known = self.store.get(self.sid).product_context
            known.origin = ("http", "localhost:4000")
            known.remember_suggestions([{"id": "shoe-12", "name": "ملعب النجوم"}])

    def send(self, text, snapshot):
        response = self.client.post(
            f"/sessions/{self.sid}/messages", json={"text": text, "snapshot": snapshot}
        )
        assert response.status_code == 202, response.text

    def events(self):
        return parse_sse(self.client.get(f"/sessions/{self.sid}/events?once=true").text)

    def actions(self):
        return [e["data"]["action"] for e in self.events() if e["event"] == "action"]

    def summaries(self):
        return [e["data"]["summary"] for e in self.events() if e["event"] == "done"]

    def rejections(self):
        return self.store.get(self.sid).last_task.retrieval_budget.rejections


@pytest.fixture(params=[False, True], ids=["plain", "retrieval"])
def retrieval(request):
    opened = []

    def make(*responses):
        opened.append(Session(request.param, *responses))
        return opened[-1]

    make.enabled = request.param
    yield make
    for session in opened:
        session.client.__exit__(None, None, None)


def test_copied_earlier_add_cannot_answer_a_remove_request(retrieval):
    copied = payload(
        "add",
        EARLIER_ADD,
        cart_target_id=4,
        cart_quantity=1,
        cart_quantity_mode="set",
        constraints={"size": "43", "color": "white"},
    )
    session = retrieval(copied, copied, copied)
    session.send(REMOVE, product_page())
    assert session.actions() == []
    if retrieval.enabled:
        assert session.rejections() == ["source_not_in_message"] * 3
    else:
        # The existing repair attempt ran once, then the existing invalid_response pause.
        assert len(session.model.requests) == 2
        assert session.events()[-1]["event"] == "error"
    assert EARLIER_ADD not in json.dumps(session.events(), ensure_ascii=False)


@pytest.mark.parametrize("source", [None, "", "   "])
def test_a_missing_source_is_not_evidence(retrieval, source):
    bad = quantity_payload("x", target_id=11)
    bad["cart_source"] = source
    session = retrieval(bad, bad, bad)
    session.send("زوّد الكمية", cart_snapshot(1))
    assert session.actions() == []


def test_a_quoted_quantity_source_runs(retrieval):
    session = retrieval(quantity_payload("الكمية تلاتة", target_id=11))
    session.send("زوّد الكمية تلاتة", cart_snapshot(1))
    assert [a["type"] for a in session.actions()] == ["type"]


def test_a_quoted_add_source_runs(retrieval):
    ok = payload(
        "add",
        "ضيفها للسلة",
        cart_target_id=4,
        cart_quantity=1,
        cart_quantity_mode="set",
        constraints={"size": "43"},
    )
    session = retrieval(ok)
    session.send("ضيفها للسلة مقاس 43", product_page())
    assert [a["type"] for a in session.actions()] == ["type"]


def test_a_quoted_remove_source_runs(retrieval):
    session = retrieval(payload("remove", REMOVE, cart_target_id=12))
    session.send(REMOVE, remove_snapshot())
    assert [a["type"] for a in session.actions()] == ["click"]


def test_a_quoted_undo_source_runs_when_the_control_is_observed(retrieval):
    session = retrieval(payload("undo", "تراجع", cart_target_id=20))
    session.send("تراجع لو سمحت", undo_snapshot())
    actions = session.actions()
    assert [a["type"] for a in actions] == ["click"] and actions[0]["id"] == 20


def test_whitespace_differences_in_the_quote_still_match(retrieval):
    session = retrieval(payload("remove", "شيل   خطوة\tسريعة من  السلة", cart_target_id=12))
    session.send("شيل خطوة سريعة\nمن السلة", remove_snapshot())
    assert [a["type"] for a in session.actions()] == ["click"]


def test_an_answer_turn_may_quote_the_original_request(retrieval):
    first = quantity_payload("زوّد الكمية", target_id=None)
    first.update(needs_clarification=True, missing_fields=["target"])
    second = quantity_payload("زوّد الكمية", target_id=11)
    session = retrieval(first, second)
    current = cart_snapshot(1)
    session.send("زوّد الكمية", current)
    question = session.actions()[-1]
    assert question["type"] == "ask_shopper"
    response = session.client.post(
        f"/sessions/{session.sid}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "التيشيرت", "snapshot": current},
    )
    assert response.status_code == 202, response.text
    assert [a["type"] for a in session.actions()] == ["ask_shopper", "type"]


def test_clear_cart_with_its_own_quote_reaches_the_confirmation_card(retrieval):
    session = retrieval(mutation("clear_cart", "empty my cart"))
    session.send("Please empty my cart", clear_page())
    action = session.actions()[-1]
    assert action["type"] == "ask_shopper" and action["kind"] == "confirmation"


def test_checkout_with_its_own_quote_reaches_the_confirmation_card(retrieval):
    session = retrieval(mutation("submit_checkout", "place my order"))
    checkout = snapshot_at(
        "/checkout",
        dict(
            id=3,
            role="button",
            name="Place order",
            form_action="/checkout/submit",
            mutation_state="cart:3",
            visible=True,
        ),
    )
    session.send("Please place my order", checkout)
    action = session.actions()[-1]
    assert action["type"] == "ask_shopper" and action["kind"] == "confirmation"


@pytest.mark.parametrize("kind", ["clear_cart", "submit_checkout"])
def test_a_mutation_quoting_another_message_is_refused(retrieval, kind):
    bad = mutation(kind, "empty my cart")
    session = retrieval(bad, bad, bad)
    session.send("show me the shoes again", clear_page())
    assert session.actions() == []
    if retrieval.enabled:
        assert session.rejections() == ["source_not_in_message"] * 3


def test_expired_undo_completes_the_task_with_an_arabic_answer_and_no_action(retrieval):
    undo = payload("undo", "تراجع", cart_target_id=20)
    session = retrieval(undo, undo, undo)
    session.send("تراجع عن آخر تعديل", snapshot_at("/cart"))
    assert session.actions() == []
    assert len(session.model.requests) == 2  # refused once for a repair, then the honest answer
    assert session.summaries() == [UNDO_EXPIRED[0]]
    assert session.store.get(session.sid).last_task.status == "completed"


def test_expired_undo_answers_in_english(retrieval):
    english = payload("undo", "undo", language="en", dialect="english")
    session = retrieval(english, english)
    session.send("undo that please", snapshot_at("/cart"))
    assert session.actions() == []
    assert session.summaries() == [UNDO_EXPIRED[1]]


def test_a_disabled_undo_control_counts_as_expired(retrieval):
    disabled = payload("undo", "تراجع", cart_target_id=20)
    session = retrieval(disabled, disabled)
    session.send("تراجع", undo_snapshot(enabled=False))
    assert session.actions() == []
    assert session.summaries() == [UNDO_EXPIRED[0]]


# Ticket 07 (copilot reliability, B7): Egyptian wording for the order and for emptying the cart
# is a guarded mutation behind the Confirmation; opening checkout only navigates.
CHECKOUT_BUTTONS = dict(
    id=3,
    role="button",
    name="Place order",
    form_action="/checkout/submit",
    mutation_state="cart:3",
    visible=True,
)


@pytest.mark.parametrize("words", ["اعمل الطلب", "خلّص الطلب", "كمّل الطلب", "أكّد الطلب"])
def test_arabic_order_wording_as_submit_checkout_reaches_the_confirmation_card(retrieval, words):
    session = retrieval(mutation("submit_checkout", words))
    session.send(words, snapshot_at("/checkout", CHECKOUT_BUTTONS))
    action = session.actions()[-1]
    assert action["type"] == "ask_shopper" and action["kind"] == "confirmation"
    assert not [a for a in session.actions() if a["type"] == "click"]


@pytest.mark.parametrize("words", ["امسح السلة كلها", "فضّي السلة"])
def test_arabic_clear_wording_as_clear_cart_reaches_the_confirmation_card(retrieval, words):
    session = retrieval(mutation("clear_cart", words))
    session.send(words, clear_page())
    action = session.actions()[-1]
    assert action["type"] == "ask_shopper" and action["kind"] == "confirmation"
    assert not [a for a in session.actions() if a["type"] == "click"]


def test_opening_checkout_only_navigates_and_never_submits(retrieval):
    from agent.tests.test_step import home_snapshot

    opened = dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="navigate",
        constraints={"target": "checkout"},
        missing_fields=[],
        needs_clarification=False,
        navigation_source="افتح الدفع",
    )
    session = retrieval(opened)
    session.send("افتح الدفع", home_snapshot())
    actions = session.actions()
    assert [a["type"] for a in actions] == ["navigate"] and actions[0]["url"] == "/checkout"
