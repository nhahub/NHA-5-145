import pytest

from agent.app import create_app
from agent.cart import scripted_cart_intent
from agent.schemas import ActionResult, AskShopperAction, Snapshot
from agent.sessions import ActionResultMismatch, SessionStore, TaskConflict
from agent.tests.http_client import TestClient
from agent.tests.test_cart_task import intent as cart_intent
from agent.tests.test_cart_task import snapshot as product_snapshot
from agent.tests.test_guarded_task import cart_snapshot, clear_intent
from agent.tests.test_guarded_task import start as start_clear
from agent.tests.test_step import home_snapshot


def create_owned_session(client: TestClient, tab_id: str = "tab-1") -> str:
    response = client.post("/sessions", json={"tab_id": tab_id})
    assert response.status_code == 201
    return response.json()["session_id"]


def test_refresh_state_restores_conversation_and_requires_fresh_reconciliation() -> None:
    client = TestClient(create_app())
    session_id = create_owned_session(client)
    client.post(
        f"/sessions/{session_id}/messages",
        headers={"x-tab-id": "tab-1"},
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )

    restored = client.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    assert restored.status_code == 200
    state = restored.json()
    assert state["lease"] == "owned"
    assert state["requires_reconciliation"] is True
    assert state["conversation"][0] == {
        "role": "shopper",
        "text": "Show me running shoes under 2000 EGP",
    }
    assert state["task"]["status"] == "awaiting_action_result"

    reconciled = client.post(
        f"/sessions/{session_id}/reconcile",
        headers={"x-tab-id": "tab-1"},
        json={"snapshot": home_snapshot()},
    )

    assert reconciled.status_code == 200
    reconciled_state = reconciled.json()
    assert reconciled_state["requires_reconciliation"] is False
    assert reconciled_state["task"]["status"] == "awaiting_answer"
    assert reconciled_state["task"]["pending_question"]["type"] == "ask_shopper"


def test_pending_question_keeps_its_identity_and_resumes_original_task_after_refresh() -> None:
    client = TestClient(create_app())
    session_id = create_owned_session(client)
    client.post(
        f"/sessions/{session_id}/messages",
        headers={"x-tab-id": "tab-1"},
        json={"text": "Show me running shoes under 2000 USD", "snapshot": home_snapshot()},
    )
    before = client.get(f"/sessions/{session_id}/state?tab_id=tab-1").json()
    question = before["task"]["pending_question"]
    assert question["type"] == "ask_shopper"
    current = {**home_snapshot(), "url": "http://localhost:4000/c/shoes"}

    after = client.post(
        f"/sessions/{session_id}/reconcile",
        headers={"x-tab-id": "tab-1"},
        json={"snapshot": current},
    ).json()
    answer = client.post(
        f"/sessions/{session_id}/tasks/{question['task_id']}/answers",
        headers={"x-tab-id": "tab-1"},
        json={"question_id": question["action_id"], "text": "2000 EGP", "snapshot": current},
    )

    assert after["task"]["pending_question"] == question
    assert answer.status_code == 202
    assert answer.json()["task_id"] == question["task_id"]


