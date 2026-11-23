"""Execution-contract tests. Model language quality is evaluated separately live."""

import asyncio
import json

import pytest

from agent.llm import LLMChunk, ScriptedLLMClient, interpret_message
from agent.schemas import Snapshot
from agent.storefront import load_storefront_definition
from agent.tests.test_cart_conversation_repair import cart_snapshot, quantity_payload


def interpret(message, payload, snapshot=None):
    return asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(payload))]]),
            message,
            storefront=load_storefront_definition(),
            resolved_state={},
            pending_clarification=None,
            snapshot=snapshot,
        )
    )


@pytest.mark.parametrize(
    "message",
    [
        "عايز تليته كمان من القميص",
        "عايز تلاته كمان من كوتشي ماراثون القاهرة",
    ],
)
def test_model_quantity_is_not_retranslated_from_shopper_words(message):
    snapshot = Snapshot.model_validate(cart_snapshot(3))
    payload = quantity_payload(message, None)
    payload.update(v=8, cart_target_id=13)
    intent = interpret(message, payload, snapshot)
    assert (intent.cart_quantity, intent.cart_quantity_mode, intent.cart_target_id) == (
        3,
        "increase",
        13,
    )


@pytest.mark.parametrize("target", [999, 10])
def test_unobserved_or_wrong_role_cart_target_cannot_act(target):
    snapshot = Snapshot.model_validate(cart_snapshot(3))
    payload = quantity_payload("increase this by three", None)
    payload.update(v=8, cart_target_id=target)
    with pytest.raises(ValueError):
        interpret("increase this by three", payload, snapshot)


def test_safe_ambiguity_does_not_require_a_redundant_field_label():
    from agent.planner import ActionIdentity, ScriptedPlanner

    payload = quantity_payload("زودلي اتنين من القميص الرسمي", None)
    payload.update(v=8, cart_quantity=2, needs_clarification=True)
    snapshot = Snapshot.model_validate(cart_snapshot(3))
    intent = interpret("زودلي اتنين من القميص الرسمي", payload, snapshot)
    action = ScriptedPlanner().plan_intent(
        intent, snapshot, ActionIdentity("task-1", "action-1", 1)
    )
    assert action.type == "ask_shopper"


def test_unresolved_discovery_category_asks_instead_of_entering_catalogue_evaluation():
    payload = dict(
        v=8,
        language="en",
        dialect="english",
        intent="find_products",
        constraints={"product_type": "running"},
        request_mode="recommend",
        missing_fields=[],
        needs_clarification=False,
    )
    intent = asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(payload))]] * 2),
            "the running section please",
            storefront=load_storefront_definition(),
            resolved_state={},
            pending_clarification=None,
        )
    )
    assert intent.needs_clarification
    assert intent.missing_fields == ["category"]
    assert intent.constraints.category is None


@pytest.mark.parametrize(
    "bad_field,bad_value,expected_feedback",
    [
        ("cart_operation", "decrease", "cart_operation"),
        ("cart_target_id", 10, "13"),
    ],
)
def test_model_repair_receives_specific_schema_or_observed_target_feedback(
    bad_field, bad_value, expected_feedback
):
    payload = quantity_payload("change the quantity", None)
    payload.update(v=8, cart_target_id=13)
    invalid = {**payload, bad_field: bad_value}
    requests = []

    class Client:
        async def complete(self, request):
            requests.append(request)
            if len(requests) == 2:
                feedback = request.system.split("Runtime validation feedback: ")[-1]
                assert expected_feedback in feedback
                assert '"executable_buttons_for_operation"' in feedback
                assert '"id": 13' in feedback
                assert "input_value" not in feedback
            yield LLMChunk(text=json.dumps(invalid if len(requests) == 1 else payload))

    result = asyncio.run(
        interpret_message(
            Client(),
            "change the quantity",
            storefront=load_storefront_definition(),
            resolved_state={},
            pending_clarification=None,
            snapshot=Snapshot.model_validate(cart_snapshot(3)),
        )
    )
    assert result.cart_target_id == 13
    assert len(requests) == 2


