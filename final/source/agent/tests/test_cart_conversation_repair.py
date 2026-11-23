import asyncio
import json

import pytest

from agent.app import create_app
from agent.llm import (
    LLMChunk,
    LLMInvalidResponseError,
    LLMSettings,
    LLMToolCall,
    ScriptedLLMClient,
    interpret_message,
)
from agent.storefront import load_storefront_definition
from agent.tests.http_client import TestClient
from agent.tests.test_real_task import real_client, snapshot_at
from agent.tests.test_sessions import parse_sse


def quantity_payload(message, target=None, *, target_id=None):
    # Explicit model decision fixture; live phrasing is evaluated separately.
    return dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="cart_edit",
        constraints={},
        missing_fields=[],
        needs_clarification=False,
        cart_operation="quantity",
        cart_source=message,
        cart_target=target,
        cart_target_id=target_id,
        cart_quantity=3,
        cart_quantity_mode="increase",
    )


def cart_snapshot(count):
    elements = []
    for index, name in enumerate(["تيشيرت إسكندرية", "قميص رسمي", "جاكيت القاهرة"][:count]):
        group = f"{name} — M / blue"
        elements.extend(
            [
                dict(
                    id=10 + index * 2,
                    role="textbox",
                    name=f"الكمية — {name}",
                    value="1",
                    group=group,
                    visible=True,
                ),
                dict(
                    id=11 + index * 2,
                    role="button",
                    name=f"تحديث الكمية — {name}",
                    form_action="/cart/quantity",
                    group=group,
                    visible=True,
                ),
            ]
        )
    return snapshot_at("/cart", *elements)


@pytest.mark.parametrize(
    "invalid_draft",
    [
        [LLMChunk(text="not valid structured output")],
        [],
        [LLMChunk(tool_call=LLMToolCall(id="call-1", name="unexpected", arguments={}))],
    ],
)
def test_invalid_model_draft_is_reconsidered_without_asking_the_shopper_again(invalid_draft):
    message = "زودلي 3 كمان من قميص رسمي"
    client = real_client(
        [
            invalid_draft,
            [LLMChunk(text=json.dumps(quantity_payload(message, target_id=13)))],
        ]
    )
    session = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session}/messages",
        json={"text": message, "snapshot": cart_snapshot(3)},
    )

    assert response.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    actions = [event["data"]["action"] for event in events if event["event"] == "action"]
    assert [action["type"] for action in actions] == ["type"]
    assert actions[0]["id"] == 12
    assert actions[0]["text"] == "4"


def test_incomplete_provider_response_gets_the_same_bounded_reconsideration():
    message = "زودلي 3 كمان من قميص رسمي"

    class IncompleteThenValid:
        calls = 0

        async def complete(self, request):
            del request
            self.calls += 1
            if self.calls == 1:
                raise LLMInvalidResponseError("provider returned an incomplete completion")
            yield LLMChunk(text=json.dumps(quantity_payload(message, target_id=13)))

    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=IncompleteThenValid(),
        )
    )
    session = client.post("/sessions").json()["session_id"]

    response = client.post(
        f"/sessions/{session}/messages",
        json={"text": message, "snapshot": cart_snapshot(3)},
    )

    assert response.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    actions = [event["data"]["action"] for event in events if event["event"] == "action"]
    assert [action["type"] for action in actions] == ["type"]
    assert actions[0]["id"] == 12


