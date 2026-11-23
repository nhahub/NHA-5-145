"""Five-Shopper HTTPS capacity probe. No paid provider or OS trust changes."""

import argparse
import json
import os
import platform
import time
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from eval.capacity.resources import Resources
from eval.capacity.services import PANEL, STORE, stack


def fetch(page, path):
    return page.evaluate(
        "async path => {const r=await fetch(path);return {status:r.status,body:await r.json()}}",
        path,
    )


def cart(page):
    return (
        page.frame_locator("#storefront-frame")
        .locator("body")
        .evaluate("async () => (await fetch('/cart/state')).json()")
    )


def cohort(browser, invitations, count, mobile, resources, folder):
    with ExitStack() as cleanup:
        pages = []
        mutation_posts = {}
        for index in range(count):
            context = cleanup.enter_context(
                browser.new_context(
                    viewport={"width": 390 if mobile else 1280, "height": 844},
                    is_mobile=mobile,
                    has_touch=mobile,
                )
            )
            page = context.new_page()
            mutation_posts[page] = 0

            def count_mutation(request, page=page):
                if request.method == "POST" and request.url.split("?")[0] == STORE + "/cart/items":
                    mutation_posts[page] += 1

            page.on("request", count_mutation)
            cdp = context.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send(
                "Network.setCookieControls",
                {
                    "enableThirdPartyCookieRestriction": True,
                    "disableThirdPartyCookieMetadata": True,
                    "disableThirdPartyCookieHeuristics": True,
                },
            )
            _, code = invitations.issue(
                time.time() - 1, time.time() + 600, redemptions=1, sessions=2
            )
            response = page.goto(PANEL)
            assert response.security_details()["protocol"] in {"TLS 1.2", "TLS 1.3"}
            assert page.evaluate("window.isSecureContext")
            page.locator("#admission-code").wait_for(timeout=15000)
            page.locator("#admission-code").fill(code)
            page.locator(".admission-entry button").click()
            expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
            frame = page.frame(url=STORE + "/")
            assert frame is not None
            frame.goto(STORE + "/p/shoe-09")
            frame.locator("#product-size").select_option("43")
            frame.locator("#product-color").select_option("blue")
            frame.locator('input[name="quantity"]').fill(str(index + 1))
            page.locator("#shopper-message").fill("capacity fixture add")
            page.evaluate("""() => {
                window.__capacityTiming = {};
                document.querySelector('.message-form').addEventListener('submit', () => {
                    window.__capacityTiming.started = performance.now();
                }, {once:true});
                new MutationObserver(() => {
                    const t=window.__capacityTiming;
                    if(t.started && t.elapsed===undefined && ['completed','paused'].includes(
                        document.querySelector('#task-status')?.dataset.taskState)) {
                        t.elapsed=performance.now()-t.started;
                    }
                }).observe(document.querySelector('#task-status'), {attributes:true});
            }""")
            pages.append(page)
        # Hold the first two model entries until every browser has submitted, so
        # overload is deterministic rather than depending on Playwright click speed.
        hold = folder / "hold"
        hold.write_text("bounded capacity fixture", encoding="utf-8")
        before = (
            json.loads((folder / "provider.json").read_text())
            if (folder / "provider.json").exists()
            else {"calls": []}
        )
        try:
            with Resources(resources) as samples:
                for page in pages:
                    page.evaluate("document.querySelector('.message-form').requestSubmit()")
                # Keep the gate shut until actual overload responses are visible;
                # do not assume every browser dispatch reaches the queue in 500ms.
                if count > 5:
                    deadline = time.monotonic() + 5
                    while (
                        sum(
                            p.locator("#task-status").get_attribute("data-task-state") == "paused"
                            for p in pages
                        )
                        < count - 5
                    ):
                        if time.monotonic() > deadline:
                            raise RuntimeError("Overload did not produce bounded refusal")
                        pages[0].wait_for_timeout(25)
                hold.unlink()
                elapsed = []
                outcomes = []
                for index, page in enumerate(pages):
                    page.wait_for_function(
                        "['completed','paused'].includes(document.querySelector('#task-status')?.dataset.taskState)",
                        timeout=15000,
                    )
                    outcomes.append(page.locator("#task-status").get_attribute("data-task-state"))
                    elapsed.append(page.evaluate("window.__capacityTiming.elapsed"))
                    state = cart(page)
                    lines = state["lines"]
                    if outcomes[-1] == "completed":
                        assert len(lines) == 1 and lines[0]["quantity"] == index + 1
                    else:
                        assert lines == []
                # Foreign session state is denied despite valid independent access.
                if len(pages) > 1:
                    foreign = pages[0].evaluate(
                        "localStorage.getItem('shopping-copilot.session-id')"
                    )
                    assert (
                        fetch(pages[1], f"/sessions/{foreign}/state?tab_id=foreign")["status"]
                        == 404
                    )
                # Refresh restores state/SSE but never repeats the applied cart POST.
                applied = next((i for i, s in enumerate(outcomes) if s == "completed"), None)
                if applied is not None:
                    page = pages[applied]
                    original = cart(page)
                    posts_before = mutation_posts[page]
                    page.reload()
                    expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
                    restored = cart(page)
                    assert restored["lines"] == original["lines"]
                    assert restored["revision"] == original["revision"]
                    assert mutation_posts[page] == posts_before == 1
            after = json.loads((folder / "provider.json").read_text())
            calls = after["calls"][len(before["calls"]) :]
            queue = after["queue"][len(before.get("queue", [])) :]
            accepted = sum(s == "completed" for s in outcomes)
            assert accepted == min(count, 5), outcomes
            assert len(calls) == accepted
            assert after["peak"] <= 2 and after["active"] == 0
            return {
                "shoppers": count,
                "completed": accepted,
                "paused": count - accepted,
                "browser_completion_ms": elapsed,
                "pre_provider_ms": [c["pre_provider_ms"] for c in calls],
                "queue_wait_ms": [q["milliseconds"] for q in queue if q["outcome"] == "acquired"],
                "queue_full": sum(q["outcome"] == "full" for q in queue),
                "provider_ms": [c["provider_ms"] for c in calls],
                "provider_peak": after["peak"],
                "resources": samples.summary(),
                "isolation_and_refresh": "passed",
            }
        finally:
            hold.unlink(missing_ok=True)
            states = []
            for page in pages:
                if not page.is_closed():
                    states.append(
                        page.evaluate("""() => ({
                        state:document.querySelector('#task-status')?.dataset.taskState,
                        conversation_entries:document.querySelector('#conversation')?.children.length,
                        has_pending_question:!!document.querySelector('#pending-question')?.children.length,
                    })""")
                    )
            (folder / "last-browser-status.json").write_text(json.dumps(states), encoding="utf-8")


