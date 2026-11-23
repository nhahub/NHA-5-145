import pytest
from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.services import local_services


def test_two_browser_shoppers_keep_equal_revision_carts_separate():
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with browser.new_context() as a_context, browser.new_context() as b_context:
                a, b = a_context.new_page(), b_context.new_page()
                for page, quantity in [(a, "1"), (b, "3")]:
                    page.goto("http://localhost:4100")
                    frame = page.frame_locator("#storefront-frame")
                    expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
                    expect(page.locator("#shopper-message")).to_be_enabled()
                    frame.locator("body").evaluate("() => { location.href = '/p/shoe-09'; }")
                    frame.locator("#product-size").select_option("43")
                    frame.locator("#product-color").select_option("blue")
                    frame.locator('input[name="quantity"]').fill(quantity)
                    frame.locator('[data-testid="add-to-cart"]').click()
                    expect(frame.locator("#cart-feedback")).to_have_text("تمت الإضافة إلى السلة")
                assert (
                    a.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                    == 1
                )
                assert (
                    b.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                    == 3
                )
                a.reload()
                expect(a.locator("#shopper-message")).to_be_enabled()
                assert (
                    a.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                    == 1
                )
                session = a.evaluate("localStorage.getItem('shopping-copilot.session-id')")
                assert (
                    b.request.get(f"http://localhost:8000/sessions/{session}/state").status == 404
                )
                serialized = (
                    a.frame_locator("#storefront-frame")
                    .locator("body")
                    .evaluate("() => JSON.stringify(window.__copilot.snapshot())")
                )
                assert "copilot_csrf" not in serialized
                assert "copilot-csrf" not in serialized
                a_context.clear_cookies()
                assert (
                    a.request.get(f"http://localhost:8000/sessions/{session}/state").status == 401
                )
                # Deleting a client cookie cannot revoke an already-open server socket.
                # The next browser request observes the loss and closes delivery.
                a.locator("#shopper-message").fill("Open my cart")
                a.get_by_role("button", name="إرسال", exact=True).click()
                expect(a.locator("#task-status")).to_contain_text("Reload", timeout=8000)
                a.reload()
                expect(a.locator("#shopper-message")).to_be_enabled()
                assert a.request.get("http://localhost:4000/cart/state").json()["lines"] == []
                assert (
                    b.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                    == 3
                )
        finally:
            browser.close()


def test_process_restarts_invalidate_authority_without_replaying_cart_changes():
    with local_services() as services, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("http://localhost:4100/")
            expect(page.locator("#shopper-message")).to_be_enabled()
            added = browser_post(
                page,
                "http://localhost:4000/cart/items",
                data={
                    "product_id": "shoe-09",
                    "size": "43",
                    "color": "blue",
                    "quantity": 2,
                    "revision": 0,
                    "operation_id": "restart-seed",
                },
            ).json()
            session = page.evaluate("localStorage.getItem('shopping-copilot.session-id')")
            services.restart("agent")
            expect(page.locator("#task-status")).to_contain_text("Reload", timeout=8000)
            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            assert (
                page.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                == 2
            )
            # The Copilot session is saved state now: after the restart it is still this
            # Shopper's. (It is reached with a tab id; without one the request is invalid, 422.)
            kept = page.request.get(
                f"http://localhost:8000/sessions/{session}/state?tab_id=restart-observer"
            )
            assert kept.status == 200
            services.restart("store")
            # The Shopper's link is stable across a Storefront restart, so the Panel is not
            # forced to reload and the saved cart is still there, with nothing replayed
            # (still quantity 2). Only the 10-second Undo is gone.
            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
            assert [(line["product_id"], line["quantity"]) for line in lines] == [("shoe-09", 2)]
            denied = browser_post(
                page,
                "http://localhost:4000/cart/undo",
                data={
                    "undo_id": added["undo"]["id"],
                    "revision": 0,
                    "operation_id": "old-undo",
                },
            )
            assert denied.status == 409
        finally:
            browser.close()


