"""Ticket 02: later plan steps and repaired readings answer the CURRENT request.

Driven through the Agent's HTTP API (and the interpreter seam) with a scripted model that
records the requests it receives.
"""

import asyncio
import json

import pytest

from agent.llm.intent_pipeline import interpret_message
from agent.storefront import load_storefront_definition
from agent.tests.test_advice import RecordingModel
from agent.tests.test_multi_step_plan import (
    SHOPPER_TEXT,
    STEP_TWO,
    complete,
    intent,
    make_client,
    request_context,
    start,
    stream,
    two_steps,
)
from agent.tests.test_source_evidence_and_undo import (
    EARLIER_ADD,
    REMOVE,
    Session,
    payload,
    product_page,
)

HANDLED = "already handled"


def mutation(source):
    return {
        "v": 8,
        "language": "en",
        "dialect": "english",
        "intent": "mutate",
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
        "mutation_kind": "clear_cart",
        "mutation_source": source,
    }


def help_reply():
    return intent("cart", intent="help", constraints={})


# --- A later plan step is interpreted from its own words ----------------------------------


def test_a_later_step_request_has_its_own_words_and_not_the_whole_message_or_last_target():
    client, model = make_client(two_steps("cart"), intent("checkout"))
    session_id = start(client)
    first = stream(client, session_id)
    complete(client, session_id, first, "/cart")

    step_one, step_two = model.requests[0], model.requests[1]
    assert step_one.messages[-1].content == SHOPPER_TEXT
    assert step_two.messages[-1].content == STEP_TWO
    assert [m.content for m in step_two.messages if SHOPPER_TEXT in m.content] == []
    assert request_context(step_two)["previous_destination"] is None
    # Only the turns of the whole message are dropped: the step's own words are the request.
    assert all(m.role != "shopper" for m in step_two.messages[:-1])


def test_a_third_step_request_also_omits_the_whole_message():
    client, model = make_client(
        intent(
            "account",
            first_step="افتح الحساب",
            remaining_steps=["خليها حمرا", "افتح السلة"],
        ),
        intent("account", first_step=None),
        intent("cart"),
    )
    session_id = start(client, "افتح الحساب وبعدين خليها حمرا وبعدين افتح السلة")
    first = stream(client, session_id)
    complete(client, session_id, first, "/account")
    second = stream(client, session_id)
    complete(client, session_id, second, "/account")
    third = model.requests[2]
    assert third.messages[-1].content == "افتح السلة"
    assert not any("وبعدين" in m.content for m in third.messages)
    assert request_context(third)["previous_destination"] is None


# --- Repair feedback names the current request and the earlier ones are handled -----------


def _interpret(model, message, history):
    return asyncio.run(
        interpret_message(
            model,
            message,
            storefront=load_storefront_definition(),
            resolved_state={
                "_original_message": message,
                "_recent_conversation": history,
            },
            pending_clarification=None,
        )
    )


HISTORY = [
    {"role": "shopper", "text": EARLIER_ADD},
    {"role": "copilot", "text": "Added it."},
]


def test_repair_feedback_names_the_current_request_and_says_earlier_ones_are_handled():
    model = RecordingModel(mutation(EARLIER_ADD), help_reply())
    result = _interpret(model, REMOVE, HISTORY)
    assert result.intent == "help"  # a correct reading on the repair succeeds
    repair = model.requests[1].system
    assert REMOVE in repair.split("Runtime validation feedback:", 1)[1]
    assert HANDLED in repair.split("Runtime validation feedback:", 1)[1]


def test_the_repair_attempt_is_sent_without_conversation_history():
    model = RecordingModel(mutation(EARLIER_ADD), help_reply())
    _interpret(model, REMOVE, HISTORY)
    assert [m.content for m in model.requests[0].messages] == [EARLIER_ADD, "Added it.", REMOVE]
    assert [m.content for m in model.requests[1].messages] == [REMOVE]


def test_the_quote_guard_still_refuses_a_source_quoted_from_an_earlier_request():
    model = RecordingModel(mutation(EARLIER_ADD), mutation(EARLIER_ADD))
    with pytest.raises(ValueError, match="quoted source"):
        _interpret(model, REMOVE, HISTORY)


# --- The retrieval path: three decisions, the last one without history ---------------------


def _retrieval_session(*responses):
    session = Session(True, *responses)
    conversation = session.store.get(session.sid).conversation
    conversation.extend(HISTORY)
    return session


def test_retrieval_feedback_names_the_request_and_the_last_attempt_has_no_history():
    copied = payload(
        "add",
        EARLIER_ADD,
        cart_target_id=4,
        cart_quantity=1,
        cart_quantity_mode="set",
        constraints={"size": "43", "color": "white"},
    )
    session = _retrieval_session(copied, copied, copied)
    try:
        session.send(REMOVE, product_page())
        assert session.rejections() == ["source_not_in_message"] * 3
        requests = session.model.requests
        assert len(requests) == 3
        assert any(m.content == EARLIER_ADD for m in requests[0].messages)
        for later in requests[1:]:
            feedback = later.system.split("Validation feedback:", 1)[1]
            assert REMOVE in feedback and HANDLED in feedback
        assert [m.content for m in requests[2].messages] == [REMOVE]
        assert len(requests[1].messages) > 1  # only the final attempt drops the history
        assert json.loads(requests[2].system.split("\n", 1)[0].split("context: ", 1)[1])
    finally:
        session.client.__exit__(None, None, None)


# --- Only a quote refusal drops the history ------------------------------------------------

QUESTION = [
    {"role": "shopper", "text": EARLIER_ADD},
    {"role": "copilot", "text": "مقاس كام؟"},
]


def test_a_repair_for_another_cause_keeps_the_question_turn_and_succeeds():
    wrong_target = intent("nowhere", constraints={"target": "nowhere"})
    model = RecordingModel(wrong_target, help_reply())
    result = _interpret(model, "42", QUESTION)
    assert result.intent == "help"
    assert [m.content for m in model.requests[1].messages] == [EARLIER_ADD, "مقاس كام؟", "42"]


def test_retrieval_keeps_history_on_the_last_attempt_after_a_non_quote_refusal():
    wrong_target = intent("nowhere", constraints={"target": "nowhere"})
    session = _retrieval_session(wrong_target, wrong_target, wrong_target)
    try:
        session.send(REMOVE, product_page())
        assert "source_not_in_message" not in session.rejections()
        assert [m.content for m in session.model.requests[2].messages][-1] == REMOVE
        assert len(session.model.requests[2].messages) > 1
    finally:
        session.client.__exit__(None, None, None)