def denied_new_shopper(browser, invitations, expected):
    """A fresh browser identity cannot replenish the shared durable allowance."""
    with browser.new_context() as context:
        page = context.new_page()
        _, code = invitations.issue(time.time() - 1, time.time() + 600, redemptions=1, sessions=1)
        page.goto(PANEL)
        page.locator("#admission-code").wait_for(timeout=15000)
        page.locator("#admission-code").fill(code)
        page.locator(".admission-entry button").click()
        expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
        page.locator("#shopper-message").fill("capacity fixture add")
        page.locator(".message-form button[type=submit]").click()
        expect(page.locator("#task-status")).to_have_attribute("data-task-state", "paused")
        expect(page.locator("#task-status")).to_contain_text(expected)
        assert cart(page)["lines"] == []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--channel", choices=["chromium", "chrome", "msedge"], default="chromium")
    parser.add_argument("--mobile-emulation", action="store_true")
    parser.add_argument("--caddy", type=Path, help="Verified native Caddy executable")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "paid_calls": 0,
        "physical_android": "not tested",
        "ec2_capacity": "not tested",
        "channel": args.channel,
        "mobile_emulation": args.mobile_emulation,
        "tls_trust": "disposable browser-only SPKI pin; no OS CA installed",
        "logical_cpus": os.cpu_count(),
        "platform": platform.system(),
        "levels": [],
    }
    try:
        with (
            stack(output, caddy_path=args.caddy) as (invitations, ledger, processes, pin),
            sync_playwright() as pw,
            pw.chromium.launch(
                channel=None if args.channel == "chromium" else args.channel,
                args=[
                    "--host-resolver-rules=MAP panel.copilot.test 127.0.0.1, "
                    "MAP store.copilot.test 127.0.0.1",
                    "--no-proxy-server",
                    "--ignore-certificate-errors-spki-list=" + pin,
                ],
            ) as browser,
        ):
            result["browser_version"] = browser.version
            for count in (1, 5, 8):
                result["levels"].append(
                    cohort(browser, invitations, count, args.mobile_emulation, processes, output)
                )
            result["allowance"] = ledger.status()
            assert result["allowance"]["attempts"] == 11
            ledger.reserve("controlled-exhaustion", Decimal(result["allowance"]["remaining_usd"]))
            denied_new_shopper(browser, invitations, "spending allowance")
            ledger.set_enabled(False)
            denied_new_shopper(browser, invitations, "temporarily disabled")
            # Reopening the authority retains both spent reservations and disable.
            from agent.inference.ledger import AllowanceLedger

            reopened = AllowanceLedger(ledger.path, ledger.identity)
            assert reopened.status()["remaining_usd"] == "0.000000000"
            assert not reopened.status()["enabled"]
            assert len(json.loads((output / "provider.json").read_text())["calls"]) == 11
            result["new_cookie_exhaustion_and_disable"] = "passed"
            result["outcome"] = "passed"
    except BaseException as error:
        result["outcome"] = "failed"
        result["failure_type"] = type(error).__name__
        raise
    finally:
        if output.is_dir():
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
