import asyncio
import json

import pytest

from agent.llm import LLMChunk, ScriptedLLMClient
from agent.llm.intent_pipeline import build_intent_request, interpret_message
from agent.storefront import load_storefront_definition


def payload(**changes):
    return {
        "v": 8,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "find_products",
        "constraints": {"category": "shoes"},
        "missing_fields": [],
        "needs_clarification": False,
        **changes,
    }


def interpret(message, value, state=None, pending=None):
    return asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(value))]] * 2),  # 2nd: the one repair
            message,
            storefront=load_storefront_definition(),
            resolved_state=state or {},
            pending_clarification=pending,
        )
    )


def test_outfit_colors_are_not_shoe_constraints():
    intent = interpret(
        "عندي تيشيرت اخضر وبنطلون بني وعايز كوتشي تقترح ايه",
        payload(
            request_mode="style",
            owned_items=[
                {
                    "category": "clothing",
                    "product_type": "tops",
                    "color": "green",
                    "source": "تيشيرت اخضر",
                },
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "brown",
                    "source": "بنطلون بني",
                },
            ],
            preferred_colors=["white", "cream"],
        ),
    )
    assert not intent.needs_clarification
    assert intent.constraints.color is None
    assert intent.constraints.product_type is None
    assert len(intent.context_items) == 2


def test_owned_running_shoes_can_have_a_type_and_category_in_one_source():
    result = interpret(
        "I own black running shoes and need trousers",
        payload(
            constraints={"category": "clothing", "product_type": "trousers"},
            request_mode="style",
            owned_items=[
                {
                    "category": "shoes",
                    "product_type": "running",
                    "color": "black",
                    "source": "black running shoes",
                }
            ],
        ),
    )
    assert not result.needs_clarification
    assert result.constraints.color is None


def test_semantic_paraphrase_is_not_required_to_match_dictionary():
    intent = interpret(
        "محتاج shoes ما تعرقش رجلي",
        payload(
            catalogue_requirements=[
                {"kind": "feature", "value": "breathable", "source": "ما تعرقش رجلي"}
            ]
        ),
    )
    assert intent.catalogue_requirements[0].value == "breathable"


def test_semantic_navigation_accepts_novel_wording_with_source():
    intent = interpret(
        "وديني عالحساب",
        payload(
            intent="navigate",
            constraints={"target": "account"},
            navigation_source="وديني عالحساب",
        ),
    )
    assert not intent.needs_clarification
    assert intent.constraints.target == "account"


def test_clarification_keeps_outfit_requirements_before_catalogue_routing():
    original = "عندي بنطلون بني وعايز حاجة مناسبة تحت 2000"
    prior = payload(
        constraints={"max_price": {"amount": "2000", "currency": "EGP"}},
        request_mode="style",
        missing_fields=["category"],
        needs_clarification=True,
        owned_items=[
            {
                "category": "clothing",
                "product_type": "trousers",
                "color": "brown",
                "source": "بنطلون بني",
            }
        ],
        preferred_colors=["white"],
    )
    intent = interpret(
        "Shoes",
        payload(),
        {"_intent": prior, "_original_message": original, "_answers": ["Shoes"]},
        "category",
    )
    assert not intent.needs_clarification
    assert intent.request_mode == "style"
    assert intent.context_items[0].color == "brown"
    assert intent.constraints.max_price.amount == "2000"
    assert intent.constraints.category == "shoes"


def test_explicit_clarification_revision_can_remove_a_budget_without_losing_size():
    prior = payload(
        constraints={"category": "shoes", "max_price": {"amount": "2000", "currency": "EGP"}},
        needs_clarification=True,
        missing_fields=["size"],
    )
    result = interpret(
        "size 43, no price limit",
        payload(
            constraints={"category": "shoes", "size": "43"},
            revised_fields=["max_price"],
            revision_source="no price limit",
        ),
        {"_intent": prior, "_original_message": "shoes under 2000"},
        "size",
    )
    assert result.constraints.max_price is None
    assert result.constraints.size == "43"


def test_explicit_feature_removal_is_not_readded_from_its_negated_word():
    prior = payload(
        catalogue_requirements=[{"kind": "feature", "value": "leather", "source": "leather"}],
        needs_clarification=True,
        missing_fields=["size"],
    )
    result = interpret(
        "size 43, forget leather",
        payload(
            constraints={"category": "shoes", "size": "43"},
            revised_fields=["catalogue"],
            revision_source="forget leather",
        ),
        {"_intent": prior, "_original_message": "leather shoes"},
        "size",
    )
    assert result.catalogue_requirements == []
    assert result.constraints.size == "43"


