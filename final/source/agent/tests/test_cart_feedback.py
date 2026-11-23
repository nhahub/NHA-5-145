"""Runtime feedback must use observations, not a second language interpreter."""

import json

import pytest

from agent.llm import LLMChunk
from agent.tests.test_cart_conversation_repair import cart_snapshot, quantity_payload
from agent.tests.test_cart_task import intent, snapshot
from agent.tests.test_real_task import action_result, intent_payload, real_client, snapshot_at
from agent.tests.test_sessions import parse_sse


def actions(client, sid):
    return [
        e["data"]["action"]
        for e in parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        if e["event"] == "action"
    ]


@pytest.mark.parametrize("language", ["en", "ar"])
def test_discovery_summary_does_not_reinterpret_raw_request(language):
    decision = json.loads(intent_payload(category="clothing"))
    decision["language"] = language
    with real_client([[LLMChunk(text=json.dumps(decision))]]) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages",
            json={
                "text": "Not running shoes. Show me clothing instead.",
                "snapshot": snapshot_at("/"),
            },
        )
        action = actions(client, sid)[0]
        observed = snapshot_at(
            action["url"],
            dict(id=1, role="heading", name="3 منتجات", level=2, visible=True),
        )
        assert (
            client.post(
                f"/sessions/{sid}/action-results", json=action_result(action, observed)
            ).status_code
            == 202
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        summary = next(e["data"]["summary"] for e in events if e["event"] == "done")
        assert summary == (
            "تم عرض المنتجات المطابقة." if language == "ar" else "Matching products are now shown."
        )


@pytest.mark.parametrize("mode,amount", [("increase", 99), ("decrease", 1)])
def test_computed_quantity_bounds_allow_model_interpreted_correction(mode, amount):
    first = quantity_payload("change the quantity", target_id=11)
    first.update(cart_quantity=amount, cart_quantity_mode=mode)
    correction = {**first, "cart_quantity": 2, "cart_quantity_mode": "set"}
    with real_client(
        [
            [LLMChunk(text=json.dumps(first))],
            [LLMChunk(text=json.dumps(correction))],
        ]
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        current = cart_snapshot(2)
        client.post(
            f"/sessions/{sid}/messages",
            json={"text": "change the quantity", "snapshot": current},
        )
        issued = actions(client, sid)
        assert len(issued) == 1 and issued[0]["type"] == "ask_shopper"
        question = issued[0]
        assert question["options"] == [] and "99" in question["question"]
        response = client.post(
            f"/sessions/{sid}/tasks/{question['task_id']}/answers",
            json={
                "question_id": question["action_id"],
                "text": "make it two altogether",
                "snapshot": current,
            },
        )
        assert response.status_code == 202
        assert actions(client, sid)[-1]["type"] == "type"
        assert actions(client, sid)[-1]["id"] == 10
        assert actions(client, sid)[-1]["text"] == "2"


def test_unavailable_option_asks_before_any_partial_form_change():
    current = snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    current["elements"][0]["options"] = ["43", "44"]
    decision = intent().model_dump(mode="json")
    decision.update(
        v=8,
        cart_target_id=4,
        cart_source="use my chosen options",
        constraints={"size": "44", "color": "red"},
    )
    with real_client([[LLMChunk(text=json.dumps(decision))]]) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages",
            json={"text": "use my chosen options", "snapshot": current},
        )
        issued = actions(client, sid)
        assert len(issued) == 1 and issued[0]["type"] == "ask_shopper"
        assert issued[0]["options"] == []
        assert "blue" in issued[0]["question"]


def test_missing_quantity_control_explains_refresh_without_allowing_mutation():
    current = cart_snapshot(1)
    current["elements"] = current["elements"][1:]
    decision = quantity_payload("change it", target_id=11)
    with real_client([[LLMChunk(text=json.dumps(decision))]]) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(f"/sessions/{sid}/messages", json={"text": "change it", "snapshot": current})
        issued = actions(client, sid)
        assert len(issued) == 1 and issued[0]["type"] == "ask_shopper"
        assert issued[0]["options"] == ["Stop"]
        assert "الكمية" in issued[0]["question"] and "الصفحة" in issued[0]["question"]
