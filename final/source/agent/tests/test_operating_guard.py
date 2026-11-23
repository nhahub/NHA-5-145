"""Guard acceptance at an injected control plane, never live AWS or model calls."""

import importlib
import importlib.util

import pytest


def guard_type():
    if importlib.util.find_spec("agent.lifecycle.operating_guard") is None:
        pytest.fail("Independent operating guard is not implemented")
    return importlib.import_module("agent.lifecycle.operating_guard").OperatingGuard


class Backend:
    closes = 40000
    baseline_credits = "179.30"
    cleanup_end = closes + 48 * 3600

    def __init__(self):
        self.calls = []
        self.record = {
            "observed": 1000,
            "closed_at": None,
            "reason": None,
            "credit_checked": 1000,
            "credits": "179.30",
            "dns_absent": None,
            "dns_since": None,
            "dns_checked": None,
            "released": False,
            "shutdown": dict.fromkeys(("fence", "authority", "delivery", "ingress"), False),
        }
        self.authority = {"closed": False}
        self.host = {"state": "stopped", "launched": 0}
        self.plan = {"free": True, "active": True, "credits": "179.30"}
        self.dns_ok = False
        self.fail = set()

    def action(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise OSError("synthetic private failure")

    def read(self):
        self.action("read")
        return dict(self.record)

    def authority_status(self):
        self.action("authority")
        return self.authority

    def host_status(self):
        self.action("host")
        return self.host

    def plan_status(self):
        self.action("plan")
        return self.plan

    def close_authority(self, reason):
        self.action("close:" + reason)
        self.authority["closed"] = True

    def fence(self):
        self.action("fence")

    def stop(self):
        self.action("stop")

    def cycle_stop(self):
        self.action("cycle")
        self.stop()

    def close_delivery(self):
        self.action("delivery")
        return True

    def close_ingress(self):
        self.action("ingress")

    def dns_absent(self):
        self.action("dns")
        return self.dns_ok

    def release(self):
        self.action("release")
        return True

    def write(self, record):
        self.action("write")
        self.record = dict(record)


def test_guard_requires_new_feature():
    assert guard_type() is not None


def test_guard_normal_observation_does_not_start_stop_or_call_provider():
    backend = Backend()
    result = guard_type()(backend, clock=lambda: 1010).handle({"kind": "guard"})
    assert result["state"] == "open"
    assert not {"stop", "fence", "delivery", "release", "plan"}.intersection(backend.calls)
    assert backend.record["observed"] == 1010


@pytest.mark.parametrize("failure", ["authority", "read", "host"])
def test_guard_storage_failure_still_fences_and_stops_without_pc(failure):
    backend = Backend()
    backend.fail.add(failure)
    result = guard_type()(backend, clock=lambda: 1010).handle({"kind": "guard"})
    assert "fence" in backend.calls and "stop" in backend.calls
    assert result["state"] in {"closing", "unverified"}
    assert "synthetic private failure" not in str(result)


@pytest.mark.parametrize("failure", ["close:fault", "fence", "stop"])
def test_guard_one_failed_safety_action_does_not_skip_other_independent_actions(failure):
    backend = Backend()
    backend.fail.update({"authority", failure})
    guard_type()(backend, clock=lambda: 1010).handle({"kind": "guard"})
    assert "close:fault" in backend.calls and "fence" in backend.calls and "stop" in backend.calls


def test_guard_closes_ingress_on_stopped_host_while_edge_disable_is_still_propagating():
    backend = Backend()
    backend.close_delivery = lambda: False
    result = guard_type()(backend, clock=lambda: 40000).handle({"kind": "guard"})
    assert "ingress" in backend.calls and "release" not in backend.calls
    assert result["state"] == "closing"


def test_guard_two_stop_failures_remain_unverified_without_retry_loop():
    backend = Backend()
    backend.fail.add("stop")
    guard = guard_type()(backend, clock=lambda: 40000)
    assert guard.handle({"kind": "guard"})["state"] == "unverified"
    assert guard.handle({"kind": "guard"})["state"] == "unverified"
    assert backend.calls.count("stop") == 2
    assert "release" not in backend.calls


@pytest.mark.parametrize("credit,free", [("144.30", True), ("29.99", True), ("179.30", False)])
def test_guard_daily_budget_or_paid_plan_refuses_and_stops(credit, free):
    backend = Backend()
    backend.closes = 200000
    backend.plan = {"credits": credit, "free": free, "active": True}
    result = guard_type()(backend, clock=lambda: 90000).handle({"kind": "guard"})
    assert "plan" in backend.calls and "stop" in backend.calls
    assert result["state"] != "open"


def test_guard_eight_hour_run_is_not_reported_as_healthy_idle():
    backend = Backend()
    backend.host = {"state": "running", "launched": 1000}
    result = guard_type()(backend, clock=lambda: 29800).handle({"kind": "guard"})
    assert "cycle" in backend.calls and "stop" in backend.calls
    assert not backend.authority["closed"] and "fence" not in backend.calls
    assert result["reason"] == "runtime"
    assert "idle" not in str(result)


def test_guard_dns_clock_is_preserved_until_full_ttl_and_rechecked_before_release():
    backend = Backend()
    backend.dns_ok = True
    now = [40000]
    guard = guard_type()(backend, clock=lambda: now[0])
    assert guard.handle({"kind": "guard"})["state"] == "closing"
    assert backend.record["dns_absent"] == 40000
    for epoch in range(40300, 47200, 300):
        now[0] = epoch
        guard.handle({"kind": "guard"})
    assert "release" not in backend.calls
    now[0] = 47200
    backend.dns_ok = False
    guard.handle({"kind": "guard"})
    assert "release" not in backend.calls
    backend.dns_ok = True
    now[0] = 47300
    guard.handle({"kind": "guard"})
    assert backend.record["dns_absent"] == 40000
    assert "release" not in backend.calls
    for epoch in range(47600, 54501, 300):
        now[0] = epoch
        guard.handle({"kind": "guard"})
    assert backend.calls.count("release") == 1
    guard.handle({"kind": "guard"})
    assert backend.calls.count("release") == 1


def test_guard_never_releases_before_actual_stopped_observation_or_after_cleanup_end():
    backend = Backend()
    backend.dns_ok = True
    backend.record.update(
        closed_at=40000,
        reason="expired",
        dns_absent=40000,
        dns_since=40000,
        dns_checked=47100,
        observed=47200,
    )
    backend.host = {"state": "running", "launched": 40000}
    guard_type()(backend, clock=lambda: 47200).handle({"kind": "guard"})
    assert "release" not in backend.calls
    backend.host["state"] = "stopped"
    result = guard_type()(backend, clock=lambda: backend.cleanup_end + 1).handle({"kind": "guard"})
    assert "release" not in backend.calls
    assert result["state"] == "cleanup_expired"


def test_guard_clock_regression_or_untrusted_event_cannot_reopen_or_release():
    backend = Backend()
    backend.record.update(
        closed_at=1000,
        reason="owner",
        dns_absent=1000,
        dns_since=1000,
        dns_checked=1000,
        observed=1500,
    )
    result = guard_type()(backend, clock=lambda: 1200).handle({"kind": "guard"})
    assert result["state"] != "open" and "release" not in backend.calls
    backend.calls.clear()
    with pytest.raises(ValueError):
        guard_type()(backend).handle({"kind": "guard", "instance": "i-other"})
    assert backend.calls == []


@pytest.mark.parametrize("damage", ["missing", "observed_type", "future_credit", "bad_reason"])
def test_corrupt_guard_receipt_is_not_repaired_and_cannot_skip_stop(damage):
    backend = Backend()
    if damage == "missing":
        del backend.record["closed_at"]
    elif damage == "observed_type":
        backend.record["observed"] = "private-invalid-time"
    elif damage == "future_credit":
        backend.record["credit_checked"] = 90000
    else:
        backend.record.update(closed_at=1000, reason="renew")
    result = guard_type()(backend, clock=lambda: 1010).handle({"kind": "guard"})
    assert result["state"] == "unverified"
    assert "stop" in backend.calls and "write" not in backend.calls


def test_positive_dns_with_lost_final_write_invalidates_the_previous_ttl_durably():
    backend = Backend()
    backend.record.update(
        closed_at=40000,
        reason="expired",
        observed=47100,
        dns_absent=40000,
        dns_since=40000,
        dns_checked=47100,
    )
    original = backend.write
    writes = []

    def lose_second_write(record):
        writes.append(dict(record))
        if len(writes) == 2:
            raise OSError("lost final update")
        original(record)

    backend.write = lose_second_write
    guard_type()(backend, clock=lambda: 47200).handle({"kind": "guard"})
    assert backend.record["dns_since"] is None
    backend.write = original
    backend.dns_ok = True
    guard_type()(backend, clock=lambda: 47300).handle({"kind": "guard"})
    assert "release" not in backend.calls and backend.record["dns_since"] == 47300


def test_dns_clock_starts_after_full_probe_and_a_missed_tick_restarts_continuity():
    backend = Backend()
    now = [40000]

    def slow_probe():
        now[0] += 10
        return True

    backend.dns_absent = slow_probe
    guard = guard_type()(backend, clock=lambda: now[0])
    guard.handle({"kind": "guard"})
    assert backend.record["dns_since"] == 40010
    now[0] = 47200
    guard.handle({"kind": "guard"})
    assert "release" not in backend.calls and backend.record["dns_since"] == 47210
