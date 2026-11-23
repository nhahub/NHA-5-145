"""Ticket 09: conditions the page can answer ("add it if it is under 1000").

Driven through the Agent's HTTP API with a scripted model, with the catalogue read both ways
(retrieval on: private catalogue reads; retrieval off: the catalogue snapshot). The model only
says the fact, the comparator and the value; code reads the product's verified record at the
step's own turn and decides. Everything asserted is visible: stream events, the actions sent,
the report and event-log records. Expected strings are written out literally.
"""

import json

import pytest

from agent.catalogue import CatalogueSnapshot
from agent.catalogue_client import CatalogueReadError
from agent.catalogue_contract import Candidate, DetailsResult
from agent.event_log import MemorySink
from agent.tests.test_catalogue_retrieval import Reads
from agent.tests.test_multi_step_plan import intent, last_action, make_client, names, stream
from agent.tests.test_plan_failure import begin, finished, post, report_result
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_this_resolution import ADD_OK, cart_page, product_page

PRODUCT = "shoe-09"
PAUSED_ASK_AR = "ما قدرتش أتأكد من الشرط ده من بيانات المنتج. تحب أعمل إيه؟"
PAUSED_ASK_EN = (
    "I couldn't check that condition from the product's data. What would you like me to do?"
)
VAGUE_AR = "أقدر أشيّك على السعر أو التوفر أو المقاس أو اللون بس. تقصد أنهي شرط؟"
UNDER_1000 = "ضيفها لو أقل من 1000"


class Shelf:
    """The Storefront's verified record of one product; the test changes it between turns."""

    def __init__(self, price="850", sizes=("42", "43"), colors=("blue",), available=True):
        self.price, self.sizes, self.colors, self.available = price, list(sizes), colors, available
        self.fail = False
        self.missing = False
        self.reads = 0

    def row(self):
        return {
            "id": "other" if self.missing else PRODUCT,
            "category": "shoes",
            "name_ar": "ممشى النيل",
            "name_en": "Nile walker",
            "product_type": "running",
            "price": {"amount": self.price, "currency": "EGP"},
            "sizes": list(self.sizes),
            "colors": list(self.colors),
            "available": self.available,
            "added_at": "2026-01-01",
            "features": [],
            "suitable_for": [],
            "wear_position": None,
        }

    def candidate(self):
        row = self.row()
        return Candidate.model_validate(
            {
                "product": {
                    "id": row["id"],
                    "category": row["category"],
                    "nameAr": row["name_ar"],
                    "nameEn": row["name_en"],
                    "type": row["product_type"],
                    "price": row["price"],
                    "sizes": row["sizes"],
                    "colors": row["colors"],
                    "available": row["available"],
                    "addedAt": row["added_at"],
                    "features": [],
                    "suitableFor": [],
                    "wearPosition": None,
                    "absent_features": [],
                    "absent_uses": [],
                },
                "product_revision": 1,
                "requirements": [],
            }
        )


class Snapshots:
    """The catalogue snapshot reader (retrieval off)."""

    def __init__(self, shelf):
        self.shelf = shelf

    async def read(self):
        self.shelf.reads += 1
        if self.shelf.fail:
            raise CatalogueReadError("unavailable")
        return CatalogueSnapshot.model_validate(
            {"v": 1, "currency": "EGP", "products": [self.shelf.row()]}
        )


class PrivateReads(Reads):
    """The private catalogue client (retrieval on)."""

    def __init__(self, shelf):
        super().__init__()
        self.shelf = shelf

    async def details(self, query):
        self.shelf.reads += 1
        if self.shelf.fail:
            raise CatalogueReadError("unavailable")
        found = [] if self.shelf.missing else [self.shelf.candidate()]
        return DetailsResult(
            v=1,
            catalogue_revision=1,
            products=found,
            missing_ids=[] if found else list(query.ids),
            unverified_requirements=[],
        )


MODES = pytest.mark.parametrize("retrieval", [False, True], ids=["retrieval-off", "retrieval-on"])


def world(retrieval, shelf, *replies, sink=None):
    options = (
        {"catalogue_client": PrivateReads(shelf), "catalogue_retrieval_enabled": True}
        if retrieval
        else {"catalogue_reader": Snapshots(shelf), "catalogue_retrieval_enabled": False}
    )
    return make_client(*replies, sink=sink, **options)


