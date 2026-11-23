import asyncio
import contextlib
import json

import pytest

from agent.catalogue_contract import Candidate, DetailsResult, SearchQuery, SearchResult
from agent.catalogue_retrieval import RetrievalBudget, RetrievalExhausted, retrieve_products
from agent.llm.contract import LLMChunk
from agent.planner import ScriptedPlanner
from agent.tests.test_advice import RecordingModel, decision


def candidate(key="p-4", status=None):
    return Candidate.model_validate(
        {
            "product": {
                "id": key,
                "category": "clothing",
                "nameAr": "قطعة",
                "nameEn": "Piece",
                "type": "shirt",
                "price": {"amount": "20", "currency": "EGP"},
                "sizes": ["M"],
                "colors": ["purple"],
                "available": True,
                "addedAt": "2026-01-01",
                "features": [],
                "suitableFor": [],
                "wearPosition": "upper",
                "absent_features": [],
                "absent_uses": [],
            },
            "product_revision": 1,
            "requirements": [] if status is None else [{"index": 0, "status": status}],
        }
    )


class Reads:
    def __init__(self):
        self.calls = []

    async def search(self, query):
        self.calls.append(query)
        return SearchResult(
            v=1,
            catalogue_revision=1,
            candidates=[
                candidate(f"p-{i}", "unknown" if query.requirements else None) for i in range(5)
            ],
            ranking="lexical",
            exact_count=None,
            next_cursor=None,
            truncated=False,
            unverified_requirements=query.unverified_requirements,
        )

    async def details(self, query):
        self.calls.append(query)
        return DetailsResult(
            v=1,
            catalogue_revision=1,
            products=[candidate(k, "unknown" if query.requirements else None) for k in query.ids],
            missing_ids=[],
            unverified_requirements=query.unverified_requirements,
        )


async def active():
    pass


def run(model, reads, **kwargs):
    return retrieve_products(
        "مش لازم الكلام يبقى مظبوط",
        {},
        model,
        reads,
        active,
        storefront=ScriptedPlanner().storefront,
        **kwargs,
    )


def test_model_selects_beyond_three_and_refreshes_selection():
    model = RecordingModel(
        {"kind": "search", "query": SearchQuery(query="purple shirt").model_dump()},
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
    )
    reads = Reads()
    outcome = asyncio.run(run(model, reads))
    assert outcome.selected_ids == ["p-4"]
    assert outcome.budget.decisions == 2 and outcome.budget.reads == 2
    assert reads.calls[-1].ids == ["p-4"]
    assert "catalogue_values" not in model.requests[0].messages[0].content


def test_direct_navigation_has_no_reads_and_preserves_action_validation():
    model = RecordingModel(
        {
            "kind": "finish",
            "intent": decision(intent="navigate", constraints={"target": "cart"}),
            "selected_ids": [],
        }
    )
    reads = Reads()
    outcome = asyncio.run(run(model, reads))
    assert outcome.intent.intent == "navigate" and not reads.calls


def test_execution_routing_uses_original_request_and_existing_intent_validation_without_reads():
    model = RecordingModel(
        {"kind": "execute", "target": "https://evil.example", "cart_quantity": 99},
        decision(intent="navigate", constraints={"target": "cart"}),
    )
    reads = Reads()
    outcome = asyncio.run(run(model, reads))
    assert outcome.intent.intent == "navigate"
    assert outcome.intent.constraints.target == "cart"
    assert not reads.calls
    assert outcome.budget.decisions == 2
    assert "evil.example" not in model.requests[1].messages[0].content
    assert model.requests[1].provider_attempt_limit == 1


def test_execution_routing_cannot_remove_cart_guards_or_expand_decision_budget():
    model = RecordingModel(
        {"kind": "execute"},
        *[
            {
                **decision(intent="cart_edit", constraints={}),
                "cart_operation": "quantity",
                "cart_quantity": 3,
                "cart_quantity_mode": "increase",
                "product_id": "untrusted-id",
            }
        ]
        * 2,
    )
    reads = Reads()
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, reads))
    assert not reads.calls
    assert len(model.requests) == 3


