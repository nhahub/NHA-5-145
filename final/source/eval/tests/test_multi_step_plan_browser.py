"""Ticket 05 browser cases: a two-step message becomes a visible, ticking checklist.

The model is scripted (no network); see eval/plan_fixture_app.py. The model's own words for
each step come from the script, so these cases test plan execution, not language accuracy.
"""

from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.plan_fixture_app import (
    ACCOUNT_STEP,
    ADD_IF_UNDER_1000,
    ADD_IF_UNDER_2000,
    ADD_NO_SIZE,
    ADD_STEP,
    ADD_STEP_2,
    ADD_THEN_CART,
    ADD_THEN_CLEAR,
    ADD_THEN_PANTS,
    ADD_THEN_TOO_MANY_THEN_CART,
    ADD_THIS,
    ADVICE,
    CART_STEP,
    CLEAR_STEP,
    FIND_TWO,
    OPEN_BY_NAME,
    OPEN_CLEAR_ACCOUNT,
    OPEN_UNNAMED,
    PANTS_STEP,
    SWAP_TO_RED,
    SWAP_TO_YELLOW,
    TOO_MANY_STEP,
)
from eval.services import local_services

TRACK_INPUT = """() => {
    const input = document.querySelector('#shopper-message');
    window.__inputStates = [];
    new MutationObserver(() => window.__inputStates.push(input.disabled)).observe(
        input, { attributes: true, attributeFilter: ['disabled'] }
    );
}"""


def open_product_page(page):
    browser_post(page, "http://localhost:4000/__test/reset")
    page.goto("http://localhost:4100")
    expect(page.locator("#shopper-message")).to_be_enabled()
    frame = page.frame_locator("#storefront-frame")
    frame.locator("body").evaluate("() => { location.href = '/p/shoe-01'; }")
    expect(frame.locator("#product-size")).to_be_visible()
    frame.locator("#product-size").select_option("42")
    frame.locator("#product-color").select_option("black")
    return frame


def send(page, message):
    page.evaluate(TRACK_INPUT)
    page.locator("#shopper-message").fill(message)
    page.get_by_role("button", name="إرسال", exact=True).click()


def marks(page):
    return page.locator("#plan-checklist li").evaluate_all("els => els.map(e => e.dataset.mark)")


def plan_requests(page):
    return page.request.get("http://localhost:8000/__eval/plan-requests").json()


def assert_input_stayed_disabled_until_the_plan_finished(page):
    expect(page.locator("#shopper-message")).to_be_enabled()
    states = page.evaluate("() => window.__inputStates")
    # Disabled when the plan started, enabled exactly once at the very end: never between steps.
    assert states and states[0] is True and states[-1] is False
    assert states.count(False) == 1, states