@pytest.mark.parametrize("kind", ["reversible", "guarded"])
def test_refresh_never_replays_an_uncertain_cart_mutation(kind: str) -> None:
    store = SessionStore(confirmation_registrar=lambda *_: True)
    if kind == "reversible":
        session = store.create()
        task = store.begin_interpretation(
            session.session_id, "Add this to my cart", product_snapshot()
        )
        store.finish_interpretation(
            session.session_id, task.task_id, task.model_call_id or "", cart_intent()
        )
        current = product_snapshot()
    else:
        session, task = start_clear(store)
        question = task.action
        assert isinstance(question, AskShopperAction)
        store.answer(
            session.session_id, task.task_id, question.action_id, "Confirm", cart_snapshot()
        )
        current = cart_snapshot("4")
    original = task.action
    assert original is not None

    store.state(session.session_id, "tab-1")
    view = store.reconcile(session.session_id, "tab-1", current)
    recovered = view["task"]["pending_question"]

    assert view["task"]["task_id"] == task.task_id
    assert recovered["options"] == ["Stop"]
    assert recovered["action_id"] != original.action_id
    with pytest.raises(ActionResultMismatch):
        store.accept_result(
            session.session_id,
            ActionResult.model_validate(
                {
                    "v": 1,
                    "task_id": task.task_id,
                    "action_id": original.action_id,
                    "sequence_number": original.sequence_number,
                    "status": "ok",
                    "snapshot": current.model_dump(mode="json", by_alias=True, exclude_none=True),
                }
            ),
            "tab-1",
        )
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id, task.task_id, recovered["action_id"], "Continue", current, "tab-1"
        )
    store.answer(session.session_id, task.task_id, recovered["action_id"], "Stop", current, "tab-1")
    assert store.state(session.session_id, "tab-1")["task"]["status"] == "cancelled"


def test_refresh_invalidates_guarded_confirmation_and_retry_uses_current_cart() -> None:
    store = SessionStore(confirmation_registrar=lambda *_: True)
    session, task = start_clear(store)
    old_question = task.action
    assert isinstance(old_question, AskShopperAction)
    refreshed = store.state(session.session_id, "tab-1")
    assert refreshed["task"]["status"] == "paused"

    current = cart_snapshot("4")
    store.reconcile(session.session_id, "tab-1", current)
    with pytest.raises(ActionResultMismatch):
        store.answer(
            session.session_id, task.task_id, old_question.action_id, "Confirm", current, "tab-1"
        )
    store.retry_interpretation(session.session_id, task.task_id, "tab-1", current)
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )
    new_question = task.action
    assert isinstance(new_question, AskShopperAction)
    assert new_question.action_id != old_question.action_id
    assert task.mutation_proposal is not None
    assert ("cart_revision", "4") in task.mutation_proposal.arguments


def test_refresh_before_reversible_mutation_retries_from_current_product_selection() -> None:
    store = SessionStore()
    session = store.create()
    incomplete = product_snapshot()
    incomplete.elements[0].value = ""
    task = store.begin_interpretation(session.session_id, "Add this to my cart", incomplete)

    assert store.state(session.session_id, "tab-1")["task"]["status"] == "paused"
    store.reconcile(session.session_id, "tab-1", product_snapshot())
    store.retry_interpretation(session.session_id, task.task_id, "tab-1", product_snapshot())
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", cart_intent()
    )

    assert task.action is not None and task.action.type == "click"
    assert task.status == "awaiting_action_result"


def test_retry_after_direct_cart_edit_uses_newest_storefront_revision() -> None:
    store = SessionStore(confirmation_registrar=lambda *_: True)
    session, task = start_clear(store)
    store.state(session.session_id, "tab-1")
    store.reconcile(session.session_id, "tab-1", cart_snapshot("4"))

    store.retry_interpretation(session.session_id, task.task_id, "tab-1", cart_snapshot("5"))
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )

    assert task.mutation_proposal is not None
    assert ("cart_revision", "5") in task.mutation_proposal.arguments


def test_refresh_before_guarded_navigation_retries_to_fresh_confirmation() -> None:
    store = SessionStore(confirmation_registrar=lambda *_: True)
    session = store.create()
    task = store.begin_interpretation(
        session.session_id, "Please empty my cart", Snapshot.model_validate(home_snapshot())
    )
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )
    assert task.action is not None and task.action.type == "navigate"

    store.state(session.session_id, "tab-1")
    recovered = store.reconcile(session.session_id, "tab-1", cart_snapshot("4"))
    assert recovered["task"]["status"] == "paused"
    assert recovered["task"]["pending_question"] is None
    store.retry_interpretation(session.session_id, task.task_id, "tab-1", cart_snapshot("4"))
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", clear_intent()
    )
    assert isinstance(task.action, AskShopperAction)
    assert task.action.kind == "confirmation"
    assert ("cart_revision", "4") in task.mutation_proposal.arguments


