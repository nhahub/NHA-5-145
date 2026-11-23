"""Acceptance operator boundaries with synthetic time and HTTP, never cloud credentials."""

import json

import httpx
import pytest


def test_reboot_does_not_renew_deadlines_or_authorize_second_boot():
    from eval.cap07_host_acceptance import SessionWindow

    window = SessionWindow(1000)
    window.authorize("start", 1001)
    window.authorize("reboot", 1000 + 130 * 60)
    with pytest.raises(ValueError):
        window.authorize("reboot", 1000 + 131 * 60)
    with pytest.raises(ValueError):
        window.authorize("start", 1000 + 132 * 60)
    with pytest.raises(ValueError):
        window.authorize("work", 1000 + 161 * 60)
    window.authorize("cleanup", 1000 + 241 * 60)


@pytest.mark.parametrize("case", ["clock", "expired", "no_watchdog", "no_barrier", "pause"])
def test_failure_conditions_refuse_work_but_preserve_cleanup(case):
    from eval.cap07_host_acceptance import SessionWindow

    window = SessionWindow(1000)
    window.authorize("prepare", 1002)
    options = {}
    now = 1003
    if case == "clock":
        now = 1001
    elif case == "expired":
        now = 1000 + 241 * 60
    else:
        options[{"no_watchdog": "watchdog", "no_barrier": "barriers", "pause": "paused"}[case]] = (
            case == "pause"
        )
    with pytest.raises(ValueError):
        window.authorize("work", now, **options)
    window.authorize("cleanup", 1000 + 250 * 60)


def test_lifecycle_deadline_is_just_in_time_and_idle_drain_runs_after_compute_stop():
    from eval.cap07_host_acceptance import SessionWindow

    w = SessionWindow(1000)
    assert w.startup_started is None
    w.begin_application(1000 + 100 * 60, generation=0)
    assert w.startup_remaining(1000 + 101 * 60) == 240
    with pytest.raises(ValueError):
        w.begin_application(1000 + 102 * 60, generation=1)
    assert w.startup_remaining(1000 + 106 * 60) == 0
    assert w.idle_reconcile_at(1000 + 160 * 60) == 14200
    assert w.idle_reconcile_at(1000 + 160 * 60) + 5 < w.end


@pytest.mark.parametrize(
    "sample",
    [
        {"mem_available": 255 * 1024**2},
        {"disk_free": 2 * 1024**3 - 1},
        {"oom_kill": 1},
        {"swap_sustained": True},
        {"memory_full_sustained": True},
        {"cpu_credits": 0},
    ],
)
def test_capacity_breach_stops_load(sample):
    from eval.cap07_host_acceptance import capacity_safe

    baseline = dict(
        mem_available=512 * 1024**2,
        disk_free=4 * 1024**3,
        oom_kill=0,
        swap_sustained=False,
        memory_full_sustained=False,
        cpu_credits=10,
    )
    assert capacity_safe(baseline)
    baseline.update(sample)
    assert not capacity_safe(baseline)


@pytest.mark.parametrize(
    ("mode", "url"),
    [
        ("control", "https://app.scpilot.tech/sessions/s/messages"),
        ("captured", "https://openrouter.ai/api/v1/chat/completions"),
        ("control", "http://app.scpilot.tech/sessions"),
        ("captured", "https://store.scpilot.tech/__internal/catalogue/search"),
    ],
)
def test_driver_refuses_model_off_origin_insecure_or_private_requests_before_transport(mode, url):
    from eval.cap07_host_acceptance import RequestBudget

    b = RequestBudget(mode, end_epoch=2000, clock=lambda: 1000)
    with pytest.raises(ValueError):
        b.check("POST", url)
    assert b.count == 0


def test_request_and_wall_limits_are_enforced_before_next_request():
    from eval.cap07_host_acceptance import RequestBudget

    clock = [1000]
    b = RequestBudget("control", 3000, clock=lambda: clock[0])
    for _ in range(150):
        b.check("GET", "https://app.scpilot.tech/health")
    with pytest.raises(ValueError):
        b.check("GET", "https://app.scpilot.tech/health")
    clock[0] += 601
    with pytest.raises(ValueError):
        RequestBudget("control", 1100, clock=lambda: clock[0]).check(
            "GET", "https://app.scpilot.tech/health"
        )


