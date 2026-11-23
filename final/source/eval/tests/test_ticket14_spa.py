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


def open_variant(browser, mode, route="/c/shoes"):
    page = browser.new_page()
    browser_post(page, "http://localhost:4000/__test/reset")
    page.goto(f"http://localhost:4100/?spa={mode}")
    frame = page.frame_locator("#storefront-frame")
    expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
    frame.locator("body").evaluate("(_, url) => { location.href = url; }", f"{route}?spa={mode}")
    expect(frame.locator("html")).to_have_attribute("data-spa-mode", mode)
    expect(frame.locator('main[aria-busy="true"]')).to_have_count(0)
    if route.startswith("/c/"):
        expect(frame.locator("#results-heading")).to_be_visible()
    else:
        expect(frame.locator("h1")).to_have_text("السلة")
    frame.locator("body").evaluate('() => { window.ticket14Document = "original"; }')
    return page, frame


@pytest.mark.parametrize("mode,expected_actions", [("url", 1), ("component", 3)])
def test_discovery_fast_path_and_component_fallback_complete_without_reload(
    browser, mode, expected_actions
):
    page, frame = open_variant(browser, mode)
    results = []
    page.on(
        "request",
        lambda r: results.append(r.post_data_json) if r.url.endswith("/action-results") else None,
    )
    try:
        page.locator("#shopper-message").fill("Show me running shoes under 2000 EGP")
        page.get_by_role("button", name="إرسال", exact=True).click()
        expect(page.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=15000
        )
        expect(frame.locator("#results-heading")).to_have_text("3 منتجات")
        expect(frame.locator("#max-price")).to_have_value("2000")
        assert frame.locator("body").evaluate("() => window.ticket14Document") == "original"
        assert len(results) == expected_actions
        assert all(r["status"] in ("ok", "navigated") for r in results)
        query = frame.locator("body").evaluate("() => location.search")
        assert ("max_price=2000" in query) if mode == "url" else query == ""
    finally:
        page.close()


def test_spa_back_forward_and_late_dom_changes_publish_current_snapshot(browser):
    page, frame = open_variant(browser, "url")
    try:
        page.evaluate("""() => { window.snapshots14 = []; addEventListener('message', e => {
          if (e.origin === 'http://localhost:4000' && e.data.type === 'snapshot')
            window.snapshots14.push(e.data.snapshot);
        }); }""")
        frame.locator('header a[href="/account"]').click()
        expect(frame.locator("h1")).to_have_text("الحساب")
        page.wait_for_function(
            "window.snapshots14.some(s => s.url.endsWith('/account') && "
            "s.elements.some(e => e.role === 'heading' && e.name === 'الحساب'))"
        )
        frame.locator("body").evaluate("() => history.back()")
        expect(frame.locator("#results-heading")).to_have_text("15 منتجات")
        frame.locator("body").evaluate("() => history.forward()")
        expect(frame.locator("h1")).to_have_text("الحساب")
        frame.locator("body").evaluate("""() => { const b = document.createElement('button');
            b.textContent = 'Late control'; document.querySelector('main').append(b); }""")
        page.wait_for_function(
            "window.snapshots14.some(s => s.elements.some(e => e.name === 'Late control'))"
        )
        assert frame.locator("body").evaluate("() => window.ticket14Document") == "original"
    finally:
        page.close()


def test_spa_quantity_undo_and_refresh_keep_exact_cart_state(browser):
    page, frame = open_variant(browser, "component", "/cart")
    lines = [{"product_id": "shoe-09", "size": "43", "color": "blue", "quantity": 1}]
    try:
        browser_post(page, "http://localhost:4000/__test/cart", data={"lines": lines})
        frame.locator('header a[href="/account"]').click()
        expect(frame.locator("h1")).to_have_text("الحساب")
        frame.locator('header a[href="/cart"]').click()
        expect(frame.locator("[data-cart-line]")).to_have_count(1)
        page.locator("#shopper-message").fill("Set quantity to 3")
        page.get_by_role("button", name="إرسال", exact=True).click()
        expect(page.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=15000
        )
        assert (
            page.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"] == 3
        )
        page.reload()
        frame = page.frame_locator("#storefront-frame")
        expect(frame.locator('[data-testid="undo-cart"]')).to_be_visible()
        frame.locator('[data-testid="undo-cart"]').click()
        expect(frame.locator("#cart-feedback")).to_have_text("تم التراجع عن تعديل السلة")
        assert page.request.get("http://localhost:4000/cart/state").json()["lines"] == lines
    finally:
        page.close()


def test_spa_bulk_clear_still_requires_fresh_confirmation(browser):
    page, frame = open_variant(browser, "url", "/cart")
    lines = [{"product_id": "shoe-09", "size": "43", "color": "blue", "quantity": 1}]
    try:
        browser_post(page, "http://localhost:4000/__test/cart", data={"lines": lines})
        frame.locator('header a[href="/cart"]').click()
        expect(frame.locator("[data-cart-line]")).to_have_count(1)
        page.locator("#shopper-message").fill("Empty my cart")
        page.get_by_role("button", name="إرسال", exact=True).click()
        expect(page.locator(".confirmation-card")).to_be_visible()
        assert page.request.get("http://localhost:4000/cart/state").json()["lines"] == lines
        page.reload()
        expect(page.locator("#task-status")).to_contain_text("Confirmation expired on refresh")
        expect(page.locator(".confirmation-card")).to_have_count(0)
        assert page.request.get("http://localhost:4000/cart/state").json()["lines"] == lines
        page.locator("#stop-task").click()
        expect(page.locator("#shopper-message")).to_be_enabled()
        frame.locator('header a[href="/cart"]').click()
        expect(frame.locator("[data-cart-line]")).to_have_count(1)
        page.locator("#shopper-message").fill("Empty my cart")
        page.get_by_role("button", name="إرسال", exact=True).click()
        page.locator('[data-question-option="Confirm"]').click()
        expect(page.locator("#task-status")).to_have_attribute("data-task-state", "completed")
        assert page.request.get("http://localhost:4000/cart/state").json()["lines"] == []
    finally:
        page.close()


