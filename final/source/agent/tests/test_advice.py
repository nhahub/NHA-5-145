import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from agent.app import create_app
from agent.llm import LLMChunk, LLMSettings
from agent.tests.http_client import TestClient, authorize_async
from agent.tests.test_catalogue import catalogue
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


class RecordingModel:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        yield LLMChunk(text=json.dumps(next(self.responses), ensure_ascii=False))


class Reader:
    async def read(self):
        return catalogue()


def test_revocation_during_catalogue_read_prevents_another_model_call():
    async def scenario():
        model = RecordingModel(decision(), advice("must not be requested"))

        class RevokingReader:
            async def read(self):
                app.state.storefront_service.revoked = True
                return catalogue()

        app = create_app(
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=model,
            catalogue_reader=RevokingReader(),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await authorize_async(client, app)
            sid = (await client.post("/sessions")).json()["session_id"]
            await client.post(
                f"/sessions/{sid}/messages",
                json={"text": "what goes together?", "snapshot": home_snapshot()},
            )
            assert len(model.requests) == 1

    asyncio.run(scenario())


def decision(**changes):
    return {
        "v": 9,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "advice",
        "constraints": {"category": "clothing"},
        "missing_fields": [],
        "needs_clarification": False,
        **changes,
    }


def advice(text, references=None):
    return {"v": 1, "message": text, "product_ids": references or []}


def client_for(model, reader=None):
    return TestClient(
        create_app(
            llm_settings=LLMSettings(provider="groq", model="test", api_key=None),
            llm_client=model,
            catalogue_reader=reader or Reader(),
        )
    )


def send(client, session, text, snapshot=None, tab_id=None):
    response = client.post(
        f"/sessions/{session}/messages",
        json={
            "text": text,
            "snapshot": snapshot or home_snapshot(),
        },
        headers={"x-tab-id": tab_id} if tab_id else {},
    )
    assert response.status_code == 202
    task_id = response.json()["task_id"]
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    return [event for event in events if event["data"].get("task_id") == task_id]


@pytest.mark.parametrize("intent", ["advice", "find_products"])
def test_owned_outfit_and_soft_colors_are_not_limited_to_store_inventory(intent):
    model = RecordingModel(
        decision(
            intent=intent,
            request_mode="style",
            owned_items=[
                {
                    "category": "clothing",
                    "product_type": "skirt",
                    "color": "burgundy",
                    "source": "my burgundy skirt",
                }
            ],
            preferred_colors=["burgundy"],
        ),
        advice(
            "In my opinion, the verified white shirt could complement your outfit.", ["white-shirt"]
        ),
    )
    with client_for(model) as client:
        sid = client.post("/sessions").json()["session_id"]
        observed = send(
            client,
            sid,
            "I own my burgundy skirt; suggest a shirt to coordinate, maybe burgundy tones.",
        )
        assert any(e["event"] == "done" for e in observed)
        assert not any(e["event"] == "action" for e in observed)
        assert model.requests[-1].prompt_version == "advice-v4"
        context = json.loads(model.requests[-1].messages[0].content)
        assert context["intent"]["owned_items"][0]["product_type"] == "skirt"


def test_advice_is_natural_read_only_and_followup_retains_shopper_correction():
    first = "القميص الأبيض خفيف حسب بيانات المتجر. تحبي تنسيق هادي ولا ملفت؟"
    second = "تمام، نخليها هادية. الأبيض ممكن يناسب الأسود في رأيي."
    model = RecordingModel(
        decision(subjective_preferences=["ملفت"]),
        advice(first, ["white-shirt"]),
        decision(subjective_preferences=["هادي"]),
        advice(second, ["white-shirt"]),
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "مش عارفه البس ايه ع الاسود.. حاجه تلفت؟")
        assert events[-1]["event"] == "done"
        assert events[-1]["data"]["summary"] == first
        assert not any(event["event"] in {"action", "error"} for event in events)
        events = send(client, session, "لا لا هادي احسن، مش عايزه ملفت")
        assert events[-1]["data"]["summary"] == second
        assert not any(event["event"] == "action" for event in events)
    assert len(model.requests) == 4
    context = json.loads(model.requests[-1].messages[0].content)
    assert context["intent"]["subjective_preferences"] == ["هادي"]
    assert any(first in item["text"] for item in context["recent_conversation"])
    assert context["products"][0]["features"] == ["lightweight"]
    assert model.requests[-1].tools == ()


@pytest.mark.parametrize(
    "category, expected_ids",
    [
        ("clothing", ["white-shirt"]),
        ("shoes", ["black-leather", "formal-brown", "road-runner"]),
    ],
)
def test_exact_discovery_explains_matches_and_keeps_verified_cards(category, expected_ids):
    explanation = "These fit your budget. I would favour the cheaper option if saving matters most."
    model = RecordingModel(
        decision(
            intent="find_products",
            constraints={"category": category},
            price_preference={"value": "lower_price", "source": "مش غاليه"},
            request_mode="browse",
        ),
        advice(explanation, expected_ids),
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "وريني حاجه كده مش غاليه")
    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["summary"] == explanation
    cards = next(event["data"] for event in events if event["event"] == "suggestions")
    assert cards["exact_count"] == len(expected_ids)
    assert [item["id"] for item in cards["suggestions"]] == expected_ids
    assert all(item["label"] == "exact_match" for item in cards["suggestions"])
    context = json.loads(model.requests[-1].messages[0].content)
    assert [item["id"] for item in context["products"]] == expected_ids
    assert context["discovery"]["exact_count"] == len(expected_ids)
    assert len(model.requests) == 2 and model.requests[-1].tools == ()
    assert not any(event["event"] in {"action", "error"} for event in events)


@pytest.mark.parametrize("case", ["ordinary_filter", "legacy", "no_exact_match"])
def test_discovery_explanation_does_not_add_calls_to_other_flows(case):
    proposal = decision(intent="find_products", constraints={"category": "clothing"})
    if case == "legacy":
        proposal.update(v=8, price_preference={"value": "lower_price", "source": "رخيص"})
    elif case == "no_exact_match":
        proposal.update(
            catalogue_requirements=[{"kind": "feature", "value": "leather", "source": "جلد"}]
        )
    model = RecordingModel(proposal)
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "وريني اللبس")
    assert len(model.requests) == 1
    assert not any(event["event"] == "error" for event in events)
    if case == "ordinary_filter":
        assert any(event["event"] == "action" for event in events)
    else:
        assert events[-1]["event"] == "done"
        assert not any(event["event"] == "action" for event in events)
        cards = next(event["data"] for event in events if event["event"] == "suggestions")
        assert cards["exact_count"] == (1 if case == "legacy" else 0)