def test_exclusion_survives_interpretation_and_never_suggests_known_leather():
    from agent.catalogue import evaluate_catalogue
    from agent.tests.test_catalogue import catalogue

    payload = dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="find_products",
        constraints={"category": "shoes"},
        missing_fields=[],
        needs_clarification=False,
        request_mode="recommend",
        catalogue_requirements=[
            {"kind": "feature", "value": "leather", "source": "مش جلد", "excluded": True}
        ],
    )
    intent = interpret("عايز كوتشي مش جلد", payload)
    assert intent.catalogue_requirements[0].excluded
    result = evaluate_catalogue(catalogue(), intent)
    assert not {"formal-brown", "black-leather"}.intersection(
        item.id for item in result.suggestions
    )
    # Missing material data is not proof of non-leather.
    assert result.exact_count == 0
    assert all(item.label == "alternative" and item.unmet for item in result.suggestions)


def test_live_session_reinterprets_after_cart_navigation_and_edits_only_selected_line():
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_real_task import snapshot_at
    from agent.tests.test_sessions import parse_sse

    requests = []
    message = "زودلي تليته من القميص"

    class Model:
        async def complete(self, request):
            requests.append(request)
            payload = quantity_payload(message, None)
            payload.update(v=8, cart_target_id=13 if len(requests) == 2 else None)
            yield LLMChunk(text=json.dumps(payload))

    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=Model())
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages",
            json={"text": message, "snapshot": snapshot_at("/p/clothing-06")},
        )

        def actions():
            return [
                e["data"]["action"]
                for e in parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
                if e["event"] == "action"
            ]

        def report(action, snapshot, status="ok"):
            payload = dict(
                v=1,
                task_id=action["task_id"],
                action_id=action["action_id"],
                sequence_number=action["sequence_number"],
                status=status,
                snapshot=snapshot,
            )
            assert client.post(f"/sessions/{sid}/action-results", json=payload).status_code == 202
            return payload

        first = actions()[-1]
        assert first["type"] == "navigate"
        cart = cart_snapshot(3)
        navigation_result = report(first, cart, "navigated")
        assert len(requests) == 2
        assert "قميص رسمي" in requests[1].system
        assert '"value":"1"' in requests[1].system
        edit = actions()[-1]
        assert (edit["type"], edit["id"], edit["text"]) == ("type", 12, "4")
        client.post(f"/sessions/{sid}/action-results", json=navigation_result)
        assert len(requests) == 2
        cart["elements"][2]["value"] = "4"
        report(edit, cart)
        click = actions()[-1]
        assert (click["type"], click["id"]) == ("click", 13)
        cart["elements"].append(dict(id=99, role="status", name="تم تحديث الكمية", visible=True))
        result = report(click, cart)
        assert (
            client.get(f"/sessions/{sid}/state?tab_id=tab-local").json()["task"]["status"]
            == "completed"
        )
        before = len(actions())
        client.post(f"/sessions/{sid}/action-results", json=result)
        assert len(actions()) == before


def test_model_context_excludes_sensitive_fields_and_unrelated_input_values():
    from agent.llm.intent_pipeline import build_intent_request
    from agent.tests.test_real_task import snapshot_at

    snapshot = Snapshot.model_validate(
        snapshot_at(
            "/cart",
            dict(id=1, role="textbox", name="Password", visible=True, sensitive=True),
            dict(id=2, role="textbox", name="Notes", visible=True, value="private-form-value"),
            dict(id=3, role="textbox", name="quantity", group="Shirt M", visible=True, value="2"),
            dict(
                id=4,
                role="button",
                name="Update",
                group="Shirt M",
                visible=True,
                form_action="/cart/quantity",
            ),
        )
    )
    request = build_intent_request(
        "add three more",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
        snapshot=snapshot,
    )
    assert "Password" not in request.system
    assert "private-form-value" not in request.system
    assert '"value":"2"' in request.system


@pytest.mark.parametrize(
    "requirement",
    [
        {"kind": "suitable_for", "value": "leather", "excluded": True, "source": "مش جلد"},
        {"kind": "feature", "value": "invented_feature_xyz", "source": "something"},
    ],
)
def test_unsupported_catalogue_capability_cannot_reach_product_evaluation(requirement):
    payload = dict(
        v=8,
        language="ar",
        dialect="egyptian_arabic",
        intent="find_products",
        constraints={"category": "shoes"},
        missing_fields=[],
        needs_clarification=False,
        catalogue_requirements=[requirement],
    )
    with pytest.raises(ValueError, match="Unsupported catalogue property"):
        interpret("عايز كوتشي مش جلد", payload)


