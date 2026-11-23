"""A selected recommendation remains the goal through navigation and cart execution."""

import json

import pytest

from agent.app import create_app
from agent.llm import LLMChunk, LLMSettings
from agent.llm.intent import StructuredIntent
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_cart_task import snapshot
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def add_decision(**changes):
    return dict(
        v=9,
        language="ar",
        dialect="egyptian_arabic",
        intent="cart_edit",
        constraints={"size": "43", "color": "blue"},
        missing_fields=[],
        needs_clarification=False,
        cart_operation="add",
        product_id="shoe-12",
        cart_quantity=1,
        cart_quantity_mode="set",
        cart_source="ضيفه فالعربية",
        **changes,
    )


def product_snapshot(path="/p/shoe-12"):
    current = snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    current["url"] = "http://localhost:4000" + path
    current["elements"][0].update(value="42", options=["42", "43"])
    current["elements"][1].update(value="yellow", options=["yellow", "blue"])
    return current


class Model:
    def __init__(self):
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        yield LLMChunk(text=json.dumps(add_decision()))


def flow():
    store, model = SessionStore(), Model()
    app = create_app(
        session_store=store,
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_retrieval_enabled=False,
    )
    return store, model, TestClient(app)


def start(store, client):
    sid = client.post("/sessions").json()["session_id"]
    session = store.get(sid)
    session.product_context.origin = ("http", "localhost:4000")
    session.product_context.remember_suggestions(
        [
            {"id": "shoe-12", "name": "ملعب النجوم"},
            {"id": "shoe-13", "name": "صانع اللعب"},
        ]
    )
    session.conversation.append(
        {"role": "copilot", "text": "ملعب النجوم أزرق وأصفر، وصانع اللعب أبيض وأسود."}
    )
    client.post(
        f"/sessions/{sid}/messages",
        json={
            "text": "عايز ملعب النجوم لون ازرق مقاس 43 ضيفه فالعربية",
            "snapshot": home_snapshot(),
        },
    )
    return sid


def events(client, sid):
    return parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)


def last_action(client, sid):
    actions = [e["data"]["action"] for e in events(client, sid) if e["event"] == "action"]
    assert actions, events(client, sid)
    return actions[-1]


def report(client, sid, action, current, status="ok"):
    body = dict(
        v=1,
        task_id=action["task_id"],
        action_id=action["action_id"],
        sequence_number=action["sequence_number"],
        status=status,
        snapshot=current,
    )
    assert client.post(f"/sessions/{sid}/action-results", json=body).status_code == 202
    return body


def test_recommendation_add_navigates_selects_and_completes_without_another_model_call():
    store, model, client = flow()
    with client:
        sid = start(store, client)
        action = last_action(client, sid)
        assert (action["type"], action["url"]) == ("navigate", "/p/shoe-12")
        current = product_snapshot()
        body = report(client, sid, action, current, "navigated")
        # A duplicate navigation result must not issue another selection or paid call.
        before = len(events(client, sid))
        client.post(f"/sessions/{sid}/action-results", json=body)
        assert len(events(client, sid)) == before
        for element, expected in [(0, "43"), (1, "blue")]:
            action = last_action(client, sid)
            assert (action["type"], action["id"], action["option"]) == (
                "select",
                element + 1,
                expected,
            )
            current["elements"][element]["value"] = expected
            report(client, sid, action, current)
        action = last_action(client, sid)
        assert (action["type"], action["text"]) == ("type", "1")
        report(client, sid, action, current)
        action = last_action(client, sid)
        assert (action["type"], action["id"]) == ("click", 4)
        current["elements"].append(
            dict(id=5, role="status", name="تمت الإضافة إلى السلة", visible=True)
        )
        body = report(client, sid, action, current)
        assert store.get(sid).last_task.status == "completed"
        before = len(events(client, sid))
        client.post(f"/sessions/{sid}/action-results", json=body)
        assert len(events(client, sid)) == before
        assert len(model.requests) == 1


@pytest.mark.parametrize(
    "variant",
    ["wrong_product", "off_origin", "disabled", "ambiguous", "truncated", "missing_color"],
)
def test_navigation_does_not_authorize_an_unverified_add_form(variant):
    store, model, client = flow()
    with client:
        sid = start(store, client)
        action = last_action(client, sid)
        assert action["type"] == "navigate"
        current = product_snapshot()
        if variant == "wrong_product":
            current["url"] = "http://localhost:4000/p/shoe-13"
        elif variant == "off_origin":
            current["url"] = "https://other.example/p/shoe-12"
        elif variant == "disabled":
            current["elements"][3]["disabled"] = True
        elif variant == "ambiguous":
            current["elements"].append({**current["elements"][3], "id": 6})
        elif variant == "truncated":
            current["truncated"] = True
        else:
            current["elements"][1]["options"] = ["yellow"]
        report(client, sid, action, current, "navigated")
        task = store.get(sid).active_task
        assert task.status in {"paused", "awaiting_answer"}
        assert task.action is None or task.action.type == "ask_shopper"
        assert not task.cart_actions
        assert len(model.requests) == 1


def test_product_identity_is_not_cart_line_authority():
    payload = add_decision()
    for operation in ["remove", "quantity", "undo"]:
        payload.update(cart_operation=operation, cart_quantity=None, cart_quantity_mode=None)
        with pytest.raises(ValueError):
            StructuredIntent.model_validate(payload)


def test_page_change_during_variant_selection_never_sends_remaining_add():
    store, model, client = flow()
    with client:
        sid = start(store, client)
        report(client, sid, last_action(client, sid), product_snapshot(), "navigated")
        selection = last_action(client, sid)
        assert selection["type"] == "select"
        report(client, sid, selection, product_snapshot("/p/shoe-13"))
        task = store.get(sid).active_task
        assert task.status == "paused"
        assert task.action is None
        assert not task.cart_actions


def test_other_shoppers_recommendations_never_authorize_a_product_add():
    store, model, client = flow()
    with client:
        start(store, client)
        other = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{other}/messages",
            json={
                "text": "add the first one",
                "snapshot": home_snapshot(),
            },
        )
        assert not any(e["event"] == "action" for e in events(client, other))