def test_sse_disconnect_and_duplicate_delivery_do_not_repeat_cart_edit(browser):
    page = browser.new_page()
    reconnect_headers = []
    mutations = []
    last_event = ""

    def finite_stream(route):
        nonlocal last_event
        if route.request.method == "OPTIONS":
            route.fulfill(
                status=204,
                headers={
                    "Access-Control-Allow-Origin": "http://localhost:4100",
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Methods": "GET",
                    "Access-Control-Allow-Headers": "last-event-id",
                },
            )
            return
        header = route.request.all_headers().get("last-event-id", "")
        reconnect_headers.append(header)
        response = page.request.get(
            route.request.url + "&once=true",
            headers={"Last-Event-ID": header} if header else {},
        )
        fresh = response.text()
        body = "retry: 100\n\n" + last_event + fresh
        if fresh.strip():
            last_event = fresh.strip().split("\n\n")[-1] + "\n\n"
        route.fulfill(
            status=200,
            content_type="text/event-stream",
            body=body,
            headers={
                "Access-Control-Allow-Origin": "http://localhost:4100",
                "Access-Control-Allow-Credentials": "true",
            },
        )

    page.route(lambda url: ":8000/sessions/" in url and "/events?" in url, finite_stream)
    page.on(
        "request",
        lambda r: mutations.append(r)
        if r.method == "POST" and r.url == "http://localhost:4000/cart/quantity"
        else None,
    )
    try:
        browser_post(page, "http://localhost:4000/__test/reset")
        browser_post(
            page,
            "http://localhost:4000/__test/cart",
            data={
                "lines": [{"product_id": "shoe-09", "size": "43", "color": "blue", "quantity": 1}]
            },
        )
        page.goto("http://localhost:4100/")
        frame = page.frame_locator("#storefront-frame")
        expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
        frame.locator("body").evaluate("() => { location.href='/cart?spa=url'; }")
        expect(frame.locator("[data-cart-line]")).to_have_count(1)
        page.locator("#shopper-message").fill("Set quantity to 2")
        page.get_by_role("button", name="إرسال", exact=True).click()
        expect(page.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=15000
        )
        # This intercepted transport deliberately replays events across closed streams.
        # Server-side Last-Event-ID semantics are asserted separately at the HTTP seam.
        assert len(reconnect_headers) >= 3
        assert len(mutations) == 1
        assert page.locator("#conversation").inner_text().count("Quantity updated") == 1
        assert (
            page.request.get("http://localhost:4000/cart/state").json()["lines"][0]["quantity"] == 2
        )
    finally:
        page.unroute_all(behavior="wait")
        page.close()


def test_spa_navigation_rejects_old_targets_and_off_origin_actions(browser):
    page, frame = open_variant(browser, "url")
    try:
        page.evaluate("""() => { window.results14 = []; addEventListener('message', e => {
            if(e.origin === 'http://localhost:4000' && e.data.type === 'action_result')
                window.results14.push(e.data.result);
        }); }""")
        old_id = frame.locator("body").evaluate(
            "() => window.__copilot.snapshot().elements.find(e => e.name === 'أقصى سعر').id"
        )
        frame.locator('header a[href="/account"]').click()
        expect(frame.locator("h1")).to_have_text("الحساب")
        base = dict(v=1, task_id="task-spa-safety", narration="Check", sequence_number=1)
        frame.locator("body").evaluate(
            "(_, action) => window.__copilot.run(action)",
            {
                **base,
                "action_id": "old-input",
                "type": "type",
                "id": old_id,
                "text": "10",
                "submit": False,
            },
        )
        page.wait_for_function(
            "window.results14.some(r => r.action_id==='old-input' && r.status==='not_found')"
        )
        frame.locator("body").evaluate(
            "(_, action) => window.__copilot.run(action)",
            {
                **base,
                "sequence_number": 2,
                "action_id": "external",
                "type": "navigate",
                "url": "https://example.com/",
            },
        )
        page.wait_for_function(
            "window.results14.some(r => r.action_id==='external' && r.status==='blocked')"
        )
        assert frame.locator("body").evaluate("() => location.origin") == "http://localhost:4000"
        page.route("http://localhost:4000/cart", lambda route: route.fulfill(status=503, body=""))
        frame.locator("body").evaluate(
            "(_, action) => window.__copilot.run(action)",
            {
                **base,
                "sequence_number": 3,
                "action_id": "failed-page",
                "type": "navigate",
                "url": "/cart",
            },
        )
        page.wait_for_function(
            "window.results14.some(r => r.action_id==='failed-page' && r.status==='blocked')"
        )
        expect(frame.locator('main [role="alert"]')).to_be_visible()
    finally:
        page.close()
