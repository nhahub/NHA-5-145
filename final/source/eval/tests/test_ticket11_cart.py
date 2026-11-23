import pytest
from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.services import local_services


@pytest.fixture(scope="module")
def browser():
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    browser_post(page, "http://localhost:4000/__test/reset")
    page.goto("http://localhost:4100/")
    frame = page.frame_locator("#storefront-frame")
    expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
    frame.locator("body").evaluate("() => { location.href = '/p/shoe-09'; }")
    expect(frame.locator("html")).to_have_attribute("data-cart-revision", "0")
    frame.locator("#product-size").select_option("43")
    frame.locator("#product-color").select_option("blue")
    yield page
    page.close()


def state(page):
    return page.request.get("http://localhost:4000/cart/state").json()


def add(page):
    frame = page.frame_locator("#storefront-frame")
    frame.locator('[data-testid="add-to-cart"]').click()
    expect(frame.locator("#cart-feedback")).to_have_text("تمت الإضافة إلى السلة")
    return frame


def test_manual_cart_quantity_coalescing_removal_and_exact_undo(page):
    frame = add(page)
    frame.locator('header a[href="/cart"]').click()
    expect(frame.locator("[data-cart-line]")).to_have_count(1)
    original = state(page)["lines"]
    for quantity in [2, 3]:
        frame.locator('input[name="quantity"]').fill(str(quantity))
        frame.locator('[data-cart-edit="quantity"] button').click()
        expect(frame.locator("html")).to_have_attribute("data-cart-revision", str(quantity))
    assert state(page)["lines"][0]["quantity"] == 3
    expect(frame.locator('[data-cart-edit="quantity"] button')).to_be_focused()
    frame.locator('[data-testid="undo-cart"]').click()
    expect(frame.locator('input[name="quantity"]')).to_have_value("1")
    assert state(page)["lines"] == original
    frame.locator('[data-cart-edit="remove"] button').click()
    expect(frame.locator("[data-cart-line]")).to_have_count(0)
    assert state(page)["lines"] == []
    expect(frame.locator('[data-testid="undo-cart"]')).to_be_focused()
    frame.locator('[data-testid="undo-cart"]').click()
    expect(frame.locator("[data-cart-line]")).to_have_count(1)
    assert state(page)["lines"] == original


def test_rejected_optimistic_edit_restores_cart_and_removes_undo(page):
    frame = add(page)
    frame.locator('header a[href="/cart"]').click()
    expect(frame.locator('input[name="quantity"]')).to_have_value("1")
    pending = []
    page.route("**/cart/quantity", lambda route: pending.append(route))
    frame.locator('input[name="quantity"]').fill("7")
    frame.locator('[data-cart-edit="quantity"] button').click()
    expect(frame.locator(".cart-total strong")).to_have_text("12950.00 EGP")
    # The optimistic total can render before the request reaches the route handler.
    for _ in range(100):
        if pending:
            break
        page.wait_for_timeout(50)
    pending[0].fulfill(status=409, body="{}", content_type="application/json")
    expect(frame.locator("#cart-feedback")).to_have_attribute("data-cart-result", "failed")
    expect(frame.locator('input[name="quantity"]')).to_have_value("1")
    expect(frame.locator('[data-testid="undo-cart"]')).to_be_hidden()
    assert state(page)["lines"][0]["quantity"] == 1


def test_undo_expires_after_ten_seconds_in_browser(page):
    frame = add(page)
    expect(frame.locator('[data-testid="undo-cart"]')).to_be_visible()
    expect(frame.locator('[data-testid="undo-cart"]')).to_be_hidden(timeout=12000)
    assert state(page)["undo"] is None


def test_refresh_keeps_only_remaining_undo_time_and_restores_exact_cart(page):
    frame = add(page)
    second = browser_post(
        page,
        "http://localhost:4000/cart/items",
        data={
            "product_id": "shoe-14",
            "size": "43",
            "color": "green",
            "quantity": 2,
            "revision": 1,
            "operation_id": "second-product-before-refresh",
        },
    )
    assert second.status == 200
    frame.locator('header a[href="/cart"]').click()
    expect(frame.locator("[data-cart-line]")).to_have_count(2)
    before = state(page)["lines"]
    frame.locator('input[name="quantity"]').first.fill("3")
    frame.locator('[data-cart-edit="quantity"] button').first.click()
    expect(frame.locator('input[name="quantity"]').first).to_have_value("3")
    remaining_before = state(page)["undo"]["remaining_ms"]

    page.wait_for_timeout(1200)
    page.reload()

    expect(frame.locator('[data-testid="undo-cart"]')).to_be_visible()
    remaining_after = state(page)["undo"]["remaining_ms"]
    assert 0 < remaining_after < remaining_before - 800
    frame.locator('[data-testid="undo-cart"]').click()
    assert state(page)["lines"] == before


def test_unverified_copilot_add_requires_new_request_after_refresh(page):
    page.route(
        "**/cart/items",
        lambda route: route.fulfill(status=409, body="{}", content_type="application/json"),
    )
    page.locator("#shopper-message").fill("Add this to my cart")
    page.get_by_role("button", name="إرسال").click()
    expect(page.locator('.question-card [data-question-option="Stop"]')).to_be_visible()
    expect(page.locator("#retry-task")).to_have_count(0)
    assert state(page)["lines"] == []

    page.reload()

    expect(page.locator('.question-card [data-question-option="Stop"]')).to_be_visible()
    expect(page.locator("#retry-task")).to_have_count(0)
    assert state(page)["lines"] == []


