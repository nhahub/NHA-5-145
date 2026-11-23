"""Ticket 08 (copilot reliability, B6): a product the Shopper did not name is confirmed first.

Driven through the Agent's HTTP API with a scripted model. The model only picks a product by
id; code checks the Shopper's own words (or "this", an exact option answer, the open page) and
otherwise asks "تقصد X؟" before anything is opened or added. Expected strings are literal.
"""

import json

import pytest

from agent.event_log import MemorySink
from agent.tests.test_multi_step_plan import intent, last_action, make_client, names, stream
from agent.tests.test_plan_failure import begin, finished, post, report_result, send, state
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_step import home_snapshot
from agent.tests.test_this_resolution import (
    ADD_THIS,
    NILE,
    actions,
    element,
    open_this,
    product_page,
    this_intent,
)

MARATHON = "ماراثون القاهرة"
BAG = "حقيبة القاهرة"
OPEN_MARATHON = "افتح ماراثون القاهرة"
QUESTION_AR = f"تقصد {BAG}؟"
NOTHING_DONE_AR = "تمام، ما عملتش حاجة. قولي تقصد أنهي منتج."
NOTHING_DONE_EN = "OK, I didn't do anything. Tell me which product you mean."
CARDS = {
    "shoe-09": f"{NILE} / Nile Walker",
    "shoe-12": f"{BAG} / Cairo Bag",
    "shoe-13": f"{MARATHON} / Cairo Marathon",
}


def home_page(*slugs) -> dict:
    """A home page whose product cards are labelled "Arabic name / English name"."""
    links = [
        element(10 + i, "link", CARDS[slug].split(" / ")[0], href=f"/p/{slug}", group=CARDS[slug])
        for i, slug in enumerate(slugs or CARDS)
    ]
    return {**home_snapshot(), "elements": links}


def opening(slug, source, **overrides) -> dict:
    return intent("cart", intent="open_product", constraints={}, product_id=slug, **overrides) | {
        "navigation_source": source
    }


def adding(slug, source, **overrides) -> dict:
    return this_intent(product_id=slug, refers_to_this=False, cart_source=source, **overrides)


def answer(client, session_id, question, text, page=None):
    return post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={
            "question_id": question["action_id"],
            "text": text,
            "snapshot": page if page is not None else home_page(),
        },
    )


def question_of(events):
    action = last_action(events)
    assert action["type"] == "ask_shopper", action
    return action


def moves(events):
    return [a for a in actions(events) if a["type"] in {"navigate", "click"}]


# --- Named products go straight through -------------------------------------------------------


def test_a_product_named_in_the_message_opens_with_no_extra_question():
    client, model = make_client(opening("shoe-13", OPEN_MARATHON))
    session_id = begin(client, OPEN_MARATHON, home_page())
    events = stream(client, session_id)

    assert last_action(events)["url"] == "/p/shoe-13"
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert len(model.requests) == 1


def test_the_english_name_of_the_product_counts_as_named():
    reply = opening("shoe-13", "open the cairo marathon", language="en", dialect="english")
    client, _ = make_client(reply)
    session_id = begin(client, "open the cairo marathon", home_page())
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-13"


@pytest.mark.parametrize(
    ("slug", "words"),
    [
        ("shoe-12", "افتح حقيبه القاهره"),  # ة -> ه
        ("shoe-09", "افتح ممشي النيل"),  # ى -> ي
        ("shoe-13", "افتح مـاراثون القاهرة"),  # tatweel
        ("shoe-13", "افتح مَاراثُون القاهرة"),  # diacritics
        ("shoe-13", "افتح ماراثون    القاهرة"),  # whitespace
        ("shoe-13", "OPEN   cairo MARATHON"),  # case and whitespace
        ("shoe-12", "افتحلي حقيبة القاهرة دي"),  # the name inside longer words
    ],
)
def test_spelling_variants_of_the_name_still_count_as_named(slug, words):
    client, model = make_client(opening(slug, words))
    session_id = begin(client, words, home_page())
    events = stream(client, session_id)
    assert last_action(events)["url"] == f"/p/{slug}"
    assert len(model.requests) == 1