def add(text=UNDER_1000, language="ar", condition=None, **extra) -> dict:
    """What the scripted model says for an add of the open product with a condition."""
    return intent(
        "cart",
        intent="cart_edit",
        constraints={},
        language=language,
        dialect="egyptian_arabic" if language == "ar" else "english",
        cart_operation="add",
        cart_source=text.split(" لو ")[0].split(" if ")[0],
        product_id=PRODUCT,
        cart_target_id=5,
        condition=condition,
        **extra,
    )


def under(value="1000", comparator="lt"):
    return {"fact": "price", "comparator": comparator, "value": value}


def when(fact, value, comparator="is"):
    return {"fact": fact, "comparator": comparator, "value": value}


def actions(events):
    return [e["data"]["action"] for e in events if e["event"] == "action"]


def summaries(events):
    return [e["data"]["summary"] for e in events if e["event"] == "done"]


def says(text, reply_condition, shelf, retrieval, *more, **extra):
    """One add message on the product page; returns (client, model, session id, events)."""
    client, model = world(retrieval, shelf, add(text, condition=reply_condition, **extra), *more)
    session_id = begin(client, text, product_page())
    return client, model, session_id, stream(client, session_id)


def assert_added(events):
    """The add went ahead: its click is on the stream and nothing says it was skipped."""
    assert [a["type"] for a in actions(events)][-1] == "click"
    assert not summaries(events)


def assert_not_added(events, summary):
    assert actions(events) == []
    assert summaries(events) == [summary]
    assert "error" not in names(events) and "cancelled" not in names(events)


# --- Price ---------------------------------------------------------------------------------


@MODES
def test_price_that_holds_adds_exactly_like_an_unconditional_add(retrieval):
    _, _, _, events = says(UNDER_1000, under(), Shelf(price="850"), retrieval)
    assert_added(events)


@MODES
def test_price_that_does_not_hold_clicks_nothing_and_tells_why(retrieval):
    _, _, _, events = says(UNDER_1000, under(), Shelf(price="1200"), retrieval)
    assert_not_added(events, "ما ضفتهاش: سعرها 1200 جنيه، والشرط مش متحقق.")


@MODES
def test_the_english_reason_uses_the_products_price_and_currency(retrieval):
    text = "add it if it is under 1000"
    _, _, session_id, events = says(text, under(), Shelf(price="1200.50"), retrieval, language="en")
    assert actions(events) == []
    assert summaries(events) == [
        "I didn't add it: it costs 1200.50 EGP, so the condition isn't met."
    ]


@pytest.mark.parametrize(
    ("comparator", "value", "price", "holds"),
    [
        ("lt", "1000", "1000", False),
        ("lte", "1000", "1000", True),
        ("gt", "1000", "1000", False),
        ("gte", "1000", "1000", True),
        ("eq", "1000", "1000.00", True),
        ("eq", "1000", "999", False),
        ("gt", "1000", "1000.50", True),
    ],
)
def test_every_price_comparator_compares_the_decimal_amounts(comparator, value, price, holds):
    _, _, _, events = says(UNDER_1000, under(value, comparator), Shelf(price=price), False)
    assert ([a["type"] for a in actions(events)] == ["click"]) is holds
    assert bool(summaries(events)) is not holds


# --- In stock ------------------------------------------------------------------------------


@MODES
def test_in_stock_true_adds_when_available_and_refuses_when_not(retrieval):
    _, _, _, events = says("ضيفها لو متاحة", when("in_stock", "true"), Shelf(), retrieval)
    assert_added(events)
    gone = Shelf(available=False)
    _, _, _, events = says("ضيفها لو متاحة", when("in_stock", "true"), gone, retrieval)
    assert_not_added(events, "ما ضفتهاش: المنتج مش متاح دلوقتي.")


@MODES
def test_in_stock_false_is_met_only_when_the_product_is_not_available(retrieval):
    text = "ضيفها لو مش متاحة"
    _, _, _, events = says(text, when("in_stock", "false"), Shelf(available=False), retrieval)
    assert_added(events)
    _, _, _, events = says(text, when("in_stock", "false"), Shelf(), retrieval)
    assert_not_added(events, "ما ضفتهاش: المنتج متاح، والشرط كان إنه مش متاح.")


