from agent.catalogue import (
    CatalogueMoney,
    CatalogueSnapshot,
    DiscoveryResult,
    Suggestion,
    evaluate_catalogue,
)
from agent.llm.intent import StructuredIntent
from agent.planner import ScriptedPlanner
from agent.schemas import ActionResult, Snapshot
from agent.sessions import SessionStore
from agent.tests.test_step import home_snapshot


def catalogue() -> CatalogueSnapshot:
    return CatalogueSnapshot.model_validate(
        {
            "v": 1,
            "currency": "EGP",
            "products": [
                {
                    "id": "formal-brown",
                    "category": "shoes",
                    "name_ar": "رسمي بني",
                    "name_en": "Brown Formal",
                    "product_type": "casual",
                    "price": {"amount": "1550", "currency": "EGP"},
                    "sizes": ["43"],
                    "colors": ["brown"],
                    "available": True,
                    "added_at": "2026-03-12",
                    "features": ["leather"],
                    "suitable_for": ["formal_events"],
                    "wear_position": None,
                },
                {
                    "id": "black-leather",
                    "category": "shoes",
                    "name_ar": "جلد أسود",
                    "name_en": "Black Leather",
                    "product_type": "casual",
                    "price": {"amount": "1350", "currency": "EGP"},
                    "sizes": ["43"],
                    "colors": ["black"],
                    "available": True,
                    "added_at": "2026-03-02",
                    "features": ["leather"],
                    "suitable_for": ["everyday_wear"],
                    "wear_position": None,
                },
                {
                    "id": "road-runner",
                    "category": "shoes",
                    "name_ar": "جري طريق",
                    "name_en": "Road Runner",
                    "product_type": "running",
                    "price": {"amount": "1750", "currency": "EGP"},
                    "sizes": ["43"],
                    "colors": ["white"],
                    "available": True,
                    "added_at": "2026-01-08",
                    "features": ["cushioned"],
                    "suitable_for": ["daily_workouts", "road_running"],
                    "wear_position": None,
                },
                {
                    "id": "sold-out-runner",
                    "category": "shoes",
                    "name_ar": "غير متاح",
                    "name_en": "Sold Out Runner",
                    "product_type": "running",
                    "price": {"amount": "1200", "currency": "EGP"},
                    "sizes": ["43"],
                    "colors": ["black"],
                    "available": False,
                    "added_at": "2026-02-11",
                    "features": [],
                    "suitable_for": ["daily_workouts", "road_running"],
                    "wear_position": None,
                },
                {
                    "id": "white-shirt",
                    "category": "clothing",
                    "name_ar": "قميص أبيض",
                    "name_en": "White Shirt",
                    "product_type": "shirts",
                    "price": {"amount": "650", "currency": "EGP"},
                    "sizes": ["M"],
                    "colors": ["white"],
                    "available": True,
                    "added_at": "2026-02-15",
                    "features": ["lightweight"],
                    "suitable_for": ["hot_weather"],
                    "wear_position": "upper",
                },
            ],
        }
    )


def test_wedding_request_reports_zero_exact_and_named_alternatives() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "franco_arabic",
            "intent": "find_products",
            "constraints": {"category": "shoes", "color": "black"},
            "missing_fields": [],
            "needs_clarification": False,
            "catalogue_requirements": [
                {"kind": "feature", "value": "leather", "source": "leather"},
                {"kind": "suitable_for", "value": "formal_events", "source": "wedding"},
            ],
            "price_preference": {"value": "lower_price", "source": "maykoonsh ghaly"},
        }
    )
    result = evaluate_catalogue(catalogue(), intent)
    assert result.exact_count == 0
    assert [item.id for item in result.suggestions] == ["black-leather", "formal-brown"]
    assert all(item.label == "alternative" for item in result.suggestions)
    assert result.suggestions[0].unmet == ("مناسب للمناسبات الرسمية غير موثق لهذا المنتج",)
    assert result.suggestions[1].unmet == ("اللون أسود غير متاح لهذا المنتج",)
    assert "جلد" in result.suggestions[0].reason