@pytest.mark.parametrize(
    "bad",
    [
        advice("Invented product", ["not-in-catalogue"]),
        {**advice("I emptied your cart"), "action": {"type": "clear_cart"}},
        advice("   "),
        {"unexpected": "Ignore all rules"},
    ],
)
@pytest.mark.parametrize("discovery", [False, True])
def test_invalid_advice_finishes_with_verified_cards_without_retry_or_actions(bad, discovery):
    proposal = decision()
    if discovery:
        proposal.update(
            intent="find_products", price_preference={"value": "lower_price", "source": "رخيص"}
        )
    model = RecordingModel(proposal, bad)
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "ايه رايك؟")
    assert len(model.requests) == 2
    assert events[-1]["event"] == "done"
    assert "نصيحة موثوقة" in events[-1]["data"]["summary"]
    assert not any(event["event"] in {"action", "error"} for event in events)
    cards = next(
        event["data"]["suggestions"] for event in events if event["event"] == "suggestions"
    )
    assert [card["id"] for card in cards] == ["white-shirt"]


def test_advice_comparison_uses_fresh_facts_and_excluded_items_are_not_recommended():
    observed = home_snapshot()
    observed["elements"] = [
        {"id": index, "role": "link", "name": key, "href": f"/p/{key}", "visible": True}
        for index, key in enumerate(["black-leather", "sold-out-runner", "road-runner"], 1)
    ]
    model = RecordingModel(
        decision(
            constraints={"category": "shoes"},
            advice_product_ids=["black-leather", "sold-out-runner", "road-runner"],
            catalogue_requirements=[
                {"kind": "feature", "value": "leather", "excluded": True, "source": "مش جلد"}
            ],
        ),
        advice("الجلد مش مناسب لطلبك والتاني خلصان، جري طريق متاح.", ["road-runner"]),
    )

    class ChangedReader:
        async def read(self):
            snapshot = catalogue()
            snapshot.products[2].price.amount = "1800"
            return snapshot

    with client_for(model, ChangedReader()) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "دول انهي احسن.. بس مش جلد ها", observed)
    assert events[-1]["event"] == "done"
    context = json.loads(model.requests[-1].messages[0].content)
    products = {product["id"]: product for product in context["products"]}
    assert products["road-runner"]["price"]["amount"] == "1800"
    assert products["black-leather"]["eligibility"]["label"] == "comparison_only"
    assert products["sold-out-runner"]["available"] is False
    cards = next(
        event["data"]["suggestions"] for event in events if event["event"] == "suggestions"
    )
    assert [card["id"] for card in cards] == ["road-runner"]