def test_hamza_variants_of_the_name_still_count_as_named():
    cards = {"shoe-14": "أحذية الجري / Runners"}
    page = {
        **home_snapshot(),
        "elements": [element(10, "link", "أحذية الجري", href="/p/shoe-14", group=cards["shoe-14"])],
    }
    client, _ = make_client(opening("shoe-14", "افتح احذية الجري"))
    session_id = begin(client, "افتح احذية الجري", page)
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-14"


def test_a_product_named_in_a_clarification_answer_counts_as_named():
    ask = intent(
        "cart",
        intent="open_product",
        constraints={},
        needs_clarification=True,
        missing_fields=["product_id"],
    )
    client, model = make_client(ask, opening("shoe-13", MARATHON))
    session_id = begin(client, "افتح المنتج ده", home_page())
    question = question_of(stream(client, session_id))
    assert answer(client, session_id, question, MARATHON).status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-13"
    assert len(model.requests) == 2


def test_the_product_whose_page_is_open_is_never_asked_about():
    client, model = make_client(adding("shoe-09", "ضيفلي الجزمة"))
    session_id = begin(client, "ضيفلي الجزمة", product_page("shoe-09", NILE))
    events = stream(client, session_id)
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert last_action(events)["type"] in {"type", "click"}
    assert len(model.requests) == 1


def test_this_is_resolved_by_code_and_not_asked_again():
    client, model = make_client(this_intent())
    session_id = begin(client, ADD_THIS, product_page("shoe-09", NILE))
    events = stream(client, session_id)
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert len(model.requests) == 1

    client, _ = make_client(open_this())
    session_id = begin(client, "افتحها", product_page("shoe-09", NILE))
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-09"


# --- An unnamed product is confirmed ----------------------------------------------------------


def test_an_unnamed_product_is_asked_about_and_nothing_is_opened():
    client, model = make_client(opening("shoe-12", OPEN_MARATHON))
    session_id = begin(client, OPEN_MARATHON, home_page())
    events = stream(client, session_id)

    question = question_of(events)
    assert question["question"] == QUESTION_AR
    assert question["narration"] == QUESTION_AR
    assert question["options"] == ["أيوه", "لا"]
    assert moves(events) == []
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 1


def test_yes_opens_exactly_that_product_without_another_model_call():
    client, model = make_client(opening("shoe-12", OPEN_MARATHON))
    session_id = begin(client, OPEN_MARATHON, home_page())
    question = question_of(stream(client, session_id))

    assert answer(client, session_id, question, "أيوه").status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-12"
    assert len(model.requests) == 1


def test_no_ends_the_task_with_nothing_done_and_frees_the_session():
    client, model = make_client(opening("shoe-12", OPEN_MARATHON), opening("shoe-13", "x"))
    session_id = begin(client, OPEN_MARATHON, home_page())
    question = question_of(stream(client, session_id))

    assert answer(client, session_id, question, "لا").status_code == 202
    events = stream(client, session_id)
    done = [e["data"] for e in events if e["event"] == "done"]
    assert [d["summary"] for d in done] == [NOTHING_DONE_AR]
    assert moves(events) == []
    assert len(model.requests) == 1
    # The Shopper can simply say which product they meant.
    assert send(client, session_id, OPEN_MARATHON, home_page()).status_code == 202


def test_the_question_and_the_decline_are_english_for_an_english_shopper():
    reply = opening("shoe-12", "open the cairo marathon", language="en", dialect="english")
    client, _ = make_client(reply)
    session_id = begin(client, "open the cairo marathon", home_page())
    question = question_of(stream(client, session_id))
    assert question["question"] == "Did you mean Cairo Bag?"
    assert question["options"] == ["Yes", "No"]

    assert answer(client, session_id, question, "No").status_code == 202
    events = stream(client, session_id)
    assert [e["data"]["summary"] for e in events if e["event"] == "done"] == [NOTHING_DONE_EN]