def test_failed_decisions_and_retries_share_three_attempt_budget():
    budget = RetrievalBudget()
    model = RecordingModel({}, {}, {}, {})
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, Reads(), budget=budget))
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, Reads(), budget=budget))
    assert len(model.requests) == 3 and budget.decisions == 3


def test_requirements_cannot_disappear_on_refinement():
    query = SearchQuery(
        query="bag", requirements=[{"field": "feature", "op": "exclude", "value": "leather"}]
    )
    model = RecordingModel(
        {"kind": "search", "query": query.model_dump()},
        {"kind": "search", "query": SearchQuery(query="fabric bag").model_dump()},
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
    )
    reads = Reads()
    outcome = asyncio.run(run(model, reads))
    assert all(call.requirements == query.requirements for call in reads.calls)
    assert outcome.products[0].requirements[0].status == "unknown"


def test_initial_filter_is_preserved_without_requiring_duplicate_model_fields():
    size = {"field": "size", "op": "eq", "value": "43"}
    model = RecordingModel(
        {"kind": "search", "query": {"query": "football", "predicates": [size]}},
        {"kind": "search", "query": {"query": "shoes", "requirements": []}},
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
    )
    reads = Reads()
    result = asyncio.run(run(model, reads))
    assert len(reads.calls) == 3
    assert result.selected_ids == ["p-4"]
    for query in reads.calls:
        assert [p.model_dump() for p in query.requirements] == [size]


def test_freezing_initial_filters_keeps_explicit_exclusions_and_deduplicates():
    size = {"field": "size", "op": "eq", "value": "43"}
    excluded = {"field": "feature", "op": "exclude", "value": "leather"}

    class EmptyReads(Reads):
        async def search(self, query):
            self.calls.append(query)
            return SearchResult(
                v=1,
                catalogue_revision=1,
                candidates=[],
                ranking="lexical",
                exact_count=0,
                truncated=False,
                next_cursor=None,
                unverified_requirements=[],
            )

    model = RecordingModel(
        {
            "kind": "search",
            "query": {"query": "shoes", "predicates": [size], "requirements": [excluded, size]},
        },
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": []},
    )
    reads = EmptyReads()
    asyncio.run(run(model, reads))
    assert [p.model_dump() for p in reads.calls[0].requirements] == [excluded, size]


def test_stop_discards_late_model_completion():
    async def scenario():
        stopped = False

        async def ensure():
            if stopped:
                raise asyncio.CancelledError()

        class Model:
            async def complete(self, request):
                nonlocal stopped
                stopped = True
                yield LLMChunk(
                    text=json.dumps({"kind": "finish", "intent": decision(), "selected_ids": []})
                )

        with pytest.raises(asyncio.CancelledError):
            await retrieve_products(
                "request", {}, Model(), Reads(), ensure, storefront=ScriptedPlanner().storefront
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("provider", ["groq", "nvidia"])
def test_provider_http_retries_cannot_escape_coordinator_budget(provider):
    import httpx

    from agent.llm import load_llm_settings
    from agent.llm.groq import GroqClient
    from agent.llm.nvidia import NvidiaNIMClient

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"error": "fixture failure"})

    settings = load_llm_settings(
        {
            "LLM_PROVIDER": provider,
            "LLM_MODEL": "fixture",
            ("GROQ_API_KEY" if provider == "groq" else "NVIDIA_API_KEY"): "fixture-key",
        }
    )
    client = (GroqClient if provider == "groq" else NvidiaNIMClient)(
        settings, transport=httpx.MockTransport(handler)
    )
    budget = RetrievalBudget()
    for _ in range(3):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(run(client, Reads(), budget=budget))
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(client, Reads(), budget=budget))
    assert len(calls) == budget.decisions == 3


