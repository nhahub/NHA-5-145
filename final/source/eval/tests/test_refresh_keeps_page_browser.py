"""Shopper-state ticket 01: reloading the Panel keeps the Storefront page.

The model is scripted (no network); see eval/plan_fixture_app.py.
"""

from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.plan_fixture_app import ADD_IF_UNDER_1000
from eval.services import local_services


def test_reload_on_a_product_reopens_it_and_a_copilot_request_works_on_it():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(page, "http://localhost:4000/__test/reset")
            page.goto("http://localhost:4100")
            expect(page.locator("#shopper-message")).to_be_enabled()
            frame = page.frame_locator("#storefront-frame")
            frame.locator("body").evaluate("() => { location.href = '/p/shoe-01'; }")
            expect(frame.locator("#product-size")).to_be_visible()

            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled()
            expect(frame.locator("#product-size")).to_be_visible()
            assert frame.locator("body").evaluate("() => location.pathname") == "/p/shoe-01"

            # The request is answered from a fresh Snapshot of the reopened product (1450 EGP).
            page.locator("#shopper-message").fill(ADD_IF_UNDER_1000)
            page.get_by_role("button", name="إرسال", exact=True).click()
            reason = "ما ضفتهاش: سعرها 1450 جنيه، والشرط مش متحقق."
            expect(page.locator("#conversation")).to_contain_text(reason, timeout=20000)
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)
        finally:
            browser.close()


def test_a_new_tab_opens_the_home_page():
    with local_services(agent_app="eval.plan_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            first = context.new_page()
            first.goto("http://localhost:4100")
            expect(first.locator("#shopper-message")).to_be_enabled()
            first_frame = first.frame_locator("#storefront-frame")
            first_frame.locator("body").evaluate("() => { location.href = '/p/shoe-01'; }")
            expect(first_frame.locator("#product-size")).to_be_visible()

            # sessionStorage is per tab: a second tab remembers nothing and opens the home page.
            # The two tabs share one Copilot session, so the second tab may ask for a takeover;
            # whether its message box is enabled is not what this case checks.
            second = context.new_page()
            second.goto("http://localhost:4100")
            second_frame = second.frame_locator("#storefront-frame")
            expect(second_frame.locator("h1")).to_have_text("تسوّق بسهولة")
            assert second_frame.locator("body").evaluate("() => location.pathname") == "/"
            # The first tab keeps its own product page.
            assert first_frame.locator("body").evaluate("() => location.pathname") == "/p/shoe-01"
        finally:
            browser.close()