def test_the_english_stock_reasons():
    text = "add it if it is in stock"
    _, _, _, events = says(
        text, when("in_stock", "true"), Shelf(available=False), False, language="en"
    )
    assert summaries(events) == ["I didn't add it: it's not available right now."]
    _, _, _, events = says(text, when("in_stock", "false"), Shelf(), False, language="en")
    assert summaries(events) == [
        "I didn't add it: it is available, and the condition was that it isn't."
    ]


# --- Size exists ---------------------------------------------------------------------------


@MODES
def test_a_size_the_product_has_holds_and_one_it_lacks_does_not(retrieval):
    text = "ضيفها لو فيه مقاس 43"
    _, _, _, events = says(text, when("size_exists", "43"), Shelf(), retrieval)
    assert_added(events)
    text = "ضيفها لو فيه مقاس 44"
    _, _, _, events = says(text, when("size_exists", "44"), Shelf(), retrieval)
    assert_not_added(events, "ما ضفتهاش: المقاس 44 مش موجود في المنتج ده.")


def test_arabic_indic_digits_and_letter_case_match_the_products_sizes():
    shelf = Shelf(sizes=("42", "43", "XL"))
    _, _, _, events = says("ضيفها لو فيه مقاس ٤٣", when("size_exists", "٤٣"), shelf, False)
    assert_added(events)
    _, _, _, events = says("ضيفها لو فيه مقاس xl", when("size_exists", "xl"), shelf, False)
    assert_added(events)
    _, _, _, events = says("ضيفها لو فيه مقاس ٤٤", when("size_exists", "٤٤"), shelf, False)
    assert_not_added(events, "ما ضفتهاش: المقاس ٤٤ مش موجود في المنتج ده.")


def test_size_is_not_refuses_when_the_size_exists_and_the_english_reasons():
    text = "ضيفها لو مفيش مقاس 43"
    cond = when("size_exists", "43", "is_not")
    _, _, _, events = says(text, cond, Shelf(), False)
    assert_not_added(events, "ما ضفتهاش: المقاس 43 موجود في المنتج ده.")
    _, _, _, events = says(
        "add it if size 44 exists", when("size_exists", "44"), Shelf(), False, language="en"
    )
    assert summaries(events) == ["I didn't add it: size 44 isn't available for this product."]
    _, _, _, events = says("add it if size 43 is missing", cond, Shelf(), False, language="en")
    assert summaries(events) == ["I didn't add it: size 43 is available for this product."]


# --- Colour exists -------------------------------------------------------------------------


@MODES
def test_an_arabic_colour_alias_maps_to_the_storefront_colour(retrieval):
    text = "ضيفها لو جاية أسود"
    shelf = Shelf(colors=("black", "blue"))
    _, _, _, events = says(text, when("colour_exists", "أسود"), shelf, retrieval)
    assert_added(events)
    _, _, _, events = says(text, when("colour_exists", "أسود"), Shelf(), retrieval)
    assert_not_added(events, "ما ضفتهاش: اللون أسود مش موجود في المنتج ده.")


def test_colour_is_not_and_the_english_colour_reasons():
    shelf = Shelf(colors=("black",))
    _, _, _, events = says(
        "ضيفها لو مش جاية أسود", when("colour_exists", "أسود", "is_not"), shelf, False
    )
    assert_not_added(events, "ما ضفتهاش: اللون أسود موجود في المنتج ده.")
    text = "add it if it comes in black"
    _, _, _, events = says(text, when("colour_exists", "black"), Shelf(), False, language="en")
    assert summaries(events) == ["I didn't add it: colour black isn't available for this product."]
    cond = when("colour_exists", "Black", "is_not")
    _, _, _, events = says("add it if not in black", cond, shelf, False, language="en")
    assert summaries(events) == ["I didn't add it: colour Black is available for this product."]


# --- Cannot read: the Copilot asks, never judges ---------------------------------------------


def asked(events, question=PAUSED_ASK_AR):
    action = last_action(events)
    assert action["type"] == "ask_shopper" and action["options"] == []
    assert action["question"] == question and action["narration"] == question
    assert [a["type"] for a in actions(events)] == ["ask_shopper"]
    assert not summaries(events)