@pytest.mark.parametrize("malformed_first", [False, True])
def test_real_openrouter_adapter_accepts_retrieval_requests_within_existing_cap(malformed_first):
    import httpx

    from agent.catalogue_contract import SearchQuery
    from agent.llm.openrouter import OpenRouterClient
    from agent.tests.test_openrouter import settings

    answers = iter(
        [
            *([{}] if malformed_first else []),
            {
                "kind": "search",
                "query": SearchQuery(
                    query="football", requirements=[{"field": "size", "op": "eq", "value": "43"}]
                ).model_dump(),
            },
            {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
        ]
    )
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        # Replay the observed provider rejection for unresolved union references.
        if schema["oneOf"][0].get("$ref"):
            return httpx.Response(
                400, json={"error": {"message": "reference to undefined schema at oneOf.0"}}
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(next(answers))}}
                ]
            },
        )

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    result = asyncio.run(run(client, Reads()))
    assert result.selected_ids == ["p-4"]
    assert result.budget.decisions == 2 + int(malformed_first) and result.budget.reads == 2
    assert methods == ["GET", "POST"] * (2 + int(malformed_first))


@pytest.mark.parametrize("failure_kind", ["budget", "configuration"])
def test_provider_failure_is_not_retried_as_bad_language_output(failure_kind):
    from agent.llm.config import LLMConfigurationError
    from agent.llm.openrouter import OpenRouterBudgetError

    error_type = OpenRouterBudgetError if failure_kind == "budget" else LLMConfigurationError
    calls = []

    class BudgetBlocked:
        async def complete(self, request):
            calls.append(request)
            raise error_type("Fixture operational failure")
            yield

    with pytest.raises(error_type):
        asyncio.run(run(BudgetBlocked(), Reads()))
    assert len(calls) == 1


def _search(text="walking sneakers"):
    return {"kind": "search", "query": SearchQuery(query=text).model_dump(mode="json")}


def _recommend(*ids):
    return {
        "kind": "recommend",
        "language": "ar",
        "selected_ids": list(ids),
        "advice_message": "مناسب للمشي، والمشي غير مؤكد في بيانات المتجر.",
    }


def test_final_decision_must_recommend_from_retrieved_evidence():
    # Live trace 2026-11-11: two searches found products, the third decision searched
    # again and the turn discarded the evidence. The last decision must conclude.
    model = RecordingModel(_search(), _search("sneakers"), _recommend("p-1"))
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.selected_ids == ["p-1"] and outcome.advice_message
    final = model.requests[2]
    assert "FINAL decision" in final.system
    with pytest.raises(ValueError):
        final.response_validator(json.dumps(_search("more")))
    final.response_validator(json.dumps(_recommend("p-1")))


def test_final_decision_cannot_spend_the_turn_on_another_search():
    reads = Reads()
    model = RecordingModel(_search(), _search("sneakers"), _search("again"))
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, reads))
    assert len(reads.calls) == 2  # the third search was refused, never executed


def test_final_decision_without_evidence_keeps_every_choice():
    model = RecordingModel({}, {}, _search())
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, Reads()))
    assert "FINAL decision" not in model.requests[2].messages[0].content


def test_interpreter_handoff_to_search_does_not_consume_search_budget():
    model = RecordingModel(
        decision(intent="find_products"), _search(), _search("sneakers"), _recommend("p-1")
    )
    outcome = asyncio.run(
        retrieve_products(
            "عايز كوتشي مريح للمشي",
            {"_known_products": [{"id": "shoe-01", "name": "x"}]},
            model,
            Reads(),
            active,
            storefront=ScriptedPlanner().storefront,
        )
    )
    assert outcome.selected_ids == ["p-1"]
    assert len(model.requests) == 4 and outcome.budget.decisions == 3


