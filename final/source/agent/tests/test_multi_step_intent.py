"""Structured Intent version 10: the optional multi-step fields, accepted beside 8 and 9.

Nothing consumes the new fields yet: the Agent still performs only the first step.
"""

import asyncio
import json

import httpx
import pytest

from agent.app import create_app
from agent.event_log import MemorySink
from agent.llm import LLMChunk, LLMRequest, LLMSettings, ScriptedLLMClient
from agent.llm.intent import StructuredIntent
from agent.llm.intent_pipeline import PROMPT_VERSION, build_intent_request, validate_live_response
from agent.storefront import load_storefront_definition
from agent.tests.http_client import TestClient
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

STEP_WORDS = "ضيفلي كوتشي أبيض لأخويا سامي"
NAME = "سامي"


def v10(**overrides) -> dict:
    return {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "navigate",
        "constraints": {"target": "orders"},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        **overrides,
    }


class CountingClient(ScriptedLLMClient):
    def __init__(self, responses):
        super().__init__(responses)
        self.requests: list[LLMRequest] = []

    async def complete(self, request):
        self.requests.append(request)
        async for chunk in super().complete(request):
            yield chunk


def counting_client(*payloads, sink=None):
    model = CountingClient([[LLMChunk(text=json.dumps(p))] for p in payloads])
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="openai/gpt-oss-120b", api_key=None),
        llm_client=model,
        **({"event_sink": sink} if sink is not None else {}),
    )
    return TestClient(app), model


def say(client, text="Open order history", snapshot=None):
    session = client.post("/sessions").json()["session_id"]
    client.post(
        f"/sessions/{session}/messages",
        json={"text": text, "snapshot": snapshot or home_snapshot()},
    )
    events = parse_sse(client.get(f"/sessions/{session}/events?once=true").text)
    state = client.get(f"/sessions/{session}/state?tab_id=tab-local").json()
    return events, state


def actions(events):
    return [e["data"]["action"] for e in events if e["event"] == "action"]


@pytest.mark.parametrize("version", [8, 9, 10])
def test_versions_8_9_and_10_each_run_their_one_step_with_one_model_call(version):
    client, model = counting_client(v10(v=version))
    events, _ = say(client)
    assert [a["type"] for a in actions(events)] == ["navigate"]
    assert len(model.requests) == 1


def test_a_one_step_v10_message_keeps_every_new_field_empty():
    intent = StructuredIntent.model_validate(v10())
    assert intent.remaining_steps == []
    assert intent.skipped_steps == []
    assert intent.condition is None
    assert intent.beneficiary is None
    assert intent.refers_to_this is False


def test_v10_carries_later_steps_as_words_but_only_the_first_step_runs():
    reply = v10(
        remaining_steps=[STEP_WORDS, "وبعدين امسح السلة لو السعر أقل من 500"],
        skipped_steps=["وبعدين افتح الحساب"],
        beneficiary="brother",
        refers_to_this=True,
        condition={"fact": "in_stock", "comparator": "is", "value": "true"},
    )
    # A condition on a navigation is asked about since ticket 09 (test_conditions.py); this
    # test is about the steps, so the first step runs from the reply without its condition.
    client, model = counting_client({**reply, "condition": None})
    events, state = say(client)
    sent = actions(events)
    assert [a["type"] for a in sent] == ["navigate"]
    assert sent[0]["url"] == "/account/orders"
    assert len(model.requests) == 1
    assert state["task"]["status"] != "paused"
    parsed = StructuredIntent.model_validate(reply)
    assert parsed.remaining_steps == [STEP_WORDS, "وبعدين امسح السلة لو السعر أقل من 500"]
    assert parsed.condition.fact == "in_stock"
    assert parsed.beneficiary == "brother"


@pytest.mark.parametrize(
    "condition",
    [
        {"fact": "price", "comparator": "lt", "value": "1500.50"},
        {"fact": "in_stock", "comparator": "is", "value": "false"},
        {"fact": "size_exists", "comparator": "is_not", "value": "43"},
        {"fact": "colour_exists", "comparator": "is", "value": "blue"},
    ],
)
def test_each_page_checkable_condition_kind_is_accepted(condition):
    intent = StructuredIntent.model_validate(v10(condition=condition))
    assert intent.condition is not None
    assert not intent.needs_clarification