@MODES
def test_a_colour_word_the_storefront_does_not_know_makes_the_copilot_ask(retrieval):
    _, _, _, events = says(
        "ضيفها لو جاية بنفسجي", when("colour_exists", "بنفسجي"), Shelf(), retrieval
    )
    asked(events)


@MODES
def test_a_failed_catalogue_read_makes_the_copilot_ask(retrieval):
    shelf = Shelf()
    shelf.fail = True
    _, _, _, events = says(UNDER_1000, under(), shelf, retrieval)
    asked(events)
    assert "error" not in names(events)


@MODES
def test_a_product_the_catalogue_does_not_have_makes_the_copilot_ask(retrieval):
    shelf = Shelf()
    shelf.missing = True
    client, _ = world(retrieval, shelf, add(UNDER_1000, condition=under()))
    session_id = begin(client, UNDER_1000, product_page())
    asked(stream(client, session_id))


def test_the_english_question_when_the_condition_cannot_be_checked():
    shelf = Shelf()
    shelf.fail = True
    _, _, _, events = says("add it if it is under 1000", under(), shelf, False, language="en")
    asked(events, PAUSED_ASK_EN)


def test_a_condition_on_a_quantity_edit_makes_the_copilot_ask():
    quantity = intent(
        "cart",
        intent="cart_edit",
        constraints={},
        cart_operation="quantity",
        cart_source="خليها 2",
        cart_quantity=2,
        cart_quantity_mode="set",
        cart_target_id=2,
        condition=under(),
    )
    client, _ = world(False, Shelf(), quantity)
    session_id = begin(client, "خليها 2 لو أقل من 1000", cart_page(("ممشى النيل", 2, 3)))
    asked(stream(client, session_id))


def test_the_answer_to_that_question_goes_through_the_normal_answer_path():
    shelf = Shelf()
    shelf.fail = True
    reply = add(UNDER_1000, condition=under())
    client, model = world(False, shelf, reply, add("ضيفها", condition=None))
    session_id = begin(client, UNDER_1000, product_page())
    question = last_action(stream(client, session_id))
    answer = post(
        client,
        session_id,
        f"/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "ضيفها", "snapshot": product_page()},
    )
    assert answer.status_code == 202
    assert [a["type"] for a in actions(stream(client, session_id))][-1] == "click"
    assert len(model.requests) == 2


def test_a_vague_condition_keeps_the_trusted_question():
    vague = add("ضيفها لو شكلها حلو", missing_fields=["condition"], needs_clarification=True)
    client, _ = world(False, Shelf(), vague)
    session_id = begin(client, "ضيفها لو شكلها حلو", product_page())
    events = stream(client, session_id)
    asked(events, VAGUE_AR)


# --- A condition in a plan, checked at the step's own turn -----------------------------------


@MODES
def test_a_conditional_first_step_that_is_false_is_skipped_and_the_plan_carries_on(retrieval):
    shelf = Shelf(price="1200")
    first = add(
        UNDER_1000, condition=under(), first_step=UNDER_1000, remaining_steps=["افتح السلة"]
    )
    client, model = world(retrieval, shelf, first, intent("cart"))
    session_id = begin(client, "ضيفها لو أقل من 1000 وبعدين افتح السلة", product_page())
    events = stream(client, session_id)

    assert [
        (e["event"], e["data"].get("position"), e["data"].get("outcome"))
        for e in events
        if e["event"] in {"plan_step_finished", "plan_finished"}
    ] == [("plan_step_finished", 1, "skipped")]
    assert last_action(events)["type"] == "navigate"
    assert len(model.requests) == 2

    report_result(client, session_id, events, snapshot_at("/cart"))
    events = stream(client, session_id)
    assert finished(events) == {
        **finished(events),
        "outcome": "done",
        "report": (
            "خلصت طلبك:\n"
            "– ضيفها لو أقل من 1000 — ما ضفتهاش: سعرها 1200 جنيه، والشرط مش متحقق.\n"
            "✓ افتح السلة"
        ),
    }


