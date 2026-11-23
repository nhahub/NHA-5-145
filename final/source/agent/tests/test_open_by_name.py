"""Ticket 06 (copilot reliability, B5): open or add a product the Shopper names, in a fresh session.

Driven through the Agent's HTTP API with a scripted model. The model only marks the request
(`request_mode: "open"`) and copies the product name from the Shopper's words into
`constraints.query`; code searches the verified catalogue for products whose Arabic or English
name equals that name (normalised) and decides: exactly one -> its page opens (or the add goes
on), several -> cards and "تقصد أنهي منتج؟", none -> the normal search answer. The model never
supplies the product id on this path. Expected strings are written out literally.
"""

import json

import pytest

from agent.event_log import MemorySink
from agent.llm.intent import StructuredIntent
from agent.product_reference import product_name_tokens
from agent.tests.test_catalogue_retrieval import Reads, _recommend, _search, candidate
from agent.tests.test_multi_step_plan import intent, last_action, make_client, names, stream
from agent.tests.test_plan_failure import begin, finished, report_result
from agent.tests.test_real_task import snapshot_at
from agent.tests.test_step import home_snapshot
from agent.tests.test_this_resolution import actions, element, product_page

QUICK, QUICK_EN = "خطوة سريعة", "Quick Step"
MARATHON, MARATHON_EN = "ماراثون القاهرة", "Cairo Marathon"
WHICH_AR = "تقصد أنهي منتج؟"
WHICH_EN = "Which product do you mean?"
EXECUTE = {"kind": "execute"}
OPEN_QUICK = f"افتح {QUICK}"
ADD_QUICK = f"ضيف {QUICK} للسلة مقاس 42 أحمر"

# id -> (Arabic name, English name)
CATALOGUE = {
    "shoe-20": (QUICK, QUICK_EN),
    "shoe-21": (MARATHON, MARATHON_EN),
    "shoe-22": (MARATHON, "Cairo Marathon Pro"),
    "shoe-23": ("عداء النيل", "Nile Runner"),
}


class NamedCatalogue(Reads):
    """A lexical catalogue: a search returns the products sharing a word with the query.

    A query that shares no word falls back to generic products, like a broad search would.
    """

    def __init__(self, products=None):
        super().__init__()
        self.searches = []
        self.products = products or CATALOGUE

    def _named(self, key):
        item = candidate(key)
        names_ = self.products.get(key, ("قطعة", "Piece"))
        product = item.product.model_copy(update={"nameAr": names_[0], "nameEn": names_[1]})
        return item.model_copy(update={"product": product})

    async def search(self, query):
        result = await super().search(query)
        self.searches.append(query.query)
        words = set(product_name_tokens(query.query).split())
        found = [
            key
            for key, pair in self.products.items()
            if words & set(product_name_tokens(" ".join(pair)).split())
        ]
        keys = found or [c.product.id for c in result.candidates]
        return result.model_copy(update={"candidates": [self._named(k) for k in keys]})

    async def details(self, query):
        result = await super().details(query)
        return result.model_copy(
            update={"products": [self._named(p.product.id) for p in result.products]}
        )


def open_intent(name, message, **overrides) -> dict:
    """The interpreter's reading of "open <name>": a marker and the name, never an id."""
    return intent(
        "cart",
        intent="find_products",
        constraints={"query": name},
        request_mode="open",
        **overrides,
    ) | {"navigation_source": message}


def add_intent(name, message, **overrides) -> dict:
    return intent(
        "cart",
        intent="cart_edit",
        constraints={"query": name, "size": "42", "color": "red"},
        request_mode="open",
        cart_operation="add",
        cart_source=message,
        cart_quantity=1,
        cart_quantity_mode="set",
        **overrides,
    )


def retrieval_client(*replies, sink=None, catalogue=None):
    catalogue = catalogue or NamedCatalogue()
    client, model = make_client(
        *replies, sink=sink, catalogue_client=catalogue, catalogue_retrieval_enabled=True
    )
    return client, model, catalogue


