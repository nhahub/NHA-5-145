"""Shopper-state ticket 03/04 browser case: a restart of all three local services keeps the
Shopper's cart and the Copilot conversation, and a new request still works.

The model is scripted (no network; see eval/plan_fixture_app.py). local_services gives the
Agent and the Storefront temporary state files, so every restart below reopens the same files.
"""

import subprocess
import time

from playwright.sync_api import expect, sync_playwright

from eval.browser_http import browser_post
from eval.plan_fixture_app import ADD_THIS, CART_STEP
from eval.services import ROOT, _wait_for, local_services

STORE = "http://localhost:4000"


def restart_panel(controller) -> None:
    """The controller restarts the Agent and the Storefront; the Panel is its third child."""
    process = controller.processes[2]
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    controller.processes[2] = subprocess.Popen(  # noqa: S603 - the fixture's own fixed command
        controller.commands[2],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=controller.creation_flags,
        env=controller.environment,
    )
    _wait_for("http://127.0.0.1:4100/")


def open_product_page(page):
    browser_post(page, STORE + "/__test/reset")
    page.goto("http://localhost:4100")
    expect(page.locator("#shopper-message")).to_be_enabled()
    frame = page.frame_locator("#storefront-frame")
    frame.locator("body").evaluate("() => { location.href = '/p/shoe-01'; }")
    expect(frame.locator("#product-size")).to_be_visible()
    frame.locator("#product-size").select_option("42")
    frame.locator("#product-color").select_option("black")
    return frame


def send(page, message):
    page.locator("#shopper-message").fill(message)
    page.get_by_role("button", name="إرسال", exact=True).click()


def cart_lines(page):
    lines = page.request.get(STORE + "/cart/state").json()["lines"]
    return [(line["product_id"], line["quantity"]) for line in lines]


def wait_for_cart(page, expected, timeout_seconds=15):
    deadline = time.monotonic() + timeout_seconds
    while cart_lines(page) != expected:
        assert time.monotonic() < deadline, f"cart never became {expected}"
        time.sleep(0.2)


def test_a_restart_of_all_services_keeps_the_cart_and_the_conversation():
    with (
        local_services(agent_app="eval.plan_fixture_app:app") as services,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            frame = open_product_page(page)

            # Add to the cart through the Copilot, then chat once more.
            send(page, ADD_THIS)
            expect(page.locator("#conversation")).to_contain_text(ADD_THIS)
            wait_for_cart(page, [("shoe-01", 1)])
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            send(page, CART_STEP)
            expect(frame.get_by_role("heading", name="السلة")).to_be_visible(timeout=15000)
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)

            # Restart all three local services, then reload.
            services.restart("agent")
            services.restart("store")
            restart_panel(services)
            page.reload()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=20000)

            # The cart and the conversation are still there.
            assert cart_lines(page) == [("shoe-01", 1)]
            conversation = page.locator("#conversation")
            expect(conversation).to_contain_text(ADD_THIS, timeout=15000)
            expect(conversation).to_contain_text(CART_STEP)

            # A new request works after the restart.
            frame = page.frame_locator("#storefront-frame")
            send(page, CART_STEP)
            expect(frame.get_by_role("heading", name="السلة")).to_be_visible(timeout=15000)
            assert cart_lines(page) == [("shoe-01", 1)]
        finally:
            browser.close()
