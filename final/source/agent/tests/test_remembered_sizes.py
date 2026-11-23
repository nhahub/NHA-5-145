"""Ticket 03: remembered sizes per person and size kind.

Driven through the Agent's HTTP API with a scripted model, with the catalogue read both ways
(retrieval on: private catalogue reads; retrieval off: the catalogue snapshot). The size kind
comes only from verified catalogue facts; the store lives in the Session and nowhere else.
"""

import json

import pytest

from agent.app import create_app
from agent.catalogue import CatalogueSnapshot
from agent.catalogue_contract import Candidate, DetailsResult, SearchResult
from agent.event_log import MemorySink
from agent.llm import LLMSettings
from agent.remembered_sizes import normalise_size, size_kind
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_advice import RecordingModel, advice
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot

# id -> (category, product type). The Storefront's verified facts, the only source of a kind.
PRODUCTS = {
    "shoe-1": ("shoes", "football"),
    "shoe-2": ("shoes", "running"),
    "trousers-1": ("clothing", "trousers"),
    "shirt-1": ("clothing", "shirts"),
    "bag-1": ("bags", "backpack"),
}
PAGE_SIZES = {
    "shoe": ["42", "43", "44"],
    "trousers": ["30", "32", "34", "36"],
    "shirt": ["l", "m", "s", "xl"],
    "bag": ["one"],
}


def product_row(product_id):
    category, kind = PRODUCTS[product_id]
    return {
        "id": product_id,
        "category": category,
        "name_ar": "منتج " + product_id,
        "name_en": "Product " + product_id,
        "product_type": kind,
        "price": {"amount": "100", "currency": "EGP"},
        "sizes": [],
        "colors": ["blue"],
        "available": True,
        "added_at": "2026-01-01",
        "features": [],
        "suitable_for": [],
        "wear_position": None,
    }


def candidate(product_id, requirements=0):
    row = product_row(product_id)
    return Candidate.model_validate(
        {
            "product": {
                "id": product_id,
                "category": row["category"],
                "nameAr": row["name_ar"],
                "nameEn": row["name_en"],
                "type": row["product_type"],
                "price": row["price"],
                "sizes": [],
                "colors": ["blue"],
                "available": True,
                "addedAt": "2026-01-01",
                "features": [],
                "suitableFor": [],
                "wearPosition": None,
                "absent_features": [],
                "absent_uses": [],
            },
            "product_revision": 1,
            "requirements": [{"index": i, "status": "unknown"} for i in range(requirements)],
        }
    )


class Shop:
    """The private catalogue client (retrieval on)."""

    def __init__(self, products=PRODUCTS):
        self.products = list(products)
        self.detail_reads = []

    async def search(self, query):
        return SearchResult(
            v=1,
            catalogue_revision=1,
            candidates=[candidate(i, len(query.requirements)) for i in self.products],
            ranking="lexical",
            exact_count=None,
            next_cursor=None,
            truncated=False,
            unverified_requirements=query.unverified_requirements,
        )

    async def details(self, query):
        self.detail_reads.append(list(query.ids))
        found = [i for i in query.ids if i in self.products]
        return DetailsResult(
            v=1,
            catalogue_revision=1,
            products=[candidate(i, len(query.requirements)) for i in found],
            missing_ids=[i for i in query.ids if i not in found],
            unverified_requirements=query.unverified_requirements,
        )


class Reader:
    """The catalogue snapshot reader (retrieval off)."""

    def __init__(self, products=PRODUCTS):
        self.products = list(products)

    async def read(self):
        return CatalogueSnapshot.model_validate(
            {"v": 1, "currency": "EGP", "products": [product_row(i) for i in self.products]}
        )