def cards(events):
    return [
        c["id"] for e in events if e["event"] == "suggestions" for c in e["data"]["suggestions"]
    ]


def card_names(events):
    return [
        c["name"] for e in events if e["event"] == "suggestions" for c in e["data"]["suggestions"]
    ]


def summary(events):
    return [e["data"]["summary"] for e in events if e["event"] == "done"]


def moves(events):
    return [a for a in actions(events) if a["type"] in {"navigate", "click"}]


def product_with_size(slug, name):
    return snapshot_at(
        f"/p/{slug}",
        element(1, "heading", name, level=1),
        element(2, "combobox", "المقاس", value="43", options=["41", "42", "43"]),
        element(3, "combobox", "اللون", value="blue", options=["blue", "red"]),
        element(4, "textbox", "الكمية", value="1"),
        element(5, "button", "أضف إلى السلة", form_action="/cart/items"),
    )


# --- Open ---------------------------------------------------------------------------------


def test_a_fresh_session_opens_the_one_product_with_that_exact_name():
    client, model, catalogue = retrieval_client(EXECUTE, open_intent(QUICK, OPEN_QUICK))
    session_id = begin(client, OPEN_QUICK, home_snapshot())
    events = stream(client, session_id)

    assert last_action(events) == {**last_action(events), "type": "navigate", "url": "/p/shoe-20"}
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert cards(events) == []
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 2  # the routing decision and the interpreter, nothing else
    assert catalogue.searches == [QUICK]


def test_the_english_name_opens_the_product_too():
    reply = open_intent(QUICK_EN, "open Quick Step", language="en", dialect="english")
    client, _, _ = retrieval_client(EXECUTE, reply)
    session_id = begin(client, "open Quick Step", home_snapshot())
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-20"


@pytest.mark.parametrize(
    ("said", "name"),
    [
        ("افتح خطوه سريعه", "خطوه سريعه"),  # ة -> ه
        ("افتح الخطوة السريعة", "الخطوة السريعة"),  # the article
        ("OPEN   quick STEP", "quick   step"),  # case and whitespace
        ("افتحلي صفحة خطوة سريعة", "خطوة سريعة"),  # the name inside longer words
    ],
)
def test_spelling_variants_of_the_name_still_match(said, name):
    language = {"language": "en", "dialect": "english"} if said.isascii() else {}
    client, _, _ = retrieval_client(EXECUTE, open_intent(name, said, **language))
    session_id = begin(client, said, home_snapshot())
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-20"


def test_a_name_in_the_other_language_is_still_named_so_no_did_you_mean_question():
    # Ticket 08: an Arabic reply naming the product by its English name is a named product.
    said = f"افتح {QUICK_EN}"
    client, _, _ = retrieval_client(EXECUTE, open_intent(QUICK_EN, said))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    assert "ask_shopper" not in [a["type"] for a in actions(events)]


def test_several_products_with_the_name_give_cards_and_the_question_and_open_nothing():
    said = f"افتح {MARATHON}"
    client, model, _ = retrieval_client(EXECUTE, open_intent(MARATHON, said))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)

    assert cards(events) == ["shoe-21", "shoe-22"]
    assert card_names(events) == [f"{MARATHON} / {MARATHON_EN}", f"{MARATHON} / Cairo Marathon Pro"]
    assert summary(events) == [WHICH_AR]
    assert moves(events) == []
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 2


def test_the_question_is_english_for_an_english_shopper():
    twins = CATALOGUE | {"shoe-22": (MARATHON, MARATHON_EN)}
    reply = open_intent(MARATHON_EN, "open Cairo Marathon", language="en", dialect="english")
    client, _, _ = retrieval_client(EXECUTE, reply, catalogue=NamedCatalogue(twins))
    session_id = begin(client, "open Cairo Marathon", home_snapshot())
    events = stream(client, session_id)
    assert summary(events) == [WHICH_EN]
    assert cards(events) == ["shoe-21", "shoe-22"]
    assert moves(events) == []