@pytest.mark.parametrize(
    "relation",
    [
        "me",
        "brother",
        "sister",
        "mother",
        "father",
        "son",
        "daughter",
        "husband",
        "wife",
        "friend",
        "named_person",
    ],
)
def test_listed_relations_are_accepted(relation):
    assert StructuredIntent.model_validate(v10(beneficiary=relation)).beneficiary == relation


STEP = "وبعدين كذا"
MALFORMED = {
    "unknown relation": v10(beneficiary="cousin"),
    "steps that are not words": v10(remaining_steps=[1, 2]),
    "skipped steps that are not a list": v10(skipped_steps="x"),
    "empty step words": v10(remaining_steps=["  "]),
    "overlong step words": v10(remaining_steps=["x" * 301]),
    "step is an object, not words": v10(remaining_steps=[{"text": "x", "target": "cart"}]),
    "replace on v9": v10(
        v=9,
        intent="cart_edit",
        constraints={},
        cart_operation="replace",
        cart_target_id=3,
    ),
    "remaining steps on v9": v10(v=9, remaining_steps=[STEP]),
    "beneficiary on v8": v10(v=8, beneficiary="mother"),
    "reference flag on v9": v10(v=9, refers_to_this=True),
    "version 11": v10(v=11),
}


@pytest.mark.parametrize("name", MALFORMED)
def test_malformed_reply_is_rejected_by_code(name):
    with pytest.raises(ValueError):
        StructuredIntent.model_validate(MALFORMED[name])
    with pytest.raises(ValueError):
        validate_live_response(json.dumps(MALFORMED[name]))


@pytest.mark.parametrize("name", ["unknown relation", "replace on v9", "remaining steps on v9"])
def test_malformed_reply_is_repaired_once_then_pauses_as_invalid_response(name):
    client, model = counting_client(MALFORMED[name], MALFORMED[name])
    events, state = say(client)
    assert state["task"]["status"] == "paused"
    assert state["task"]["pending_question"] is None
    assert not actions(events)
    errors = [e["data"]["message"] for e in events if e["event"] == "error"]
    assert len(errors) == 1
    assert "model response" in errors[0].lower()
    assert len(model.requests) == 2
    assert model.requests[1].prompt_version == f"{PROMPT_VERSION}-repair"


def test_repaired_reply_recovers_after_one_malformed_attempt():
    client, model = counting_client(MALFORMED["unknown relation"], v10())
    events, _ = say(client)
    assert [a["type"] for a in actions(events)] == ["navigate"]
    assert len(model.requests) == 2


@pytest.mark.parametrize(
    "condition",
    [
        {"fact": "weather", "comparator": "is", "value": "sunny"},
        {"fact": "in_stock", "comparator": "lt", "value": "true"},
        {"fact": "price", "comparator": "lt", "value": "cheap"},
        {"fact": "price", "comparator": "lt"},
        "if it looks nice",
    ],
)
def test_anything_that_is_not_a_condition_needs_clarification(condition):
    reply = v10(condition=condition)
    intent = StructuredIntent.model_validate(reply)
    assert intent.needs_clarification
    assert "condition" in intent.missing_fields
    assert intent.condition is None
    client, model = counting_client(reply)
    events, state = say(client)
    sent = actions(events)
    assert [a["type"] for a in sent] == ["ask_shopper"]
    assert state["task"]["status"] == "awaiting_answer"
    assert len(model.requests) == 1


def test_no_shopper_words_step_words_or_names_reach_the_event_log():
    reply = v10(
        remaining_steps=[STEP_WORDS],
        skipped_steps=["وبعدين كلم سامي"],
        beneficiary="named_person",
        condition={"fact": "colour_exists", "comparator": "is", "value": "أبيض"},
    )
    sink = MemorySink()
    client, _ = counting_client(reply, sink=sink)
    say(client, f"افتح الطلبات وبعدين {STEP_WORDS}")
    assert sink.records
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (STEP_WORDS, NAME, "كوتشي", "أبيض", "الطلبات", "named_person"):
        assert private not in dumped