def test_handoff_refund_is_granted_once_per_turn():
    model = RecordingModel(
        decision(intent="find_products"),
        {"kind": "execute"},
        decision(intent="find_products"),
        _search(),
        _search(),
    )
    with pytest.raises(RetrievalExhausted):
        asyncio.run(
            retrieve_products(
                "x",
                {"_known_products": [{"id": "shoe-01", "name": "x"}]},
                model,
                Reads(),
                active,
                storefront=ScriptedPlanner().storefront,
            )
        )
    assert len(model.requests) == 4


class Misbehaving:
    """Answers with the scripted JSON, or raises the scripted error instead."""

    def __init__(self, *responses):
        self.responses = iter(responses)

    async def complete(self, request):
        del request
        answer = next(self.responses)
        if isinstance(answer, Exception):
            raise answer
        yield LLMChunk(text=json.dumps(answer, ensure_ascii=False))


def _rejections(model, **kwargs):
    budget = RetrievalBudget()
    with contextlib.suppress(RetrievalExhausted):
        asyncio.run(run(model, Reads(), budget=budget, **kwargs))
    return budget


def test_one_invalid_decision_then_a_valid_recommend_records_one_reason():
    model = RecordingModel(_search(), {"kind": "teleport"}, _recommend("p-1"))
    budget = RetrievalBudget()
    outcome = asyncio.run(run(model, Reads(), budget=budget))
    assert outcome.selected_ids == ["p-1"]
    assert budget.rejections == ["decision_schema"]


def test_three_invalid_decisions_record_three_reasons_in_order_and_still_exhaust():
    from agent.llm.contract import LLMInvalidResponseError

    model = Misbehaving({}, _recommend("p-1"), LLMInvalidResponseError("Decision exceeds budget"))
    budget = RetrievalBudget()
    with pytest.raises(RetrievalExhausted):
        asyncio.run(run(model, Reads(), budget=budget))
    assert budget.decisions == 3
    assert budget.rejections == ["decision_schema", "selection_before_read", "model_response"]


def test_a_rejected_final_decision_is_recorded_as_a_final_schema_failure():
    budget = _rejections(RecordingModel(_search(), _search("sneakers"), _search("again")))
    assert budget.rejections == ["final_schema"]
    assert budget.decisions == 3 and budget.reads == 2


@pytest.mark.parametrize(
    ("ids", "code"),
    [(["p-1", "p-1"], "duplicate_ids"), (["p-9"], "ids_not_retrieved")],
)
def test_selected_id_problems_are_told_apart(ids, code):
    model = RecordingModel(_search(), _recommend(*ids), _recommend("p-1"))
    budget = RetrievalBudget()
    asyncio.run(run(model, Reads(), budget=budget))
    assert budget.rejections == [code]


def test_blank_advice_is_recorded():
    blank = {**_recommend("p-1"), "advice_message": "   "}
    model = RecordingModel(_search(), blank, _recommend("p-1"))
    budget = RetrievalBudget()
    asyncio.run(run(model, Reads(), budget=budget))
    assert budget.rejections == ["blank_advice"]


def test_execution_intent_rejections_are_recorded_by_what_was_refused():
    from dataclasses import replace

    storefront = ScriptedPlanner().storefront
    model = RecordingModel(
        {"kind": "execute"},
        decision(intent="navigate", constraints={"target": "cart"}),
        decision(
            intent="open_product", product_id="ghost-1", constraints={}, request_mode="browse"
        ),
    )
    budget = RetrievalBudget()
    with pytest.raises(RetrievalExhausted):
        asyncio.run(
            retrieve_products(
                "x",
                {},
                model,
                Reads(),
                active,
                storefront=replace(storefront, destination_routes={}),
                budget=budget,
            )
        )
    assert budget.decisions == 3
    assert budget.rejections == ["unknown_destination", "unknown_product"]


def test_an_execution_intent_that_is_not_an_intent_is_an_intent_schema_failure():
    budget = _rejections(RecordingModel({"kind": "execute"}, {}, {}))
    assert budget.rejections == ["intent_schema", "intent_schema"]


