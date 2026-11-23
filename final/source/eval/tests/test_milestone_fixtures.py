from playwright.sync_api import sync_playwright

from eval.milestone import BASE, Flow
from eval.milestone_cases import Case
from eval.services import local_services


def test_milestone_fixture_uses_owned_cart_and_authenticated_telemetry(monkeypatch):
    monkeypatch.setenv("MILESTONE_EVAL", "1")
    with local_services(agent_app="eval.milestone_server:app"), sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            flow = Flow(
                browser, Case("owned-fixture", "navigation", "Open my cart", expected="/cart")
            )
            assert flow.cart()["lines"] == BASE
            assert flow.metrics() == []
            flow.check()
            first_task = flow.turns[-1]["task_id"]
            flow.done("Open my account")
            assert flow.turns[-1]["task_id"] != first_task
            assert flow.turns[-1]["outcome"] == "done"
            flow.install_reconnect()
            flow.done("Open my cart")
            assert flow.reconnect_count > 1
            assert flow.finish(None)["passed"]
        finally:
            browser.close()