def product_page(product_id, options, value=""):
    path = "/p/" + product_id
    return {
        **home_snapshot(),
        "url": "http://localhost:4000" + path,
        "title": product_id,
        "elements": [
            {
                "id": 1,
                "role": "combobox",
                "name": "المقاس",
                "value": value,
                "options": options,
                "visible": True,
            },
            {
                "id": 2,
                "role": "combobox",
                "name": "اللون",
                "value": "blue",
                "options": ["blue"],
                "visible": True,
            },
            {
                "id": 4,
                "role": "button",
                "name": "أضف إلى السلة",
                "form_action": "/cart/items",
                "visible": True,
            },
        ],
    }


def page_for(product_id, options=None, value=""):
    family = PRODUCTS[product_id][1]
    key = (
        "shoe"
        if PRODUCTS[product_id][0] == "shoes"
        else "bag"
        if PRODUCTS[product_id][0] == "bags"
        else "trousers"
        if family == "trousers"
        else "shirt"
    )
    return product_page(product_id, options or PAGE_SIZES[key], value)


def add_intent(product_id, language="ar", **overrides):
    constraints = overrides.pop("constraints", {})
    return {
        "v": 10,
        "language": language,
        "dialect": "egyptian_arabic" if language == "ar" else "english",
        "intent": "cart_edit",
        "constraints": constraints,
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
        "cart_operation": "add",
        "product_id": product_id,
        "cart_target_id": 4,
        **overrides,
    }


def search_replies(retrieval, size, *, who=None, language="ar", ids=("shoe-1", "shoe-2"), **extra):
    """The scripted model replies of one search turn that carries a size."""
    category = PRODUCTS[ids[0]][0]
    if retrieval:
        return [
            {"kind": "search", "query": {"query": "shoes"}, "beneficiary": who},
            {
                "kind": "recommend",
                "language": language,
                "selected_ids": list(ids),
                "constraints": {"category": category, "size": size},
                "advice_message": "Here are some options.",
                "beneficiary": who,
            },
        ]
    return [
        {
            "v": 10,
            "language": language,
            "dialect": "egyptian_arabic" if language == "ar" else "english",
            "intent": "advice",
            "constraints": {"category": category, "size": size},
            "missing_fields": [],
            "conflicting_fields": [],
            "needs_clarification": False,
            "request_mode": "recommend",
            "beneficiary": who,
            **extra,
        },
        advice("Here are some options.", list(ids)),
    ]


class World:
    def __init__(self, retrieval, *replies, sink=None, products=PRODUCTS):
        self.retrieval = retrieval
        self.store = SessionStore()
        self.model = RecordingModel(*replies)
        self.shop = Shop(products) if retrieval else None
        options = (
            {"catalogue_client": self.shop, "catalogue_retrieval_enabled": True}
            if retrieval
            else {"catalogue_reader": Reader(products), "catalogue_retrieval_enabled": False}
        )
        app = create_app(
            session_store=self.store,
            llm_settings=LLMSettings(provider="groq", model="test", api_key=None),
            llm_client=self.model,
            **({"event_sink": sink} if sink is not None else {}),
            **options,
        )
        self.client = TestClient(app)
        self.sid = self.client.post("/sessions").json()["session_id"]
        self.page = home_snapshot()

    def events(self):
        return parse_sse(self.client.get(f"/sessions/{self.sid}/events?once=true").text)

    def say(self, text, page=None):
        self.page = page or self.page
        response = self.client.post(
            f"/sessions/{self.sid}/messages", json={"text": text, "snapshot": self.page}
        )
        assert response.status_code == 202, response.text

    def last_action(self):
        actions = [e["data"]["action"] for e in self.events() if e["event"] == "action"]
        return actions[-1] if actions else None

    def report(self, action, status="ok"):
        body = {
            "v": 1,
            "task_id": action["task_id"],
            "action_id": action["action_id"],
            "sequence_number": action["sequence_number"],
            "status": status,
            "snapshot": self.page,
        }
        assert (
            self.client.post(f"/sessions/{self.sid}/action-results", json=body).status_code == 202
        )

    def run_add(self):
        """Carry out the add's actions on the current page; return the final action or done."""
        for _ in range(8):
            if self.store.get(self.sid).last_task.status == "completed":
                return None
            action = self.last_action()
            if action["type"] == "ask_shopper":
                return action
            elements = self.page["elements"]
            if action["type"] == "select":
                next(e for e in elements if e["id"] == action["id"])["value"] = action["option"]
            if action["type"] == "click":
                elements.append(
                    {"id": 9, "role": "status", "name": "تمت الإضافة إلى السلة", "visible": True}
                )
            self.report(action)
        raise AssertionError("the add did not finish")

    def selected(self):
        return [
            (e["data"]["action"]["id"], e["data"]["action"]["option"])
            for e in self.events()
            if e["event"] == "action" and e["data"]["action"]["type"] == "select"
        ]

    def done(self):
        return [e["data"]["summary"] for e in self.events() if e["event"] == "done"]

    def add(self, product_id, text="ضيفها", options=None, value="", **intent):
        """One add turn on the product page; returns the question it asked, if any."""
        if self.store.get(self.sid).active_task is not None:
            self.store.stop(self.sid)  # an unanswered question from the turn before
        said = intent.get("constraints", {}).get("size")
        if said and said not in text:
            text = f"{text} مقاس {said}"  # the Shopper says the size; the model cannot invent it
        reply = add_intent(product_id, **{"cart_source": text, **intent})
        self.model.responses = iter([reply, *self.model.responses])
        self.say(text, page_for(product_id, options, value))
        return self.run_add()

    def search_again(self, text, size, **kwargs):
        """A later search turn that carries a size. With retrieval on, the session already knows
        products, so the action interpreter answers first and hands the request back to search."""
        replies = search_replies(self.retrieval, size, **kwargs)
        if self.retrieval:
            replies = [search_replies(False, size, **kwargs)[0], *replies]
        self.model.responses = iter(replies)
        self.say(text, home_snapshot())

    def remembered(self):
        return dict(self.store.get(self.sid).remembered_sizes)