def test_a_search_decision_to_catalogue_failure_is_not_a_rejection():
    from agent.catalogue_client import CatalogueReadError

    class Down(Reads):
        async def search(self, query):
            raise CatalogueReadError("down")

    budget = RetrievalBudget()
    with pytest.raises(CatalogueReadError):
        asyncio.run(run(RecordingModel(_search()), Down(), budget=budget))
    assert budget.rejections == []


def test_the_reason_never_carries_the_error_text_and_stays_in_the_vocabulary():
    from agent.event_log import REJECTION_CODES

    budget = _rejections(RecordingModel({"kind": "teleport"}, {}, {}))
    assert budget.rejections and set(budget.rejections) <= REJECTION_CODES
    assert all(len(code) < 40 and " " not in code for code in budget.rejections)


def test_rejection_text_is_debug_only():
    from agent.event_log import DebugSwitch, EventLog, MemorySink, bind

    def attempt(switch):
        sink = MemorySink()
        with bind(EventLog(sink, debug=switch)):
            _rejections(RecordingModel({"kind": "teleport"}, {}, {}))
        return sink.records

    assert attempt(None) == []

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        marker = Path(folder) / "debug-logging"
        marker.write_text("")
        records = attempt(DebugSwitch(marker, owner=None))
        assert [r["kind"] for r in records] == ["retrieval_rejection"] * 3
        assert all(r["debug"] is True and r["event"] == "debug" for r in records)
        assert "kind" in records[0]["text"].lower() and len(records[0]["text"]) <= 1000
        off = DebugSwitch(Path(folder) / "missing", owner=None)
        assert attempt(off) == []


def test_a_wrong_version_the_model_copied_does_not_cost_a_decision() -> None:
    from agent.catalogue_retrieval import DECISION, FINAL_PARSE

    final = FINAL_PARSE.validate_json(
        '{"v": 10, "kind": "clarify", "question": "Which size?", "language": "en"}'
    )
    search = DECISION.validate_json(
        '{"v": 10, "kind": "search", "query": {"v": 9, "query": "running shoes"}}'
    )

    assert final.v == 1 and final.kind == "clarify"
    assert search.v == 1 and search.query.v == 1 and search.query.query == "running shoes"


def test_other_decision_fields_stay_strict_after_the_version_is_ignored() -> None:
    import pytest
    from pydantic import ValidationError

    from agent.catalogue_retrieval import DECISION

    with pytest.raises(ValidationError):
        DECISION.validate_json('{"v": 10, "kind": "search", "query": {"query": 5}}')
    with pytest.raises(ValidationError):
        DECISION.validate_json('{"v": 1, "kind": "browse"}')


def _offered_kinds(request):
    from agent.llm.provider_schema import openrouter_response_schema

    schema = openrouter_response_schema(request.response_schema)
    return [branch["properties"]["kind"]["enum"][0] for branch in schema["oneOf"]]


def test_after_a_handoff_to_retrieval_execute_is_no_longer_offered():
    # Live trace 2026-11-20: execute, intent find_products, hand-back, execute again, ...
    model = RecordingModel(
        {"kind": "execute"},
        decision(intent="find_products"),
        _search(),
        _recommend("p-1"),
    )
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.selected_ids == ["p-1"]
    assert len(model.requests) == 4
    assert "execute" in _offered_kinds(model.requests[0])
    for request in model.requests[2:]:
        assert "execute" not in _offered_kinds(request)
    assert sorted(_offered_kinds(model.requests[2])) == [
        "clarify",
        "details",
        "recommend",
        "search",
    ]


def test_an_execute_decision_after_a_handoff_is_an_invalid_decision_with_its_own_reason():
    model = RecordingModel(
        {"kind": "execute"},
        decision(intent="find_products"),
        {"kind": "execute"},
        {"kind": "clarify", "language": "en", "question": "Which bag?"},
    )
    budget = RetrievalBudget()
    outcome = asyncio.run(run(model, Reads(), budget=budget))
    assert outcome.question == "Which bag?"
    assert budget.rejections == ["execute_after_handoff"]