def test_only_the_english_name_decides_when_the_arabic_names_are_shared():
    reply = open_intent(MARATHON_EN, "open Cairo Marathon", language="en", dialect="english")
    client, _, _ = retrieval_client(EXECUTE, reply)
    session_id = begin(client, "open Cairo Marathon", home_snapshot())
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-21"


def test_choosing_one_of_the_cards_by_name_then_opens_it():
    said = f"افتح {MARATHON}"
    follow = "افتح Cairo Marathon Pro"
    client, _, _ = retrieval_client(
        EXECUTE,
        open_intent(MARATHON, said),
        intent("cart", intent="open_product", constraints={}, product_id="shoe-22")
        | {"navigation_source": follow},
    )
    session_id = begin(client, said, home_snapshot())
    stream(client, session_id)
    assert (
        client.post(
            f"/sessions/{session_id}/messages", json={"text": follow, "snapshot": home_snapshot()}
        ).status_code
        == 202
    )
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-22"
    assert "ask_shopper" not in [a["type"] for a in actions(events)]


def test_no_exact_name_match_gives_the_normal_search_answer():
    said = "افتح بوت الجبل"
    client, model, catalogue = retrieval_client(
        EXECUTE, open_intent("بوت الجبل", said), _search("mountain boots"), _recommend("p-1")
    )
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)

    assert moves(events) == []
    assert cards(events) == ["p-1"]
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert not [e for e in events if e["event"] == "error"]
    # The routing decision, the interpreter, then the search and the recommendation.
    assert len(model.requests) == 4
    assert catalogue.searches[0] == "بوت الجبل"


def test_a_partial_name_is_not_an_exact_match():
    said = "افتح خطوة"
    client, _, _ = retrieval_client(
        EXECUTE, open_intent("خطوة", said), _search("step"), _recommend("shoe-20")
    )
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert moves(events) == []
    assert cards(events) == ["shoe-20"]


def test_a_name_the_shopper_did_not_say_is_not_resolved():
    said = "افتح الجزمة الجديدة"
    client, _, catalogue = retrieval_client(
        EXECUTE, open_intent(QUICK, said), _search("new shoes"), _recommend("p-1")
    )
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert moves(events) == []
    assert cards(events) == ["p-1"]
    assert catalogue.searches == ["new shoes"]  # code never looked the model's wording up


def test_the_marker_in_a_plan_opens_the_product_and_the_next_step_still_runs():
    said = f"{OPEN_QUICK} وبعدين افتح الدفع"
    first = open_intent(
        QUICK, OPEN_QUICK, first_step=OPEN_QUICK, remaining_steps=["وبعدين افتح الدفع"]
    )
    client, _, _ = retrieval_client(EXECUTE, first, intent("checkout"))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    report_result(client, session_id, events, product_page("shoe-20", QUICK))
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/checkout"
    report_result(client, session_id, events, snapshot_at("/checkout"))
    assert finished(stream(client, session_id))["outcome"] == "done"


def test_several_matches_inside_a_plan_pause_it_with_the_names_as_options():
    said = f"افتح {MARATHON} وبعدين افتح الدفع"
    first = open_intent(
        MARATHON, f"افتح {MARATHON}", first_step=f"افتح {MARATHON}", remaining_steps=["افتح الدفع"]
    )
    client, _, _ = retrieval_client(EXECUTE, first)
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    asked = last_action(events)
    assert asked["type"] == "ask_shopper"
    assert asked["question"] == WHICH_AR
    assert asked["options"] == [f"{MARATHON} / {MARATHON_EN}", f"{MARATHON} / Cairo Marathon Pro"]
    assert "plan_paused" in names(events)
    assert moves(events) == []


# --- Known products keep the existing path ------------------------------------------------


def test_a_known_product_still_opens_through_open_product_with_no_catalogue_lookup():
    links = [element(10, "link", QUICK, href="/p/shoe-20", group=f"{QUICK} / {QUICK_EN}")]
    page = {**home_snapshot(), "elements": links}
    reply = intent("cart", intent="open_product", constraints={}, product_id="shoe-20") | {
        "navigation_source": OPEN_QUICK
    }
    client, model, catalogue = retrieval_client(reply)
    session_id = begin(client, OPEN_QUICK, page)
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    assert len(model.requests) == 1
    assert catalogue.searches == []