MODES = pytest.mark.parametrize("retrieval", [False, True], ids=["retrieval-off", "retrieval-on"])


def world_with_size(retrieval, size, *, who=None, language="ar", ids=("shoe-1", "shoe-2")):
    world = World(retrieval, *search_replies(retrieval, size, who=who, language=language, ids=ids))
    world.say("عايز جزمة اكسر بيها الملعب مقاسي " + size)
    return world


# --- The owner's bug ---------------------------------------------------------------------


@MODES
def test_the_owners_phrase_then_add_on_the_product_page_uses_43_without_asking(retrieval):
    world = world_with_size(retrieval, "43")
    assert world.remembered() == {("me", "shoe"): "43"}
    question = world.add("shoe-1")
    assert question is None
    assert world.selected() == [(1, "43")]
    done = world.done()[-1]
    assert done.startswith("تمت الإضافة إلى السلة")
    assert "ضفتها بمقاس 43 زي ما قلت" in done
    # The search turn and the add were the only model calls: no question, no repair.
    assert len(world.model.requests) == 3


@MODES
def test_the_used_size_note_is_in_english_for_an_english_shopper(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43", language="en"))
    world.say("I need football shoes size 43")
    world.add("shoe-2", text="add it", language="en")
    assert world.done()[-1] == "Added to cart. Added it in size 43, as you said."


@MODES
def test_the_next_add_in_the_same_session_keeps_using_the_remembered_size(retrieval):
    world = world_with_size(retrieval, "43")
    world.add("shoe-1")
    world.add("shoe-2")
    assert world.selected() == [(1, "43"), (1, "43")]


# --- Per person --------------------------------------------------------------------------


@MODES
def test_sizes_for_me_and_a_brother_are_kept_apart(retrieval):
    world = world_with_size(retrieval, "43")
    world.search_again("for my brother, size 40 shoes", "40", who="brother")
    assert world.remembered() == {("me", "shoe"): "43", ("brother", "shoe"): "40"}

    options = ["40", "42", "43"]
    assert (
        world.add("shoe-1", text="add it for my brother", options=options, beneficiary="brother")
        is None
    )
    assert world.selected()[-1] == (1, "40")
    assert world.add("shoe-1", text="add it", options=options) is None
    assert world.selected()[-1] == (1, "43")


@MODES
def test_a_person_with_no_remembered_size_is_asked_not_given_someone_elses(retrieval):
    world = world_with_size(retrieval, "43")
    question = world.add("shoe-1", beneficiary="sister")
    assert question is not None and question["type"] == "ask_shopper"
    assert world.selected() == []
    assert "42, 43, 44" in question["question"]


@pytest.mark.parametrize(
    "relation",
    ["brother", "sister", "mother", "father", "son", "daughter", "husband", "wife", "friend"],
)
def test_each_listed_relation_is_its_own_person(relation):
    world = World(True, *search_replies(True, "41", who=relation))
    world.say("size 41 for them")
    assert world.remembered() == {(relation, "shoe"): "41"}


# --- Per kind ----------------------------------------------------------------------------


@MODES
def test_a_shoe_size_is_never_used_for_trousers_or_tops(retrieval):
    world = world_with_size(retrieval, "43")
    for product_id, page_options in (("trousers-1", None), ("shirt-1", None)):
        question = world.add(product_id, options=page_options)
        assert question is not None
        assert "Size" not in question["question"] and "المقاس 43" not in question["question"]
    assert world.selected() == []


@MODES
def test_each_kind_has_its_own_size_per_person(retrieval):
    world = World(retrieval)
    assert world.add("shoe-1", constraints={"size": "43"}) is None
    assert world.add("trousers-1", constraints={"size": "32"}) is None
    assert world.add("shirt-1", constraints={"size": "l"}) is None
    assert world.remembered() == {("me", "shoe"): "43", ("me", "waist"): "32", ("me", "top"): "L"}
    # Reading follows the kind of each product.
    for product_id in ("shoe-2", "trousers-1", "shirt-1"):
        assert world.add(product_id) is None
    assert world.selected()[-3:] == [(1, "43"), (1, "32"), (1, "l")]


@MODES
def test_a_top_size_matches_the_pages_own_option_text_ignoring_case(retrieval):
    world = World(retrieval)
    world.add("shirt-1", constraints={"size": "xl"})
    world.add("shirt-1", options=["S", "M", "L", "XL"])
    assert world.selected()[-1] == (1, "XL")


@MODES
def test_a_product_with_no_derivable_kind_gets_no_remembered_size_and_asks(retrieval):
    world = world_with_size(retrieval, "43")
    question = world.add("bag-1", options=["43", "44"])
    assert question is not None
    assert world.selected() == []
    # Nothing is stored for a kind that does not exist, even with an explicit size.
    world.add("bag-1", options=["43", "44"], constraints={"size": "44"})
    assert world.remembered() == {("me", "shoe"): "43"}


@MODES
def test_a_product_the_catalogue_cannot_verify_gets_no_remembered_size(retrieval):
    # The page exists but the catalogue has never heard of this id: no kind, so the Copilot asks.
    world = World(retrieval, *search_replies(retrieval, "43"), products=("shoe-2",))
    world.say("عايز جزمة مقاسي 43")
    question = world.add("shoe-1")
    assert question is not None and world.selected() == []


@MODES
def test_a_search_that_shows_products_of_different_kinds_stores_nothing(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43", ids=("trousers-1", "shirt-1")))
    world.say("حاجة مقاسي 43")
    assert world.remembered() == {}


@MODES
def test_a_search_that_shows_nothing_stores_nothing(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43", ids=("shoe-1",)), products=())
    world.say("عايز جزمة مقاسي 43")
    assert world.remembered() == {}


@pytest.mark.parametrize(
    ("kind", "raw", "stored"),
    [
        ("shoe", "43", "43"),
        ("shoe", " 43 ", "43"),
        ("shoe", "29", None),
        ("shoe", "51", None),
        ("shoe", "43.5", None),
        ("shoe", "XL", None),
        ("waist", "32", "32"),
        ("waist", "23", None),
        ("waist", "47", None),
        ("waist", "L", None),
        ("top", "l", "L"),
        ("top", "XXL", "XXL"),
        ("top", "xs", "XS"),
        ("top", "43", None),
        ("top", "كبير", None),
        ("top", None, None),
    ],
)
def test_a_size_that_does_not_fit_its_kinds_format_is_not_stored(kind, raw, stored):
    assert normalise_size(kind, raw) == stored


@pytest.mark.parametrize(
    ("category", "product_type", "kind"),
    [
        ("shoes", "football", "shoe"),
        ("shoes", "anything", "shoe"),
        ("clothing", "trousers", "waist"),
        ("clothing", "tops", "top"),
        ("clothing", "shirts", "top"),
        ("clothing", "outerwear", "top"),
        ("clothing", "sportswear", "top"),
        ("clothing", "dresses", "top"),
        ("clothing", "scarves", None),
        ("bags", "backpack", None),
        ("electronics", "trousers", None),
        (None, None, None),
    ],
)
def test_the_size_kind_table(category, product_type, kind):
    assert size_kind(category, product_type) == kind


@MODES
def test_a_size_in_the_wrong_format_with_an_add_is_not_stored(retrieval):
    world = World(retrieval)
    world.add("shoe-1", constraints={"size": "43"})
    world.add("shoe-1", options=["XL", "43"], constraints={"size": "XL"})
    assert world.remembered() == {("me", "shoe"): "43"}


# --- Latest wins -------------------------------------------------------------------------


@MODES
def test_the_latest_size_said_replaces_the_earlier_one(retrieval):
    world = world_with_size(retrieval, "43")
    world.search_again("لا مقاسي 44", "44")
    assert world.remembered() == {("me", "shoe"): "44"}
    world.add("shoe-1")
    assert world.selected()[-1] == (1, "44")


@MODES
def test_an_explicit_size_beats_the_remembered_one_and_is_then_remembered(retrieval):
    world = world_with_size(retrieval, "43")
    world.add("shoe-1", constraints={"size": "42"})
    assert world.selected() == [(1, "42")]
    assert "ضفتها بمقاس" not in world.done()[-1]
    assert world.remembered() == {("me", "shoe"): "42"}
    world.add("shoe-2")
    assert world.selected()[-1] == (1, "42")


@MODES
def test_the_page_already_holding_a_size_is_left_alone(retrieval):
    world = world_with_size(retrieval, "43")
    # The page's own selected value stands: nothing is read, nothing is selected.
    world.add("shoe-1", options=["42", "43"], value="42")
    assert world.selected() == []
    assert "ضفتها بمقاس" not in world.done()[-1]


@MODES
def test_an_answered_size_question_is_remembered_for_the_next_add(retrieval):
    world = World(retrieval)
    question = world.add("shoe-1")
    assert question is not None and question["options"] == []
    page = page_for("shoe-1")
    world.page = page
    world.client.post(
        f"/sessions/{world.sid}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "44", "snapshot": page},
    )
    world.run_add()
    assert world.remembered() == {("me", "shoe"): "44"}
    world.add("shoe-2")
    assert world.selected()[-1] == (1, "44")


# --- Missing size: ask, never nearest ----------------------------------------------------


@MODES
def test_a_product_without_the_remembered_size_asks_with_the_options_and_says_why(retrieval):
    world = world_with_size(retrieval, "43")
    question = world.add("shoe-1", options=["40", "41", "42", "44"])
    assert question["type"] == "ask_shopper"
    text = question["question"]
    assert text.startswith("المقاس 43 مش متاح في المنتج ده.")
    assert "40, 41, 42, 44" in text
    # Neither 42 nor 44, the nearest sizes, was chosen.
    assert world.selected() == []
    assert world.store.get(world.sid).active_task.status == "awaiting_answer"


@MODES
def test_the_unavailable_size_line_is_english_for_an_english_shopper(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43", language="en"))
    world.say("football shoes size 43")
    question = world.add("shoe-1", text="add it", options=["42", "44"], language="en")
    assert question["question"].startswith("Size 43 isn't available for this product.")
    assert world.selected() == []


@MODES
def test_a_nearby_size_is_never_picked_for_trousers_either(retrieval):
    world = World(retrieval)
    world.add("trousers-1", constraints={"size": "32"})
    question = world.add("trousers-1", options=["30", "34", "36"])
    assert question is not None and question["question"].startswith("المقاس 32")
    assert world.selected()[-1] == (1, "32")  # only the first add selected anything


# --- A named person ----------------------------------------------------------------------


@MODES
def test_a_named_persons_size_is_used_for_this_request_only_and_the_note_says_so(retrieval):
    world = World(retrieval, *search_replies(retrieval, "41", who="named_person"))
    world.say("عايز جزمة لأحمد مقاس 41")
    assert world.remembered() == {}
    done = world.done()[-1]
    assert "استخدمت المقاس ده للطلب ده بس ومش هحفظه" in done
    # Nothing was stored for the named person, nor for the Shopper.
    question = world.add("shoe-1")
    assert question is not None and world.selected() == []


@MODES
def test_the_not_saved_note_is_english_for_an_english_shopper(retrieval):
    world = World(retrieval, *search_replies(retrieval, "41", who="named_person", language="en"))
    world.say("shoes for Ahmed, size 41")
    assert "I used that size for this request only and didn't save it." in world.done()[-1]
    assert world.remembered() == {}


@MODES
def test_an_add_for_a_named_person_uses_the_size_said_and_does_not_save_it(retrieval):
    world = World(retrieval)
    world.add(
        "shoe-1", constraints={"size": "41"}, beneficiary="named_person", options=["41", "42"]
    )
    assert world.selected() == [(1, "41")]
    assert "ومش هحفظه" in world.done()[-1]
    assert world.remembered() == {}


@MODES
def test_a_named_person_never_reads_a_stored_size(retrieval):
    world = world_with_size(retrieval, "43")
    question = world.add("shoe-1", beneficiary="named_person")
    assert question is not None and world.selected() == []


# --- The decision's beneficiary ----------------------------------------------------------


def test_the_decision_beneficiary_reaches_the_store_without_a_model_written_intent_field():
    world = World(True, *search_replies(True, "40", who="brother"))
    world.say("for my brother, size 40")
    assert world.remembered() == {("brother", "shoe"): "40"}


def test_a_search_size_given_only_as_a_search_predicate_is_remembered_too():
    replies = search_replies(True, "43")
    replies[0]["query"] = {
        "query": "shoes",
        "predicates": [{"field": "size", "op": "eq", "value": "43"}],
    }
    replies[1]["constraints"] = {"category": "shoes"}
    world = World(True, *replies)
    world.say("جزمة مقاسي 43")
    assert world.remembered() == {("me", "shoe"): "43"}


# --- Privacy -----------------------------------------------------------------------------


def test_no_size_person_or_message_text_reaches_any_record_including_plan_records():
    sink = MemorySink()
    secret_text = "عايز جزمة لاخويا حسام مقاس 47 وبعدين افتح السلة"
    replies = search_replies(True, "47", who="brother")
    replies[0].update(first_step="عايز جزمة لاخويا حسام مقاس 47", remaining_steps=["افتح السلة"])
    navigate = {
        "v": 10,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "intent": "navigate",
        "constraints": {"target": "cart"},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
    }
    world = World(True, *replies, navigate, sink=sink)
    world.say(secret_text)
    # Step two (open the cart) is the plan's pending action; finishing it ends the plan.
    world.page = {**home_snapshot(), "url": "http://localhost:4000/cart", "elements": []}
    world.report(world.last_action(), "navigated")
    assert world.remembered() == {("brother", "shoe"): "47"}
    world.add("shoe-1", text="ضيفها لاخويا", options=["46", "47"], beneficiary="brother")
    assert world.selected()[-1] == (1, "47")
    assert any(r["event"].startswith("plan_") for r in sink.records)
    dumped = json.dumps(sink.records, ensure_ascii=False)
    for private in (
        '"47"',
        "حسام",
        "لاخويا",
        "brother",
        "named_person",
        "ضفتها",
        "افتح السلة",
        "عايز جزمة",
        "remembered",
    ):
        assert private not in dumped, private
    assert not {"size", "person", "beneficiary", "text"} & {k for r in sink.records for k in r}


def test_the_session_state_endpoint_does_not_expose_remembered_sizes():
    world = world_with_size(True, "43")
    world.add("shoe-1")
    state = world.client.get(f"/sessions/{world.sid}/state", params={"tab_id": "tab-1"})
    assert state.status_code == 200
    assert set(state.json()) <= {
        "session_id",
        "lease",
        "event_cursor",
        "conversation",
        "requires_reconciliation",
        "plan",
        "task",
    }
    text = json.dumps({k: v for k, v in state.json().items() if k != "conversation"})
    assert "remembered" not in text and "product_kinds" not in text and "shoe" not in text
    for event in world.events():
        assert "remembered" not in json.dumps(event, ensure_ascii=False)


def test_remembered_sizes_are_not_in_the_session_repr_and_vanish_with_the_session():
    world = world_with_size(True, "43")
    session = world.store.get(world.sid)
    assert "remembered_sizes" not in repr(session) and "product_kinds" not in repr(session)
    assert session.remembered_sizes == {("me", "shoe"): "43"}
    fresh = world.client.post("/sessions").json()["session_id"]
    assert world.store.get(fresh).remembered_sizes == {}


# --- A size the Copilot selected for someone else is not another person's size -----------


def brother_picks_32(world):
    assert world.add("trousers-1", constraints={"size": "32"}, beneficiary="brother") is None
    assert world.selected() == [(1, "32")]


@MODES
def test_a_size_selected_for_a_brother_is_not_silently_used_for_me(retrieval):
    world = World(retrieval)
    brother_picks_32(world)
    # The same page still holds 32; I have no remembered waist size.
    question = world.add("trousers-1", text="وضيفلي واحد ليا", value="32")
    assert question is not None and question["type"] == "ask_shopper"
    assert "30, 32, 34, 36" in question["question"]
    assert world.selected() == [(1, "32")]  # nothing new was selected, and no click followed
    assert len(world.done()) == 1


@MODES
def test_my_own_remembered_size_replaces_the_one_selected_for_the_brother(retrieval):
    world = World(retrieval)
    assert world.add("trousers-1", constraints={"size": "34"}) is None
    assert world.add("trousers-1", constraints={"size": "32"}, beneficiary="brother") is None
    assert world.add("trousers-1", text="وضيفلي واحد ليا", value="32") is None
    assert world.selected()[-1] == (1, "34")
    assert "ضفتها بمقاس 34 زي ما قلت" in world.done()[-1]


@MODES
def test_the_same_person_adding_again_keeps_the_size_already_on_the_page(retrieval):
    world = World(retrieval)
    brother_picks_32(world)
    assert world.add("trousers-1", text="وزود واحد", value="32", beneficiary="brother") is None
    assert world.selected() == [(1, "32")]
    assert "ضفتها بمقاس" not in world.done()[-1]


@MODES
def test_a_size_the_shopper_picked_on_the_page_is_still_used(retrieval):
    world = World(retrieval)
    assert world.add("trousers-1", value="34") is None
    assert world.selected() == []
    assert len(world.done()) == 1


@MODES
def test_a_size_selected_for_a_named_person_is_not_used_for_anyone_after(retrieval):
    world = World(retrieval)
    world.add("trousers-1", constraints={"size": "32"}, beneficiary="named_person")
    question = world.add("trousers-1", value="32", beneficiary="named_person")
    assert question is not None


# --- A size counts only when the Shopper said it -----------------------------------------


def invented(world, product_id, size, text, **intent):
    """An add whose size the model wrote but the Shopper's words do not contain."""
    reply = add_intent(product_id, constraints={"size": size}, cart_source=text, **intent)
    world.model.responses = iter([reply, *world.model.responses])
    if world.store.get(world.sid).active_task is not None:
        world.store.stop(world.sid)
    world.say(text, page_for(product_id, value=intent.pop("value", "")))
    return world.run_add()


@MODES
def test_a_size_the_model_invented_is_not_used_as_the_shoppers_size(retrieval):
    world = World(retrieval)
    brother_picks_32(world)
    page_value = {"value": "32"}
    reply = add_intent(
        "trousers-1", constraints={"size": "32"}, cart_source="وضيفلي واحد ليا أنا كمان بس كاكي"
    )
    world.model.responses = iter([reply])
    world.say("وضيفلي واحد ليا أنا كمان بس كاكي", page_for("trousers-1", **page_value))
    question = world.run_add()
    assert question is not None and "30, 32, 34, 36" in question["question"]
    assert world.selected() == [(1, "32")]
    assert len(world.done()) == 1
    assert world.remembered() == {("brother", "waist"): "32"}


@MODES
def test_an_invented_size_gives_way_to_my_remembered_size(retrieval):
    world = World(retrieval)
    assert world.add("trousers-1", constraints={"size": "34"}) is None
    question = invented(world, "trousers-1", "32", "ضيفه تاني")
    assert question is None
    assert world.selected()[-1] == (1, "34")
    assert world.remembered() == {("me", "waist"): "34"}


@pytest.mark.parametrize(
    ("size", "said", "expected"),
    [
        ("43", "عايز جزمة مقاسي ٤٣", True),
        ("43", "مقاسي ۴۳", True),
        ("43", "size 43 please", True),
        ("43", "size 143", False),
        ("43", "43.5", False),
        ("43", "ضيفها", False),
        ("L", "عايز تيشيرت لارج", True),
        ("L", "اكس لارج", False),
        ("XL", "اكس لارج", True),
        ("XXL", "دبل اكس لارج", True),
        ("XXL", "xxl", True),
        ("XS", "اكس سمول", True),
        ("S", "سمول", True),
        ("S", "I'm looking for shoes", False),
        ("M", "I'm looking", False),
        ("m", "medium please", True),
        ("l", "size L", True),
        ("L", "ladies", False),
        ("M", "ميديم", True),
        ("S", "small", True),
        ("XL", "xl", True),
    ],
)
def test_a_size_is_said_only_as_a_whole_token_in_any_of_the_shoppers_forms(size, said, expected):
    from agent.remembered_sizes import size_said

    assert size_said(size, [said]) is expected


@MODES
def test_arabic_indic_digits_in_the_shoppers_words_are_accepted(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43"))
    world.say("عايز جزمة اكسر بيها الملعب مقاسي ٤٣")
    assert world.remembered() == {("me", "shoe"): "43"}
    assert world.add("shoe-1") is None
    assert world.selected() == [(1, "43")]


@MODES
def test_a_transliterated_letter_size_is_accepted_for_an_add(retrieval):
    world = World(retrieval)
    assert world.add("shirt-1", text="ضيفه لارج", constraints={"size": "l"}) is None
    assert world.selected() == [(1, "l")]
    assert world.remembered() == {("me", "top"): "L"}


@MODES
def test_a_size_given_in_the_answer_to_the_size_question_is_accepted(retrieval):
    world = World(retrieval)
    question = world.add("trousers-1", text="ضيفه")
    assert question is not None
    page = page_for("trousers-1")
    world.page = page
    world.client.post(
        f"/sessions/{world.sid}/tasks/{question['task_id']}/answers",
        json={"question_id": question["action_id"], "text": "34", "snapshot": page},
    )
    world.run_add()
    assert world.selected() == [(1, "34")]
    assert world.remembered() == {("me", "waist"): "34"}


@MODES
def test_a_size_the_model_invented_on_a_search_turn_is_not_stored(retrieval):
    world = World(retrieval, *search_replies(retrieval, "43"))
    world.say("عايز جزمة اكسر بيها الملعب")
    assert world.remembered() == {}