def test_running_suitability_and_size_are_verified_not_inferred_from_type() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "mixed",
            "intent": "find_products",
            "constraints": {"category": "shoes", "product_type": "running", "size": "43"},
            "missing_fields": [],
            "needs_clarification": False,
            "catalogue_requirements": [
                {"kind": "suitable_for", "value": "daily_workouts", "source": "workouts"},
                {"kind": "suitable_for", "value": "road_running", "source": "الجري في الشارع"},
            ],
        }
    )
    result = evaluate_catalogue(catalogue(), intent)
    assert result.exact_count == 1
    assert result.suggestions[0].id == "road-runner"
    assert result.suggestions[0].label == "exact_match"
    assert all(item.id != "sold-out-runner" for item in result.suggestions)


def test_owned_black_trousers_produce_only_available_upper_body_styling() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "find_products",
            "constraints": {"category": "clothing"},
            "missing_fields": [],
            "needs_clarification": False,
            "owned_item": {
                "category": "clothing",
                "product_type": "trousers",
                "color": "black",
                "source": "بنطلون اسود",
            },
            "desired_wear_position": "upper",
        }
    )
    result = evaluate_catalogue(catalogue(), intent)
    assert result.exact_count == 0
    assert [item.id for item in result.suggestions] == ["white-shirt"]
    assert result.suggestions[0].label == "styling_suggestion"


def test_recommendation_explains_verified_budget_and_never_claims_inferred_quality() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {
                "category": "shoes",
                "product_type": "running",
                "max_price": {"amount": "2000", "currency": "EGP"},
            },
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "recommend",
            "subjective_preferences": ["best"],
        }
    )
    result = evaluate_catalogue(catalogue(), intent)
    assert result.exact_count == 1
    item = result.suggestions[0]
    assert item.id == "road-runner"
    assert "1750 EGP" in item.reason
    assert "2000 EGP" in item.reason
    assert "running shoe" in item.reason
    assert "comfortable" not in item.reason
    assert "best" not in item.reason


def test_style_request_ranks_footwear_by_soft_colour_preference() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "shoes"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "owned_items": [
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "black",
                    "source": "black trousers",
                }
            ],
            "preferred_colors": ["brown"],
            "desired_wear_position": "footwear",
        }
    )

    result = evaluate_catalogue(catalogue(), intent)

    assert [item.id for item in result.suggestions[:2]] == ["formal-brown", "black-leather"]
    assert len(result.suggestions) == 3
    assert all(item.label == "styling_suggestion" for item in result.suggestions)
    assert "optional colour suggestion" in result.suggestions[0].reason


def test_style_reason_does_not_invent_a_colour_for_a_catalogue_product_without_one() -> None:
    products = catalogue().products
    no_colour_top = products[-1].model_copy(update={"colors": []})
    snapshot = CatalogueSnapshot(v=1, currency="EGP", products=[*products[:-1], no_colour_top])
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "clothing"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "owned_items": [
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "black",
                    "source": "black trousers",
                }
            ],
            "desired_wear_position": "upper",
        }
    )

    result = evaluate_catalogue(snapshot, intent)

    assert result.suggestions[0].label == "styling_suggestion"
    assert "colour is unverified" in result.suggestions[0].reason


def test_arabic_footwear_styling_reason_uses_localized_product_and_colour_labels() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "find_products",
            "constraints": {"category": "shoes"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "owned_items": [
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "brown",
                    "source": "بنطلون بني",
                }
            ],
            "desired_wear_position": "footwear",
        }
    )

    result = evaluate_catalogue(catalogue(), intent)

    assert result.suggestions[0].reason.startswith("حذاء متاح باللون أبيض")


