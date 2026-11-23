import asyncio
import json

import pytest

from agent.llm import LLMChunk, ScriptedLLMClient, interpret_message
from agent.llm.intent import StructuredIntent
from agent.schemas import Snapshot
from agent.sessions import SessionStore
from agent.storefront import load_storefront_definition
from agent.tests.test_real_task import intent_payload, real_client
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


@pytest.mark.parametrize("message", ["افتح صفحة القميص الرسمي", "افتح صفحة قَمِيص رَسْمِي"])
def test_verified_product_reference_does_not_depend_on_model_source_metadata(message):
    # Captured provider output: the product is correct, navigation_source is omitted.
    payload = {
        "v": 8,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "open_product",
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
        "product_id": "clothing-05",
        "cart_quantity": None,
        "cart_quantity_mode": None,
    }
    result = asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(payload))]]),
            message,
            storefront=load_storefront_definition(),
            resolved_state={
                "_previous_suggestions": [
                    {"id": "clothing-04", "name": "قميص قطن"},
                    {"id": "clothing-05", "name": "قميص رسمي"},
                ]
            },
            pending_clarification=None,
        )
    )
    assert result.product_id == "clothing-05"
    assert not result.needs_clarification


@pytest.mark.parametrize(
    "bad_output",
    [
        "not json",
        "{}",
        '["not an intent"]',
        json.dumps(
            {
                "v": 8,
                "language": "en",
                "dialect": "english",
                "intent": "mutate",
                "constraints": {},
                "mutation_kind": "unsupported_operation",
                "mutation_source": "Open my cart",
                "missing_fields": [],
                "needs_clarification": False,
            }
        ),
    ],
)
def test_two_unusable_interpretations_pause_without_telling_the_shopper_to_rephrase(bad_output):
    client = real_client([[LLMChunk(text=bad_output)], [LLMChunk(text=bad_output)]])

    session = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session}/messages",
        json={
            "text": "Open my cart",
            "snapshot": home_snapshot(),
        },
    )
    state = client.get(f"/sessions/{session}/state?tab_id=tab-local").json()
    assert state["task"]["status"] == "paused"
    assert state["task"]["pending_question"] is None
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    assert not any(event["event"] == "action" for event in events)
    errors = [event["data"]["message"] for event in events if event["event"] == "error"]
    assert len(errors) == 1
    assert "model response" in errors[0].lower()


def test_ambiguous_verified_product_choice_survives_refresh_without_another_model_call():
    store = SessionStore()
    session = store.create()
    snap = Snapshot.model_validate(home_snapshot())
    task = store.begin_interpretation(session.session_id, "افتح صفحته", snap)
    task.resolved_state["_previous_suggestions"] = [
        {"id": "clothing-04", "name": "قميص قطن"},
        {"id": "clothing-05", "name": "قميص رسمي"},
    ]
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "open_product",
            "constraints": {},
            "product_id": None,
            "missing_fields": ["product_id"],
            "needs_clarification": True,
        }
    )
    store.finish_interpretation(session.session_id, task.task_id, task.model_call_id, intent)
    question = store.state(session.session_id, "tab-local")["task"]["pending_question"]
    assert question["options"] == ["قميص قطن", "قميص رسمي"]
    store.begin_answer_interpretation(
        session.session_id,
        task.task_id,
        question["action_id"],
        "قميص رسمي",
        snap,
        None,
    )
    assert task.model_call_id is None
    assert task.action.type == "navigate"
    assert task.action.url == "/p/clothing-05"
    assert task.action.sequence_number == question["sequence_number"] + 1


def test_manual_retry_after_two_invalid_drafts_can_recover_without_a_new_shopper_message():
    client = real_client(
        [
            [LLMChunk(text="not json")],
            [LLMChunk(text="still not json")],
            [LLMChunk(text=intent_payload(category="shoes"))],
        ]
    )
    session = client.post("/sessions").json()["session_id"]
    task = client.post(
        f"/sessions/{session}/messages",
        json={
            "text": "عايز حذاء",
            "snapshot": home_snapshot(),
        },
    ).json()["task_id"]
    assert (
        client.get(f"/sessions/{session}/state?tab_id=tab-local").json()["task"]["status"]
        == "paused"
    )

    response = client.post(
        f"/sessions/{session}/tasks/{task}/retry",
        json={"snapshot": home_snapshot()},
    )
    assert response.status_code == 202
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    actions = [event["data"]["action"] for event in events if event["event"] == "action"]
    assert [action["type"] for action in actions] == ["navigate"]
    assert actions[0]["url"] == "/c/shoes"