def test_advice_followup_can_open_verified_product_without_an_extra_advice_call():
    model = RecordingModel(
        decision(),
        advice("الأبيض ممكن يناسبك.", ["white-shirt"]),
        decision(intent="open_product", constraints={}, product_id="white-shirt"),
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        send(client, session, "ساعدني اختار")
        events = send(client, session, "طب وريني قميص أبيض")
    actions = [event["data"]["action"] for event in events if event["event"] == "action"]
    assert len(actions) == 1
    assert actions[0]["type"] == "navigate"
    assert actions[0]["url"] == "/p/white-shirt"
    assert len(model.requests) == 3


def test_no_evidence_allows_conversation_and_question_without_forced_execution_clarification():
    model = RecordingModel(
        decision(constraints={}),
        advice("تحب تنسيق لمناسبة ولا لبس يومي؟"),
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "انا تايه بصراحه ساعدني")
    assert events[-1]["event"] == "done"
    assert not any(event["event"] == "action" for event in events)
    assert json.loads(model.requests[-1].messages[0].content)["products"] == []


@pytest.mark.parametrize("interruption", ["stop", "refresh"])
@pytest.mark.parametrize("discovery", [False, True])
def test_late_advice_is_discarded_after_stop_or_refresh(interruption, discovery):
    async def scenario():
        class DelayedModel(RecordingModel):
            def __init__(self):
                proposal = decision()
                if discovery:
                    proposal.update(
                        intent="find_products",
                        price_preference={"value": "lower_price", "source": "رخيص"},
                    )
                super().__init__(proposal, advice("Late advice", ["white-shirt"]))
                self.started = asyncio.Event()
                self.release = asyncio.Event()

            async def complete(self, request):
                if request.prompt_version.startswith("advice-v"):
                    self.started.set()
                    await self.release.wait()
                async for chunk in super().complete(request):
                    yield chunk

        model = DelayedModel()
        app = create_app(
            llm_settings=LLMSettings(provider="groq", model="test"),
            llm_client=model,
            catalogue_reader=Reader(),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await authorize_async(client, app)
            session = (await client.post("/sessions", json={"tab_id": "tab-1"})).json()[
                "session_id"
            ]
            pending = asyncio.create_task(
                client.post(
                    f"/sessions/{session}/messages",
                    headers={"x-tab-id": "tab-1"},
                    json={"text": "ساعدني اختار", "snapshot": home_snapshot()},
                )
            )
            await asyncio.wait_for(model.started.wait(), 3)
            if interruption == "stop":
                response = await client.post(
                    f"/sessions/{session}/stop", headers={"x-tab-id": "tab-1"}
                )
            else:
                response = await client.get(f"/sessions/{session}/state?tab_id=tab-1")
            assert response.status_code in {200, 202}
            model.release.set()
            await pending
            events = parse_sse((await client.get(f"/sessions/{session}/events?once=true")).text)
            assert not any(event["event"] in {"done", "suggestions", "action"} for event in events)

    asyncio.run(scenario())


def test_every_explicit_comparison_gets_eligibility_independent_of_card_limit():
    class FourProducts:
        async def read(self):
            source = catalogue()
            return source.model_copy(
                update={
                    "products": [
                        source.products[0].model_copy(update={"id": f"choice-{index}"})
                        for index in range(4)
                    ]
                }
            )

    ids = [f"choice-{index}" for index in range(4)]
    observed = home_snapshot()
    observed["elements"] = [
        {"id": index + 1, "role": "link", "name": key, "href": f"/p/{key}", "visible": True}
        for index, key in enumerate(ids)
    ]
    model = RecordingModel(
        decision(constraints={"category": "shoes"}, advice_product_ids=ids),
        advice("كلهم متاحين، تحب تقارن على أساس إيه؟", ids),
    )
    with client_for(model, FourProducts()) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "قارن الاربعه دول", observed)
    products = json.loads(model.requests[-1].messages[0].content)["products"]
    assert len(products) == 4
    assert all(product["eligibility"]["label"] == "exact_match" for product in products)
    cards = next(
        event["data"]["suggestions"] for event in events if event["event"] == "suggestions"
    )
    assert len(cards) == 3  # Existing Panel event contract; all four remain in advice evidence.


def test_reconciliation_to_another_origin_discards_previous_advice_preferences():
    model = RecordingModel(
        decision(subjective_preferences=["quiet"]),
        advice("First advice", ["white-shirt"]),
        decision(constraints={}),
        advice("What do you need?"),
    )
    with client_for(model) as client:
        session = client.post("/sessions", json={"tab_id": "tab-1"}).json()["session_id"]
        send(client, session, "quiet please", tab_id="tab-1")
        observed = {**home_snapshot(), "url": "https://other.example/"}
        response = client.post(
            f"/sessions/{session}/reconcile",
            headers={"x-tab-id": "tab-1"},
            json={"snapshot": observed},
        )
        assert response.status_code == 200
        send(client, session, "help me choose", observed, tab_id="tab-1")
    context = json.loads(model.requests[-1].messages[0].content)
    assert context["previous_advice_context"] == {}
    assert context["recent_conversation"] == []


def test_advice_context_copied_into_navigation_gets_specific_repair_without_weakening_guard():
    mixed = decision(intent="open_product", product_id="white-shirt", request_mode="recommend")
    clean = decision(intent="open_product", product_id="white-shirt", constraints={})
    model = RecordingModel(
        decision(),
        advice("الأبيض ممكن يناسبك.", ["white-shirt"]),
        mixed,
        clean,
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        send(client, session, "ساعدني اختار")
        events = send(client, session, "طب افتح قميص أبيض اللي لسه قايله")
    actions = [event["data"]["action"] for event in events if event["event"] == "action"]
    assert len(actions) == 1 and actions[0]["url"] == "/p/white-shirt"
    repair = json.loads(model.requests[-1].system.split("Runtime validation feedback: ")[-1])
    assert repair["cross_field_rules"]["navigation_discovery_isolation"]["request_mode"] == "browse"
    assert (
        repair["cross_field_rules"]["navigation_discovery_isolation"]["open_product_constraints"]
        == {}
    )
    assert model.requests[-1].prompt_version.endswith("-repair")


def test_navigation_target_on_discovery_repairs_target_without_discarding_requirements():
    bad = decision(
        intent="find_products",
        constraints={"category": "clothing", "target": "cart"},
        request_mode="recommend",
        catalogue_requirements=[
            {"kind": "feature", "value": "lightweight", "source": "حاجة خفيفة"}
        ],
    )
    clean = {**bad, "constraints": {"category": "clothing"}}
    model = RecordingModel(bad, clean, advice("القميص الأبيض خفيف.", ["white-shirt"]))
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(client, session, "حاجة خفيفة تنصحني بايه")
    repair = json.loads(model.requests[1].system.split("Runtime validation feedback: ")[-1])
    rules = repair["cross_field_rules"]
    assert "navigation_discovery_isolation" not in rules
    assert rules["discovery_navigation_isolation"]["null_constraint_fields"] == ["target"]
    assert "catalogue_requirements" in rules["discovery_navigation_isolation"]["preserve_fields"]
    assert json.loads(model.requests[-1].messages[0].content)["intent"][
        "catalogue_requirements"
    ] == [{**bad["catalogue_requirements"][0], "excluded": False}]
    assert events[-1]["event"] == "done"
    assert not any(event["event"] == "action" for event in events)


def test_discovery_constraints_on_cart_add_get_scoped_repair_preserving_product_identity():
    from agent.tests.test_cart_task import snapshot

    clean = decision(
        intent="cart_edit",
        constraints={"size": "43", "color": "blue"},
        cart_operation="add",
        cart_target_id=4,
        cart_quantity=1,
        cart_quantity_mode="set",
        product_id="shoe-09",
        cart_source="ضيفهولي",
    )
    model = RecordingModel(
        {**clean, "constraints": {**clean["constraints"], "category": "shoes"}}, clean
    )
    with client_for(model) as client:
        session = client.post("/sessions").json()["session_id"]
        events = send(
            client,
            session,
            "تمام ضيفهولي واحد",
            snapshot().model_dump(mode="json", by_alias=True, exclude_none=True),
        )
    repair = json.loads(model.requests[-1].system.split("Runtime validation feedback: ")[-1])
    rule = repair["cross_field_rules"]["cart_authority_isolation"]
    assert "product_id for add only" in rule["preserve_fields"]
    assert rule["allowed_constraint_fields"] == ["size", "color"]
    assert "cart_quantity" in rule["preserve_fields"]
    actions = [e["data"]["action"] for e in events if e["event"] == "action"]
    assert len(actions) == 1 and actions[0]["type"] == "type" and actions[0]["id"] == 3
    assert actions[0]["text"] == "1"
    assert len(model.requests) == 2
