from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.services import local_services


def send(page, message):
    expect(page.locator("#shopper-message")).to_be_enabled()
    page.locator("#shopper-message").fill(message)
    page.get_by_role("button", name="إرسال", exact=True).click()


def test_retrieval_advice_actions_and_two_shoppers_share_database_not_carts():
    with local_services(agent_app="eval.catalogue_fixture_app:app"), sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            with browser.new_context() as a_context, browser.new_context() as b_context:
                a, b = a_context.new_page(), b_context.new_page()
                for page in (a, b):
                    page.goto("http://localhost:4100")
                    expect(page.locator("#shopper-message")).to_be_enabled()
                send(a, "[fixture:recommend]")
                expect(
                    a.get_by_text(
                        "Catalogue evidence checked; unrecorded material remains unknown.",
                        exact=True,
                    )
                ).to_be_visible(timeout=15000)
                # Selected ninth candidate is rendered despite an unknown exclusion.
                expect(a.locator('[data-product-id="shoe-09"]')).to_be_visible()
                send(a, "[fixture:open]")
                # The message names no product, so the Copilot confirms the model's pick first.
                question = a.locator("#pending-question")
                expect(question).to_contain_text("Did you mean", timeout=15000)
                question.get_by_role("button", name="Yes", exact=True).click()
                frame = a.frame_locator("#storefront-frame")
                expect(frame.locator("#product-size")).to_be_visible()
                frame.locator("#product-size").select_option("43")
                frame.locator("#product-color").select_option("blue")
                send(a, "[fixture:add]")
                expect(a.get_by_text("Added to cart", exact=True)).to_be_visible(timeout=15000)
                state = a.request.get("http://localhost:4000/cart/state").json()
                assert state["lines"][0]["quantity"] == 2
                assert b.request.get("http://localhost:4000/cart/state").json()["lines"] == []
                added = browser_post(
                    a,
                    "http://localhost:4000/cart/items",
                    data={
                        "product_id": "shoe-01",
                        "size": "42",
                        "color": "black",
                        "quantity": 1,
                        "revision": state["revision"],
                        "operation_id": "second-line",
                    },
                )
                assert added.status == 200
                frame.locator("body").evaluate("() => { location.href='/cart'; }")
                expect(frame.locator('input[name="quantity"]')).to_have_count(2)
                send(a, "[fixture:quantity]")
                expect(a.get_by_text("Quantity updated", exact=True)).to_be_visible(timeout=15000)
                lines = a.request.get("http://localhost:4000/cart/state").json()["lines"]
                assert {line["product_id"]: line["quantity"] for line in lines} == {
                    "shoe-09": 5,
                    "shoe-01": 1,
                }
                assert b.request.get("http://localhost:4000/cart/state").json()["lines"] == []
        finally:
            browser.close()
