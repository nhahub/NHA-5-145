import json

from agent.app import create_app
from agent.catalogue_contract import SearchQuery
from agent.llm import LLMSettings
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel, advice, decision
from agent.tests.test_catalogue_retrieval import Reads
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def test_retrieved_unknown_exclusion_stays_alternative_and_advisor_sees_fresh_facts():
    query = SearchQuery(
        query="something unusual",
        requirements=[{"field": "feature", "op": "exclude", "value": "leather"}],
        unverified_requirements=["washable"],
    )
    model = RecordingModel(
        {"kind": "search", "query": query.model_dump()},
        {"kind": "finish", "intent": decision(constraints={}), "selected_ids": ["p-4"]},
        advice("Material is unverified; this is only an alternative.", ["p-4"]),
    )
    reads = Reads()
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=reads,
        catalogue_retrieval_enabled=True,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        response = client.post(
            f"/sessions/{sid}/messages",
            json={"text": "مش عاوزه جلد وعاوزه تتغسل", "snapshot": home_snapshot()},
        )
        assert response.status_code == 202
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        cards = next(e["data"] for e in events if e["event"] == "suggestions")
        assert cards["exact_count"] is None
        assert cards["suggestions"][0]["id"] == "p-4"
        assert cards["suggestions"][0]["label"] == "alternative"
        assert "washable" in cards["suggestions"][0]["unmet"]
        context = json.loads(model.requests[-1].messages[0].content)
        assert context["products"][0]["price"]["amount"] == "20"
        assert context["products"][0]["eligibility"]["label"] == "alternative"
        assert len(model.requests) == 3


def test_no_category_no_vocabulary_whitelist_and_no_reads_for_navigation():
    model = RecordingModel(
        {
            "kind": "finish",
            "intent": decision(intent="navigate", constraints={"target": "account"}),
            "selected_ids": [],
        }
    )
    reads = Reads()
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=reads,
        catalogue_retrieval_enabled=True,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        client.post(
            f"/sessions/{sid}/messages", json={"text": "my acount plz", "snapshot": home_snapshot()}
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert any(e["event"] == "action" for e in events)
        assert not reads.calls


def test_read_preferences_reach_advisor_without_becoming_factual_requirements():
    model = RecordingModel(
        {
            "kind": "search",
            "query": {"query": "shirt"},
            "subjective_preferences": ["something a bit different"],
        },
        {"kind": "recommend", "language": "en", "selected_ids": ["p-4"]},
        advice("In my opinion, purple could suit your preference.", ["p-4"]),
    )
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
            json={"text": "shirt but a bit different", "snapshot": home_snapshot()},
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert any(e["event"] == "suggestions" for e in events)
        assert not any(e["event"] == "action" for e in events)
        context = json.loads(model.requests[-1].messages[0].content)
        assert context["intent"]["subjective_preferences"] == ["something a bit different"]
        assert context["products"][0]["eligibility"]["label"] == "styling_suggestion"


def test_recommendation_cannot_smuggle_action_authority():
    import pytest
    from pydantic import ValidationError

    from agent.catalogue_retrieval import DECISION

    with pytest.raises(ValidationError):
        DECISION.validate_python(
            {"kind": "recommend", "language": "en", "selected_ids": [], "cart_operation": "add"}
        )
    model = RecordingModel(
        *[
            {
                "kind": "recommend",
                "language": "en",
                "selected_ids": [],
                "constraints": {"target": "cart"},
            }
        ]
        * 3
    )
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
            json={"text": "recommend something", "snapshot": home_snapshot()},
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert not any(e["event"] == "action" for e in events)


def test_known_excluded_product_is_comparison_only_never_a_recommendation():
    from agent.advice import prepare_retrieved_advice
    from agent.catalogue_retrieval import RetrievalBudget, RetrievalOutcome
    from agent.llm.intent import StructuredIntent
    from agent.tests.test_catalogue_retrieval import candidate

    query = SearchQuery(
        query="bag", requirements=[{"field": "feature", "op": "exclude", "value": "leather"}]
    )
    outcome = RetrievalOutcome(
        StructuredIntent.model_validate(decision()),
        ["p-4"],
        [candidate(status="violated")],
        RetrievalBudget(),
        query.requirements,
    )
    evidence = prepare_retrieved_advice(outcome)
    assert not evidence.discovery.suggestions
    assert evidence.products[0]["eligibility"]["label"] == "comparison_only"


def test_exhausted_budget_ends_with_question_not_an_unusable_retry():
    model = RecordingModel({}, {}, {})
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
            json={"text": "anything messy", "snapshot": home_snapshot()},
        )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert events[-1]["event"] == "done"
        assert not any(e["event"] == "error" for e in events)
        assert len(model.requests) == 3