# --- Add by name (added scope) --------------------------------------------------------------


def test_adding_a_named_unknown_product_opens_its_page_and_goes_on_to_add_it():
    client, model, catalogue = retrieval_client(EXECUTE, add_intent(QUICK, ADD_QUICK))
    session_id = begin(client, ADD_QUICK, home_snapshot())
    events = stream(client, session_id)

    assert last_action(events)["url"] == "/p/shoe-20"
    assert "ask_shopper" not in [a["type"] for a in actions(events)]
    assert len(model.requests) == 2
    assert catalogue.searches == [QUICK]
    report_result(client, session_id, events, product_with_size("shoe-20", QUICK))
    follow = stream(client, session_id)
    nxt = last_action(follow)
    assert nxt["type"] in {"select", "click", "type"}
    assert nxt["type"] != "ask_shopper"


def test_adding_with_several_name_matches_gives_cards_and_the_question():
    said = f"ضيف {MARATHON} للسلة"
    client, _, _ = retrieval_client(EXECUTE, add_intent(MARATHON, said))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert cards(events) == ["shoe-21", "shoe-22"]
    assert summary(events) == [WHICH_AR]
    assert moves(events) == []


def test_adding_a_name_with_no_match_gives_the_normal_search_answer():
    said = "ضيف بوت الجبل للسلة"
    client, _, _ = retrieval_client(
        EXECUTE, add_intent("بوت الجبل", said), _search("mountain boots"), _recommend("p-1")
    )
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert moves(events) == []
    assert cards(events) == ["p-1"]


# --- Privacy ----------------------------------------------------------------------------------


def test_no_event_record_carries_a_product_name_id_or_the_shoppers_words():
    sink = MemorySink()
    client, _, _ = retrieval_client(EXECUTE, open_intent(QUICK, OPEN_QUICK), sink=sink)
    session_id = begin(client, OPEN_QUICK, home_snapshot())
    stream(client, session_id)
    text = json.dumps(sink.records, ensure_ascii=False)
    for secret in (QUICK, QUICK_EN, "shoe-20", OPEN_QUICK):
        assert secret not in text


# --- The marker is normalised, never refused (live hotfix) ----------------------------------------


def test_adding_a_named_product_while_another_products_page_is_open_adds_the_named_one():
    # Live: on the Cairo Marathon page the model marked the add as open and also set the page's
    # product_id. The id is dropped; the Shopper's words decide, so Quick Step is added.
    page = product_with_size("shoe-21", MARATHON)
    reply = add_intent(QUICK, ADD_QUICK) | {"product_id": "shoe-21"}
    client, model, _ = retrieval_client(reply)
    session_id = begin(client, ADD_QUICK, page)
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 1  # no repair round, no exhausted fallback


def test_a_remove_marked_open_is_an_ordinary_remove():
    cart = snapshot_at(
        "/cart",
        element(1, "link", MARATHON, href="/p/shoe-21", group=f"{MARATHON} — 43 — أزرق"),
        element(2, "button", "حذف", form_action="/cart/remove", group=f"{MARATHON} — 43 — أزرق"),
    )
    said = "ما تشيلش ماراثون القاهرة احذف خطوة سريعة بس"
    reply = intent(
        "cart",
        intent="cart_edit",
        constraints={"query": QUICK},
        request_mode="open",
        cart_operation="remove",
        cart_target_id=2,
        cart_source=said,
    )
    client, model, catalogue = retrieval_client(reply)
    session_id = begin(client, said, cart)
    events = stream(client, session_id)
    assert last_action(events)["type"] == "click"
    assert last_action(events)["id"] == 2
    assert catalogue.searches == []
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 1


