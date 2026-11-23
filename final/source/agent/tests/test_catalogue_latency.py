"""Call-count regressions at the real retrieval/advice preparation boundary."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from agent.catalogue_turn import prepare_turn
from agent.planner import ScriptedPlanner
from agent.tests.test_advice import RecordingModel, decision
from agent.tests.test_catalogue_retrieval import Reads, active


def recommendation(message="Purple is my preference; material is unverified."):
    return {
        "kind": "recommend",
        "language": "en",
        "selected_ids": ["p-4"],
        "advice_message": message,
    }


def prepare(model, reads=None, state=None):
    task = SimpleNamespace(
        message="something different pls.. actually open that one?",
        language="en",
        resolved_state=state or {},
        retrieval_budget=None,
        pending_clarification=None,
    )
    return asyncio.run(
        prepare_turn(task, None, ScriptedPlanner().storefront, model, reads or Reads(), active)
    )


def test_search_selection_and_grounded_advice_take_two_model_calls():
    model = RecordingModel(
        {
            "kind": "search",
            "query": {
                "query": "shirt",
                "requirements": [{"field": "feature", "op": "exclude", "value": "leather"}],
            },
        },
        recommendation(),
    )
    result = prepare(model)
    assert len(model.requests) == 2
    assert result.summary == recommendation()["advice_message"]
    assert result.evidence.discovery.suggestions[0].label == "alternative"
    context = json.loads(model.requests[1].messages[0].content)
    assert context["evidence"][-1]["advice_products"][0]["added_at"] == "2026-01-01"
    assert context["evidence"][-1]["advice_products"][0]["wear_position"] == "upper"
    assert context["evidence"][-1]["advice_products"][0]["eligibility"]["label"] == "alternative"


def test_known_product_open_goes_directly_to_interpreter_in_one_call():
    model = RecordingModel(
        decision(
            intent="open_product", constraints={}, product_id="p-4", navigation_source="open that"
        )
    )
    reads = Reads()
    result = prepare(model, reads, {"_known_products": [{"id": "p-4", "name": "Piece"}]})
    assert result.intent.intent == "open_product"
    assert len(model.requests) == 1
    assert model.requests[0].prompt_version.startswith("intent-")
    # The only read is code checking the Shopper's words against catalogue names (ticket 06).
    assert [call.query for call in reads.calls] == [
        "something different pls.. actually open that one?"
    ]


@pytest.mark.parametrize("references", [[], ["p-1"]])
def test_followup_can_change_goal_to_new_search_with_shared_budget(references):
    model = RecordingModel(
        decision(constraints={}, advice_product_ids=references),
        {"kind": "search", "query": {"query": "shirt"}},
        recommendation(),
    )
    result = prepare(model, state={"_known_products": [{"id": "p-1", "name": "Old item"}]})
    assert result.summary == recommendation()["advice_message"]
    assert len(model.requests) == 3


@pytest.mark.parametrize("change", ["price", "availability", "requirements", "revision"])
def test_combined_advice_is_repaired_when_final_refresh_changes_evidence(change):
    class ChangingReads(Reads):
        async def details(self, query):
            result = await super().details(query)
            item = next(p for p in result.products if p.product.id == "p-4")
            if change == "price":
                item.product.price.amount = "30"
            elif change == "availability":
                item.product.available = False
            elif change == "requirements":
                item.requirements[0].status = "violated"
            else:
                item.product_revision = 2
            return result

    model = RecordingModel(
        {
            "kind": "search",
            "query": {
                "query": "shirt",
                "requirements": [{"field": "feature", "op": "exclude", "value": "leather"}],
            },
        },
        recommendation("Old facts must not be published."),
        recommendation("Updated facts; check the changed option."),
    )
    result = prepare(model, ChangingReads())
    assert result.summary == "Updated facts; check the changed option."
    assert len(model.requests) == 3
    if change in {"availability", "requirements"}:
        assert not result.evidence.discovery.suggestions


def test_unselected_comparison_facts_are_refreshed_before_combined_prose_is_published():
    class ChangingComparison(Reads):
        async def details(self, query):
            result = await super().details(query)
            for item in result.products:
                if item.product.id == "p-0":
                    item.product.available = False
            return result

    model = RecordingModel(
        {"kind": "search", "query": {"query": "shirt"}},
        recommendation("The other option is available too."),
        recommendation("The other option is no longer available."),
    )
    result = prepare(model, ChangingComparison())
    assert result.summary == "The other option is no longer available."
    assert len(model.requests) == 3


@pytest.mark.parametrize("search_count", [1, 2])
def test_large_evidence_pool_respects_read_budget_and_discards_unrefreshable_prose(search_count):
    from agent.tests.test_advice import advice
    from agent.tests.test_catalogue_retrieval import candidate

    class FullReads(Reads):
        async def search(self, query):
            result = await super().search(query)
            base = (len(self.calls) - 1) * 10
            result.candidates = [candidate(f"p-{i}") for i in range(base, base + 10)]
            return result

    replies = [{"kind": "search", "query": {"query": "shirt"}}] * search_count
    replies.append(recommendation("Combined comparison."))
    if search_count == 2:
        replies.append(advice("Fresh selected product only.", ["p-4"]))
    model = RecordingModel(*replies)
    reads = FullReads()
    result = prepare(model, reads)
    assert len(reads.calls) == 3
    if search_count == 1:
        assert len(model.requests) == 2
        assert result.summary == "Combined comparison."
        assert len(result.evidence.products) == 10
    else:
        assert len(model.requests) == 4
        assert result.summary == "Fresh selected product only."
        assert [p["id"] for p in result.evidence.products] == ["p-4"]


def test_unknown_product_from_direct_interpreter_is_never_accepted():
    model = RecordingModel(
        *[
            decision(
                intent="open_product",
                constraints={},
                product_id="invented",
                navigation_source="open it",
            )
        ]
        * 3
    )
    result = prepare(model, state={"_known_products": [{"id": "p-4", "name": "Piece"}]})
    assert result.intent.intent != "open_product"
    assert len(model.requests) == 3


def test_combined_flow_uses_real_provider_adapter_within_unchanged_size_guard():
    import httpx

    from agent.llm.openrouter import OpenRouterClient
    from agent.schemas import Snapshot
    from agent.tests.test_openrouter import settings
    from agent.tests.test_step import home_snapshot

    answers = iter(
        [
            {"kind": "search", "query": {"query": "shirt"}},
            recommendation(),
        ]
    )
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "limit": 0.25,
                        "limit_remaining": 0.25,
                        "limit_reset": None,
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(next(answers))},
                    }
                ]
            },
        )

    model = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    task = SimpleNamespace(
        message="shirt pls",
        language="en",
        resolved_state={},
        retrieval_budget=None,
        pending_clarification=None,
    )
    result = asyncio.run(
        prepare_turn(
            task,
            Snapshot.model_validate(home_snapshot()),
            ScriptedPlanner().storefront,
            model,
            Reads(),
            active,
        )
    )
    assert result.summary == recommendation()["advice_message"]
    assert methods == ["GET", "POST", "GET", "POST"]


def test_combined_advice_then_open_publishes_cards_and_guarded_navigation_in_three_calls():
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_sessions import parse_sse
    from agent.tests.test_step import home_snapshot

    model = RecordingModel(
        {"kind": "search", "query": {"query": "shirt"}},
        recommendation(),
        decision(intent="open_product", constraints={}, product_id="p-4", navigation_source="open"),
    )
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=Reads(),
        catalogue_retrieval_enabled=True,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        for text in ["shirt but smthng diffrent", "حلو ده افتحلي صفحة Piece"]:
            assert (
                client.post(
                    f"/sessions/{sid}/messages",
                    json={
                        "text": text,
                        "snapshot": home_snapshot(),
                    },
                ).status_code
                == 202
            )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert any(e["event"] == "suggestions" for e in events)
        actions = [e["data"]["action"] for e in events if e["event"] == "action"]
        assert len(actions) == 1 and actions[0]["type"] == "navigate"
        assert not any(e["event"] == "error" for e in events)
        assert len(model.requests) == 3