def test_legacy_model_response_cannot_enter_live_name_matching():
    payload = quantity_payload("add three more", "Shirt")
    payload["v"] = 7
    with pytest.raises(ValueError, match="schema version 8"):
        interpret("add three more", payload, Snapshot.model_validate(cart_snapshot(3)))


def test_live_service_does_not_expose_scripted_step_endpoint():
    from agent.tests.test_real_task import real_client, snapshot_at

    with real_client([]) as client:
        result = client.post("/step", json={"message": "open cart", "snapshot": snapshot_at("/")})
        assert result.status_code == 404


def test_snapshot_change_during_model_call_discards_the_proposed_action():
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.sessions import SessionStore
    from agent.tests.http_client import TestClient
    from agent.tests.test_sessions import parse_sse

    store = SessionStore()
    session = store.create()

    class Model:
        async def complete(self, request):
            # A direct cart change occurs while the model is interpreting the old view.
            session.last_snapshot.elements[0].value = "9"
            payload = quantity_payload("add three more", None)
            payload.update(v=8, cart_target_id=13)
            yield LLMChunk(text=json.dumps(payload))

    with TestClient(
        create_app(
            session_store=store,
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=Model(),
        )
    ) as client:
        session = store.get(client.post("/sessions").json()["session_id"])
        response = client.post(
            f"/sessions/{session.session_id}/messages",
            json={"text": "add three more", "snapshot": cart_snapshot(3)},
        )
        assert response.status_code == 202
        events = parse_sse(client.get(f"/sessions/{session.session_id}/events?once=true").text)
        assert not any(event["event"] == "action" for event in events)
        assert session.active_task.status == "paused"
        assert "interrupted" in session.active_task.pause_message


def test_add_accepts_explicit_form_quantity_without_treating_it_as_a_cart_total():
    from agent.cart import plan_cart_edit
    from agent.tests.test_cart_task import intent as add_intent
    from agent.tests.test_cart_task import snapshot as product_snapshot

    payload = add_intent().model_dump(mode="json")
    payload.update(
        v=8, cart_target_id=4, cart_quantity=2, cart_quantity_mode="set", cart_source="add two"
    )
    current = product_snapshot()
    decision = interpret("add two of this", payload, current)
    actions = plan_cart_edit(decision, current, "task-add", 1)
    assert [(action.type, action.id) for action in actions] == [("type", 3), ("click", 4)]
    assert actions[0].text == "2"


@pytest.mark.parametrize("operation", ["add", "remove", "undo"])
def test_delta_mode_is_not_executable_as_another_cart_operation(operation):
    payload = quantity_payload("request", None)
    payload.update(v=8, cart_operation=operation, cart_quantity_mode="increase")
    with pytest.raises(ValueError, match="Quantity mode"):
        interpret("request", payload, Snapshot.model_validate(cart_snapshot(3)))


@pytest.mark.parametrize("quantity", [-2, 0, 1.5, 1000])
def test_unexecutable_quantity_gets_a_useful_question_without_a_model_retry(quantity):
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_sessions import parse_sse

    calls = []

    class Model:
        async def complete(self, request):
            calls.append(request)
            payload = quantity_payload("requested quantity", None)
            payload.update(v=8, cart_target_id=13, cart_quantity=quantity, cart_quantity_mode="set")
            yield LLMChunk(text=json.dumps(payload))

    with TestClient(
        create_app(llm_settings=LLMSettings(provider="groq", model="test"), llm_client=Model())
    ) as client:
        sid = client.post("/sessions").json()["session_id"]
        response = client.post(
            f"/sessions/{sid}/messages",
            json={"text": "requested quantity", "snapshot": cart_snapshot(3)},
        )
        assert response.status_code == 202
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        actions = [e["data"]["action"] for e in events if e["event"] == "action"]
        assert len(calls) == 1
        assert [a["type"] for a in actions] == ["ask_shopper"]
        assert "99" in actions[0]["question"]
        assert actions[0]["options"] == []