@pytest.mark.parametrize(
    "message,target",
    [
        ("عايز 3 كمان من تيشرت اسكندرية", "تيشرت اسكندرية"),
        ("عايز تلاته كمان من كوتشي ماراثون القاهرة", "ماراثون القاهرة"),
        ("عايز 3 كمان من كوتشي ماراثون القاهرة", "ماراثون القاهرة"),
        ("عايز تلاته كمان من تيشرت اسكندرية", "تيشرت اسكندرية"),
    ],
)
@pytest.mark.parametrize("count,from_product", [(1, False), (3, False), (3, True)])
def test_more_three_completes_without_questions_and_only_changes_named_line(
    count, from_product, message, target
):
    outputs = [quantity_payload(message, target_id=11)]
    if from_product:
        outputs.insert(0, quantity_payload(message))
    client = real_client([[LLMChunk(text=json.dumps(payload))] for payload in outputs])
    session = client.post("/sessions").json()["session_id"]
    cart = cart_snapshot(count)
    for element in cart["elements"]:
        for key in ("name", "group"):
            element[key] = element[key].replace("تيشيرت إسكندرية", target)
    current = snapshot_at("/p/clothing-06") if from_product else cart
    client.post(f"/sessions/{session}/messages", json={"text": message, "snapshot": current})

    def latest():
        events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
        actions = [event["data"]["action"] for event in events if event["event"] == "action"]
        assert all(action["type"] != "ask_shopper" for action in actions)
        return actions[-1]

    def report(action, snapshot, status="ok"):
        result = dict(
            v=1,
            task_id=action["task_id"],
            action_id=action["action_id"],
            sequence_number=action["sequence_number"],
            status=status,
            snapshot=snapshot,
        )
        assert client.post(f"/sessions/{session}/action-results", json=result).status_code == 202
        return result

    action = latest()
    if from_product:
        assert action["type"] == "navigate" and action["url"] == "/cart"
        current = cart
        report(action, current, "navigated")
        action = latest()
    assert action["type"] == "type" and action["id"] == 10 and action["text"] == "4"
    current["elements"][0]["value"] = "4"
    report(action, current)
    action = latest()
    assert action["type"] == "click" and action["id"] == 11
    current["elements"].append(dict(id=90, role="status", name="تم تحديث الكمية", visible=True))
    result = report(action, current)
    view = client.get(f"/sessions/{session}/state?tab_id=tab-local").json()
    assert view["task"]["status"] == "completed"
    # Duplicate result must not issue another increment or click.
    assert client.post(f"/sessions/{session}/action-results", json=result).status_code == 202
    assert [e["value"] for e in current["elements"] if e["role"] == "textbox"] == ["4"] + ["1"] * (
        count - 1
    )


def test_named_egyptian_take_me_to_product_does_not_ask_again():
    message = "وديني لصفحة تيشرت اسكندرية"
    payload = dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="open_product",
        product_id="clothing-06",
        constraints={},
        missing_fields=[],
        needs_clarification=False,
    )
    result = asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(payload))]]),
            message,
            storefront=load_storefront_definition(),
            resolved_state={
                "_previous_suggestions": [
                    {"id": "clothing-06", "name": "تيشيرت إسكندرية"},
                    {"id": "clothing-05", "name": "قميص رسمي"},
                ]
            },
            pending_clarification=None,
        )
    )
    assert not result.needs_clarification
    assert result.product_id == "clothing-06"


def test_cart_navigation_to_foreign_origin_never_continues_with_an_edit():
    message = "عايز 3 كمان من تيشرت اسكندرية"
    client = real_client([[LLMChunk(text=json.dumps(quantity_payload(message, "تيشرت اسكندرية")))]])
    session = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session}/messages",
        json={"text": message, "snapshot": snapshot_at("/p/clothing-06")},
    )
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    action = [e["data"]["action"] for e in events if e["event"] == "action"][-1]
    assert action["type"] == "navigate"
    foreign = cart_snapshot(3)
    foreign["url"] = "https://outside.example/cart"
    response = client.post(
        f"/sessions/{session}/action-results",
        json=dict(
            v=1,
            task_id=action["task_id"],
            action_id=action["action_id"],
            sequence_number=action["sequence_number"],
            status="navigated",
            snapshot=foreign,
        ),
    )
    assert response.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    assert [e["data"]["action"]["type"] for e in events if e["event"] == "action"] == ["navigate"]
    assert (
        client.get(f"/sessions/{session}/state?tab_id=tab-local").json()["task"]["status"]
        == "paused"
    )