def test_explicit_browse_revision_clears_inherited_outfit_context_only():
    prior = payload(
        constraints={
            "category": "shoes",
            "size": "43",
            "max_price": {"amount": "2000", "currency": "EGP"},
        },
        request_mode="style",
        owned_item={
            "category": "clothing",
            "product_type": "trousers",
            "color": "brown",
            "source": "brown trousers",
        },
        owned_items=[
            {
                "category": "clothing",
                "product_type": "trousers",
                "color": "brown",
                "source": "brown trousers",
            }
        ],
        preferred_colors=["white"],
        desired_wear_position="footwear",
        needs_clarification=True,
        missing_fields=["product_type"],
    )

    result = interpret(
        "Shoes, forget the outfit—just show running shoes",
        payload(
            constraints={"category": "shoes", "product_type": "running"},
            request_mode="browse",
            revised_fields=[
                "request_mode",
                "owned_items",
                "owned_item",
                "preferred_colors",
                "desired_wear_position",
            ],
            revision_source="forget the outfit",
        ),
        {"_intent": prior, "_original_message": "brown trousers, shoes size 43 under 2000"},
        "product_type",
    )

    assert result.request_mode == "browse"
    assert result.context_items == []
    assert result.desired_wear_position is None
    assert result.preferred_colors == []
    assert result.constraints.size == "43"
    assert result.constraints.max_price is not None
    assert result.constraints.max_price.amount == "2000"


def test_owned_item_source_accepts_a_single_t_shirt_despite_overlapping_aliases():
    intent = interpret(
        "I own a white t-shirt; suggest shoes",
        payload(
            constraints={"category": "shoes"},
            request_mode="style",
            owned_items=[
                {
                    "category": "clothing",
                    "product_type": "tops",
                    "color": "white",
                    "source": "white t-shirt",
                }
            ],
        ),
    )

    assert intent.context_items[0].product_type == "tops"


def test_owned_item_source_accepts_one_running_shoe_with_category_and_type_mentions():
    intent = interpret(
        "I own black running shoes; suggest clothing",
        payload(
            constraints={"category": "clothing"},
            request_mode="style",
            owned_items=[
                {
                    "category": "shoes",
                    "product_type": "running",
                    "color": "black",
                    "source": "black running shoes",
                }
            ],
        ),
    )

    assert intent.context_items[0].product_type == "running"


def test_owned_item_revision_prefers_a_supplied_v3_replacement_over_legacy_context():
    prior = payload(
        constraints={"category": "clothing"},
        request_mode="style",
        owned_item={
            "category": "clothing",
            "product_type": "trousers",
            "color": "black",
            "source": "black trousers",
        },
        desired_wear_position="upper",
        needs_clarification=True,
        missing_fields=["category"],
    )

    result = interpret(
        "blue trousers",
        payload(
            constraints={"category": "clothing"},
            request_mode="style",
            owned_items=[
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "blue",
                    "source": "blue trousers",
                }
            ],
            revised_fields=["owned_item", "owned_items"],
            revision_source="blue trousers",
        ),
        {"_intent": prior, "_original_message": "I own black trousers"},
        "category",
    )

    assert result.request_mode == "style"
    assert result.owned_item is None
    assert [item.color for item in result.owned_items] == ["blue"]
    assert result.desired_wear_position == "upper"


@pytest.mark.parametrize(
    ("message", "intent_name"),
    [
        ("Do not open the cart", "help"),
        ("empty cart", "unsupported"),
    ],
)
def test_v3_non_navigation_intent_is_not_rewritten_by_navigation_cues(message, intent_name):
    intent = interpret(message, payload(intent=intent_name, constraints={}))

    assert intent.intent == intent_name
    assert intent.constraints.target is None


def test_live_intent_request_requires_schema_version_ten():
    request = build_intent_request(
        "show shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )

    assert all(
        request.response_schema["$defs"][branch["$ref"].split("/")[-1]]["properties"]["v"]["const"]
        == 10
        for branch in request.response_schema["anyOf"]
    )


def test_context_is_restored_before_api_routes_to_suggestions():
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_catalogue import catalogue
    from agent.tests.test_sessions import parse_sse
    from agent.tests.test_step import home_snapshot

    class Reader:
        async def read(self):
            return catalogue()

    first = payload(
        constraints={},
        request_mode="style",
        needs_clarification=True,
        missing_fields=["category"],
        owned_items=[
            {
                "category": "clothing",
                "product_type": "trousers",
                "color": "brown",
                "source": "بنطلون بني",
            }
        ],
        preferred_colors=["white", "black"],
    )
    client = TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
            llm_client=ScriptedLLMClient(
                [[LLMChunk(text=json.dumps(first))], [LLMChunk(text=json.dumps(payload()))]]
            ),
            catalogue_reader=Reader(),
        )
    )
    session_id = client.post("/sessions").json()["session_id"]
    response = client.post(
        f"/sessions/{session_id}/messages",
        json={
            "text": "عندي بنطلون بني وعايز حاجة مناسبة",
            "snapshot": home_snapshot(),
        },
    )
    task_id = response.json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session_id}/events?once=true").text)
    question = next(event["data"]["action"] for event in events if event["event"] == "action")
    assert question["type"] == "ask_shopper"
    response = client.post(
        f"/sessions/{session_id}/tasks/{task_id}/answers",
        json={
            "question_id": question["action_id"],
            "text": "Shoes",
            "snapshot": home_snapshot(),
        },
    )
    assert response.status_code == 202
    after = parse_sse(
        client.get(f"/sessions/{session_id}/events?after={events[-1]['id']}&once=true").text
    )
    assert not any(event["event"] == "action" for event in after)
    suggestions = next(
        event["data"]["suggestions"] for event in after if event["event"] == "suggestions"
    )
    assert 1 <= len(suggestions) <= 3
    assert all(item["label"] == "styling_suggestion" for item in suggestions)