def test_refresh_before_reversible_quantity_entry_replans_from_current_cart() -> None:
    store = SessionStore()
    session = store.create()

    def quantity_snapshot(value: str) -> Snapshot:
        return Snapshot.model_validate(
            {
                **home_snapshot(),
                "url": "http://localhost:4000/cart",
                "elements": [
                    {
                        "id": 1,
                        "role": "textbox",
                        "name": "الكمية — صانع اللعب",
                        "value": value,
                        "group": "صانع اللعب",
                        "visible": True,
                    },
                    {
                        "id": 2,
                        "role": "button",
                        "name": "تحديث الكمية — صانع اللعب",
                        "group": "صانع اللعب",
                        "form_action": "/cart/quantity",
                        "visible": True,
                    },
                ],
            }
        )

    task = store.submit_message(session.session_id, "Set quantity to 3", quantity_snapshot("1"))
    assert task.action is not None and task.action.type == "type"

    store.state(session.session_id, "tab-1")
    recovered = store.reconcile(session.session_id, "tab-1", quantity_snapshot("2"))
    assert recovered["task"]["status"] == "paused"
    store.retry_interpretation(session.session_id, task.task_id, "tab-1", quantity_snapshot("2"))
    intent = scripted_cart_intent("Set quantity to 3")
    assert intent is not None
    store.finish_interpretation(session.session_id, task.task_id, task.model_call_id or "", intent)
    assert task.action is not None and task.action.type == "type"
    assert task.action.text == "3"


def test_unverified_reversible_result_cannot_retry_even_after_refresh() -> None:
    store = SessionStore()
    session = store.create()
    task = store.begin_interpretation(session.session_id, "Add this to my cart", product_snapshot())
    store.finish_interpretation(
        session.session_id, task.task_id, task.model_call_id or "", cart_intent()
    )
    action = task.action
    assert action is not None
    store.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": action.action_id,
                "sequence_number": action.sequence_number,
                "status": "blocked",
                "snapshot": product_snapshot().model_dump(
                    mode="json", by_alias=True, exclude_none=True
                ),
            }
        ),
    )

    before = store.state(session.session_id, "tab-1")
    after = store.reconcile(session.session_id, "tab-1", product_snapshot())
    assert before["task"]["status"] == "awaiting_answer"
    assert after["task"]["pending_question"] == before["task"]["pending_question"]
    assert after["task"]["pending_question"]["options"] == ["Stop"]
    with pytest.raises(TaskConflict):
        store.retry_interpretation(session.session_id, task.task_id, "tab-1", product_snapshot())


@pytest.mark.parametrize(
    "message,answer,option,fragment",
    [
        ("Place my fictional order", "Confirm", "Stop", "fictional order"),
        ("اتمم طلبي الخيالي", "تأكيد", "إيقاف", "الطلب الخيالي"),
    ],
)
def test_uncertain_checkout_recovery_describes_order_not_cart(
    message: str, answer: str, option: str, fragment: str
) -> None:
    checkout = Snapshot.model_validate(
        {
            **home_snapshot(),
            "url": "http://localhost:4000/checkout",
            "elements": [
                {
                    "id": 7,
                    "role": "button",
                    "name": "إتمام الطلب الخيالي",
                    "visible": True,
                    "form_action": "/checkout/submit",
                    "mutation_state": "cart:3",
                }
            ],
        }
    )
    store = SessionStore(confirmation_registrar=lambda *_: True)
    session = store.create()
    task = store.submit_message(session.session_id, message, checkout)
    confirmation = task.action
    assert isinstance(confirmation, AskShopperAction)
    store.answer(session.session_id, task.task_id, confirmation.action_id, answer, checkout)
    assert task.action is not None and task.action.type == "guarded_click"

    store.state(session.session_id, "tab-1")
    recovered = store.reconcile(session.session_id, "tab-1", checkout)["task"]["pending_question"]

    assert recovered["options"] == [option]
    assert fragment in recovered["narration"]
    assert "Review the current cart" not in recovered["narration"]
    store.answer(
        session.session_id, task.task_id, recovered["action_id"], option, checkout, "tab-1"
    )
    assert store.state(session.session_id, "tab-1")["task"]["status"] == "cancelled"


