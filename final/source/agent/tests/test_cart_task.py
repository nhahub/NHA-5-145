import pytest

from agent.llm.intent import StructuredIntent
from agent.schemas import ActionResult, AskShopperAction, Snapshot
from agent.sessions import SessionStore
from agent.tests.test_step import home_snapshot


def snapshot():
    return Snapshot.model_validate(
        {
            **home_snapshot(),
            "url": "http://localhost:4000/p/shoe-09",
            "elements": [
                {
                    "id": 1,
                    "role": "combobox",
                    "name": "المقاس",
                    "value": "43",
                    "options": ["43"],
                    "visible": True,
                },
                {
                    "id": 2,
                    "role": "combobox",
                    "name": "اللون",
                    "value": "blue",
                    "options": ["blue"],
                    "visible": True,
                },
                {"id": 3, "role": "textbox", "name": "الكمية", "value": "1", "visible": True},
                {
                    "id": 4,
                    "role": "button",
                    "name": "أضف إلى السلة",
                    "form_action": "/cart/items",
                    "visible": True,
                },
            ],
        }
    )


def intent(source="Add this to my cart"):
    return StructuredIntent.model_validate(
        {
            "v": 5,
            "language": "en",
            "dialect": "english",
            "intent": "cart_edit",
            "cart_operation": "add",
            "cart_source": source,
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )


@pytest.mark.parametrize("confirmed", [True, False])
def test_cart_task_completes_only_after_storefront_confirmation(confirmed):
    store = SessionStore()
    session = store.create()
    task = store.begin_interpretation(session.session_id, "Add this to my cart", snapshot())
    store.finish_interpretation(session.session_id, task.task_id, task.model_call_id, intent())
    action = task.action
    assert action.type == "click"
    updated = snapshot().model_dump(by_alias=True, exclude_none=True)
    updated["elements"] += [
        {"id": 5, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
    ]
    result = ActionResult.model_validate(
        {
            "v": 1,
            "task_id": task.task_id,
            "action_id": action.action_id,
            "sequence_number": action.sequence_number,
            "status": "ok" if confirmed else "blocked",
            "snapshot": updated,
        }
    )
    store.accept_result(session.session_id, result)
    assert task.status == ("completed" if confirmed else "awaiting_answer")
    if not confirmed:
        assert isinstance(task.action, AskShopperAction)
        assert task.action.options == ["Stop"]


def test_missing_product_options_hands_back_without_add():
    store = SessionStore()
    session = store.create()
    current = snapshot()
    current.elements[0].value = ""
    task = store.begin_interpretation(session.session_id, "Add this to my cart", current)
    store.finish_interpretation(session.session_id, task.task_id, task.model_call_id, intent())
    assert isinstance(task.action, AskShopperAction)


def test_current_selected_product_resolves_model_missing_query():
    from agent.cart import plan_cart_edit

    requested = intent("ضيفلي المنتجده للسلة").model_copy(
        update={"needs_clarification": True, "missing_fields": ["query"]}
    )
    actions = plan_cart_edit(requested, snapshot(), "task-test", 1)
    assert [a.type for a in actions] == ["click"]


def test_arabic_color_evidence_is_valid_for_canonical_variant():
    from agent.cart import validate_cart_intent

    requested = intent("مقاسي 43 وعايز اللون اسود ضيفه فالعربية")
    requested.constraints.size = "43"
    requested.constraints.color = "black"
    validate_cart_intent(requested.cart_source, requested)


@pytest.mark.parametrize("version", [6, 7])
def test_named_line_relative_quantity_uses_current_value_in_multi_item_cart(version):
    from agent.cart import plan_cart_edit, validate_cart_intent

    payload = intent("زود كمية ممشى النيل 2 كمان").model_dump()
    payload.update(
        v=version,
        cart_operation="quantity",
        cart_target="ممشى النيل",
        cart_quantity=2,
        cart_quantity_mode="increase",
    )
    requested = StructuredIntent.model_validate(payload)
    current = snapshot().model_copy(update={"url": "http://localhost:4000/cart", "elements": []})
    from agent.schemas import SnapshotElement

    for index, name, qty in [(10, "ممشى النيل", "3"), (20, "صانع اللعب", "1")]:
        current.elements.extend(
            [
                SnapshotElement(
                    id=index,
                    role="textbox",
                    name=f"الكمية — {name}",
                    value=qty,
                    visible=True,
                    group=name,
                ),
                SnapshotElement(
                    id=index + 1,
                    role="button",
                    name=f"تحديث الكمية — {name}",
                    visible=True,
                    form_action="/cart/quantity",
                    group=name,
                ),
            ]
        )
    validate_cart_intent(requested.cart_source, requested)
    actions = plan_cart_edit(requested, current, "task-test", 1)
    assert [(a.type, getattr(a, "id", None)) for a in actions] == [("type", 10), ("click", 11)]
    assert actions[0].text == "5"


def test_owned_color_does_not_override_current_selected_variant():
    from agent.cart import plan_cart_edit, validate_cart_intent

    message = "I own black shoes; add this to my cart"
    requested = validate_cart_intent(message, intent(message))
    assert requested.constraints.color is None
    assert [a.type for a in plan_cart_edit(requested, snapshot(), "task-test", 1)] == ["click"]


def test_arabic_written_quantity_is_validated_from_current_request():
    from agent.cart import validate_cart_intent

    source = "عايزك تضيف اتنين كمان من كوتشي صانع اللعب"
    payload = intent(source).model_dump()
    payload.update(
        v=6,
        cart_operation="quantity",
        cart_target="صانع اللعب",
        cart_quantity=2,
        cart_quantity_mode="increase",
    )
    assert validate_cart_intent(source, StructuredIntent.model_validate(payload)).cart_quantity == 2
