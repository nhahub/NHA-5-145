"""Opt-in live navigation followup plus deterministic sign-in handoff acceptance."""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from agent.llm import load_llm_settings
from agent.llm.intent_pipeline import PROMPT_VERSION
from eval.services import local_services


def main() -> int:
    if os.environ.get("LLM_BROWSER_SMOKE") != "1":
        raise SystemExit("Set LLM_BROWSER_SMOKE=1 for credentialed acceptance.")
    settings = load_llm_settings()
    if settings.provider != "groq":
        raise SystemExit("This check requires the configured local Groq provider.")
    report = {"prompt_version": PROMPT_VERSION, "schema_version": 3, "passed": False}
    reports = Path(__file__).resolve().parent / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    with local_services(real_model=True), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto("http://localhost:4100/")
            page.locator("#shopper-message").fill("وريني سجل الطلبات فين")
            page.get_by_role("button", name="إرسال").click()
            expect(page.locator("#task-status")).to_have_attribute(
                "data-task-state", "completed", timeout=60_000
            )
            print("Verified initial locate; waiting for free-tier token window.", flush=True)
            time.sleep(45)
            page.locator("#shopper-message").fill("ممكن توديني هناك؟")
            page.get_by_role("button", name="إرسال").click()
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("h1")).to_have_text("تسجيل الدخول", timeout=60_000)
            continue_button = page.locator('[data-question-option="Continue"]')
            expect(continue_button).to_be_visible()
            before = page.locator("#conversation li").count()
            continue_button.click()
            expect(continue_button).to_be_disabled()
            expect(page.locator("#login-wait-hint")).to_be_visible()
            assert page.locator("#conversation li").count() == before
            # Fictional test account; credentials are entered by the test browser,
            # never by a Copilot Action or sent to the model.
            frame.locator("#username").fill("shopper@example.test")
            frame.locator("#password").fill("fictional-only")
            frame.get_by_role("button", name="متابعة").click()
            expect(frame.locator("h1")).to_have_text("الطلبات")
            expect(continue_button).to_be_enabled()
            continue_button.click()
            expect(page.locator("#task-status")).to_have_attribute("data-task-state", "completed")
            report["passed"] = True
        except Exception as error:
            report["failure"] = type(error).__name__
            report["status"] = page.locator("#task-status").inner_text()
        finally:
            browser.close()
    path = reports / f"semantic-followup-browser-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), **report}, ensure_ascii=True), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