def test_an_unnamed_add_asks_first_and_yes_goes_on_to_add_that_product():
    client, model = make_client(adding("shoe-12", "ضيفلي الجزمة"))
    session_id = begin(client, "ضيفلي الجزمة", home_page())
    events = stream(client, session_id)
    question = question_of(events)
    assert question["question"] == QUESTION_AR
    assert moves(events) == []

    assert answer(client, session_id, question, "أيوه").status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-12"
    assert len(model.requests) == 1
    page = product_page("shoe-12", BAG)
    report_result(client, session_id, events, page)
    assert last_action(stream(client, session_id))["type"] in {"type", "click"}


def test_no_to_an_unnamed_add_changes_nothing():
    client, _ = make_client(adding("shoe-12", "ضيفلي الجزمة"))
    session_id = begin(client, "ضيفلي الجزمة", home_page())
    question = question_of(stream(client, session_id))
    assert answer(client, session_id, question, "لا").status_code == 202
    events = stream(client, session_id)
    assert moves(events) == []
    assert [e["data"]["summary"] for e in events if e["event"] == "done"] == [NOTHING_DONE_AR]


def test_a_typed_reply_that_is_not_yes_or_no_is_read_by_the_model_again():
    client, model = make_client(opening("shoe-12", OPEN_MARATHON), opening("shoe-13", MARATHON))
    session_id = begin(client, OPEN_MARATHON, home_page())
    question = question_of(stream(client, session_id))
    assert answer(client, session_id, question, MARATHON).status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-13"
    assert len(model.requests) == 2


# --- Inside a plan -----------------------------------------------------------------------------


def plan_reply(slug="shoe-12"):
    return opening(
        slug,
        OPEN_MARATHON,
        first_step=OPEN_MARATHON,
        remaining_steps=["وبعدين افتح الدفع"],
    )


def test_inside_a_plan_the_question_pauses_the_plan():
    client, _ = make_client(plan_reply())
    session_id = begin(client, f"{OPEN_MARATHON} وبعدين افتح الدفع", home_page())
    events = stream(client, session_id)

    assert question_of(events)["question"] == QUESTION_AR
    assert "plan_paused" in names(events)
    assert state(client, session_id)["plan"]["paused"] == "question"
    assert not [e for e in events if e["event"] == "plan_step_finished"]
    assert moves(events) == []


def test_yes_inside_a_plan_resumes_it_and_the_next_step_still_runs():
    client, _ = make_client(plan_reply(), intent("checkout"))
    session_id = begin(client, f"{OPEN_MARATHON} وبعدين افتح الدفع", home_page())
    question = question_of(stream(client, session_id))

    assert answer(client, session_id, question, "أيوه").status_code == 202
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-12"
    report_result(client, session_id, events, product_page("shoe-12", BAG))
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/checkout"
    report_result(client, session_id, events, snapshot_at("/checkout"))
    assert finished(stream(client, session_id))["outcome"] == "done"


def test_no_inside_a_plan_fails_the_step_and_skips_the_rest():
    client, model = make_client(plan_reply())
    session_id = begin(client, f"{OPEN_MARATHON} وبعدين افتح الدفع", home_page())
    question = question_of(stream(client, session_id))

    assert answer(client, session_id, question, "لا").status_code == 202
    events = stream(client, session_id)
    assert moves(events) == []
    assert finished(events)["outcome"] == "failed"
    assert finished(events)["report"] == (
        f"وقفت عند خطوة ماتمّتش:\n✕ {OPEN_MARATHON} — ما أكدتش المنتج، فما نفّذتش الخطوة دي.\n"
        "– وبعدين افتح الدفع (اتخطّت)"
    )
    assert len(model.requests) == 1


# --- Privacy ----------------------------------------------------------------------------------


def test_no_event_record_carries_a_product_name_or_the_shoppers_words():
    sink = MemorySink()
    client, _ = make_client(opening("shoe-12", OPEN_MARATHON), sink=sink)
    session_id = begin(client, OPEN_MARATHON, home_page())
    question = question_of(stream(client, session_id))
    assert answer(client, session_id, question, "لا").status_code == 202
    stream(client, session_id)

    text = json.dumps(sink.records, ensure_ascii=False)
    for secret in (BAG, MARATHON, "Cairo", "أيوه", "shoe-12", OPEN_MARATHON):
        assert secret not in text
