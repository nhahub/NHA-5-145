"""Opt-in paid cart acceptance against running local OpenRouter-backed services."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    if os.environ.get("LLM_BROWSER_SMOKE") != "1":
        raise SystemExit("Set LLM_BROWSER_SMOKE=1 with local OpenRouter services running")
    selected = os.environ.get("LLM_BROWSER_CASE")
    if selected and selected not in {"add", "quantity", "remove", "clear"}:
        raise SystemExit("Unknown LLM_BROWSER_CASE")
    report = Path(
        "eval/reports/openrouter-cart-browser" + (f"-{selected}" if selected else "") + ".json"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        api = pw.request.new_context(base_url="http://localhost:4000")
        saved = api.get("/__test/cart-state").json()["lines"]
        base = [
            {"product_id": "shoe-13", "size": "43", "color": "black", "quantity": 1},
            {"product_id": "clothing-01", "size": "L", "color": "black", "quantity": 1},
        ]
        try:
            for kind, message in [
                ("add", "ضيف صانع اللعب للسلة مقاس 43 لون اسود"),
                ("quantity", "عايزك تضيف اتنين كمان من كوتشي صانع اللعب"),
                ("remove", "شيل صانع اللعب من السلة"),
                ("clear", "شيل الحاجة اللي فالسلة كلها"),
            ]:
                if selected and kind != selected:
                    continue
                api.post("/__test/cart", data={"lines": base})
                page = browser.new_page()
                row = {"case": kind, "passed": False}
                try:
                    page.goto("http://localhost:4100/")
                    frame = page.frame_locator("#storefront-frame")
                    expect(frame.locator("h1")).to_have_text("تسوّق بسهولة")
                    route = "/p/shoe-13" if kind == "add" else "/cart"
                    frame.locator("body").evaluate(
                        "(element, route) => {location.href=route}", route
                    )
                    if kind == "add":
                        expect(frame.locator("#product-size")).to_be_visible()
                        frame.locator("#product-size").select_option("43")
                        frame.locator("#product-color").select_option("black")
                    else:
                        expect(frame.locator("[data-cart-line]")).to_have_count(2)
                    page.locator("#shopper-message").fill(message)
                    page.get_by_role("button", name="إرسال", exact=True).click()
                    if kind == "clear":
                        card = page.locator(".confirmation-card")
                        expect(card).to_be_visible(timeout=45000)
                        assert api.get("/__test/cart-state").json()["lines"] == base
                        row["unchanged_before_confirmation"] = True
                        card.locator(
                            'button[data-question-option="تأكيد"],button[data-question-option="Confirm"]'
                        ).click()
                    expect(page.locator("#task-status")).to_have_attribute(
                        "data-task-state", "completed", timeout=45000
                    )
                    lines = api.get("/__test/cart-state").json()["lines"]
                    expected = (
                        []
                        if kind == "clear"
                        else base[1:]
                        if kind == "remove"
                        else [{**base[0], "quantity": 2 if kind == "add" else 3}, base[1]]
                    )
                    assert lines == expected
                    if kind != "clear":
                        frame.locator('[data-testid="undo-cart"]').click()
                        expect(frame.locator("#cart-feedback")).to_contain_text("تم التراجع")
                        assert api.get("/__test/cart-state").json()["lines"] == base
                        row["undo_restored_exact_cart"] = True
                    row["passed"] = True
                except Exception as error:
                    row["error"] = type(error).__name__
                    row["detail"] = str(error)[:1800]
                    row["status"] = page.locator("#task-status").inner_text()
                    row["panel"] = page.locator("body").inner_text()[-1800:]
                finally:
                    page.close()
                results.append(row)
                report.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(kind, row["passed"], flush=True)
        finally:
            api.post("/__test/cart", data={"lines": saved})
            browser.close()
            api.dispose()
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