def test_copilot_add_quantity_remove_and_undo_only_reports_verified_success(page):
    frame = page.frame_locator("#storefront-frame")

    def ask(text, expected):
        page.locator("#shopper-message").fill(text)
        page.get_by_role("button", name="إرسال").click()
        expect(frame.locator("#cart-feedback")).to_have_text(expected, timeout=12000)
        expect(page.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=12000
        )

    ask("Add this to my cart", "تمت الإضافة إلى السلة")
    frame.locator('header a[href="/cart"]').click()
    expect(frame.locator('input[name="quantity"]')).to_have_value("1")
    ask("Set quantity to 3", "تم تحديث الكمية")
    assert state(page)["lines"][0]["quantity"] == 3
    ask("Remove this item", "تم حذف المنتج من السلة")
    assert state(page)["lines"] == []
    ask("Undo", "تم التراجع عن تعديل السلة")
    assert state(page)["lines"][0]["quantity"] == 3


def test_fractional_scrolling_add_finishes_and_next_cart_request_is_available(page):
    frame = page.frame_locator("#storefront-frame")
    # Browser zoom/smooth scrolling can expose subpixel CSS offsets. Exercise
    # the real Bridge -> Panel -> HTTP result, not a handcrafted wire result.
    frame.locator("body").evaluate(
        "() => Object.defineProperty(window, 'scrollY', {get: () => 211.42857360839844})"
    )
    page.locator("#shopper-message").fill("Add this to my cart")
    page.get_by_role("button", name="إرسال").click()
    expect(frame.locator("#cart-feedback")).to_have_text("تمت الإضافة إلى السلة")
    expect(page.locator("#task-status")).to_have_attribute(
        "data-task-state", "completed", timeout=12000
    )
    expect(page.locator("#shopper-message")).to_be_enabled()
    # Stay on the product page: the Copilot must open the cart itself and read
    # its current quantity before incrementing. Undo restores the single add.
    page.locator("#shopper-message").fill("Increase quantity by 3 for ممشى النيل")
    page.get_by_role("button", name="إرسال").click()
    expect(frame.locator('input[name="quantity"]')).to_have_value("4", timeout=12000)
    expect(page.locator("#task-status")).to_have_attribute(
        "data-task-state", "completed", timeout=12000
    )
    assert state(page)["lines"][0]["quantity"] == 4
    frame.locator('[data-testid="undo-cart"]').click()
    expect(frame.locator('input[name="quantity"]')).to_have_value("1")


def test_manual_clear_requires_confirmation_and_cancel_keeps_cart(page):
    frame = add(page)
    frame.locator('header a[href="/cart"]').click()
    before = state(page)["lines"]
    frame.locator('[data-testid="empty-cart"]').click()
    expect(frame.locator("#manual-clear-dialog")).to_be_visible()
    assert state(page)["lines"] == before
    frame.locator("#cancel-manual-clear").click()
    expect(frame.locator("#manual-clear-dialog")).to_be_hidden()
    assert state(page)["lines"] == before
    frame.locator('[data-testid="empty-cart"]').click()
    frame.locator("#confirm-manual-clear").click()
    expect(frame.locator('#cart-contents [role="status"]')).to_have_text("السلة فارغة")
    assert state(page)["lines"] == []


def test_named_relative_quantity_changes_only_one_line_and_undo_restores_it(page):
    frame = add(page)
    response = browser_post(
        page,
        "http://localhost:4000/cart/items",
        data={
            "product_id": "shoe-14",
            "size": "43",
            "color": "green",
            "quantity": 1,
            "revision": 1,
            "operation_id": "second-product",
        },
    )
    assert response.status == 200
    frame.locator('header a[href="/cart"]').click()
    expect(frame.locator("[data-cart-line]")).to_have_count(2)
    page.locator("#shopper-message").fill("Increase quantity by 2 for ممشى النيل")
    page.get_by_role("button", name="إرسال").click()
    expect(page.locator("#task-status")).to_have_attribute(
        "data-task-state", "completed", timeout=12000
    )
    lines = state(page)["lines"]
    assert [(line["product_id"], line["quantity"]) for line in lines] == [
        ("shoe-09", 3),
        ("shoe-14", 1),
    ]
    frame.locator('[data-testid="undo-cart"]').click()
    expect(frame.locator('input[name="quantity"]').first).to_have_value("1")
    assert [line["quantity"] for line in state(page)["lines"]] == [1, 1]


def test_manual_clear_refuses_stale_cart_and_bridge_cannot_skip_confirmation(page):
    frame = add(page)
    frame.locator('header a[href="/cart"]').click()
    frame.locator('[data-testid="empty-cart"]').click()
    expect(frame.locator("#manual-clear-dialog")).to_be_visible()
    page.evaluate("""() => window.addEventListener('message', event => {
      if (event.origin === 'http://localhost:4000' &&
          event.data.type === 'action_result' &&
          event.data.result.action_id === 'action-test') window.manualResult = event.data.result;
    })""")
    frame.locator("body").evaluate("""async () => {
        const snapshot = window.__copilot.snapshot();
        const target = snapshot.elements.find(e => e.name === 'نعم، إفراغ السلة');
        return window.__copilot.run({v:1,type:'click',task_id:'task-test',
          action_id:'action-test',sequence_number:1,narration:'test',id:target.id});
    }""")
    page.wait_for_function("window.manualResult !== undefined")
    assert page.evaluate("window.manualResult.status") == "blocked"
    response = browser_post(
        page,
        "http://localhost:4000/cart/quantity",
        data={
            "product_id": "shoe-09",
            "size": "43",
            "color": "blue",
            "quantity": 2,
            "revision": 1,
            "operation_id": "external-edit",
        },
    )
    assert response.status == 200
    frame.locator("#confirm-manual-clear").click()
    expect(frame.locator("#manual-clear-summary")).to_contain_text("تغيّرت السلة")
    assert state(page)["lines"][0]["quantity"] == 2