@pytest.mark.parametrize(
    ("changes", "mode", "product_id", "query"),
    [
        # open on an intent that cannot be an open: back to browse, the query goes with it
        (
            {"intent": "navigate", "constraints": {"query": QUICK, "target": "cart"}},
            "browse",
            None,
            None,
        ),
        (
            {"intent": "open_product", "constraints": {"query": QUICK}, "product_id": "shoe-20"},
            "browse",
            "shoe-20",
            None,
        ),
        # a name and an id: the id goes, the name stays for code to resolve
        (
            {
                "intent": "cart_edit",
                "cart_operation": "add",
                "constraints": {"query": QUICK},
                "product_id": "shoe-21",
            },
            "open",
            None,
            QUICK,
        ),
        ({"constraints": {"query": QUICK}, "product_id": "shoe-21"}, "open", None, QUICK),
        # no name: nothing to resolve, the id path stays
        (
            {
                "intent": "cart_edit",
                "cart_operation": "add",
                "constraints": {},
                "product_id": "shoe-21",
            },
            "browse",
            "shoe-21",
            None,
        ),
        ({"v": 9}, "browse", None, QUICK),
    ],
)
def test_the_open_marker_is_normalised_not_refused(changes, mode, product_id, query):
    extra = {"cart_source": "x"} if changes.get("intent") == "cart_edit" else {}
    parsed = StructuredIntent.model_validate(_v10(request_mode="open") | extra | changes)
    assert (parsed.request_mode, parsed.product_id, parsed.constraints.query) == (
        mode,
        product_id,
        query,
    )


# --- A model-chosen product the Shopper's words contradict (live hotfix, wrong-product add) -----

NILE_RUNNER = "عداء النيل"


def chosen_add(product_id, constraints=None, **overrides) -> dict:
    """The model adds the product it picked by id (the open page's), no name marker."""
    return intent(
        "cart",
        intent="cart_edit",
        constraints=constraints or {"size": "42", "color": "red"},
        cart_operation="add",
        cart_source=overrides.pop("source", ADD_QUICK),
        cart_quantity=1,
        cart_quantity_mode="set",
        product_id=product_id,
        **overrides,
    )


def test_an_add_naming_another_product_than_the_open_page_adds_the_named_one():
    # Live: on product A's page the model returned A's id for "add Quick Step"; ticket 08
    # exempts the open page, so A would have been added. Code sees B's name and switches.
    client, model, catalogue = retrieval_client(chosen_add("shoe-23"))
    session_id = begin(client, ADD_QUICK, product_with_size("shoe-23", NILE_RUNNER))
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"  # B's page, not a form on A's page
    assert [a["type"] for a in actions(events)] == ["navigate"]
    assert not [e for e in events if e["event"] == "error"]
    assert len(model.requests) == 1
    assert catalogue.searches == [ADD_QUICK]
    # On B's page the requested size and colour apply to B.
    report_result(client, session_id, events, product_with_size("shoe-20", QUICK))
    follow = last_action(stream(client, session_id))
    assert follow["type"] in {"select", "type", "click"}


def test_an_open_naming_another_product_than_the_chosen_one_opens_the_named_one():
    reply = intent("cart", intent="open_product", constraints={}, product_id="shoe-23") | {
        "navigation_source": OPEN_QUICK
    }
    client, _, _ = retrieval_client(reply)
    session_id = begin(client, OPEN_QUICK, product_with_size("shoe-23", NILE_RUNNER))
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    assert "ask_shopper" not in [a["type"] for a in actions(events)]


def test_an_add_naming_only_the_open_pages_product_is_unchanged():
    said = f"ضيف {NILE_RUNNER} للسلة مقاس 42"
    client, model, _ = retrieval_client(chosen_add("shoe-23", source=said))
    session_id = begin(client, said, product_with_size("shoe-23", NILE_RUNNER))
    events = stream(client, session_id)
    assert last_action(events)["type"] in {"select", "click", "type"}
    assert "navigate" not in [a["type"] for a in actions(events)]
    assert len(model.requests) == 1


def test_an_add_naming_the_chosen_product_and_another_is_unchanged():
    said = f"ضيف {NILE_RUNNER} مع {QUICK} للسلة"
    client, _, _ = retrieval_client(chosen_add("shoe-23", source=said))
    session_id = begin(client, said, product_with_size("shoe-23", NILE_RUNNER))
    events = stream(client, session_id)
    assert "navigate" not in [a["type"] for a in actions(events)]
    assert "ask_shopper" not in [a["type"] for a in actions(events)]