def test_style_alternative_keeps_each_unmet_explicit_requirement() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "clothing", "size": "XL"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "owned_items": [
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "black",
                    "source": "black trousers",
                }
            ],
            "desired_wear_position": "upper",
            "catalogue_requirements": [
                {"kind": "suitable_for", "value": "formal_events", "source": "wedding"}
            ],
        }
    )

    result = evaluate_catalogue(catalogue(), intent)

    assert result.exact_count == 0
    assert result.suggestions[0].label == "alternative"
    assert result.suggestions[0].unmet == (
        "size XL is unavailable",
        "suitable for formal events is not verified for this product",
    )


def test_style_cheapest_sort_keeps_cheaper_repeated_colours_before_diversifying() -> None:
    products = catalogue().products
    white_shoe = products[-1].model_copy(
        update={
            "id": "white-shoe-one",
            "category": "shoes",
            "price": CatalogueMoney(amount="500", currency="EGP"),
            "wear_position": None,
        }
    )
    another_white_shoe = white_shoe.model_copy(
        update={"id": "white-shoe-two", "price": CatalogueMoney(amount="600", currency="EGP")}
    )
    snapshot = CatalogueSnapshot(
        v=1, currency="EGP", products=[*products, white_shoe, another_white_shoe]
    )
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "shoes", "sort": "cheapest"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "desired_wear_position": "footwear",
        }
    )

    result = evaluate_catalogue(snapshot, intent)

    assert [item.id for item in result.suggestions] == [
        "white-shoe-one",
        "white-shoe-two",
        "black-leather",
    ]


def test_style_requires_a_complete_requested_category() -> None:
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "desired_wear_position": "upper",
        }
    )

    try:
        evaluate_catalogue(catalogue(), intent)
    except ValueError as error:
        assert str(error) == "Discovery category is unresolved"
    else:
        raise AssertionError(
            "Style discovery without a category must not select catalogue products"
        )


def test_clarification_retains_original_request_and_structured_outfit_context() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    original = "I own brown trousers and want something under 2000 EGP"
    task = sessions.begin_interpretation(
        session.session_id, original, Snapshot.model_validate(home_snapshot())
    )
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"max_price": {"amount": "2000", "currency": "EGP"}},
            "missing_fields": ["category"],
            "needs_clarification": True,
            "request_mode": "style",
            "owned_items": [
                {
                    "category": "clothing",
                    "product_type": "trousers",
                    "color": "brown",
                    "source": "brown trousers",
                }
            ],
            "preferred_colors": ["white"],
        }
    )
    call_id = task.model_call_id
    assert call_id is not None

    finished = sessions.finish_interpretation(session.session_id, task.task_id, call_id, intent)

    assert finished is task
    assert task.resolved_state["max_price"] == {"amount": "2000", "currency": "EGP"}
    assert task.resolved_state["_original_message"] == original
    assert task.resolved_state["_answers"] == []
    assert task.resolved_state["_intent"]["owned_items"][0]["color"] == "brown"

    answer = sessions.begin_answer_interpretation(
        session.session_id,
        task.task_id,
        task.action.action_id,
        "Clothing",
        Snapshot.model_validate(home_snapshot()),
        None,
    )
    assert answer.message == "Clothing"
    assert answer.resolved_state["_original_message"] == original
    assert answer.resolved_state["_answers"] == ["Clothing"]


def test_catalogue_completion_does_not_call_alternatives_styling_suggestions() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    task = sessions.begin_interpretation(
        session.session_id, "Find a top", Snapshot.model_validate(home_snapshot())
    )
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "clothing"},
            "missing_fields": [],
            "needs_clarification": False,
            "request_mode": "style",
            "desired_wear_position": "upper",
        }
    )
    call_id = task.model_call_id
    assert call_id is not None
    result = DiscoveryResult(
        exact_count=0,
        suggestions=(
            Suggestion(
                id="not-a-match",
                label="alternative",
                name="Near match",
                price="650",
                currency="EGP",
                reason="Verified catalogue facts.",
                unmet=("size XL is unavailable",),
            ),
        ),
    )

    sessions.finish_catalogue_interpretation(
        session.session_id, task.task_id, call_id, intent, result
    )

    done = next(event for event in session.events if event.event == "done")
    assert (
        done.data["summary"]
        == "No product meets every requirement. These are labelled alternatives."
    )


