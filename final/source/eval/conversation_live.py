"""Opt-in real-model conversations across product, recommendation and cart tasks."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from agent.llm import load_llm_settings


def main() -> int:
    if os.environ.get("LLM_CONVERSATION_EVAL") != "1":
        raise SystemExit("Set LLM_CONVERSATION_EVAL=1 with real-model local services running")
    if load_llm_settings().provider == "scripted":
        raise SystemExit("Conversation evaluation requires a real provider")
    output = Path("eval/reports/conversation-live.json")
    output.parent.mkdir(exist_ok=True)
    rows = []
    requests = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        api = pw.request.new_context(base_url="http://localhost:4000")
        saved = api.get("/__test/cart-state").json()["lines"]
        base = [
            {"product_id": "shoe-04", "size": "44", "color": "black", "quantity": 1},
            {"product_id": "clothing-05", "size": "L", "color": "white", "quantity": 1},
            {"product_id": "shoe-02", "size": "42", "color": "white", "quantity": 1},
        ]
        try:
            for scenario in ("cart_product_return", "earlier_recommendation"):
                api.post("/__test/cart", data={"lines": base})
                page = browser.new_page()
                row = {"scenario": scenario, "turns": [], "passed": False}
                session_url = ""
                tab_id = ""

                def submit(message, page=page, row=row):
                    nonlocal requests, session_url, tab_id
                    if requests >= 8:
                        raise RuntimeError("Conversation evaluation request bound reached")
                    requests += 1
                    page.locator("#shopper-message").fill(message)
                    with page.expect_response(
                        lambda r: r.request.method == "POST" and r.url.endswith("/messages"),
                        timeout=45000,
                    ) as pending:
                        page.get_by_role("button", name="إرسال", exact=True).click()
                    response = pending.value
                    session_url = response.url.removesuffix("/messages")
                    tab_id = response.request.headers.get("x-tab-id", "")
                    row["turns"].append(
                        {"message": message, "task_id": response.json().get("task_id")}
                    )
                    assert response.status == 202
                    expect(page.locator("#task-status")).to_have_attribute(
                        "data-task-state", "completed", timeout=45000
                    )
                    row["turns"][-1]["completed"] = True

                try:
                    page.goto("http://localhost:4100/")
                    frame = page.frame_locator("#storefront-frame")
                    expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
                    if scenario == "cart_product_return":
                        frame.locator("body").evaluate("() => {location.href='/cart'}")
                        expect(frame.locator("[data-cart-line]")).to_have_count(3)
                        submit("عايز 4 كمان من ماراثون القاهرة")
                        assert api.get("/__test/cart-state").json()["lines"] == [
                            {**base[0], "quantity": 5},
                            *base[1:],
                        ]
                        submit("وديني لصفحة قميص رسمي تاني كده")
                        expect(frame.locator("h1")).to_have_text("قميص رسمي")
                        submit("خلينا نرجع للسلة")
                        expect(frame.locator("[data-cart-line]")).to_have_count(3)
                        submit("افتحلي صفحة القميص من تاني")
                        expect(frame.locator("h1")).to_have_text("قميص رسمي")
                    else:
                        submit("رشحلي قميص أبيض")
                        # Read the actual recommendations; never supply model decisions.
                        event_text = api.get(
                            session_url + "/events", params={"once": "true", "tab_id": tab_id}
                        ).text()
                        recommendations = [
                            json.loads(line[6:])["suggestions"]
                            for line in event_text.splitlines()
                            if line.startswith("data: ") and '"suggestions":' in line
                        ]
                        first = recommendations[-1][0]
                        submit("افتح صفحة " + first["name"])
                        expect(frame.locator("h1")).to_have_text(first["name"])
                        submit("رشحلي حذاء خفيف للمشي")
                        # Leave the original product page before testing an older reference.
                        frame.locator("body").evaluate("() => {location.href='/c/shoes'}")
                        expect(frame.locator("h1")).to_contain_text("الأحذية")
                        submit("ارجع لصفحة " + first["name"] + " اللي كنت مقترحه في الأول")
                        expect(frame.locator("h1")).to_have_text(first["name"])
                        assert api.get("/__test/cart-state").json()["lines"] == base
                    row["passed"] = True
                except Exception as error:
                    row["error"] = type(error).__name__
                    row["status"] = page.locator("#task-status").inner_text()
                finally:
                    page.close()
                    rows.append(row)
                    output.write_text(
                        json.dumps(
                            {"requests": requests, "scenarios": rows}, ensure_ascii=False, indent=2
                        ),
                        encoding="utf-8",
                    )
                    print(scenario, row["passed"], flush=True)
        finally:
            api.post("/__test/cart", data={"lines": saved})
            browser.close()
            api.dispose()
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
