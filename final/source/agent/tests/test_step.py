from agent.app import create_app
from agent.planner import ActionIdentity, ScriptedPlanner
from agent.schemas import Snapshot, parse_action
from agent.storefront import parse_storefront_definition
from agent.tests.http_client import TestClient
from agent.tests.test_storefront import valid_definition

app = create_app(evaluation=True)


def home_snapshot() -> dict[str, object]:
    return {
        "v": 1,
        "url": "http://localhost:4000/",
        "title": "المتجر التجريبي",
        "lang": "ar",
        "viewport": {"w": 390, "h": 844, "scrollY": 0},
        "truncated": False,
        "elements": [
            {
                "id": 1,
                "role": "link",
                "name": "الأحذية",
                "href": "/c/shoes",
                "visible": True,
            }
        ],
    }


def test_step_turns_arabic_running_shoes_request_into_one_filter_action() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "عاوز كوتشي للجري بأقل من ٢٠٠٠",
            "snapshot": home_snapshot(),
        },
    )

    assert response.status_code == 200
    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/shoes?type=running&max_price=2000"
    assert action.task_id
    assert action.action_id
    assert action.sequence_number == 1
    assert action.narration == "هفلتر لك أحذية الجري بحد أقصى ٢٠٠٠ جنيه."


def test_step_turns_english_running_shoes_request_into_one_filter_action() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Show me running shoes under 2000 EGP",
            "snapshot": home_snapshot(),
        },
    )

    assert response.status_code == 200
    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/shoes?type=running&max_price=2000"
    assert action.narration == "I'll filter running shoes to a maximum of EGP 2000."


def test_step_understands_franco_arabic_discovery_constraints() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "3ayez kootshi running ta7t 2,000 EGP",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/shoes?type=running&max_price=2000"


def test_step_combines_mixed_language_attributes_and_sorting() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "عاوز black running shoes مقاس 42 تحت 2500 EGP والأرخص",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == ("/c/shoes?type=running&max_price=2500&size=42&color=black&sort=cheapest")


def test_step_filters_unavailable_bags_without_hiding_them() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Show unavailable bags newest first",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/bags?availability=unavailable&sort=newest"


def test_step_asks_when_the_category_is_ambiguous() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Show me something under 1000 EGP",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "ask_shopper"
    assert action.options == ["Shoes", "Clothing", "Bags", "Electronics"]


def test_step_preserves_exact_decimal_egp_amounts() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Show me bags under 1500.50 EGP",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/bags?max_price=1500.50"


def test_step_preserves_an_explicit_catalogue_search_term() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": 'Search bags for "Nile"',
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/bags?q=Nile"


def test_planner_uses_storefront_definition_vocabulary_instead_of_code_constants() -> None:
    payload = valid_definition()
    vocabulary = payload["vocabulary"]
    assert isinstance(vocabulary, dict)
    vocabulary["categories"] = {
        "shoes": ["trainers"],
        "clothing": ["garments"],
        "bags": ["satchels"],
        "electronics": ["devices"],
    }
    vocabulary["types"] = {"running": ["sprinting"]}
    vocabulary["colors"] = {"black": ["onyx"]}
    vocabulary["availability"] = {
        "available": ["in-stock"],
        "unavailable": ["soldout"],
    }
    vocabulary["sort"] = {"cheapest": ["budget-first"], "newest": ["recent-first"]}
    planner = ScriptedPlanner(parse_storefront_definition(payload))

    action = planner.plan(
        "Show soldout onyx trainers for sprinting recent-first",
        snapshot=Snapshot.model_validate(home_snapshot()),
        identity=ActionIdentity("task-1", "action-1", 1),
    )

    assert action.type == "navigate"
    assert action.url == ("/c/shoes?type=running&color=black&availability=unavailable&sort=newest")


def test_step_supports_an_inclusive_minimum_price() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Show me running shoes at least 1500 EGP",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/shoes?type=running&min_price=1500"


def test_step_extracts_an_unquoted_known_product_search() -> None:
    response = TestClient(app).post(
        "/step",
        json={
            "message": "Find Nile bags",
            "snapshot": home_snapshot(),
        },
    )

    action = parse_action(response.json())
    assert action.type == "navigate"
    assert action.url == "/c/bags?q=Nile"