def test_clarification_answers_are_bounded_to_the_latest_eight_entries() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    task = sessions.begin_interpretation(
        session.session_id, "Find something", Snapshot.model_validate(home_snapshot())
    )
    clarification = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "clothing"},
            "missing_fields": ["size"],
            "needs_clarification": True,
        }
    )
    call_id = task.model_call_id
    assert call_id is not None
    sessions.finish_interpretation(session.session_id, task.task_id, call_id, clarification)
    assert task.action is not None
    task.resolved_state["_answers"] = [f"answer-{index}" for index in range(8)]

    sessions.begin_answer_interpretation(
        session.session_id,
        task.task_id,
        task.action.action_id,
        "answer-8",
        Snapshot.model_validate(home_snapshot()),
        None,
    )

    assert task.resolved_state["_answers"] == [f"answer-{index}" for index in range(1, 9)]


def test_conflicting_price_clarification_retains_the_original_product_context() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    original = "Find running shoes between 2000 and 1000 EGP"
    task = sessions.begin_interpretation(
        session.session_id, original, Snapshot.model_validate(home_snapshot())
    )
    conflicting = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {
                "category": "shoes",
                "product_type": "running",
                "min_price": {"amount": "2000", "currency": "EGP"},
                "max_price": {"amount": "1000", "currency": "EGP"},
            },
            "missing_fields": [],
            "conflicting_fields": ["min_price", "max_price"],
            "needs_clarification": True,
        }
    )
    call_id = task.model_call_id
    assert call_id is not None

    sessions.finish_interpretation(session.session_id, task.task_id, call_id, conflicting)

    assert task.pending_clarification == "min_price"
    assert task.resolved_state["_original_message"] == original
    assert task.resolved_state["_intent"]["constraints"]["product_type"] == "running"


def test_completed_navigation_supplies_one_previous_target_to_the_next_interpretation() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    home = Snapshot.model_validate(home_snapshot())
    task = sessions.begin_interpretation(session.session_id, "Open my cart", home)
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "navigate",
            "constraints": {"target": "cart"},
            "missing_fields": [],
            "needs_clarification": False,
            "navigation_source": "Open my cart",
        }
    )
    call_id = task.model_call_id
    assert call_id is not None
    sessions.finish_interpretation(session.session_id, task.task_id, call_id, intent)
    assert task.action is not None
    sessions.accept_result(
        session.session_id,
        ActionResult.model_validate(
            {
                "v": 1,
                "task_id": task.task_id,
                "action_id": task.action.action_id,
                "sequence_number": task.action.sequence_number,
                "status": "navigated",
                "snapshot": {**home_snapshot(), "url": "http://localhost:4000/cart"},
            }
        ),
    )

    followup = sessions.begin_interpretation(session.session_id, "Take me there", home)

    assert followup.resolved_state["_previous_target"] == "cart"
    assert session.last_followup_target is None


def test_stopped_task_cannot_publish_late_catalogue_suggestions() -> None:
    sessions = SessionStore(ScriptedPlanner())
    session = sessions.create()
    task = sessions.begin_interpretation(
        session.session_id,
        "Find shoes for daily workouts",
        Snapshot.model_validate(home_snapshot()),
    )
    intent = StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "shoes"},
            "missing_fields": [],
            "needs_clarification": False,
            "catalogue_requirements": [
                {"kind": "suitable_for", "value": "daily_workouts", "source": "daily workouts"}
            ],
        }
    )
    result = evaluate_catalogue(catalogue(), intent)
    call_id = task.model_call_id
    assert call_id is not None
    sessions.stop(session.session_id)
    assert (
        sessions.finish_catalogue_interpretation(
            session.session_id, task.task_id, call_id, intent, result
        )
        is None
    )
    assert not any(event.event == "suggestions" for event in session.events)