def test_the_prompt_asks_for_v10_and_keeps_its_existing_rules():
    request = build_intent_request(
        "show shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )
    assert PROMPT_VERSION == "intent-v39"
    assert request.prompt_version == "intent-v39"
    assert request.schema_version == 10
    assert "StructuredIntent JSON object, v=10." in request.system
    for kept in (
        "Cart edits use cart_edit with operation add, quantity, remove (one line), or undo.",
        "Emptying the whole cart is always mutate/clear_cart",
        "Never read or enter credentials/payment fields.",
    ):
        assert kept in request.system
    for added in (
        "interpret ONLY the first step",
        "never as an intent, product ID, element ID or target",
        "Three steps at most",
        "skipped_steps",
        "refers_to_this=true",
        "fill first_step",
    ):
        assert added in request.system


def test_the_provider_schema_offers_the_new_fields_on_every_branch():
    schema = build_intent_request(
        "show shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    ).response_schema
    new = {
        "first_step",
        "remaining_steps",
        "skipped_steps",
        "condition",
        "beneficiary",
        "refers_to_this",
    }
    carried = {}
    for branch in schema["anyOf"]:
        name = branch["$ref"].split("/")[-1]
        properties = schema["$defs"][name]["properties"]
        assert properties["v"]["const"] == 10
        carried[name] = new & set(properties)
    assert carried["CartDecision"] == new
    assert carried["DiscoveryDecision"] == new - {"condition"}
    assert carried["ConversationDecision"] == set()
    assert all("remaining_steps" in carried[n] for n in carried if n != "ConversationDecision")
    steps = schema["$defs"]["CartDecision"]["properties"]["remaining_steps"]
    assert steps["items"] == {"type": "string", "minLength": 1, "maxLength": 300}
    assert steps["maxItems"] == 2
    # The provider schema is copied into every branch: keep it free of descriptions.
    for name in new:
        assert "description" not in json.dumps(schema["$defs"]["CartDecision"]["properties"][name])
    cart = schema["$defs"]["CartDecision"]["properties"]["cart_operation"]
    assert "replace" in json.dumps(cart)


# --- Every provider adapter must still carry the live request -----------------------------

LIVE_REPLY = json.dumps(
    v10(
        remaining_steps=[STEP_WORDS],
        skipped_steps=[],
        beneficiary="brother",
        condition={"fact": "price", "comparator": "lt", "value": "900"},
        refers_to_this=False,
    )
)


def live_request(**overrides) -> LLMRequest:
    request = build_intent_request(
        "show shoes",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )
    from dataclasses import replace

    return replace(request, **overrides)


def drain(adapter, request):
    async def run():
        return "".join([c.text or "" async for c in adapter.complete(request)])

    return asyncio.run(run())


def test_openrouter_structural_schema_keeps_the_new_fields_without_references():
    from agent.llm.provider_schema import openrouter_response_schema

    schema = openrouter_response_schema(live_request().response_schema)
    text = json.dumps(schema)
    assert '"$ref"' not in text and '"$defs"' not in text
    for branch in schema["anyOf"]:
        assert "title" not in json.dumps(branch["properties"]["v"])
        assert "enum" not in branch["properties"]["v"]
        if "remaining_steps" in branch["properties"]:
            assert "maxItems" not in branch["properties"]["remaining_steps"]
    cart = next(b for b in schema["anyOf"] if b["title"] == "CartDecision")
    assert "replace" in cart["properties"]["cart_operation"]["anyOf"][0]["enum"]


def test_openrouter_adapter_delivers_and_validates_a_v10_reply():
    from agent.llm.openrouter import OpenRouterClient
    from agent.tests.test_openrouter import settings

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        assert "remaining_steps" in json.dumps(schema)
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": LIVE_REPLY}}]},
        )

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    assert drain(client, live_request()) == LIVE_REPLY


def test_groq_strict_schema_lists_every_new_field_as_required_and_closed():
    from agent.llm.groq import GroqClient, _strict_schema

    strict = _strict_schema(live_request().response_schema)

    def visit(node):
        if isinstance(node, dict):
            if "properties" in node:
                assert node["additionalProperties"] is False
                assert node["required"] == list(node["properties"])
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(strict)
    assert strict["$defs"]["IntentCondition"]["required"] == ["fact", "comparator", "value"]

    from agent.llm.config import load_llm_settings

    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "groq",
            "LLM_MODEL": "qwen/qwen3.8-27b",
            "GROQ_API_KEY": "local-test-key",
            "GROQ_BASE_URL": "https://example.test/openai/v1",
            "LLM_REASONING_EFFORT": "low",
        }
    )

    def handler(request):
        sent = json.loads(request.content)["response_format"]["json_schema"]["schema"]
        assert sent == strict
        return httpx.Response(200, json={"choices": [{"message": {"content": LIVE_REPLY}}]})

    client = GroqClient(settings, transport=httpx.MockTransport(handler))
    assert drain(client, live_request()) == LIVE_REPLY