def test_an_add_with_no_name_on_the_open_page_is_unchanged():
    said = "ضيفه للسلة مقاس 42"
    client, model, catalogue = retrieval_client(chosen_add("shoe-23", source=said))
    session_id = begin(client, said, product_with_size("shoe-23", NILE_RUNNER))
    events = stream(client, session_id)
    assert last_action(events)["type"] in {"select", "click", "type"}
    assert "navigate" not in [a["type"] for a in actions(events)]
    assert len(model.requests) == 1


def test_an_add_naming_two_other_products_asks_which_and_does_nothing():
    said = f"ضيف {QUICK} و {NILE_RUNNER} للسلة"
    client, _, _ = retrieval_client(chosen_add("shoe-21", source=said))
    session_id = begin(client, said, product_with_size("shoe-21", MARATHON))
    events = stream(client, session_id)
    assert cards(events) == ["shoe-20", "shoe-23"]
    assert summary(events) == [WHICH_AR]
    assert moves(events) == []


def test_a_product_the_shopper_confirmed_is_not_second_guessed():
    # "Yes" to "تقصد X؟" names nothing in the message, but it is the Shopper's own choice.
    from agent.named_product import needs_name_check
    from agent.product_confirmation import CONFIRMED_KEY

    parsed = StructuredIntent.model_validate(chosen_add("shoe-23"))
    assert needs_name_check(parsed, {})
    assert not needs_name_check(parsed, {CONFIRMED_KEY: "shoe-23"})
    assert not needs_name_check(
        parsed.model_copy(update={"refers_to_this": True}),
        {"_this_candidates": [{"id": "shoe-23"}]},
    )


def test_the_switch_leaves_no_names_in_event_records():
    sink = MemorySink()
    client, _, _ = retrieval_client(chosen_add("shoe-23"), sink=sink)
    session_id = begin(client, ADD_QUICK, product_with_size("shoe-23", NILE_RUNNER))
    stream(client, session_id)
    text = json.dumps(sink.records, ensure_ascii=False)
    for secret in (QUICK, QUICK_EN, NILE_RUNNER, "shoe-20", "shoe-23", ADD_QUICK):
        assert secret not in text


class NoCatalogueReads(NamedCatalogue):
    """Any catalogue search is a failure (the release smoke's catalogue client). The size-kind
    details read an add makes of its own product is not a name lookup and stays allowed."""

    async def search(self, query):
        raise AssertionError("Unexpected catalogue search")


def test_an_answer_to_a_variant_question_runs_no_name_check_and_no_catalogue_read():
    # The product was settled when the question was asked; "اسود" names no product, and the
    # check must not look it up (release smoke: "Unexpected catalogue search").
    from agent.tests.test_confirm_unnamed_product import answer, question_of

    said = "ضيفه للسلة"  # "this": code resolves the open page's product, no name needed
    page = snapshot_at(
        "/p/shoe-23",
        element(1, "heading", NILE_RUNNER, level=1),
        element(2, "combobox", "المقاس", value="43", options=["42", "43"]),
        element(3, "combobox", "اللون", value="", options=["blue", "black", "white"]),
        element(4, "textbox", "الكمية", value="1"),
        element(5, "button", "أضف إلى السلة", form_action="/cart/items"),
    )
    first = chosen_add("shoe-23", source=said, constraints={"size": "43"}, refers_to_this=True)
    second = chosen_add("shoe-23", source="اسود", constraints={"size": "43", "color": "black"})
    client, model, _ = retrieval_client(first, second, catalogue=NoCatalogueReads())
    session_id = begin(client, said, page)
    question = question_of(stream(client, session_id))
    assert answer(client, session_id, question, "اسود", page).status_code == 202
    events = stream(client, session_id)
    assert not [e for e in events if e["event"] == "error"]
    assert last_action(events)["type"] in {"select", "click", "type"}
    assert len(model.requests) == 2


