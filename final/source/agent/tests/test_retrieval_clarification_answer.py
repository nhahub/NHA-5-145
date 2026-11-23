"""Answers to add-option questions continue the same cart task in retrieval mode."""

import asyncio
import json

from agent.app import create_app
from agent.catalogue_retrieval import retrieve_products
from agent.llm import LLMSettings
from agent.planner import ScriptedPlanner
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel
from agent.tests.test_catalogue_retrieval import Reads
from agent.tests.test_recommended_add import (
    add_decision,
    events,
    last_action,
    product_snapshot,
    report,
)
from agent.tests.test_step import home_snapshot

ADD_REQUEST = "ضيف ملعب النجوم للسلة"
CONTEXT_PREFIX = "Shopping Copilot intent context: "


def add_with(constraints):
    return {**add_decision(), "cart_source": ADD_REQUEST, "constraints": constraints}


def intent_context(request):
    """The JSON context the action interpreter receives in its system prompt."""
    first_line = request.system.split("\n", 1)[0]
    assert first_line.startswith(CONTEXT_PREFIX), request.prompt_version
    return json.loads(first_line.removeprefix(CONTEXT_PREFIX))


def unselected_product_page():
    # The Bridge omits the disabled "choose…" placeholder from options.
    current = product_snapshot()
    current["elements"][0].update(value="", options=["42", "43"])
    current["elements"][1].update(value="", options=["yellow", "blue"])
    return current


def start(*responses):
    store, model = SessionStore(), RecordingModel(*responses)
    app = create_app(
        session_store=store,
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
        catalogue_client=Reads(),  # A size said with an add reads the product's size kind.
        catalogue_retrieval_enabled=True,
    )
    client = TestClient(app)
    client.__enter__()
    sid = client.post("/sessions").json()["session_id"]
    session = store.get(sid)
    session.product_context.origin = ("http", "localhost:4000")
    session.product_context.remember_suggestions([{"id": "shoe-12", "name": "ملعب النجوم"}])
    client.post(
        f"/sessions/{sid}/messages", json={"text": ADD_REQUEST, "snapshot": home_snapshot()}
    )
    navigate = last_action(client, sid)
    assert (navigate["type"], navigate["url"]) == ("navigate", "/p/shoe-12")
    return store, model, client, sid, navigate


def answer(client, sid, question, text, current):
    response = client.post(
        f"/sessions/{sid}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": text, "snapshot": current},
    )
    assert response.status_code == 202, response.text


def complete_add(store, client, sid, current):
    for element, expected in [(0, "43"), (1, "blue")]:
        action = last_action(client, sid)
        assert (action["type"], action["id"], action["option"]) == (
            "select",
            element + 1,
            expected,
        )
        current["elements"][element]["value"] = expected
        report(client, sid, action, current)
    action = last_action(client, sid)
    assert (action["type"], action["text"]) == ("type", "1")
    report(client, sid, action, current)
    action = last_action(client, sid)
    assert (action["type"], action["id"]) == ("click", 4)
    current["elements"].append(
        dict(id=5, role="status", name="تمت الإضافة إلى السلة", visible=True)
    )
    report(client, sid, action, current)
    assert store.get(sid).last_task.status == "completed"
    assert not any(e["event"] == "suggestions" for e in events(client, sid))


def test_exact_option_replies_continue_the_add_without_another_model_call():
    store, model, client, sid, navigate = start(add_with({}))
    try:
        current = unselected_product_page()
        report(client, sid, navigate, current, "navigated")
        size_question = last_action(client, sid)
        assert size_question["type"] == "ask_shopper" and size_question["options"] == []
        assert "42, 43" in size_question["question"]
        # The question is now part of the conversation the next interpretation reads.
        assert store.get(sid).conversation[-1]["text"] == size_question["question"]

        answer(client, sid, size_question, "43", current)
        colour_question = last_action(client, sid)
        assert colour_question["type"] == "ask_shopper"
        assert "أصفر, أزرق" in colour_question["question"]

        answer(client, sid, colour_question, " Blue ", current)
        complete_add(store, client, sid, current)
        assert len(model.requests) == 1
    finally:
        client.__exit__(None, None, None)


def test_free_text_reply_is_interpreted_with_the_question_and_cart_draft():
    store, model, client, sid, navigate = start(
        add_with({}),
        add_with({"size": "43"}),
        add_with({"size": "43", "color": "blue"}),
    )
    try:
        current = unselected_product_page()
        report(client, sid, navigate, current, "navigated")
        size_question = last_action(client, sid)

        answer(client, sid, size_question, "مقاس ٤٣ لو سمحت", current)
        size_turn = model.requests[1]
        context = intent_context(size_turn)
        assert size_turn.attempt_id.startswith("retrieval-execution-")
        assert context["pending_clarification"] == size_question["question"]
        assert context["resolved_state"]["_intent"]["product_id"] == "shoe-12"
        history = [m.content for m in size_turn.messages[:-1]]
        # The add request and the question just asked precede the reply.
        assert ADD_REQUEST in history and history[-1] == size_question["question"]

        colour_question = last_action(client, sid)
        answer(client, sid, colour_question, "الأزرق", current)
        colour_context = intent_context(model.requests[2])
        assert colour_context["pending_clarification"] == colour_question["question"]
        assert colour_context["resolved_state"]["_intent"]["constraints"]["size"] == "43"
        complete_add(store, client, sid, current)
        assert len(model.requests) == 3
    finally:
        client.__exit__(None, None, None)


def test_exact_value_does_not_bind_to_a_question_about_a_different_field():
    store, model, client, sid, navigate = start(add_with({}), add_with({}))
    try:
        current = unselected_product_page()
        # Two add buttons: the handback asks which item, not for an option value.
        current["elements"].append({**current["elements"][3], "id": 6})
        report(client, sid, navigate, current, "navigated")
        question = last_action(client, sid)
        assert question["type"] == "ask_shopper"
        assert store.get(sid).active_task.pending_variant is None
        answer(client, sid, question, "43", current)
        assert len(model.requests) == 2
    finally:
        client.__exit__(None, None, None)


def test_discovery_clarification_answer_merges_the_pending_intent_in_retrieval():
    pending = {
        "v": 9,
        "language": "en",
        "dialect": "english",
        "intent": "find_products",
        "constraints": {"category": "shoes", "color": "blue"},
        "missing_fields": ["size"],
        "needs_clarification": True,
    }
    model = RecordingModel(
        {
            **pending,
            "constraints": {"size": "43"},
            "missing_fields": [],
            "needs_clarification": False,
        },
        {"v": 1, "kind": "clarify", "question": "Any budget?", "language": "en"},
    )

    async def active():
        pass

    outcome = asyncio.run(
        retrieve_products(
            "43",
            {"_intent": pending},
            model,
            object(),
            active,
            storefront=ScriptedPlanner().storefront,
            pending_clarification="size",
        )
    )
    # A pending answer goes to the action interpreter first, even with no known products.
    assert intent_context(model.requests[0])["pending_clarification"] == "size"
    # The restored discovery intent keeps earlier constraints when it moves to search.
    search_context = json.loads(model.requests[1].messages[0].content)
    constraints = search_context["pending_intent"]["constraints"]
    assert {key: value for key, value in constraints.items() if value is not None} == {
        "category": "shoes",
        "color": "blue",
        "size": "43",
    }
    assert outcome.question == "Any budget?"
