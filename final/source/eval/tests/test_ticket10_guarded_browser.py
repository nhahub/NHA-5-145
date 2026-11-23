from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.services import local_services


def test_bulk_clear_requires_visible_shopper_confirmation_in_real_browser() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            seed = browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 2}]},
            )
            assert seed.status == 204
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(page.locator("#task-status")).to_contain_text("جاهز")
            frame.locator("body").evaluate("() => { location.href = '/cart'; }")
            expect(frame.locator('[data-testid="empty-cart"]')).to_be_visible()
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال").click()

            card = page.locator(".confirmation-card")
            expect(card).to_contain_text("Remove every item from the current cart")
            state_before = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert len(state_before["lines"]) == 1
            card.get_by_role("button", name="Confirm").click()

            expect(page.locator("#task-status")).to_have_attribute(
                "data-task-state", "completed", timeout=15_000
            )
            expect(frame.get_by_role("status")).to_have_text("السلة فارغة")
            state_after = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert state_after["lines"] == []
        finally:
            browser.close()


def test_fictional_checkout_never_reads_card_values_and_needs_confirmation() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            assert (
                browser_post(
                    page,
                    "http://localhost:4000/__test/cart",
                    data={"lines": [{"product_id": "shoe-09", "quantity": 1}]},
                ).status
                == 204
            )
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(page.locator("#task-status")).to_contain_text("جاهز")
            frame.locator("body").evaluate("() => { location.href = '/checkout'; }")
            expect(frame.locator('[data-testid="place-order"]')).to_be_enabled()
            frame.locator("#card-number").fill("0000 0000 0000 0000")
            frame.locator("#card-expiry").fill("01/30")
            frame.locator("#card-security-code").fill("000")
            snapshot = frame.locator("body").evaluate(
                "() => JSON.stringify(window.__copilot.snapshot())"
            )
            assert "0000 0000 0000 0000" not in snapshot
            assert '"000"' not in snapshot
            page.locator("#shopper-message").fill("Place my fictional order")
            page.get_by_role("button", name="إرسال").click()
            card = page.locator(".confirmation-card")
            expect(card).to_contain_text("Submit one fictional order")
            order_state = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert order_state["orders"] == []
            card.get_by_role("button", name="Confirm").click()

            expect(page.locator("#task-status")).to_have_attribute(
                "data-task-state", "completed", timeout=15_000
            )
            expect(frame.get_by_role("heading", name="تم تسجيل طلب خيالي")).to_be_visible()
            state = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert len(state["orders"]) == 1
            assert state["lines"] == []
        finally:
            browser.close()


def test_changed_cart_invalidates_a_visible_confirmation_before_execution() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 1}]},
            )
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(page.locator("#task-status")).to_contain_text("جاهز")
            frame.locator("body").evaluate("() => { location.href = '/cart'; }")
            expect(frame.locator('[data-testid="empty-cart"]')).to_be_visible()
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال").click()
            card = page.locator(".confirmation-card")
            expect(card).to_be_visible()

            browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 2}]},
            )
            frame.locator("body").evaluate("() => { location.reload(); }")
            expect(frame.locator('[data-testid="empty-cart"]')).to_have_attribute(
                "data-cart-revision", "2"
            )
            card.get_by_role("button", name="Confirm").click()
            expect(page.locator("#task-status")).to_contain_text("تعذر إرسال إجابتك")
            state = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert state["revision"] == 2
            assert state["lines"] == [{"product_id": "shoe-09", "quantity": 2}]
        finally:
            browser.close()


def test_expired_browser_confirmation_never_mutates_cart() -> None:
    with local_services(test_clock=True), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 1}]},
            )
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(page.locator("#task-status")).to_contain_text("جاهز")
            frame.locator("body").evaluate("() => { location.href = '/cart'; }")
            expect(frame.locator('[data-testid="empty-cart"]')).to_be_visible()
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال").click()
            card = page.locator(".confirmation-card")
            expect(card).to_be_visible()

            advanced = browser_post(
                page, "http://localhost:8000/__test/advance-time", data={"seconds": 61}
            )
            assert advanced.status == 204
            card.get_by_role("button", name="Confirm").click()
            expect(page.locator("#task-status")).to_contain_text("تعذر إرسال إجابتك")
            cart_state = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert len(cart_state["lines"]) == 1
        finally:
            browser.close()


def test_browser_refresh_invalidates_unused_confirmation() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            browser_post(
                page,
                "http://localhost:4000/__test/cart",
                data={"lines": [{"product_id": "shoe-09", "quantity": 1}]},
            )
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(page.locator("#task-status")).to_contain_text("جاهز")
            frame.locator("body").evaluate("() => { location.href = '/cart'; }")
            expect(frame.locator('[data-testid="empty-cart"]')).to_be_visible()
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال").click()
            expect(page.locator(".confirmation-card")).to_be_visible()

            page.reload()

            expect(page.locator("#task-status")).to_have_attribute(
                "data-task-state", "paused", timeout=15_000
            )
            expect(page.locator(".confirmation-card")).to_have_count(0)
            cart_state = page.request.get("http://localhost:4000/__test/cart-state").json()
            assert len(cart_state["lines"]) == 1
            assert cart_state["orders"] == []
        finally:
            browser.close()


def test_equivalent_guarded_form_targets_cannot_bypass_confirmation() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
            # The Bridge hook exists once the Panel has linked; the heading shows earlier.
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            submissions = frame.locator("body").evaluate(
                """async (body) => {
                    body.insertAdjacentHTML('beforeend', `
                        <form id="review-cart" action="http://localhost:4000/cart/clear"
                            method="get"></form>
                        <button form="review-cart" formmethod="post">Review clear</button>
                        <button form="review-cart" formmethod="post" aria-label="Outer clear">
                            <span role="button">Review inner clear</span>
                        </button>
                    `);
                    let submissions = 0;
                    document.getElementById('review-cart').addEventListener('submit', event => {
                        event.preventDefault();
                        submissions++;
                    });
                    let sequence = 0;
                    for (const name of ['Review clear', 'Review inner clear']) {
                        const target = window.__copilot.snapshot().elements.find(
                            element => element.name === name
                        );
                        await window.__copilot.run({
                            v: 1, type: 'click', task_id: 'task-review-guarded',
                            action_id: `review-clear-${++sequence}`, sequence_number: sequence,
                            narration: 'Safety regression', id: target.id
                        });
                    }
                    return submissions;
                }"""
            )
            assert submissions == 0
        finally:
            browser.close()
