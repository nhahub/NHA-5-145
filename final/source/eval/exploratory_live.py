"""Bounded, opt-in exploratory shopping flows using the real model and browser."""

import json
import os
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path.cwd()
REPORT = ROOT / (
    "eval/reports/exploratory-user-flows"
    + ("-" + os.environ["LLM_EXPLORATORY_CASE"] if os.environ.get("LLM_EXPLORATORY_CASE") else "")
    + ".json"
)
BASE = [
    {"product_id": "shoe-04", "size": "44", "color": "black", "quantity": 1},
    {"product_id": "clothing-05", "size": "M", "color": "white", "quantity": 1},
    {"product_id": "clothing-05", "size": "L", "color": "white", "quantity": 2},
    {"product_id": "shoe-02", "size": "42", "color": "white", "quantity": 1},
]


def main():
    if os.environ.get("LLM_EXPLORATORY_EVAL") != "1":
        raise SystemExit("Set LLM_EXPLORATORY_EVAL=1 with real-model local services running")
    from agent.llm import load_llm_settings

    if load_llm_settings().provider == "scripted":
        raise SystemExit("A real provider is required")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    selected = os.environ.get("LLM_EXPLORATORY_CASE")
    rows = []
    requests = 0

    def parse(text):
        out = []
        for block in text.split("\n\n"):
            fields = {
                k: v.lstrip()
                for line in block.splitlines()
                if ": " in line
                for k, v in [line.split(": ", 1)]
            }
            if "data" in fields and "id" in fields:
                out.append(
                    {
                        "id": int(fields["id"]),
                        "event": fields["event"],
                        "data": json.loads(fields["data"]),
                    }
                )
        return out

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        api = pw.request.new_context(base_url="http://localhost:4000")
        saved = api.get("/__test/cart-state").json()["lines"]

        def cart():
            return api.get("/__test/cart-state").json()["lines"]

        class Flow:
            def __init__(self, name):
                self.row = {"case": name, "passed": False, "turns": []}
                self.page = browser.new_page()
                self.cursor = 0
                self.session = ""
                self.tab = ""
                api.post("/__test/cart", data={"lines": BASE})
                self.page.goto("http://localhost:4100/")
                self.frame = self.page.frame_locator("#storefront-frame")
                expect(self.frame.locator("h1")).to_have_text("تسوّق بسهولة")
                self.frame.locator("body").evaluate("() => {location.href='/cart'}")
                expect(self.frame.locator("[data-cart-line]")).to_have_count(4)

            def send(self, message, answer=False):
                nonlocal requests
                if requests >= 12:
                    raise RuntimeError("Live request cap reached")
                requests += 1
                suffix = "/answers" if answer else "/messages"
                self.page.locator("#question-answer-input" if answer else "#shopper-message").fill(
                    message
                )
                with self.page.expect_response(
                    lambda r: r.request.method == "POST" and r.url.endswith(suffix), timeout=45000
                ) as pending:
                    if answer:
                        self.page.locator("#question-answer-form button").click()
                    else:
                        self.page.get_by_role("button", name="إرسال", exact=True).click()
                response = pending.value
                if not answer:
                    self.session = response.url.removesuffix("/messages")
                self.tab = response.request.headers.get("x-tab-id", "")
                assert response.status == 202, f"HTTP {response.status}"
                task = response.json()["task_id"]
                turn = {"message": message, "task_id": task}
                self.row["turns"].append(turn)
                deadline = time.monotonic() + 40
                found = []
                while time.monotonic() < deadline:
                    events = parse(
                        api.get(
                            self.session + "/events",
                            params={"once": "true", "tab_id": self.tab, "after": self.cursor},
                        ).text()
                    )
                    if events:
                        self.cursor = events[-1]["id"]
                    found += [e for e in events if e["data"].get("task_id") == task]
                    terminal = next(
                        (e["event"] for e in found if e["event"] in ("done", "error", "cancelled")),
                        None,
                    )
                    question = next(
                        (
                            e["data"]["action"]
                            for e in found
                            if e["event"] == "action"
                            and e["data"]["action"]["type"] == "ask_shopper"
                        ),
                        None,
                    )
                    if terminal or question:
                        turn.update(outcome=terminal or "question", events=found, cart=cart())
                        print(self.row["case"], turn["outcome"], flush=True)
                        if question:
                            expect(self.page.locator(".question-card")).to_be_visible()
                        return turn
                    time.sleep(0.1)
                raise AssertionError("Task did not reach an outcome")

            def finish(self, error=None):
                if error:
                    self.row.update(error=type(error).__name__, detail=str(error)[:500])
                else:
                    self.row["passed"] = True
                self.page.close()
                rows.append(self.row)
                REPORT.write_text(
                    json.dumps(
                        {"submitted_requests": requests, "cases": rows},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

        def run(name, check):
            if selected and name != selected:
                return
            f = Flow(name)
            try:
                check(f)
            except Exception as e:
                f.finish(e)
            else:
                f.finish()

        def ambiguity(f):
            t = f.send("زود القميص اتنين")
            assert t["outcome"] == "question" and cart() == BASE, (
                "Ambiguous variants must ask without mutation"
            )
            t = f.send("الابيض مقاس L", answer=True)
            expected = [BASE[0], BASE[1], {**BASE[2], "quantity": 4}, BASE[3]]
            assert t["outcome"] == "done" and cart() == expected, (
                "Clarified L variant must increase 2 -> 4 only"
            )
            t = f.send("لا خليه واحد بس")
            assert t["outcome"] == "done" and cart() == [
                BASE[0],
                BASE[1],
                {**BASE[2], "quantity": 1},
                BASE[3],
            ], "Changed final quantity must affect same variant only"

        def negated_remove(f):
            t = f.send("ما تشيلش ماراثون القاهرة، احذف خطوة سريعة بس")
            assert t["outcome"] == "done" and cart() == BASE[:3], (
                "Only the positively requested line may be removed"
            )
            t = f.send("رجع اللي شلته")
            assert t["outcome"] == "done" and cart() == BASE, (
                "Undo must restore the exact deleted line"
            )

        def clear_cancel(f):
            t = f.send("فضي العربية كلها")
            assert t["outcome"] == "question" and cart() == BASE
            expect(f.page.locator(".confirmation-card")).to_be_visible()
            f.page.locator("#stop-task").click()
            expect(f.page.locator(".confirmation-card")).to_have_count(0)
            assert cart() == BASE, "Cancelling confirmation must preserve cart"

        def no_change(f, message):
            t = f.send(message)
            assert t["outcome"] in ("done", "question") and cart() == BASE, (
                "Should clarify or decline without a format error or mutation"
            )

        def exclusion(f):
            t = f.send("عايز حذاء مش جلد ومش اغلى من الفين جنيه")
            assert t["outcome"] == "done" and cart() == BASE
            suggestions = [
                e["data"]["suggestions"] for e in t["events"] if e["event"] == "suggestions"
            ]
            assert suggestions, "Must return grounded search results"
            products = {p["id"]: p for p in api.get("/__catalogue/v1/products").json()["products"]}
            for p in suggestions[-1]:
                assert float(p["price"]) <= 2000 and "leather" not in products[p["id"]]["features"]

        def typo(f):
            t = f.send("ودينى لصفحت قميص رسمى")
            assert t["outcome"] == "done" and cart() == BASE
            expect(f.frame.locator("h1")).to_have_text("قميص رسمي")

        try:
            run("ambiguous_variant_then_correction", ambiguity)
            run("negated_remove_then_undo", negated_remove)
            run("clear_then_cancel", clear_cancel)
            run("quantity_out_of_bounds", lambda f: no_change(f, "خلي عدد ماراثون القاهرة 1000"))
            run("vague_reference", lambda f: no_change(f, "زود ده اتنين"))
            run("self_correction_no_removal", lambda f: no_change(f, "شيل القميص لا استنى متشيلوش"))
            run("excluded_material_and_budget", exclusion)
            run("spelling_variation_navigation", typo)
        finally:
            api.post("/__test/cart", data={"lines": saved})
            assert cart() == saved
            browser.close()
            api.dispose()
    print(
        f"{sum(r['passed'] for r in rows)}/{len(rows)} cases passed; {requests} submitted requests",
        flush=True,
    )

    return 0 if rows and all(r["passed"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
