"""Browser transport intercepted before any request can leave the test process."""

import hashlib
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://d123example.cloudfront.net"


@pytest.mark.parametrize("code", ["offline-invitation", "دعوة للتجربة"])
@pytest.mark.parametrize("origin", [ORIGIN, "http://localhost:4200"])
def test_waiting_browser_hashes_exact_body_and_keeps_code_private(code, origin):
    requests = []
    html = (ROOT / "agent/lifecycle/waiting.html").read_text(encoding="utf-8")
    html = html.replace("NONCE", "test-nonce")
    shopping = (
        "http://localhost:4100/" if origin.startswith("http:") else "https://app.scpilot.tech/"
    )
    html = html.replace("http://localhost:4100/", shopping)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        def intercept(route):
            request = route.request
            if request.url == origin + "/":
                route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=html,
                    headers={
                        "Content-Security-Policy": "default-src 'none'; connect-src 'self'; "
                        "script-src 'nonce-test-nonce'; style-src 'nonce-test-nonce'; "
                        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
                    },
                )
            elif request.url == origin + "/wake":
                requests.append((request.url, request.headers, request.post_data))
                route.fulfill(
                    status=202, content_type="application/json", body='{"state":"starting"}'
                )
            elif request.url == origin + "/status":
                route.fulfill(status=200, content_type="application/json", body='{"state":"ready"}')
            else:
                route.abort()

        page.route("**/*", intercept)
        page.goto(origin)
        page.locator("input").fill(code)
        page.locator("button").click()
        expect(page.locator("#enter")).to_be_visible()
        assert len(requests) == 1
        url, headers, body = requests[0]
        assert json.loads(body) == {"code": code}
        assert (
            headers.get("x-amz-content-sha256") == hashlib.sha256(body.encode("utf-8")).hexdigest()
        )
        assert url == origin + "/wake"
        assert page.locator("input").input_value() == ""
        assert page.evaluate("localStorage.length + sessionStorage.length") == 0
        assert page.locator("#enter").get_attribute("href") == shopping
        browser.close()


def test_waiting_browser_hash_failure_sends_no_wake():
    requests = []
    html = (
        (ROOT / "agent/lifecycle/waiting.html").read_text(encoding="utf-8").replace("NONCE", "test")
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script("crypto.subtle.digest = async () => { throw new Error('offline'); };")

        def intercept(route):
            if route.request.url == ORIGIN + "/":
                route.fulfill(status=200, content_type="text/html", body=html)
            else:
                requests.append(route.request.url)
                route.fulfill(status=503, content_type="application/json", body="{}")

        page.route("**/*", intercept)
        page.goto(ORIGIN)
        page.locator("input").fill("offline-invitation")
        page.locator("button").click()
        expect(page.locator("#status")).to_have_text("Could not request startup. Retry later.")
        expect(page.locator("button")).to_be_enabled()
        assert not requests
        assert page.locator("input").input_value() == ""
        browser.close()