def test_comparison_only_ids_survive_for_the_next_turn():
    model = RecordingModel(
        {
            "kind": "details",
            "query": {"v": 1, "ids": ["p-4"], "requirements": [], "unverified_requirements": []},
        },
        {
            "kind": "finish",
            "intent": decision(constraints={}, advice_product_ids=["p-4"]),
            "selected_ids": [],
        },
        advice("A comparison, no card.", ["p-4"]),
        decision(
            intent="open_product", constraints={}, product_id="p-4", navigation_source="open it"
        ),
    )
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=Reads(),
        catalogue_retrieval_enabled=True,
    )
    with TestClient(app) as client:
        sid = client.post("/sessions").json()["session_id"]
        for text in ["compare it", "open the Piece قطعة"]:
            client.post(
                f"/sessions/{sid}/messages", json={"text": text, "snapshot": home_snapshot()}
            )
        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert any(
            e["event"] == "action" and e["data"]["action"]["type"] == "navigate" for e in events
        )
        assert any(
            p["id"] == "p-4"
            for p in json.loads(model.requests[-1].system.split("\n", 1)[0].split(": ", 1)[1])[
                "known_products"
            ]
        )


def test_revoked_shopper_during_retrieval_cannot_reach_another_model_call():
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from agent.tests.http_client import authorize_async

    async def scenario():
        class RevokingReads(Reads):
            async def search(self, query):
                result = await super().search(query)
                app.state.storefront_service.revoked = True
                return result

        model = RecordingModel({"kind": "search", "query": SearchQuery(query="bag").model_dump()})
        app = create_app(
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=model,
            catalogue_client=RevokingReads(),
            catalogue_retrieval_enabled=True,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await authorize_async(client, app)
            sid = (await client.post("/sessions")).json()["session_id"]
            await client.post(
                f"/sessions/{sid}/messages", json={"text": "any bag", "snapshot": home_snapshot()}
            )
            assert len(model.requests) == 1

    asyncio.run(scenario())


def test_changed_snapshot_during_decision_pauses_without_publishing():
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from agent.llm import LLMChunk
    from agent.planner import ScriptedPlanner
    from agent.schemas import Snapshot
    from agent.sessions import SessionStore
    from agent.tests.http_client import authorize_async

    async def scenario():
        sessions = SessionStore(ScriptedPlanner())

        class ChangingModel:
            async def complete(self, request):
                sessions.get(sid).last_snapshot = Snapshot.model_validate(
                    {**home_snapshot(), "title": "changed"}
                )
                yield LLMChunk(
                    text=json.dumps({"kind": "finish", "intent": decision(), "selected_ids": []})
                )

        app = create_app(
            session_store=sessions,
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=ChangingModel(),
            catalogue_client=Reads(),
            catalogue_retrieval_enabled=True,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await authorize_async(client, app)
            sid = (await client.post("/sessions")).json()["session_id"]
            await client.post(
                f"/sessions/{sid}/messages", json={"text": "any bag", "snapshot": home_snapshot()}
            )
            task = sessions.get(sid).active_task
            assert task.status == "paused" and task.model_call_id is None
            assert not any(
                e.event in {"action", "suggestions", "done"} for e in sessions.get(sid).events
            )

    asyncio.run(scenario())
