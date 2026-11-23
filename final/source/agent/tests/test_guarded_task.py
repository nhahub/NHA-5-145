import json

import pytest

from agent.app import create_app
from agent.llm import LLMChunk, LLMSettings, ScriptedLLMClient
from agent.llm.intent import StructuredIntent
from agent.schemas import ActionResult, AskShopperAction, GuardedClickAction, Snapshot
from agent.sessions import ActionResultMismatch, SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def cart_snapshot(revision: str = "3") -> Snapshot:
    return Snapshot.model_validate(
        {
            **home_snapshot(),
            "url": "http://localhost:4000/cart",
            "elements": [
                {
                    "id": 7,
                    "role": "button",
                    "name": "Empty cart",
                    "visible": True,
                    "form_action": "/cart/clear",
                    "mutation_state": f"cart:{revision}",
                }
            ],
        }
    )


def clear_intent() -> StructuredIntent:
    return StructuredIntent.model_validate(
        {
            "v": 4,
            "language": "en",
            "dialect": "english",
            "intent": "mutate",
            "mutation_kind": "clear_cart",
            "mutation_source": "empty my cart",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )


def start(store: SessionStore):
    session = store.create()
    task = store.begin_interpretation(session.session_id, "Please empty my cart", cart_snapshot())
    result = store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )
    assert result is not None
    assert isinstance(result.action, AskShopperAction)
    return session, result


def test_clear_cart_requires_exact_card_answer_before_a_guarded_click() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session, task = start(store)
    question = task.action
    assert isinstance(question, AskShopperAction)
    assert question.kind == "confirmation"
    assert "Remove every item" in question.question
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id,
            task.task_id,
            question.action_id,
            "yes",
            cart_snapshot(),
        )
    assert isinstance(task.action, AskShopperAction)

    confirmed = store.answer(
        session.session_id,
        task.task_id,
        question.action_id,
        "Confirm",
        cart_snapshot(),
    )
    assert isinstance(confirmed.action, GuardedClickAction)
    assert confirmed.action.id == 7
    assert confirmed.action.confirmation_id == question.action_id
    assert confirmed.action.target_signature == "button|Empty cart|POST /cart/clear"


def test_arabic_confirmation_card_explains_the_bulk_effect() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session = store.create()
    task = store.begin_interpretation(session.session_id, "فضي السلة", cart_snapshot())
    intent = StructuredIntent.model_validate(
        {
            "v": 4,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "mutate",
            "mutation_kind": "clear_cart",
            "mutation_source": "فضي السلة",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )

    store.finish_interpretation(session.session_id, task.task_id, task.model_call_id or "", intent)

    assert isinstance(task.action, AskShopperAction)
    assert task.action.kind == "confirmation"
    assert "إزالة كل المنتجات من السلة الحالية" in task.action.question
    assert task.action.options == ["تأكيد", "إيقاف"]


def test_changed_cart_or_expired_offer_cannot_authorize_mutation() -> None:
    clock = [100.0]
    store = SessionStore(clock=lambda: clock[0], confirmation_registrar=lambda *_: True)
    session, task = start(store)
    question = task.action
    assert isinstance(question, AskShopperAction)
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id,
            task.task_id,
            question.action_id,
            "Confirm",
            cart_snapshot("4"),
        )
    clock[0] = 160.0
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id,
            task.task_id,
            question.action_id,
            "Confirm",
            cart_snapshot(),
        )


def test_refresh_invalidates_unused_confirmation() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session, task = start(store)
    question = task.action
    assert isinstance(question, AskShopperAction)
    view = store.state(session.session_id, "tab-a")

    assert view["task"]["pending_question"] is None
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id,
            task.task_id,
            question.action_id,
            "Confirm",
            cart_snapshot(),
        )


