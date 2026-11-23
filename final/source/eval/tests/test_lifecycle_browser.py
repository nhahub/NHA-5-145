"""Waiting page and a built shopping host with external durable authority."""

import threading
import time
from pathlib import Path

import httpx
import uvicorn
from playwright.sync_api import expect, sync_playwright

from agent.admission.store import InvitationStore
from agent.lifecycle import Lifecycle
from agent.lifecycle.http import create_waiting_app
from deploy.lifecycle import LocalHost
from eval.tests.test_release import built_release as release_fixture
from eval.tests.test_release import configure_state

built_release = release_fixture


def test_invitation_waiting_page_boots_built_host_and_rechecks_revoked_access(
    built_release,
    tmp_path,
):
    config, values = configure_state(tmp_path / "host-state")
    # These files live outside the simulated host's release and survive stop.
    control = tmp_path / "outside-host"
    control.mkdir()
    old_admission = Path(values["ADMISSION_DB_PATH"])
    outside_admission = control / "admission.sqlite"
    old_admission.rename(outside_admission)
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            old_admission.as_posix(), outside_admission.as_posix()
        ),
        encoding="utf-8",
    )
    values["ADMISSION_DB_PATH"] = str(outside_admission)
    path = control / "lifecycle.sqlite"
    identity = Lifecycle.initialize(path)
    invitations = InvitationStore(Path(values["ADMISSION_DB_PATH"]), values["ADMISSION_DB_ID"])
    _, code = invitations.issue(time.time() - 1, time.time() + 600, redemptions=4, sessions=8)
    revoked, revoked_code = invitations.issue(
        time.time() - 1, time.time() + 600, redemptions=1, sessions=1
    )
    life = Lifecycle(path, identity, invitations)
    with config.open("a", encoding="utf-8") as output:
        output.write(f"LIFECYCLE_DB_PATH='{path.as_posix()}'\nLIFECYCLE_DB_ID='{identity}'\n")
    host = LocalHost(built_release, config, tmp_path / "logs")
    server = uvicorn.Server(
        uvicorn.Config(
            create_waiting_app(life, origin="http://localhost:4200"),
            host="127.0.0.1",
            port=4200,
            access_log=False,
            log_level="critical",
        )
    )
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            context = browser.new_context()
            page = context.new_page()
            page.goto("http://localhost:4200/")
            assert life.status()["state"] == "stopped"
            assert host.commands == set()
            page.locator("#code").fill(code)
            page.locator("button").click()
            page.wait_for_function("document.querySelector('#code').value === ''")
            deadline = time.monotonic() + 30
            while life.status()["state"] != "ready" and time.monotonic() < deadline:
                life.tick(host)
                time.sleep(0.1)
            assert life.status()["state"] == "ready"
            assert host.commands == {("start", 1)}
            page.locator("#enter").wait_for(state="visible", timeout=10000)
            assert page.url == "http://localhost:4200/"
            assert code not in page.evaluate("JSON.stringify([localStorage, sessionStorage])")
            # Expiry/revocation during startup never grants application access.
            invitations.revoke(revoked)
            page.locator("#enter").click()
            interactions = []
            page.on(
                "request",
                lambda request: interactions.append(request.url)
                if request.url.endswith("/shopper/activity")
                else None,
            )
            page.locator("#admission-code").wait_for(timeout=15000)
            page.locator("#admission-code").fill(revoked_code)
            page.locator(".admission-entry button").click()
            page.locator(".admission-entry [role='status']").filter(
                has_text="Code unavailable"
            ).wait_for()
            assert page.locator(".admission-entry").is_visible()
            assert interactions == []
            page.locator("#admission-code").fill(code)
            page.locator(".admission-entry button").click()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            assert invitations.status()[0]["used_redemptions"] == 1
            frame = page.frame(url="http://localhost:4000/")
            assert frame is not None
            frame.goto("http://localhost:4000/p/shoe-09")
            frame.locator("#product-size").select_option("43")
            frame.locator("#product-color").select_option("blue")
            page.locator("#shopper-message").fill("Add this to my cart")
            page.get_by_role("button", name="إرسال", exact=True).click()
            expect(frame.locator("#mini-cart-count")).to_have_text("1")
            expect(page.locator("#task-status")).to_have_attribute("data-task-state", "completed")
            # Closing the simulated host does not remove coordination or grant
            # a fresh quota. The ordinary release recovery suite covers cart /
            # Confirmation uncertainty across these same process restarts.
            host.stop(1)
            deadline = time.monotonic() + 15
            while host.observe()[0] != "stopped" and time.monotonic() < deadline:
                time.sleep(0.1)
            life.tick(host)
            assert life.status()["state"] == "stopped"
            assert Lifecycle(path, identity, invitations).status()["generation"] == 1
            assert invitations.status()[0]["used_redemptions"] == 1
            life.wake(code)
            deadline = time.monotonic() + 30
            while life.status()["state"] != "ready" and time.monotonic() < deadline:
                life.tick(host)
                time.sleep(0.1)
            assert life.status()["state"] == "ready"
            page.goto("http://localhost:4100/")
            page.locator("#admission-code").wait_for(timeout=15000)
            page.locator("#admission-code").fill(code)
            page.locator(".admission-entry button").click()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            # A host stop no longer empties the cart: saved state outlives the idle stop.
            lines = page.request.get("http://localhost:4000/cart/state").json()["lines"]
            assert [(line["product_id"], line["quantity"]) for line in lines] == [("shoe-09", 1)]
            assert invitations.status()[0]["used_redemptions"] == 2
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        host.close()
    with httpx.Client(timeout=1) as client:
        try:
            response = client.get("http://localhost:8000/health")
        except httpx.TransportError:
            response = None
        assert response is None
