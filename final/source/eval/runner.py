import json
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from playwright.sync_api import BrowserContext, BrowserType, Frame, expect, sync_playwright

from eval.browser_http import browser_post
from eval.cases import (
    DISCOVERY_CASES,
    TICKET_08_CASES,
    TICKET_13_CASES,
    EvaluationAssertion,
    EvaluationCase,
)
from eval.services import local_services

PANEL_URL = "http://localhost:4100/"
RESET_URL = "http://localhost:4000/__test/reset"
STATE_URL = "http://localhost:4000/__test/state"
LOGIN_URL = "http://localhost:4000/login"
ORDER_HISTORY_PATH = "/account/orders"
_TEST_SHOPPER_CREDENTIALS = {
    "username": "ticket08-shopper@example.test",
    "password": "ticket08-fictional-password",
}


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    step_count: int
    elapsed_ms: float
    failure: str | None
    suggestions: tuple[dict[str, str], ...] = ()
    status_text: str = ""
    pending_question: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def remaining_timeout_ms(deadline: float) -> int:
    remaining = int((deadline - time.perf_counter()) * 1000)
    if remaining <= 0:
        raise TimeoutError("Evaluation Case exceeded its configured timeout")
    return remaining


def state_value(state: Mapping[str, Any], path: str) -> Any:
    value: Any = state
    for segment in path.split("."):
        if not isinstance(value, Mapping) or segment not in value:
            raise AssertionError(f"Authoritative Storefront state has no value at {path!r}")
        value = value[segment]
    return value


def _reset_storefront(context: BrowserContext, timeout_ms: int) -> None:
    response = browser_post(context, RESET_URL, timeout=max(timeout_ms, 1))
    if response.status != 204:
        raise RuntimeError(f"Storefront reset failed with {response.status}")


def _frame_for_storefront(page) -> Frame:
    frame = page.frame(url=re.compile(r"http://localhost:4000/"))
    if frame is None:
        raise AssertionError("Storefront frame was not available")
    return frame


def authoritative_state_url(frame_url: str) -> str:
    parts = urlsplit(frame_url)
    parameters: list[tuple[str, str]] = []
    path_match = re.fullmatch(r"/c/([^/]+)", parts.path)
    if path_match is not None:
        parameters.append(("category", path_match.group(1)))
    parameters.extend(parse_qsl(parts.query, keep_blank_values=True))
    query = urlencode(parameters)
    return f"{STATE_URL}?{query}" if query else STATE_URL


def _authoritative_store_state(
    context: BrowserContext, frame_url: str, timeout_ms: int
) -> dict[str, Any]:
    url = authoritative_state_url(frame_url)
    response = context.request.get(url, timeout=max(timeout_ms, 1))
    if not response.ok:
        raise RuntimeError(f"Storefront state unavailable: {response.status}")
    return response.json()


def _prepare_case_setup(context: BrowserContext, case: EvaluationCase, timeout_ms: int) -> None:
    if case.setup != "authenticated":
        return
    response = browser_post(
        context,
        LOGIN_URL,
        form=_TEST_SHOPPER_CREDENTIALS,
        timeout=max(timeout_ms, 1),
        max_redirects=0,
    )
    if response.status != 303 or response.headers.get("location") != ORDER_HISTORY_PATH:
        raise AssertionError("Fictional authenticated Evaluation Case setup failed")


def _prepare_storefront_controls(page, case: EvaluationCase, timeout_ms: int) -> None:
    if case.setup not in {"selected_swatch", "disabled_product", "loaded_catalogue"}:
        return
    # Panel startup chooses the initial iframe URL asynchronously. Wait before
    # manually preparing a case so startup cannot overwrite this navigation.
    expect(page.locator("#shopper-message")).to_be_enabled(timeout=timeout_ms)
    frame = page.frame_locator("#storefront-frame")
    destination = "/c/shoes" if case.setup == "loaded_catalogue" else "/p/shoe-09"
    _frame_for_storefront(page).goto(
        "http://localhost:4000" + destination,
        wait_until="domcontentloaded",
        timeout=timeout_ms,
    )
    if case.setup == "loaded_catalogue":
        expect(frame.locator("#results-heading")).to_have_text("15 منتجات", timeout=timeout_ms)
        load_more = frame.locator("#load-more-products")
        load_more.evaluate("button => button.click()")
        expect(frame.locator("[data-product-id]")).to_have_count(12, timeout=timeout_ms)
        load_more.evaluate("button => button.click()")
        expect(frame.locator("[data-product-id]")).to_have_count(15, timeout=timeout_ms)
        return
    expect(frame.locator("#product-size")).to_be_visible(timeout=timeout_ms)
    expect(frame.locator("html")).to_have_attribute("data-cart-revision", "0", timeout=timeout_ms)
    frame.get_by_role("button", name="مقاس 43").click(timeout=timeout_ms)
    frame.locator("#product-color").select_option("blue", timeout=timeout_ms)
    if case.setup == "disabled_product":
        frame.locator("form[data-cart-edit='add']").evaluate(
            "form => { form.setAttribute('aria-disabled', 'true'); "
            "document.dispatchEvent(new Event('change')); }"
        )


def _assert_store_state(state: Mapping[str, Any], target: str, expected: str | None) -> None:
    if expected is None:
        raise AssertionError("Storefront state assertion requires an expected value")
    actual = state_value(state, target)
    if str(actual) != expected:
        raise AssertionError(
            f"Authoritative Storefront state {target!r} was {actual!r}, expected {expected!r}"
        )


