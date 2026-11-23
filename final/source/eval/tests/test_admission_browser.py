from time import time

import pytest
from playwright.sync_api import expect, sync_playwright

from agent.admission.runtime import FIELDS
from agent.admission.store import InvitationStore
from eval.services import local_services


@pytest.mark.parametrize("mobile", [False, True])
def test_invitation_entry_refresh_isolation_and_live_revocation(tmp_path, monkeypatch, mobile):
    path = tmp_path / "admission.sqlite"
    identity = InvitationStore.initialize(path)
    store = InvitationStore(path, identity)
    invitation, code = store.issue(time() - 1, time() + 300, redemptions=1, sessions=8)
    monkeypatch.setenv("ADMISSION_DB_PATH", str(path))
    monkeypatch.setenv("ADMISSION_DB_ID", identity)
    values = dict(
        maximum_bytes=2621440,
        global_rate=1000,
        browser_rate=120,
        maximum_requests=16,
        maximum_streams=16,
        maximum_sessions=20,
        browser_sessions=2,
    )
    for key, name in FIELDS.items():
        monkeypatch.setenv("ADMISSION_" + name, str(values[key]))
    with local_services(), sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            first = browser.new_context(viewport={"width": 390 if mobile else 1280, "height": 844})
            page = first.new_page()
            page.goto("http://localhost:4100/")
            # The first Vite module graph can start cold, before any Panel UI exists.
            # Match the existing browser startup/restart allowance; all admission
            # and action assertions below keep their ordinary bounded deadlines.
            expect(page.locator("#admission-code")).to_be_visible(timeout=15000)
            expect(page.frame_locator("#storefront-frame").locator("h1")).to_have_text(
                "تسوّق بسهولة"
            )
            expect(page.locator("#shopper-message")).to_be_disabled()
            page.screenshot(path=str(tmp_path / "admission-entry.png"))
            page.locator("#admission-code").fill("invalid-test-code")
            page.locator(".admission-entry button").click()
            expect(page.locator(".admission-entry [role=status]")).to_contain_text(
                "Code unavailable"
            )
            assert page.locator("#admission-code").input_value() == ""
            page.locator("#admission-code").fill(code)
            page.locator(".admission-entry button").click()
            expect(page.locator("#shopper-message")).to_be_enabled()
            page.locator("#shopper-message").fill("Open my cart")
            page.locator(".message-form button[type=submit]").click()
            expect(page.frame_locator("#storefront-frame").locator("h1")).to_have_text("السلة")
            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled()
            assert page.locator("#admission-code").count() == 0
            saved = page.evaluate(
                "JSON.stringify({local:{...localStorage},session:{...sessionStorage}})"
            )
            assert code not in saved and code not in page.url
            page.route(
                "**/sessions/*/events?**",
                lambda route: route.fulfill(
                    status=429,
                    content_type="application/json",
                    body='{"code":"access_busy"}',
                    headers={
                        "Access-Control-Allow-Origin": "http://localhost:4100",
                        "Access-Control-Allow-Credentials": "true",
                    },
                ),
            )
            page.reload()
            expect(page.locator("#access-reload")).to_be_visible(timeout=8000)
            expect(page.locator("#shopper-message")).to_be_disabled()
            page.unroute("**/sessions/*/events?**")
            page.locator("#access-reload").click()
            expect(page.locator("#shopper-message")).to_be_enabled()
            second = browser.new_context()
            other = second.new_page()
            other.goto("http://localhost:4100/")
            expect(other.locator("#admission-code")).to_be_visible()
            other.locator("#admission-code").fill(code)
            other.locator(".admission-entry button").click()
            expect(other.locator(".admission-entry [role=status]")).to_contain_text(
                "Code unavailable"
            )
            expect(other.locator("#shopper-message")).to_be_disabled()
            store.revoke(invitation)
            expect(page.locator("#admission-code")).to_be_visible(timeout=10000)
            expect(page.locator("#shopper-message")).to_be_disabled()
            assert store.status()[0]["used_redemptions"] == 1
            second.close()
            first.close()
        finally:
            browser.close()