def test_two_step_sequence_shows_a_ticking_checklist_and_runs_both_steps_in_order():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            frame = open_product_page(page)
            send(page, ADD_THEN_CART)

            checklist = page.locator("#plan-checklist")
            expect(checklist).to_be_visible(timeout=15000)
            expect(checklist.locator("ol > li")).to_have_count(2)
            expect(checklist.locator("li").nth(0)).to_contain_text(ADD_STEP)
            expect(checklist.locator("li").nth(1)).to_contain_text(CART_STEP)
            expect(page.locator("#shopper-message")).to_be_disabled()

            expect(checklist.locator("li").nth(0)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            expect(checklist.locator("li").nth(1)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            assert marks(page) == ["done", "done"]

            expect(frame.get_by_role("heading", name="السلة")).to_be_visible(timeout=15000)
            assert frame.locator("body").evaluate("() => location.pathname") == "/cart"
            lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
            assert [(line["product_id"], line["quantity"]) for line in lines] == [("shoe-01", 1)]
            assert (lines[0]["size"], lines[0]["color"]) == ("42", "black")

            assert_input_stayed_disabled_until_the_plan_finished(page)

            requests = plan_requests(page)
            assert [r["message"] for r in requests] == [ADD_THEN_CART, CART_STEP]
            assert requests[0]["plan_step"] is None
            assert requests[1]["plan_step"] == {
                "position": 2,
                "of": 2,
                "earlier_steps_done": True,
            }
            # One plan only: the second step's own interpretation never makes a nested plan.
            assert page.locator("#plan-checklist ol").count() == 1
            assert page.locator("#plan-checklist li").count() == 2
        finally:
            browser.close()


def test_unrelated_pair_adds_once_then_shows_suggestions_with_retrieval_on():
    with local_services(agent_app="eval.plan_fixture_app:retrieval_app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            open_product_page(page)
            send(page, ADD_THEN_PANTS)

            checklist = page.locator("#plan-checklist")
            expect(checklist.locator("ol > li")).to_have_count(2, timeout=15000)
            expect(checklist.locator("li").nth(0)).to_contain_text(ADD_STEP_2)
            expect(checklist.locator("li").nth(1)).to_contain_text(PANTS_STEP)
            expect(checklist.locator("li").nth(0)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            expect(checklist.locator("li").nth(1)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            assert marks(page) == ["done", "done"]

            # Step 2 is a search/recommend: its suggestions are on screen.
            expect(page.get_by_text(ADVICE, exact=True)).to_be_visible()
            expect(page.locator('[data-product-id="shoe-09"]')).to_be_visible()

            lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
            assert [(line["product_id"], line["quantity"]) for line in lines] == [("shoe-01", 1)]

            assert_input_stayed_disabled_until_the_plan_finished(page)

            requests = plan_requests(page)
            # On a product page the entry point is the action interpreter: step 1 is one intent
            # call that names the steps. Step 2 is interpreted at its turn, marked position 2,
            # and its search is handed back to the catalogue decision loop (same marker).
            assert [(r["prompt"], r["message"], r["plan_step"]) for r in requests[:2]] == [
                ("intent-v39", ADD_THEN_PANTS, None),
                ("intent-v39", PANTS_STEP, {"position": 2, "of": 2, "earlier_steps_done": True}),
            ]
            decisions = requests[2:]
            # search, then recommend (its advice text rides in the decision: no advice call).
            assert [r["prompt"] for r in decisions] == ["catalogue-decision-v11"] * 2
            assert all(r["message"] == PANTS_STEP for r in decisions)
            assert all(r["plan_step"]["position"] == 2 for r in decisions)
            assert page.locator("#plan-checklist li").count() == 2
        finally:
            browser.close()


REFUSED_EDIT_REPORT = (
    "وقفت عند خطوة ماتمّتش:\n"
    f"✓ {ADD_STEP}\n"
    f"✕ {TOO_MANY_STEP} — مش متأكد إذا تعديل السلة اكتمل. راجع السلة الحالية؛ مش هكرره تلقائيًا.\n"
    f"– {CART_STEP} (اتخطّت)"
)


def test_a_refused_cart_edit_midway_stops_the_plan_reports_it_and_rolls_nothing_back():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            posts = []
            page.on(
                "request",
                lambda request: posts.append(request.url) if request.method == "POST" else None,
            )
            frame = open_product_page(page)
            send(page, ADD_THEN_TOO_MANY_THEN_CART)

            checklist = page.locator("#plan-checklist")
            expect(checklist.locator("ol > li")).to_have_count(3, timeout=15000)
            expect(checklist.locator("li").nth(0)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            # Step 1's add is in the cart and its 10-second Undo was offered.
            offered = page.request.get("http://localhost:4000/cart/state").json()["undo"]
            assert offered is not None and offered["remaining_ms"] > 0

            expect(checklist.locator("li").nth(1)).to_have_attribute(
                "data-mark", "failed", timeout=20000
            )
            expect(checklist.locator("li").nth(2)).to_have_attribute("data-mark", "skipped")
            assert marks(page) == ["done", "failed", "skipped"]

            # The report is one message in the Shopper's language; no Retry or question waits.
            expect(page.locator("#conversation li").last).to_contain_text("وقفت عند خطوة ماتمّتش")
            assert page.locator("#conversation li").last.text_content() == REFUSED_EDIT_REPORT
            expect(page.locator("#task-status")).to_have_text("وقفت عند خطوة ماتمّتش:")
            expect(page.locator("#retry-task")).to_have_count(0)
            expect(page.locator("#pending-question button")).to_have_count(0)
            expect(page.locator("#shopper-message")).to_be_enabled()

            # Nothing was rolled back and step 3 never ran: the line is still in the cart and
            # the page never went to the cart.
            lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
            assert [(line["product_id"], line["quantity"]) for line in lines] == [("shoe-01", 1)]
            assert frame.locator("body").evaluate("() => location.pathname") == "/p/shoe-01"
            assert [r["message"] for r in plan_requests(page)] == [
                ADD_THEN_TOO_MANY_THEN_CART,
                TOO_MANY_STEP,
            ]

            # No request is made after the failure.
            made = len(posts)
            page.wait_for_timeout(1500)
            assert len(posts) == made
        finally:
            browser.close()


def cart_lines(page):
    return page.request.get("http://localhost:4000/__test/cart-state").json()["lines"]


def test_add_then_clear_asks_for_confirmation_at_step_two_and_clears_only_after_confirm():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            frame = open_product_page(page)
            send(page, ADD_THEN_CLEAR)

            checklist = page.locator("#plan-checklist")
            expect(checklist.locator("ol > li")).to_have_count(2, timeout=15000)
            expect(checklist.locator("li").nth(0)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            # Step 2 waits on its own Confirmation card, offered only now, for the cart as it is.
            card = page.locator(".confirmation-card")
            expect(card).to_be_visible(timeout=15000)
            expect(card).to_contain_text("إزالة كل المنتجات من السلة الحالية")
            expect(checklist.locator("li").nth(1)).to_have_attribute("data-mark", "paused")
            expect(checklist.locator("li").nth(1).locator(".plan-state")).to_have_text("مستني ردك")
            expect(page.locator("#shopper-message")).to_be_disabled()
            assert [line["product_id"] for line in cart_lines(page)] == ["shoe-01"]

            card.get_by_role("button", name="تأكيد").click()
            expect(checklist.locator("li").nth(1)).to_have_attribute(
                "data-mark", "done", timeout=15000
            )
            assert marks(page) == ["done", "done"]
            expect(frame.get_by_role("status")).to_have_text("السلة فارغة")
            assert cart_lines(page) == []
            expect(page.locator("#conversation li").last).to_have_text(
                f"خلصت طلبك:\n✓ {ADD_NO_SIZE}\n✓ {CLEAR_STEP}"
            )
            expect(page.locator("#shopper-message")).to_be_enabled()
            assert [r["message"] for r in plan_requests(page)] == [ADD_THEN_CLEAR, CLEAR_STEP]
        finally:
            browser.close()


def test_a_guarded_step_in_the_middle_waits_for_confirm_then_step_three_runs_on_a_phone():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 375, "height": 812})
            browser_post(page, "http://localhost:4000/__test/reset")
            seeded = browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 2}]},
            )
            assert seeded.status == 204
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            frame = page.frame_locator("#storefront-frame")
            send(page, OPEN_CLEAR_ACCOUNT)

            checklist = page.locator("#plan-checklist")
            card = page.locator(".confirmation-card")
            expect(card).to_be_visible(timeout=20000)
            expect(checklist.locator("li").nth(1)).to_have_attribute("data-mark", "paused")
            assert marks(page) == ["done", "paused", "pending"]
            # On a phone the checklist does not push the Confirmation card out of view.
            expect(checklist).to_be_in_viewport()
            expect(card).to_be_in_viewport()
            expect(card.get_by_role("button", name="تأكيد")).to_be_in_viewport()
            assert len(cart_lines(page)) == 1  # nothing cleared before the Shopper confirms

            card.get_by_role("button", name="تأكيد").click()
            expect(checklist.locator("li").nth(2)).to_have_attribute(
                "data-mark", "done", timeout=20000
            )
            assert marks(page) == ["done", "done", "done"]
            assert cart_lines(page) == []
            expect(frame.locator("body")).to_be_visible()
            assert frame.locator("body").evaluate("() => location.pathname") == "/account"
            assert [r["message"] for r in plan_requests(page)] == [
                OPEN_CLEAR_ACCOUNT,
                CLEAR_STEP,
                ACCOUNT_STEP,
            ]
            expect(page.locator("#shopper-message")).to_be_enabled()
        finally:
            browser.close()


def test_an_ambiguous_this_after_two_suggestions_makes_the_copilot_ask_and_adds_nothing():
    with local_services(agent_app="eval.plan_fixture_app:retrieval_app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(page, "http://localhost:4000/__test/reset")
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            send(page, FIND_TWO)

            cards = page.locator(".suggestion-card")
            expect(cards).to_have_count(2, timeout=20000)
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            names = [cards.nth(i).locator("h2").text_content() for i in range(2)]

            send(page, ADD_THIS)
            question = page.locator("#pending-question")
            expect(question).to_contain_text("تقصد أنهي منتج؟", timeout=20000)
            options = question.locator("button")
            expect(options).to_have_count(2)
            assert [options.nth(i).text_content() for i in range(2)] == names

            # The model only said "this"; code asked instead of picking one, so nothing was
            # added and the page never left the home page.
            assert cart_lines(page) == []
            frame = page.frame_locator("#storefront-frame")
            assert frame.locator("body").evaluate("() => location.pathname") == "/"
            assert [r["message"] for r in plan_requests(page)][-1] == ADD_THIS
        finally:
            browser.close()


def test_add_it_if_it_is_under_a_price_adds_when_true_and_says_why_not_when_false():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            open_product_page(page)

            # 1450 EGP is not under 1000: nothing is clicked and the reason is on screen.
            send(page, ADD_IF_UNDER_1000)
            reason = "ما ضفتهاش: سعرها 1450 جنيه، والشرط مش متحقق."
            expect(page.locator("#conversation")).to_contain_text(reason, timeout=20000)
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            assert cart_lines(page) == []

            # It is under 2000: the add runs exactly as an unconditional add.
            send(page, ADD_IF_UNDER_2000)
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            assert [(line["product_id"], line["quantity"]) for line in cart_lines(page)] == [
                ("shoe-01", 1)
            ]
            assert [r["message"] for r in plan_requests(page)] == [
                ADD_IF_UNDER_1000,
                ADD_IF_UNDER_2000,
            ]
        finally:
            browser.close()


def seed_blue_line(page):
    browser_post(page, "http://localhost:4000/__test/reset")
    seeded = browser_post(
        page,
        "http://localhost:4000/__test/cart",
        data={"lines": [{"product_id": "shoe-12", "quantity": 3, "size": "42", "color": "blue"}]},
    )
    assert seeded.status == 204
    page.goto("http://localhost:4100")
    expect(page.locator("#shopper-message")).to_be_enabled()
    frame = page.frame_locator("#storefront-frame")
    frame.locator("body").evaluate("() => { location.href = '/cart'; }")
    expect(frame.get_by_role("button", name="حذف المنتج", exact=False)).to_be_visible()
    return frame


def line_facts(page):
    lines = page.request.get("http://localhost:4000/__test/cart-state").json()["lines"]
    return [(x["product_id"], x["quantity"], x["size"], x["color"]) for x in lines]


def test_a_colour_swap_leaves_one_line_with_the_same_size_and_quantity_in_the_new_colour():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            frame = seed_blue_line(page)
            assert line_facts(page) == [("shoe-12", 3, "42", "blue")]
            send(page, SWAP_TO_YELLOW)

            expect(page.locator("#conversation")).to_contain_text(
                "غيّرت اللون: ضفت ملعب النجوم مقاس 42 باللون الأصفر وشلت اللي باللون الأزرق.",
                timeout=30000,
            )
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            # The old line is gone; exactly one line remains, same size and quantity, new colour.
            assert line_facts(page) == [("shoe-12", 3, "42", "yellow")]
            expect(frame.locator("[data-cart-line]")).to_have_count(1)
            assert [r["message"] for r in plan_requests(page)] == [SWAP_TO_YELLOW]
        finally:
            browser.close()


def test_a_swap_to_a_colour_the_product_does_not_offer_asks_and_leaves_the_cart_alone():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            seed_blue_line(page)
            send(page, SWAP_TO_RED)

            question = page.locator("#conversation")
            expect(question).to_contain_text(
                "اللون الأحمر مش متاح للمنتج ده في المقاس 42. الألوان المتاحة: أصفر. "
                "تحب أغيّره لأنهي لون؟",
                timeout=20000,
            )
            assert line_facts(page) == [("shoe-12", 3, "42", "blue")]
        finally:
            browser.close()


def test_a_product_the_message_does_not_name_is_confirmed_and_no_leaves_the_cart_alone():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(page, "http://localhost:4000/__test/reset")
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            # The product cards of the shoes page are what makes the picked id a known product.
            frame = page.frame_locator("#storefront-frame")
            frame.locator("body").evaluate("() => { location.href = '/c/shoes'; }")
            expect(frame.locator("[data-product-id='shoe-02']")).to_be_visible(timeout=15000)
            send(page, OPEN_UNNAMED)

            question = page.locator("#pending-question")
            expect(question).to_contain_text("تقصد", timeout=20000)
            options = question.locator("button")
            expect(options).to_have_count(2)
            assert [options.nth(i).text_content() for i in range(2)] == ["أيوه", "لا"]
            assert frame.locator("body").evaluate("() => location.pathname") == "/c/shoes"

            options.nth(1).click()
            expect(page.locator("#conversation")).to_contain_text(
                "تمام، ما عملتش حاجة. قولي تقصد أنهي منتج.", timeout=20000
            )
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            assert frame.locator("body").evaluate("() => location.pathname") == "/c/shoes"
            assert cart_lines(page) == []
            assert [r["message"] for r in plan_requests(page)] == [OPEN_UNNAMED]
        finally:
            browser.close()


def test_a_fresh_session_opens_the_product_the_shopper_names():
    with local_services(agent_app="eval.plan_fixture_app:retrieval_app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(page, "http://localhost:4000/__test/reset")
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            frame = page.frame_locator("#storefront-frame")
            expect(frame.get_by_role("link", name="الأحذية").first).to_be_visible(timeout=15000)
            assert frame.locator("body").evaluate("() => location.pathname") == "/"
            send(page, OPEN_BY_NAME)

            # The page of exactly that product opens: no search answer, no question.
            expect(frame.get_by_role("heading", name="خطوة سريعة")).to_be_visible(timeout=20000)
            assert frame.locator("body").evaluate("() => location.pathname") == "/p/shoe-02"
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
            expect(page.locator("#pending-question button")).to_have_count(0)
            expect(page.locator("[data-product-id]")).to_have_count(0)
            assert cart_lines(page) == []
            # The routing decision, then the interpreter's marker; code did the rest.
            assert [(r["prompt"], r["message"]) for r in plan_requests(page)] == [
                ("catalogue-decision-v11", OPEN_BY_NAME),
                ("intent-v39", OPEN_BY_NAME),
            ]
        finally:
            browser.close()
