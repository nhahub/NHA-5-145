import re

from playwright.sync_api import expect, sync_playwright

from eval.cases import (
    DISCOVERY_CASES,
    TICKET_08_CASES,
    EvaluationAssertion,
    EvaluationCase,
)
from eval.runner import run_evaluation
from eval.services import local_services


def test_bilingual_discovery_cases_run_through_the_real_browser_path() -> None:
    with local_services(), sync_playwright() as playwright:
        results = run_evaluation(playwright.chromium, DISCOVERY_CASES)

    assert [result.case_id for result in results] == [
        "filter-ar",
        "filter-en",
        "filter-franco",
        "filter-mixed",
        "filter-unavailable",
        "filter-empty",
        "ask-ambiguous",
    ]
    assert all(result.passed for result in results), [result.failure for result in results]
    assert [result.step_count for result in results] == [1, 1, 1, 1, 1, 1, 0]
    assert all(result.elapsed_ms > 0 for result in results)
    assert all(result.failure is None for result in results)


def test_ticket_08_destination_cases_run_through_the_real_browser_path() -> None:
    with local_services(), sync_playwright() as playwright:
        results = run_evaluation(playwright.chromium, TICKET_08_CASES)

    assert [result.case_id for result in results] == [
        "ticket08-locate-cart",
        "ticket08-navigate-cart",
        "ticket08-locate-orders",
        "ticket08-orders-logged-out",
        "ticket08-orders-authenticated",
        "ticket08-navigate-account",
        "ticket08-navigate-checkout",
    ]
    assert all(result.passed for result in results), [result.failure for result in results]
    assert [result.step_count for result in results] == [1, 1, 1, 1, 2, 1, 1]
    assert "After signing in, should I continue to the newest order?" in (
        results[3].pending_question
    )
    assert all(result.failure is None for result in results)


def test_ticket_08_clarification_choice_opens_cart_without_stale_action() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("http://localhost:4100/")
            page.locator("#shopper-message").fill("Open cart or account")
            page.get_by_role("button", name="إرسال").click()
            choice = page.locator('[data-question-option="Open Cart"]')
            expect(choice).to_be_visible()
            choice.click()

            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("h1")).to_have_text("السلة")
            expect(page.locator("#task-status")).to_have_attribute("data-task-state", "completed")
            expect(page.locator("#conversation")).not_to_contain_text(
                re.compile("تعذر تنفيذ الإجراء بأمان|could not be completed safely")
            )
        finally:
            browser.close()


def test_ticket_08_login_handoff_waits_once_then_spotlights_newest_order() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("http://localhost:4100/")
            page.locator("#shopper-message").fill("Open order history")
            page.get_by_role("button", name="إرسال").click()
            frame = page.frame_locator("#storefront-frame")
            expect(frame.locator("h1")).to_have_text("تسجيل الدخول")
            continue_button = page.locator('[data-question-option="Continue"]')
            expect(continue_button).to_be_visible()
            before = page.locator("#conversation li").count()
            continue_button.click()
            expect(continue_button).to_be_disabled()
            expect(page.locator("#login-wait-hint")).to_contain_text("سجّل الدخول")
            assert page.locator("#conversation li").count() == before
            expect(page.locator('[data-question-option="Stop"]')).to_be_enabled()

            frame.locator("#username").fill("shopper@example.test")
            frame.locator("#password").fill("fictional-only")
            frame.get_by_role("button", name="متابعة").click()
            expect(frame.locator("h1")).to_have_text("الطلبات")
            expect(continue_button).to_be_enabled()
            continue_button.click()
            newest = frame.get_by_role("link", name="أحدث طلب")
            expect(newest).to_have_attribute("data-copilot-spotlight", re.compile(".+"))
            expect(page.locator("#task-status")).to_have_attribute("data-task-state", "completed")
        finally:
            browser.close()


def test_ticket_08_cart_spotlight_has_visible_emphasis() -> None:
    with local_services(), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto("http://localhost:4100/")
            page.locator("#shopper-message").fill("Where is my cart?")
            page.get_by_role("button", name="إرسال").click()
            cart_link = page.frame_locator("#storefront-frame").locator('a[href="/cart"]')
            expect(cart_link).to_have_attribute("data-copilot-spotlight", re.compile(".+"))
            emphasis = cart_link.evaluate(
                """element => {
                  const style = getComputedStyle(element);
                  const bounds = element.getBoundingClientRect();
                  return {
                    outline: style.outlineStyle,
                    width: parseFloat(style.outlineWidth),
                    halo: style.boxShadow,
                    inView: bounds.top >= 0 && bounds.bottom <= innerHeight
                  };
                }"""
            )
            assert emphasis["outline"] == "solid"
            assert emphasis["width"] >= 3
            assert emphasis["halo"] != "none"
            assert emphasis["inView"] is True
        finally:
            browser.close()


def test_case_timeout_is_reported_within_the_case_deadline() -> None:
    timeout_case = EvaluationCase(
        case_id="bounded-timeout",
        message="Show me running shoes under 2000 EGP",
        language="en",
        timeout_ms=750,
        assertions=(EvaluationAssertion(kind="element_visible", target="#never-appears"),),
    )

    with local_services(), sync_playwright() as playwright:
        result = run_evaluation(playwright.chromium, (timeout_case,))[0]

    assert result.passed is False
    assert "Timeout" in (result.failure or "")
    assert result.elapsed_ms < 2_000
