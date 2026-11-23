"""Pipeline shapes the intent prompt asks for when a named product is not yet known."""

import json
from urllib.parse import quote_plus

from agent.llm import LLMChunk
from agent.tests.test_real_task import real_client, snapshot_at
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def reply(**fields):
    base = dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        constraints={},
        missing_fields=[],
        needs_clarification=False,
    )
    return [LLMChunk(text=json.dumps({**base, **fields}))]


def actions_of(client, session):
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    return [e["data"]["action"] for e in events if e["event"] == "action"]


def test_find_products_with_a_product_name_query_runs_a_search_from_home():
    client = real_client(
        [
            reply(
                intent="find_products",
                constraints={"category": "shoes", "query": "خطوة سريعة"},
                request_mode="browse",
            )
        ]
    )
    session = client.post("/sessions").json()["session_id"]
    response = client.post(
        f"/sessions/{session}/messages",
        json={"text": "افتح خطوة سريعة", "snapshot": home_snapshot()},
    )
    assert response.status_code == 202
    actions = actions_of(client, session)
    assert actions, "a named unseen product must start a search, not end the task"
    assert actions[0]["type"] != "ask_shopper"
    assert actions[0]["type"] == "navigate"
    assert actions[0]["url"] == "/c/shoes?q=" + quote_plus("خطوة سريعة")
    state = client.get(f"/sessions/{session}/state?tab_id=tab-local").json()
    assert state["task"]["status"] not in {"paused", "failed"}


def test_remove_of_an_unseen_product_opens_the_cart_then_completes_the_remove():
    message = "شيل خطوة سريعة من السلة"
    remove = dict(
        intent="cart_edit",
        cart_operation="remove",
        cart_source=message,
        cart_target=None,
        cart_target_id=None,
    )
    client = real_client([reply(**remove), reply(**{**remove, "cart_target_id": 11})])
    session = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session}/messages",
        json={"text": message, "snapshot": snapshot_at("/p/clothing-06")},
    )
    action = actions_of(client, session)[-1]
    assert action["type"] == "navigate" and action["url"] == "/cart"
    cart = snapshot_at(
        "/cart",
        dict(
            id=11,
            role="button",
            name="حذف — خطوة سريعة",
            form_action="/cart/remove",
            group="خطوة سريعة — M / blue",
            visible=True,
        ),
    )
    result = dict(
        v=1,
        task_id=action["task_id"],
        action_id=action["action_id"],
        sequence_number=action["sequence_number"],
        status="navigated",
        snapshot=cart,
    )
    assert client.post(f"/sessions/{session}/action-results", json=result).status_code == 202
    action = actions_of(client, session)[-1]
    assert action["type"] == "click" and action["id"] == 11
    state = client.get(f"/sessions/{session}/state?tab_id=tab-local").json()
    assert state["task"]["status"] != "paused"


def test_navigation_completion_emits_one_done_and_no_identical_narration():
    from agent.tests.test_real_task import action_result, navigation_intent

    client = real_client([[LLMChunk(text=navigation_intent("navigate", "cart"))]])
    session = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session}/messages",
        json={"text": "open the cart", "snapshot": home_snapshot()},
    )
    action = actions_of(client, session)[-1]
    assert action["type"] == "navigate"
    posted = client.post(
        f"/sessions/{session}/action-results",
        json=action_result(action, snapshot_at("/cart")),
    )
    assert posted.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    names = [e["event"] for e in events]
    done = [e["data"]["summary"] for e in events if e["event"] == "done"]
    narrations = [e["data"]["text"] for e in events if e["event"] == "narration"]
    assert len(done) == 1
    assert done[0] not in narrations
    assert names[-1] == "done"