@pytest.mark.parametrize("kind", ["reversible", "guarded"])
def test_refresh_after_verified_cart_mutation_keeps_task_complete(kind: str) -> None:
    store = SessionStore(confirmation_registrar=lambda *_: True)
    if kind == "reversible":
        session = store.create()
        task = store.begin_interpretation(
            session.session_id, "Add this to my cart", product_snapshot()
        )
        store.finish_interpretation(
            session.session_id, task.task_id, task.model_call_id or "", cart_intent()
        )
        current = product_snapshot().model_dump(mode="json", by_alias=True, exclude_none=True)
        current["elements"].append(
            {"id": 5, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
        )
        status = "ok"
    else:
        session, task = start_clear(store)
        question = task.action
        assert isinstance(question, AskShopperAction)
        store.answer(
            session.session_id, task.task_id, question.action_id, "Confirm", cart_snapshot()
        )
        current = {
            **home_snapshot(),
            "url": "http://localhost:4000/cart",
            "elements": [{"id": 1, "role": "status", "name": "السلة فارغة", "visible": True}],
        }
        status = "navigated"
    action = task.action
    assert action is not None
    store.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": action.action_id,
                "sequence_number": action.sequence_number,
                "status": status,
                "snapshot": current,
            }
        ),
    )
    assert task.status == "completed"

    store.state(session.session_id, "tab-1")
    view = store.reconcile(session.session_id, "tab-1", Snapshot.model_validate(current))

    assert view["task"]["status"] == "completed"
    assert view["task"]["pending_question"] is None
    assert store.get(session.session_id).active_task is None


def test_second_tab_requires_explicit_takeover_before_actions_resume() -> None:
    client = TestClient(create_app())
    session_id = create_owned_session(client)

    other_tab = client.get(f"/sessions/{session_id}/state?tab_id=tab-2")
    blocked_message = client.post(
        f"/sessions/{session_id}/messages",
        headers={"x-tab-id": "tab-2"},
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )
    takeover = client.post(
        f"/sessions/{session_id}/takeover",
        json={"tab_id": "tab-2"},
    )
    accepted_message = client.post(
        f"/sessions/{session_id}/messages",
        headers={"x-tab-id": "tab-2"},
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )

    assert other_tab.status_code == 200
    assert other_tab.json()["lease"] == "takeover_required"
    assert blocked_message.status_code == 409
    assert takeover.status_code == 200
    assert accepted_message.status_code == 202


def test_action_events_are_delivered_only_to_the_execution_lease_owner() -> None:
    client = TestClient(create_app())
    session_id = create_owned_session(client)
    client.post(
        f"/sessions/{session_id}/messages",
        headers={"x-tab-id": "tab-1"},
        json={"text": "Show me running shoes under 2000 EGP", "snapshot": home_snapshot()},
    )
    client.post(f"/sessions/{session_id}/takeover", json={"tab_id": "tab-2"})

    previous_owner = client.get(
        f"/sessions/{session_id}/events?after=0&once=true&tab_id=tab-1"
    ).text
    current_owner = client.get(f"/sessions/{session_id}/events?after=0&once=true&tab_id=tab-2").text

    assert "event: action" not in previous_owner
    assert "event: action" in current_owner


def test_inactive_session_expires_after_seven_days() -> None:
    week = 7 * 24 * 60 * 60
    now = [1_000.0]
    store = SessionStore(clock=lambda: now[0])
    client = TestClient(create_app(store))
    session_id = create_owned_session(client)

    now[0] += week - 1
    assert client.get(f"/sessions/{session_id}/state?tab_id=tab-1").status_code == 200

    now[0] += week + 1
    expired = client.get(f"/sessions/{session_id}/state?tab_id=tab-1")

    assert expired.status_code == 410
    assert expired.json()["detail"] == "Session expired"