def test_gemini_receives_the_schema_unchanged_and_accepts_a_v10_reply():
    from agent.llm.config import load_llm_settings
    from agent.llm.gemini import GeminiClient

    settings = load_llm_settings(
        {"LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-2.5-flash", "GEMINI_API_KEY": "test"}
    )
    request = live_request()

    def handler(sent):
        schema = json.loads(sent.content)["generationConfig"]["responseJsonSchema"]
        assert schema == dict(request.response_schema)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": LIVE_REPLY}]},
                    }
                ]
            },
        )

    client = GeminiClient(settings, transport=httpx.MockTransport(handler))
    assert drain(client, request) == LIVE_REPLY


def test_nvidia_asks_for_json_only_and_accepts_a_v10_reply():
    from agent.llm.config import load_llm_settings
    from agent.llm.nvidia import NvidiaNIMClient

    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "nvidia",
            "LLM_MODEL": "test-model",
            "NVIDIA_API_KEY": "local-test-key",
            "NVIDIA_BASE_URL": "https://example.test/v1",
        }
    )

    def handler(sent):
        body = json.loads(sent.content)
        assert body["response_format"] == {"type": "json_object"}
        assert "json_schema" not in json.dumps(body["response_format"])
        return httpx.Response(200, json={"choices": [{"message": {"content": LIVE_REPLY}}]})

    client = NvidiaNIMClient(settings, transport=httpx.MockTransport(handler))
    assert drain(client, live_request()) == LIVE_REPLY


def test_bedrock_inlines_the_schema_with_the_new_fields_and_accepts_a_v10_reply():
    from agent.llm.bedrock import BedrockClient, _payload
    from agent.tests.test_bedrock import SDK, response, settings

    request = live_request()
    payload = _payload(settings(), request)
    schema_text = payload["system"][-1]["text"]
    assert "remaining_steps" in schema_text and "refers_to_this" in schema_text
    assert '"$ref"' not in schema_text and '"$defs"' not in schema_text
    sdk = SDK(
        response(output={"message": {"role": "assistant", "content": [{"text": LIVE_REPLY}]}})
    )
    assert drain(BedrockClient(settings(), sdk_client=sdk), request) == LIVE_REPLY


# --- The evaluation budget size bound ---------------------------------------------------


def element(i, role, name, **extra):
    return {"id": i, "role": role, "name": name, "visible": True, **extra}


def _nav():
    pages = [("الرئيسية", "/"), ("أحذية", "/c/shoes"), ("ملابس", "/c/clothing"), ("السلة", "/cart")]
    return [element(i, "link", name, href=href) for i, (name, href) in enumerate(pages, 1)]


def large_pages() -> dict[str, dict]:
    def page(url, elements):
        return {**home_snapshot(), "url": f"http://localhost:4000{url}", "elements": elements}

    links = [element(20 + i, "link", f"منتج رقم {i}", href=f"/p/shoe-{i:02d}") for i in range(12)]
    product = [
        element(30, "heading", "ممشى النيل"),
        element(31, "combobox", "المقاس", value="43", options=[str(n) for n in range(38, 46)]),
        element(32, "combobox", "اللون", value="blue", options=["blue", "black", "white", "red"]),
        element(33, "textbox", "الكمية", value="1"),
        element(34, "button", "أضف إلى السلة", form_action="/cart/items"),
    ]
    cart = []
    for n in range(4):
        group = f"ممشى النيل {n} — 43 — أسود"
        cart += [
            element(100 + n * 4, "link", group, href=f"/p/shoe-{n:02d}"),
            element(101 + n * 4, "textbox", f"الكمية — {group}", value="2", group=group),
            element(
                102 + n * 4,
                "button",
                f"تحديث الكمية — {group}",
                form_action="/cart/quantity",
                group=group,
            ),
            element(
                103 + n * 4, "button", f"حذف — {group}", form_action="/cart/remove", group=group
            ),
        ]
    cart.append(element(900, "button", "تفريغ السلة", form_action="/cart/clear"))
    return {
        "home": page("/", _nav() + links),
        "product": page("/p/shoe-09", _nav() + product + links[:8]),
        "cart": page("/cart", _nav() + cart),
    }