@MODES
def test_a_conditional_later_step_reads_the_catalogue_when_its_turn_comes(retrieval):
    shelf = Shelf(price="500")
    first = add(
        "ضيفها",
        condition=None,
        first_step="ضيفها",
        remaining_steps=["ضيف كمان واحدة لو أقل من 1000"],
    )
    second = add("ضيف كمان واحدة لو أقل من 1000", condition=under())
    client, _ = world(retrieval, shelf, first, second)
    session_id = begin(client, "ضيفها وبعدين ضيف كمان واحدة لو أقل من 1000", product_page())
    events = stream(client, session_id)
    assert [a["type"] for a in actions(events)][-1] == "click"

    shelf.price = "1200"  # the catalogue changed while step 1 ran: step 2 sees it as it is now
    report_result(client, session_id, events, product_page(status=ADD_OK), status="ok")
    events = stream(client, session_id)

    assert finished(events)["outcome"] == "done"
    assert finished(events)["report"] == (
        "خلصت طلبك:\n"
        "✓ ضيفها\n"
        "– ضيف كمان واحدة لو أقل من 1000 — ما ضفتهاش: سعرها 1200 جنيه، والشرط مش متحقق."
    )
    outcomes = [e["data"]["outcome"] for e in events if e["event"] == "plan_step_finished"]
    assert outcomes == ["done", "skipped"]
    assert [a["type"] for a in actions(events)] == ["click"]  # step 2 clicked nothing


@MODES
def test_a_conditional_later_step_that_holds_adds(retrieval):
    shelf = Shelf(price="500")
    first = add(
        "ضيفها",
        condition=None,
        first_step="ضيفها",
        remaining_steps=["ضيف كمان واحدة لو أقل من 1000"],
    )
    second = add("ضيف كمان واحدة لو أقل من 1000", condition=under())
    client, _ = world(retrieval, shelf, first, second)
    session_id = begin(client, "ضيفها وبعدين ضيف كمان واحدة لو أقل من 1000", product_page())
    events = stream(client, session_id)
    report_result(client, session_id, events, product_page(status=ADD_OK), status="ok")
    events = stream(client, session_id)

    assert [a["type"] for a in actions(events)] == ["click", "click"]
    assert "plan_finished" not in names(events)


def test_a_condition_that_cannot_be_checked_pauses_the_plan():
    shelf = Shelf()
    shelf.fail = True
    first = add(
        UNDER_1000, condition=under(), first_step=UNDER_1000, remaining_steps=["افتح السلة"]
    )
    client, _ = world(False, shelf, first)
    session_id = begin(client, "ضيفها لو أقل من 1000 وبعدين افتح السلة", product_page())
    events = stream(client, session_id)

    assert [e["data"]["reason"] for e in events if e["event"] == "plan_paused"] == ["question"]
    assert "plan_finished" not in names(events)
    asked(events)


# --- Records and unchanged behaviour ---------------------------------------------------------


def test_no_condition_value_price_or_text_reaches_an_event_record():
    sink = MemorySink()
    shelf = Shelf(price="1477")
    text = "ضيفها لو أقل من 1311"
    first = add(text, condition=under("1311"), first_step=text, remaining_steps=["افتح السلة"])
    client, _ = world(False, shelf, first, intent("cart"), sink=sink)
    session_id = begin(client, f"{text} وبعدين افتح السلة", product_page())
    stream(client, session_id)

    steps = [r for r in sink.records if r["event"] == "plan_step"]
    assert [(r["position"], r["outcome"]) for r in steps] == [(1, "skipped")]
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in ("1477", "1311", "ضفتهاش", "أقل من", "condition", "جنيه"):
        assert private not in dumped


@MODES
def test_an_unconditional_add_is_unchanged_one_model_call_and_one_size_kind_read(retrieval):
    shelf = Shelf()
    client, model = world(retrieval, shelf, add("ضيفها", condition=None))
    session_id = begin(client, "ضيفها", product_page())
    events = stream(client, session_id)

    assert_added(events)
    assert len(model.requests) == 1
    assert shelf.reads == 1  # only what is read today: the product's size kind


@MODES
def test_a_conditional_add_reads_the_product_once_for_both_the_kind_and_the_condition(retrieval):
    shelf = Shelf()
    client, model = world(retrieval, shelf, add(UNDER_1000, condition=under()))
    session_id = begin(client, UNDER_1000, product_page())
    assert_added(stream(client, session_id))
    assert len(model.requests) == 1
    assert shelf.reads == 1
