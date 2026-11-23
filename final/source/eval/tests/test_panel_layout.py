from playwright.sync_api import expect, sync_playwright

from eval.services import local_services


def test_recommendations_follow_live_events_without_interrupting_older_reading() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.route(
                "http://localhost:4100/",
                lambda route: route.fulfill(
                    content_type="text/html",
                    body='<link rel="stylesheet" href="/src/styles.css">'
                    '<main class="workspace"><div id="app"></div></main>',
                ),
            )
            page.goto("http://localhost:4100/")
            page.evaluate("""async () => {
                const { PanelController } = await import('/src/panel.ts');
                const controller = new PanelController(document.getElementById('app'), {
                    createSession: async () => 'layout-session',
                    subscribe: (_, handler) => { window.emit = handler; return () => {}; },
                    speechAvailable: async () => false,
                }, { requestSnapshot() {} });
                await controller.start();
                window.emit({type:'task_started', data:{task_id:'layout-task'}});
                for (let i = 0; i < 30; i++)
                    window.emit({type:'narration', data:{text:'رسالة سابقة ' + i}});
                window.showSuggestions = () => {
                    window.emit({type:'suggestions', data:{exact_count:3,
                        suggestions: [1,2,3].map(id => ({ id:String(id), label:'exact_match',
                            name:'كوتشي جري', price:'1750', currency:'EGP', unmet:[],
                            reason:'اختيار يناسب ميزانيتك. تفاصيل موثقة في المتجر.' }))}});
                    window.emit({type:'done',
                        data:{summary:'وجدت هذه الاختيارات.', language:'ar'}});
                };
                window.showSuggestions();
            }""")
            expect(page.locator(".suggestion-card h2").first).to_be_in_viewport()
            page.evaluate("""() => {
                window.emit({type:'task_started', data:{task_id:'second-task'}});
                document.getElementById('chat-scroll').scrollTop = 0;
                window.showSuggestions();
            }""")
            assert page.locator("#chat-scroll").evaluate("el => el.scrollTop") == 0
            page.evaluate("""() => {
                window.emit({type:'task_started', data:{task_id:'failed-task'}});
                window.emit({type:'error', data:{message:'Try again'}});
            }""")
            expect(page.locator("#retry-task")).to_be_in_viewport()
            expect(page.locator("#retry-task")).to_be_focused()
        finally:
            browser.close()


def test_long_conversation_stays_inside_panel_on_desktop_and_mobile() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for width, height in [(1280, 900), (390, 844), (390, 640)]:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto("http://localhost:4100/")
                expect(page.locator("#shopper-message")).to_be_enabled()
                store_before = page.locator("#storefront-frame").bounding_box()
                page.locator("#conversation").evaluate("""list => {
                    for (let i = 0; i < 60; i++) {
                        const item = document.createElement('li');
                        item.className = 'message message-copilot';
                        item.textContent = 'اختيار يناسب ميزانيتك — راجع التفاصيل قبل الإضافة.';
                        list.append(item);
                    }
                }""")
                assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1")
                assert page.locator("#chat-scroll").evaluate(
                    "el => el.scrollHeight > el.clientHeight && el.clientHeight > 30"
                )
                for selector in ["#stop-task", "#shopper-message"]:
                    box = page.locator(selector).bounding_box()
                    assert box and box["y"] >= 0 and box["y"] + box["height"] <= height
                assert page.locator("#storefront-frame").bounding_box() == store_before
                page.locator("#chat-scroll").evaluate("el => el.scrollTop = el.scrollHeight")
                expect(page.locator("#conversation li").last).to_be_in_viewport()
                page.locator("#speech-fallback-area").evaluate("el => el.hidden = false")
                assert page.locator("#chat-scroll").evaluate("el => el.clientHeight >= 100")
                box = page.locator("#shopper-message").bounding_box()
                assert box and box["y"] + box["height"] <= height
                page.close()
        finally:
            browser.close()
