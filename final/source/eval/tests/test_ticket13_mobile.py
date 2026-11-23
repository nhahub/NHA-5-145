from playwright.sync_api import expect, sync_playwright

from eval.cases import TICKET_13_CASES
from eval.runner import _prepare_storefront_controls, run_evaluation
from eval.services import local_services


def test_mobile_agent_evaluation_cases() -> None:
    with local_services(), sync_playwright() as playwright:
        outcomes = run_evaluation(playwright.chromium, TICKET_13_CASES)
    assert all(outcome.passed for outcome in outcomes), [outcome.failure for outcome in outcomes]
    assert [outcome.step_count for outcome in outcomes] == [1, 1, 1, 0, 1]


def test_case_setup_waits_for_initial_storefront_navigation():
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})

            # Delay only the real Panel's startup trigger. All linking, Snapshot
            # and iframe behavior remains real; setup must await its readiness.
            def delay_start(route):
                if route.request.frame != page.main_frame:
                    route.continue_()
                    return
                response = route.fetch()
                source = response.text()
                assert source.count("void startLinked();") == 1
                route.fulfill(
                    response=response,
                    body=source.replace(
                        "void startLinked();", "setTimeout(() => { void startLinked(); }, 300);"
                    ),
                )

            page.route("**/src/main.ts", delay_start)
            page.goto("http://localhost:4100/", wait_until="domcontentloaded")
            _prepare_storefront_controls(page, TICKET_13_CASES[3], 5000)
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("#product-size")).to_have_value("43")
            expect(frame.locator("form[data-cart-edit='add']")).to_have_attribute(
                "aria-disabled", "true"
            )
        finally:
            browser.close()


def test_mobile_controls_delayed_products_and_semantic_targets() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
            frame.get_by_text("القائمة", exact=True).click()
            expect(frame.get_by_role("navigation", name="أقسام المتجر")).to_be_visible()
            frame.get_by_role("link", name="الأحذية", exact=True).last.click()
            expect(frame.locator("#results-heading")).to_have_text("15 منتجات")
            frame.get_by_text("الفلاتر والترتيب").click()
            expect(frame.get_by_role("form", name="فلترة الأحذية")).to_be_visible()
            frame.locator("#sort-trigger").click()
            frame.locator('#sort-options [data-sort-value="cheapest"]').click()
            assert frame.locator("#sort").input_value() == "cheapest"
            storefront_frame = page.query_selector("#storefront-frame").content_frame()
            frame.get_by_role("button", name="تطبيق الفلاتر").click()
            storefront_frame.wait_for_url("**/c/shoes?*sort=cheapest*")
            expect(frame.locator("#results-heading")).to_have_text("15 منتجات")
            expect(frame.locator("[data-product-id]")).to_have_count(6)
            load_more = frame.locator("#load-more-products")
            load_more.evaluate("button => button.click()")
            expect(frame.locator("[data-product-id]")).to_have_count(12)
            snapshot = frame.locator("body").evaluate("() => window.__copilot.snapshot()")
            detail_links = [
                item
                for item in snapshot["elements"]
                if item["name"] == "عرض التفاصيل" and item["visible"]
            ]
            assert len(detail_links) >= 6
            assert len({item["group"] for item in detail_links}) >= 6
            frame.locator('[data-product-id="shoe-09"] h2 a').click()
            frame.get_by_role("button", name="مقاس 43").click()
            assert frame.locator("#product-size").input_value() == "43"
            expect(frame.get_by_role("button", name="مقاس 43")).to_have_attribute(
                "aria-pressed", "true"
            )
            frame.locator("#product-color").select_option("beige")
            frame.get_by_role("button", name="أضف إلى السلة").click()
            expect(frame.locator("#mini-cart-count")).to_have_text("1")
            frame.locator(".mini-cart summary").click()
            expect(frame.locator("#mini-cart-summary")).to_contain_text("1 قطعة")
            frame.locator('header a[href="/cart"]').click()
            frame.locator('[data-testid="empty-cart"]').click()
            expect(frame.locator("#manual-clear-dialog")).to_be_visible()
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            stop = page.locator("#stop-task")
            assert stop.is_visible()
            assert (stop.bounding_box() or {})["y"] < 60
            stop.click()
            desktop = browser.new_page(viewport={"width": 1280, "height": 800})
            desktop.goto("http://localhost:4000/c/shoes")
            expect(desktop.get_by_role("form", name="فلترة الأحذية")).to_be_visible()
            desktop.close()
        finally:
            browser.close()


def test_closed_mobile_drawer_and_disabled_loading_target_are_blocked() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto("http://localhost:4100/")
            frame = page.frame_locator("#storefront-frame")
            frame.locator("body").evaluate("() => { location.href = '/c/shoes'; }")
            expect(frame.locator("#results-heading")).to_have_text("15 منتجات")
            page.evaluate("""() => {
                window.__ticket13Results = [];
                window.addEventListener('message', event => {
                    if (event.data?.type === 'action_result')
                        window.__ticket13Results.push(event.data.result.status);
                });
            }""")
            result = frame.locator("body").evaluate(
                """async () => {
                    const snapshot = window.__copilot.snapshot();
                    const target = snapshot.elements.find(item => item.name === 'الفلاتر والترتيب');
                    const form = document.getElementById('filter-drawer');
                    form.open = true;
                    const apply = window.__copilot.snapshot().elements.find(
                        item => item.name === 'تطبيق الفلاتر');
                    form.open = false;
                    const action = (id, sequence_number) => ({v: 1, type: 'click',
                        task_id: 'ticket13-closed-drawer', action_id: `action-${sequence_number}`,
                        sequence_number, narration: 'browser test', id});
                    await window.__copilot.run(action(apply.id, 1));
                    await window.__copilot.run(action(target.id, 2));
                    const load = window.__copilot.snapshot().elements.find(
                        item => item.name === 'تحميل المزيد من المنتجات');
                    document.getElementById('load-more-products').disabled = true;
                    await window.__copilot.run(action(load.id, 3));
                    return {isOpen: form.open};
                }"""
            )
            page.wait_for_function("window.__ticket13Results.length >= 3")
            assert page.evaluate("window.__ticket13Results") == ["blocked", "ok", "blocked"]
            assert result == {"isOpen": True}
        finally:
            browser.close()