@pytest.mark.parametrize("delayed_first_tab", [False, True], ids=["concurrent", "second-tab-wins"])
def test_simultaneous_tabs_share_one_shopper_but_require_task_takeover(delayed_first_tab):
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            a, b = context.new_page(), context.new_page()
            held_scripts = []
            if delayed_first_tab:
                # A committed document may run its script after the second tab.
                a.route("**/src/main.ts", lambda route: held_scripts.append(route))
            a.goto("http://localhost:4100/", wait_until="commit")
            b.goto("http://localhost:4100/", wait_until="commit")
            if delayed_first_tab:
                expect(b.locator("#shopper-message")).to_be_enabled(timeout=15000)
                assert len(held_scripts) == 1
                held_scripts[0].continue_()
            for page in (a, b):
                # Wait for either valid initialization result without choosing a winner.
                expect(page.locator("#shopper-message:enabled, #takeover-session")).to_be_visible(
                    timeout=15000
                )
            assert sum(page.locator("#shopper-message").is_enabled() for page in (a, b)) == 1
            owner, observer = (a, b) if a.locator("#shopper-message").is_enabled() else (b, a)
            expect(observer.locator("#shopper-message")).to_be_disabled()
            expect(observer.locator("#task-status")).to_contain_text("another tab")
            expect(observer.locator("#takeover-session")).to_be_visible()
            browser_post(
                owner,
                "http://localhost:4000/cart/items",
                data={
                    "product_id": "shoe-09",
                    "size": "43",
                    "color": "blue",
                    "quantity": 2,
                    "revision": 0,
                    "operation_id": "shared-profile",
                },
            )
            frame = observer.frame_locator("#storefront-frame")
            frame.locator("body").evaluate("() => { location.href = '/cart'; }")
            expect(frame.locator('input[name="quantity"]')).to_have_value("2")
            assert a.evaluate("localStorage.getItem('shopping-copilot.session-id')") == b.evaluate(
                "localStorage.getItem('shopping-copilot.session-id')"
            )
        finally:
            browser.close()


@pytest.mark.parametrize("mode", ["off", "url", "component"])
def test_storefront_cookie_change_blocks_the_old_chat_before_new_cart_actions(mode):
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(f"http://localhost:4100/?spa={mode}")
            expect(page.locator("#shopper-message")).to_be_enabled()
            old_session = page.evaluate("localStorage.getItem('shopping-copilot.session-id')")
            context.clear_cookies(name="copilot_store")
            frame = page.frame_locator("#storefront-frame")
            # Category navigation uses SPA replacement in both SPA modes.
            frame.locator('main a.primary-link[href="/c/shoes"]').click()
            expect(page.locator("#task-status")).to_contain_text("Reload", timeout=10000)
            expect(page.locator("#shopper-message")).to_be_disabled()
            assert page.request.get("http://localhost:4000/cart/state").json()["lines"] == []
            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            assert (
                page.request.get(f"http://localhost:8000/sessions/{old_session}/state").status
                == 404
            )
        finally:
            browser.close()


def test_cart_refresh_cannot_render_a_new_cookie_owner_under_an_old_document():
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto("http://localhost:4100/")
            expect(page.locator("#shopper-message")).to_be_enabled()
            frame = page.frame_locator("#storefront-frame")
            frame.locator("body").evaluate("() => { location.href = '/p/shoe-09'; }")
            frame.locator("#product-size").select_option("43")
            frame.locator("#product-color").select_option("blue")
            frame.locator('[data-testid="add-to-cart"]').click()
            expect(frame.locator("#cart-feedback")).to_have_text("تمت الإضافة إلى السلة")
            context.clear_cookies(name="copilot_store")
            other = context.new_page()
            other.goto("http://localhost:4000/")
            assert (
                browser_post(
                    other,
                    "http://localhost:4000/cart/items",
                    data={
                        "product_id": "shoe-09",
                        "size": "43",
                        "color": "blue",
                        "quantity": 7,
                        "revision": 0,
                        "operation_id": "new-cookie-owner",
                    },
                ).status
                == 200
            )
            frame.locator('[data-testid="add-to-cart"]').click()
            expect(page.locator("#task-status")).to_contain_text("Reload", timeout=10000)
            expect(frame.locator('header a[href="/cart"]')).to_have_text("السلة (1)")
            assert (
                other.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"]
                == 7
            )
        finally:
            browser.close()
