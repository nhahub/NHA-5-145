"""Ticket 04: colours are named in the Shopper's language and normalised before the check.

Driven through the Agent's HTTP API with a scripted model (prior art: test_cart_replace,
test_conditions). Expected strings are written out literally.
"""

from agent.cart import plan_cart_edit
from agent.llm.intent import StructuredIntent
from agent.storefront import colour_label, load_storefront_definition
from agent.tests.test_cart_replace import SIZE, actions, errors, kinds, replace_intent, swap
from agent.tests.test_cart_task import snapshot as product_snapshot
from agent.tests.test_conditions import Shelf, assert_not_added, says, when
from agent.tests.test_multi_step_plan import last_action

STOREFRONT = load_storefront_definition()


def test_every_storefront_colour_has_an_arabic_label():
    for key in STOREFRONT.vocabulary.colors:
        label = colour_label(key, "ar", STOREFRONT)
        assert label != key and any("؀" <= ch <= "ۿ" for ch in label), key
    assert colour_label("yellow", "ar", STOREFRONT) == "أصفر"
    assert colour_label("yellow", "ar", STOREFRONT, definite=True) == "الأصفر"


def test_the_helper_leaves_english_and_unknown_values_alone():
    assert colour_label("yellow", "en", STOREFRONT) == "yellow"
    assert colour_label("أصفر", "en", STOREFRONT) == "yellow"
    assert colour_label("Black", "en", STOREFRONT) == "Black"
    assert colour_label("mauve", "ar", STOREFRONT) == "mauve"
    assert colour_label("mauve", "ar", STOREFRONT, definite=True) == "mauve"


def test_the_swap_unavailable_question_names_colours_in_arabic():
    shelf = Shelf(colors=("blue", "white"), sizes=("42", SIZE))
    _, _, _, events = swap(shelf)
    assert last_action(events)["question"] == (
        "اللون الأصفر مش متاح للمنتج ده في المقاس XXL. الألوان المتاحة: أبيض. تحب أغيّره لأنهي لون؟"
    )


def test_the_swap_questions_without_a_colour_and_with_the_same_colour_use_arabic_names():
    shelf = Shelf(colors=("blue", "yellow", "black"), sizes=("42", SIZE))
    _, _, _, events = swap(shelf, replace_intent(constraints={}))
    assert last_action(events)["question"] == ("تحب تغيّره للون إيه؟ الألوان المتاحة: أصفر, أسود.")
    _, _, _, events = swap(shelf, replace_intent(constraints={"color": "blue"}))
    assert last_action(events)["question"] == (
        "اللون الأزرق هو اللي في السلة أصلاً. تحب تغيّره للون إيه؟ الألوان المتاحة: أصفر, أسود."
    )


def test_the_english_swap_question_keeps_english_names():
    shelf = Shelf(colors=("blue", "black"), sizes=("42", SIZE))
    _, _, _, events = swap(
        shelf,
        replace_intent(language="en", dialect="english", cart_source="make it yellow"),
        text="make it yellow",
    )
    assert last_action(events)["question"] == (
        "yellow isn't available for this product in size XXL. Available colours: black. "
        "Which colour would you like?"
    )


def test_the_swap_summary_names_colours_in_arabic():
    from agent.swap import summary

    swap_state = {
        "name_ar": "ممشى النيل",
        "name_en": "Nile walker",
        "size": "XXL",
        "new_color": "yellow",
        "old_color": "red",
    }
    assert summary(swap_state, "ar", STOREFRONT) == (
        "غيّرت اللون: ضفت ممشى النيل مقاس XXL باللون الأصفر وشلت اللي باللون الأحمر."
    )
    assert summary(swap_state, "en", STOREFRONT) == (
        "Changed the colour: added Nile walker in size XXL in yellow and removed the red one."
    )


def test_a_colour_condition_reason_names_the_colour_in_arabic():
    _, _, _, events = says("ضيفها لو جاية أصفر", when("colour_exists", "yellow"), Shelf(), False)
    assert_not_added(events, "ما ضفتهاش: اللون أصفر مش موجود في المنتج ده.")


def test_a_swap_colour_with_a_leading_space_and_arabic_is_normalised_to_the_key():
    shelf = Shelf(colors=("blue", "yellow"), sizes=("42", SIZE))
    client, _, session_id, events = swap(shelf, replace_intent(constraints={"color": " أصفر"}))
    assert kinds(events) == ["navigate"] and not errors(events)
    assert actions(events)[0]["url"].startswith("/p/")


def test_an_unknown_colour_is_still_refused():
    _, model, _, events = swap(
        None,
        replace_intent(constraints={"color": "mauve"}),
        replace_intent(constraints={"color": "mauve"}),
    )
    assert "navigate" not in kinds(events)
    assert len(model.requests) == 2


def test_a_replace_reading_with_a_stray_quantity_mode_is_accepted_with_quantity_cleared():
    shelf = Shelf(colors=("blue", "yellow"), sizes=("42", SIZE))
    _, model, _, events = swap(
        shelf, replace_intent(cart_quantity=2, cart_quantity_mode="increase")
    )
    assert kinds(events) == ["navigate"] and not errors(events)
    assert len(model.requests) == 1


def _add_intent(colour):
    return StructuredIntent.model_validate(
        {
            "v": 8,
            "language": "ar",
            "dialect": "egyptian_arabic",
            "intent": "cart_edit",
            "cart_operation": "add",
            "cart_source": "ضيفه",
            "cart_target_id": 4,
            "constraints": {"color": colour},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )


def test_the_add_option_question_maps_known_colours_and_keeps_unknown_ones():
    page = product_snapshot()
    for element in page.elements:
        if element.name == "اللون":
            element.value, element.options = "", ["white", "mauve"]
    actions_ = plan_cart_edit(_add_intent("yellow"), page, "task-test", 1, storefront=STOREFRONT)
    assert actions_[0].question == "محتاج اختيارًا متاحًا لحقل اللون. المتاح: أبيض, mauve. تختار إيه؟"
    assert actions_[0].options == []


def test_catalogue_advice_names_every_storefront_colour_in_arabic():
    from agent.catalogue import _fact

    for key in STOREFRONT.vocabulary.colors:
        assert _fact(key, True) == colour_label(key, "ar", STOREFRONT)