@pytest.mark.parametrize("page", ["home", "product", "cart"])
def test_the_live_request_fits_the_openrouter_evaluation_budget_on_large_pages(page):
    from agent.llm.config import load_llm_settings
    from agent.llm.openrouter import OpenRouterClient
    from agent.schemas import Snapshot

    snapshot = Snapshot.model_validate(large_pages()[page])
    request = build_intent_request(
        "ضيفلي ده للسلة",
        storefront=load_storefront_definition(),
        # The worst case "this" context: three candidates (ticket 08).
        resolved_state={
            "_this_candidates": [
                {"id": f"shoe-0{i}", "name": f"ممشى النيل الإصدار {i}"} for i in range(3)
            ]
        },
        pending_clarification=None,
        snapshot=snapshot,
    )
    posted = []

    def handler(sent):
        if sent.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 2, "limit_remaining": 2, "limit_reset": None}}
            )
        posted.append(json.loads(sent.content))
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": LIVE_REPLY}}]},
        )

    settings = load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_MODEL": "google/gemini-2.5-flash",
            "OPENROUTER_API_KEY": "test-secret",
            "OPENROUTER_TOTAL_CAP_DOLLARS": "2.00",
        }
    )
    client = OpenRouterClient(settings, transport=httpx.MockTransport(handler))
    assert drain(client, request) == LIVE_REPLY  # no OpenRouterBudgetError
    reserve = (
        (len(json.dumps(posted[0]).encode()) + 4096) * 0.3 + request.max_tokens * 2.5
    ) / 1_000_000
    # The client refuses above 0.02 (agent/llm/openrouter.py); keep 10% headroom on these
    # large pages.
    assert reserve <= 0.018, f"{page}: reserve {reserve:.4f} leaves too little headroom"


def test_step_overflow_moves_to_skipped_in_spoken_order_and_the_first_step_still_runs():
    reply = v10(remaining_steps=["two", "three", "four"], skipped_steps=["five"])
    intent = StructuredIntent.model_validate(reply)
    assert intent.remaining_steps == ["two", "three"]
    assert intent.skipped_steps == ["four", "five"]
    client, model = counting_client(reply)
    events, state = say(client)
    assert [a["type"] for a in actions(events)] == ["navigate"]
    assert not [e for e in events if e["event"] == "error"]
    assert state["task"]["status"] != "paused"
    assert len(model.requests) == 1


def test_skipped_steps_are_truncated_with_the_overflow_first():
    reply = v10(
        remaining_steps=["r1", "r2", "o1", "o2", "o3"],
        skipped_steps=["s1", "s2", "s3", "s4", "s5", "s6"],
    )
    intent = StructuredIntent.model_validate(reply)
    assert intent.remaining_steps == ["r1", "r2"]
    assert intent.skipped_steps == ["o1", "o2", "o3", "s1", "s2", "s3"]


def test_v9_replies_are_not_normalised():
    with pytest.raises(ValueError):
        StructuredIntent.model_validate(v10(v=9, remaining_steps=["a", "b", "c"]))


def test_step_overflow_is_kept_when_the_model_sends_null_skipped_steps():
    intent = StructuredIntent.model_validate(
        v10(remaining_steps=["one", "two", "three"], skipped_steps=None)
    )

    assert intent.remaining_steps == ["one", "two"]
    assert intent.skipped_steps == ["three"]


def test_first_step_is_optional_additive_and_only_allowed_on_v10():
    assert StructuredIntent.model_validate(v10()).first_step is None
    intent = StructuredIntent.model_validate(
        v10(first_step="  افتح الطلبات ", remaining_steps=["افتح السلة"])
    )
    assert intent.first_step == "افتح الطلبات"
    with pytest.raises(ValueError):
        StructuredIntent.model_validate(v10(v=9, first_step="x"))
    with pytest.raises(ValueError):
        StructuredIntent.model_validate(v10(first_step=""))
    client, model = counting_client(v10(first_step="افتح الطلبات", remaining_steps=["افتح السلة"]))
    events, _ = say(client)
    assert [a["type"] for a in actions(events)] == ["navigate"]
    assert len(model.requests) == 1