def test_off_page_clear_navigates_then_asks_before_any_mutation() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session = store.create()
    task = store.begin_interpretation(
        session.session_id, "Please empty my cart", Snapshot.model_validate(home_snapshot())
    )
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )
    assert task.action is not None and task.action.type == "navigate"
    first = task.action

    store.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": first.action_id,
                "sequence_number": first.sequence_number,
                "status": "navigated",
                "snapshot": cart_snapshot(),
            }
        ),
    )
    assert isinstance(task.action, AskShopperAction)
    assert task.action.kind == "confirmation"


def test_verified_clear_completes_only_after_a_matching_result() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session, task = start(store)
    question = task.action
    assert isinstance(question, AskShopperAction)
    store.answer(session.session_id, task.task_id, question.action_id, "Confirm", cart_snapshot())
    action = task.action
    assert isinstance(action, GuardedClickAction)
    empty = Snapshot.model_validate(
        {
            **home_snapshot(),
            "url": "http://localhost:4000/cart",
            "elements": [{"id": 1, "role": "status", "name": "السلة فارغة", "visible": True}],
        }
    )

    store.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": action.action_id,
                "sequence_number": action.sequence_number,
                "status": "navigated",
                "snapshot": empty,
            }
        ),
    )

    assert task.status == "completed"
    assert store.get(session.session_id).active_task is None


def test_guarded_result_from_another_origin_is_never_reported_as_success() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session, task = start(store)
    question = task.action
    assert isinstance(question, AskShopperAction)
    store.answer(session.session_id, task.task_id, question.action_id, "Confirm", cart_snapshot())
    action = task.action
    assert isinstance(action, GuardedClickAction)
    forged = Snapshot.model_validate(
        {
            **home_snapshot(),
            "url": "https://attacker.example/cart",
            "elements": [{"id": 1, "role": "status", "name": "السلة فارغة", "visible": True}],
        }
    )

    store.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": action.action_id,
                "sequence_number": action.sequence_number,
                "status": "navigated",
                "snapshot": forged,
            }
        ),
    )

    assert task.status == "awaiting_answer"
    assert isinstance(task.action, AskShopperAction)
    assert task.action.options == ["Stop"]


@pytest.mark.parametrize("schema_version", [8, 9])
def test_agent_api_registers_only_the_exact_shopper_confirmed_mutation(schema_version) -> None:
    registered: list[tuple[str, str, str, str, int]] = []
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=ScriptedLLMClient(
                [
                    [
                        LLMChunk(
                            text=json.dumps(
                                {**clear_intent().model_dump(mode="json"), "v": schema_version}
                            )
                        )
                    ]
                ]
            ),
            confirmation_registrar=lambda *parts: registered.append(parts) or True,
        )
    )
    session_id = client.post("/sessions").json()["session_id"]
    snapshot = cart_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
    message = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Please empty my cart", "snapshot": snapshot},
    )
    assert message.status_code == 202
    task_id = message.json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)
    question = next(event["data"]["action"] for event in events if event["event"] == "action")
    assert question["kind"] == "confirmation"
    assert registered == []

    answer = client.post(
        f"/sessions/{session_id}/tasks/{task_id}/answers",
        json={"question_id": question["action_id"], "text": "Confirm", "snapshot": snapshot},
    )
    assert answer.status_code == 202
    assert [parts[1:] for parts in registered] == [
        ("http://localhost:4000/cart", question["action_id"], task_id, "clear_cart", 3)
    ]
    all_events = parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)
    assert [
        event["data"]["action"]["type"] for event in all_events if event["event"] == "action"
    ] == ["ask_shopper", "guarded_click"]


def test_scripted_browser_provider_can_exercise_the_real_confirmation_boundary() -> None:
    store = SessionStore(clock=lambda: 100.0, confirmation_registrar=lambda *_: True)
    session = store.create()

    task = store.submit_message(session.session_id, "Empty my cart", cart_snapshot())

    assert isinstance(task.action, AskShopperAction)
    assert task.action.kind == "confirmation"