EMPTY_RECOMMEND = {
    "kind": "recommend",
    "language": "ar",
    "selected_ids": [],
    "advice_message": "عذراً، لا أستطيع مسح السلة.",
}


def test_an_empty_recommend_without_evidence_is_routed_to_the_action_interpreter():
    # Live trace 2026-11-20: "امسح السلة كلها" after a search was refused as a recommendation.
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_sessions import parse_sse
    from agent.tests.test_step import home_snapshot

    clear = {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "mutate",
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
        "mutation_kind": "clear_cart",
        "mutation_source": "امسح السلة كلها",
    }
    model = RecordingModel(EMPTY_RECOMMEND, clear)
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=Reads(),
        catalogue_retrieval_enabled=True,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages",
            json={"text": "امسح السلة كلها", "snapshot": home_snapshot()},
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
    # The interpreter ran; the guarded flow starts by opening the cart for the Confirmation.
    assert len(model.requests) == 2
    action = [e["data"]["action"] for e in events if e["event"] == "action"][-1]
    assert (action["type"], action["url"]) == ("navigate", "/cart")
    assert "suggestions" not in [e["event"] for e in events]
    assert "لا أستطيع" not in json.dumps(events, ensure_ascii=False)


def test_the_empty_recommend_is_routed_once_and_costs_no_extra_budget():
    model = RecordingModel(
        EMPTY_RECOMMEND, decision(intent="navigate", constraints={"target": "cart"})
    )
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.intent.intent == "navigate"
    assert outcome.budget.decisions == 2 and len(model.requests) == 2


def test_an_empty_recommend_after_a_handoff_is_accepted_not_routed_again():
    model = RecordingModel(
        {"kind": "execute"},
        decision(intent="find_products"),
        EMPTY_RECOMMEND,
    )
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.intent.intent == "advice" and outcome.selected_ids == []
    assert len(model.requests) == 3


def test_an_empty_recommend_is_routed_at_most_once_per_turn():
    model = RecordingModel(EMPTY_RECOMMEND, decision(intent="find_products"), EMPTY_RECOMMEND)
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.selected_ids == [] and len(model.requests) == 3


def test_a_recommend_with_selected_ids_or_after_reads_is_unchanged():
    model = RecordingModel(_search(), _recommend("p-1"))
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.selected_ids == ["p-1"] and len(model.requests) == 2
    # After a read, an empty recommend is a real (empty) recommendation: no routing.
    model = RecordingModel(_search(), EMPTY_RECOMMEND)
    outcome = asyncio.run(run(model, Reads()))
    assert outcome.selected_ids == [] and len(model.requests) == 2


# Ticket 07 (copilot reliability, B7 / sticky topic): a recommend that carries a cart or
# checkout target is an action request in disguise (capture #57: "امسح السلة كلها" after a
# search came back as recommend with constraints.target "cart", three times).
@pytest.mark.parametrize("target", ["cart", "checkout"])
def test_a_recommend_carrying_a_cart_or_checkout_target_is_refused_for_an_execute_repair(target):
    advice = {**_recommend("p-1"), "constraints": {"target": target}}
    model = RecordingModel(_search(), advice, _recommend("p-1"))
    budget = RetrievalBudget()
    outcome = asyncio.run(run(model, Reads(), budget=budget))
    assert budget.rejections == ["action_in_advice"]
    assert "this is a cart/checkout action: return execute" in model.requests[2].messages[0].content
    assert outcome.selected_ids == ["p-1"]


def test_a_recommend_without_an_action_target_is_not_refused():
    advice = {**_recommend("p-1"), "constraints": {"category": "shoes"}}
    budget = RetrievalBudget()
    asyncio.run(run(RecordingModel(_search(), advice), Reads(), budget=budget))
    assert budget.rejections == []