# --- The legacy (non-retrieval) interpreter path -----------------------------------------------


class Snapshot:
    """The catalogue reader of the non-retrieval path: every product at once."""

    async def read(self):
        from agent.catalogue import CatalogueSnapshot

        def product(key, name_ar, name_en):
            return {
                "id": key,
                "category": "shoes",
                "name_ar": name_ar,
                "name_en": name_en,
                "product_type": "running",
                "price": {"amount": "100", "currency": "EGP"},
                "sizes": ["42"],
                "colors": ["red"],
                "available": True,
                "added_at": "2026-01-01",
                "features": [],
                "suitable_for": [],
                "wear_position": None,
            }

        return CatalogueSnapshot.model_validate(
            {
                "v": 1,
                "currency": "EGP",
                "products": [product(k, *pair) for k, pair in CATALOGUE.items()],
            }
        )


def legacy_client(*replies):
    return make_client(*replies, catalogue_reader=Snapshot(), catalogue_retrieval_enabled=False)


def test_without_retrieval_one_exact_match_opens_the_page():
    client, model = legacy_client(open_intent(QUICK, OPEN_QUICK))
    session_id = begin(client, OPEN_QUICK, home_snapshot())
    events = stream(client, session_id)
    assert last_action(events)["url"] == "/p/shoe-20"
    assert len(model.requests) == 1


def test_without_retrieval_several_matches_give_cards_and_the_question():
    said = f"افتح {MARATHON}"
    client, _ = legacy_client(open_intent(MARATHON, said))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert cards(events) == ["shoe-21", "shoe-22"]
    assert summary(events) == [WHICH_AR]
    assert moves(events) == []


def test_without_retrieval_an_add_by_name_opens_the_page():
    client, _ = legacy_client(add_intent(QUICK, ADD_QUICK))
    session_id = begin(client, ADD_QUICK, home_snapshot())
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-20"


def test_without_retrieval_an_add_naming_another_product_than_the_open_page_adds_the_named_one():
    client, _ = legacy_client(chosen_add("shoe-23"))
    session_id = begin(client, ADD_QUICK, product_with_size("shoe-23", NILE_RUNNER))
    assert last_action(stream(client, session_id))["url"] == "/p/shoe-20"


def test_without_retrieval_no_match_asks_the_usual_category_question():
    said = "افتح بوت الجبل"
    client, _ = legacy_client(open_intent("بوت الجبل", said))
    session_id = begin(client, said, home_snapshot())
    events = stream(client, session_id)
    assert moves(events) == []
    assert last_action(events)["type"] == "ask_shopper"


# --- The intent contract ---------------------------------------------------------------------


def _v10(**changes) -> dict:
    return intent("cart", intent="find_products", constraints={"query": QUICK}, **changes)


def test_the_open_mode_is_part_of_structured_intent_v10():
    parsed = StructuredIntent.model_validate(_v10(request_mode="open"))
    assert parsed.request_mode == "open"
    assert parsed.constraints.query == QUICK
    assert not parsed.catalogue_discovery  # it is not a search request


def test_the_prompts_describe_the_open_mode_and_their_versions_are_bumped():
    from agent.catalogue_retrieval import RetrievalBudget, _request
    from agent.llm import PROMPT_VERSION, build_intent_request
    from agent.storefront import load_storefront_definition

    storefront = load_storefront_definition()
    interpreter = build_intent_request(
        OPEN_QUICK, storefront=storefront, resolved_state={}, pending_clarification=None
    )
    decision = _request(OPEN_QUICK, {}, None, storefront, [], None, RetrievalBudget())
    assert PROMPT_VERSION == "intent-v39" == interpreter.prompt_version
    assert decision.prompt_version == "catalogue-decision-v11"
    assert "request_mode=open" in interpreter.system
    # An add of a named product is never read as an open, with or without size or colour.
    assert "NEVER find_products" in interpreter.system
    assert "request_mode=open" in decision.system
    assert "execute" in decision.system.split("request_mode=open", 1)[1][:400]