def test_control_driver_exercises_session_stream_and_reconnect_without_messages():
    import asyncio

    from eval.cap07_host_acceptance import RequestBudget, exercise

    requests = []

    async def respond(request):
        requests.append((request.method, request.url.path))
        p = request.url.path
        value = {}
        status = 200
        if p == "/__shopper" or p == "/shopper/bootstrap":
            value = {"csrf": "a" * 64}
        elif p == "/shopper/challenge":
            value = {"challenge": "b" * 64}
        elif p == "/__copilot/link-ticket":
            value, status = {"ticket": "c" * 64}, 201
        elif p == "/shopper/link":
            value = {"linked": True}
        elif p == "/shopper/admission":
            value = {"required": True, "admitted": True}
        elif p == "/sessions":
            value, status = {"session_id": json.loads(request.content)["tab_id"]}, 201
        elif p.endswith("/events"):
            assert request.url.params.get("tab_id") == p.split("/")[2]
            return httpx.Response(
                200, text=": keepalive\n\n", headers={"content-type": "text/event-stream"}
            )
        elif p.endswith("/stop"):
            status = 202
        else:
            raise AssertionError(p)
        return httpx.Response(status, json=value)

    async def check():
        transport = httpx.MockTransport(respond)

        def factory():
            return httpx.AsyncClient(transport=transport, trust_env=False)

        result = await exercise(
            "control",
            "synthetic-code",
            None,
            RequestBudget("control", 2000, clock=lambda: 1000),
            factory,
        )
        assert [row["requested"] for row in result] == [1, 5, 8]
        assert len([p for _, p in requests if p.endswith("/events")]) == 28
        assert not any(p.endswith("/messages") for _, p in requests)
        assert not any(p.endswith("/stop") for _, p in requests)
        assert len(requests) <= 150

    asyncio.run(check())


def test_captured_sse_refusals_and_actions_are_classified_without_logging_payload():
    from eval.cap07_host_acceptance import classify_events

    assert classify_events('event: action\ndata: {"action":{"type":"navigate"}}\n\n') == "completed"
    assert (
        classify_events('event: interpretation_paused\ndata: {"reason":"inference_busy"}\n\n')
        == "inference_busy"
    )
    assert (
        classify_events('event: interpretation_paused\ndata: {"reason":"budget"}\n\n') == "failed"
    )
    assert "secret" not in json.dumps(classify_events("secret"))


@pytest.mark.parametrize(
    ("status", "body", "allowed"),
    [
        (202, {}, True),
        (409, {"detail": "There is no active Shopping Task"}, True),
        (409, {"detail": "Unknown outcome"}, False),
        (403, {}, False),
    ],
)
def test_cleanup_accepts_only_success_or_known_already_finished_task(status, body, allowed):
    import asyncio

    from eval.cap07_host_acceptance import RequestBudget, close_task

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))
        ) as client:
            action = close_task(
                client, "synthetic", {}, RequestBudget("captured", 2000, clock=lambda: 1000)
            )
            if allowed:
                await action
            else:
                with pytest.raises(ValueError):
                    await action

    asyncio.run(check())


def test_actual_shopping_suggestions_and_wire_busy_error_are_recognized():
    from eval.cap07_host_acceptance import classify_events

    assert (
        classify_events(
            'event: suggestions\ndata: {"candidates":[]}\n\n'
            'event: done\ndata: {"summary":"Synthetic catalogue result"}\n\n'
        )
        == "completed"
    )
    assert (
        classify_events(
            'event: error\ndata: {"message":"The assistant is busy. Your request was not sent '
            'to the model; retry shortly."}\n\n'
        )
        == "inference_busy"
    )


def test_driver_failure_receipt_retains_safe_stage_count_without_exception_secrets(
    tmp_path, monkeypatch
):
    import json

    import eval.cap07_host_acceptance as driver

    code = tmp_path / "code"
    code.write_text("synthetic")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            dict(
                mode="control",
                ca_file="synthetic",
                invitation_file=str(code),
                snapshot_file="unused",
                deadline_epoch=10**12,
                cohort_file=None,
            )
        )
    )
    monkeypatch.setattr(driver.ssl, "create_default_context", lambda **kw: type("TLS", (), {})())

    async def refused(mode, code, snapshot, budget, factory, **kw):
        budget.count = 17
        budget.diagnostic = {"stage": "cohort", "requested": 5, "outcomes": ["failed"]}
        raise ValueError("private-token-never-print")

    monkeypatch.setattr(driver, "exercise", refused)
    receipt = tmp_path / "result.json"
    assert driver.run(profile, receipt) == 1
    result = json.loads(receipt.read_bytes())
    assert result["requests"] == 17
    assert result["failure"]["exception"] == "ValueError"
    assert result["failure"]["stage"] == "cohort"
    assert "private-token" not in receipt.read_text()


def test_captured_driver_waits_for_delayed_terminal_event_in_single_stream():
    import asyncio

    from eval.cap07_host_acceptance import RequestBudget, captured_outcome

    class Delayed(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: status\ndata: {"state":"interpreting"}\n\n'
            await asyncio.sleep(0.01)
            yield b'event: action\ndata: {"action":{"type":"navigate"}}\n\n'

    async def check():
        requests = []

        def respond(request):
            requests.append(request)
            assert "once" not in request.url.params
            return httpx.Response(200, stream=Delayed())

        budget = RequestBudget("captured", 2000, clock=lambda: 1000)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await captured_outcome(
                client, "https://app.scpilot.tech/sessions/synthetic/events?tab_id=tab", {}, budget
            )
        assert result == "completed"
        assert budget.count == len(requests) == 1

    asyncio.run(check())