def _assert_outcome(
    page,
    frame: Frame,
    assertion: EvaluationAssertion,
    store_state: Mapping[str, Any],
    timeout_ms: int,
) -> None:
    if assertion.kind == "panel_text":
        locator = page.locator(assertion.target)
        expect(locator).to_be_visible(timeout=timeout_ms)
        if assertion.expected is not None:
            expect(locator).to_have_text(assertion.expected, timeout=timeout_ms)
        return
    if assertion.kind == "panel_contains":
        if assertion.expected is None:
            raise AssertionError("Panel contains assertion requires expected text")
        expect(page.locator(assertion.target)).to_contain_text(
            assertion.expected, timeout=timeout_ms
        )
        return
    if assertion.kind == "panel_count":
        if assertion.expected is None:
            raise AssertionError("Panel count assertion requires an expected value")
        expect(page.locator(assertion.target)).to_have_count(
            int(assertion.expected), timeout=timeout_ms
        )
        return

    if assertion.kind == "url_matches":
        frame.wait_for_url(
            re.compile(assertion.target),
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
        return

    if assertion.kind == "store_state":
        _assert_store_state(store_state, assertion.target, assertion.expected)
        return

    locator = frame.locator(assertion.target)
    if assertion.kind == "element_visible":
        expect(locator).to_be_visible(timeout=timeout_ms)
        if assertion.expected is not None:
            expect(locator).to_have_text(assertion.expected, timeout=timeout_ms)
    elif assertion.kind == "element_spotlighted":
        expect(locator).to_be_visible(timeout=timeout_ms)
        expect(locator).to_have_attribute(
            "data-copilot-spotlight",
            assertion.expected or re.compile(".+"),
            timeout=timeout_ms,
        )


def run_evaluation(
    browser_type: BrowserType,
    cases: tuple[EvaluationCase, ...],
    *,
    inter_case_delay_seconds: float = 0,
) -> list[EvaluationResult]:
    browser = browser_type.launch(headless=True)
    results: list[EvaluationResult] = []
    try:
        for case_index, case in enumerate(cases):
            if case_index and inter_case_delay_seconds:
                time.sleep(inter_case_delay_seconds)
            started = time.perf_counter()
            deadline = started + (case.timeout_ms / 1000)
            context = browser.new_context(
                viewport={"width": case.viewport[0], "height": case.viewport[1]}
                if case.viewport is not None
                else None
            )
            page = context.new_page()
            step_count = 0

            def count_action_result(request) -> None:
                nonlocal step_count
                if request.method == "POST" and request.url.endswith("/action-results"):
                    step_count += 1

            page.on("request", count_action_result)
            failure: str | None = None
            try:
                _reset_storefront(context, remaining_timeout_ms(deadline))
                _prepare_case_setup(context, case, remaining_timeout_ms(deadline))
                page.goto(
                    PANEL_URL,
                    wait_until="domcontentloaded",
                    timeout=remaining_timeout_ms(deadline),
                )
                _prepare_storefront_controls(page, case, remaining_timeout_ms(deadline))
                page.locator("#shopper-message").fill(
                    case.message, timeout=remaining_timeout_ms(deadline)
                )
                page.get_by_role("button", name="إرسال").click(
                    timeout=remaining_timeout_ms(deadline)
                )
                if case.expected_status == "complete":
                    expect(page.locator("#task-status")).to_have_attribute(
                        "data-task-state", "completed", timeout=remaining_timeout_ms(deadline)
                    )
                frame = _frame_for_storefront(page)
                store_state = _authoritative_store_state(
                    context, frame.url, remaining_timeout_ms(deadline)
                )
                for assertion in case.assertions:
                    _assert_outcome(
                        page,
                        frame,
                        assertion,
                        store_state,
                        remaining_timeout_ms(deadline),
                    )
                remaining_timeout_ms(deadline)
            except Exception as error:  # Playwright failures must become case results
                if time.perf_counter() >= deadline:
                    failure = (
                        "TimeoutError: Evaluation Case exceeded its configured "
                        f"timeout of {case.timeout_ms}ms"
                    )
                else:
                    failure = f"{type(error).__name__}: {error}"
            elapsed_ms = (time.perf_counter() - started) * 1000
            observed_suggestions = tuple(
                {
                    "id": card.get_attribute("data-product-id") or "",
                    "label": card.get_attribute("data-match-kind") or "",
                    "visible_text": card.inner_text(),
                }
                for card in page.locator("#suggestions .suggestion-card").all()
            )
            results.append(
                EvaluationResult(
                    case_id=case.case_id,
                    passed=failure is None,
                    step_count=step_count,
                    elapsed_ms=elapsed_ms,
                    failure=failure,
                    suggestions=observed_suggestions,
                    status_text=(
                        page.locator("#task-status").inner_text()
                        if page.locator("#task-status").count()
                        else ""
                    ),
                    pending_question=(
                        page.locator("#pending-question").inner_text()
                        if page.locator("#pending-question").count()
                        else ""
                    ),
                )
            )
            context.close()
    finally:
        browser.close()
    return results


def main() -> int:
    with local_services(), sync_playwright() as playwright:
        results = run_evaluation(
            playwright.chromium, DISCOVERY_CASES + TICKET_08_CASES + TICKET_13_CASES
        )
    for result in results:
        print(json.dumps(result.as_dict(), ensure_ascii=True))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
