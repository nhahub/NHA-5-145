"""Browser-independent observation passes with real mocked durable authority."""

import json
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from threading import Barrier

import httpx
import pytest

from agent.lifecycle.lambda_entry import make_entry
from agent.lifecycle.lambda_runtime import create_controller_runtime
from agent.lifecycle.readiness import readiness_reply
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_control_worker import Probe, described, worker
from agent.tests.test_lambda_runtime import settings
from agent.tests.test_lifecycle_dynamodb import idle_stop_intent, make_ready
from agent.tests.test_lifecycle_dynamodb import world as _world
from agent.tests.test_lifecycle_executor import INSTANCE, reply
from agent.tests.test_lifecycle_executor import ec2 as _ec2
from agent.tests.test_readiness import RELEASE, SECRET

world, ec2 = _world, _ec2
TICK = {"kind": "tick"}


def describe(ec2, state="running", code=16):
    ec2[1].add_response("describe_instances", described(state, code), {"InstanceIds": [INSTANCE]})


def test_stopped_tick_does_not_write_or_enter_ec2(world, ec2, monkeypatch):
    before = world[4].observation_token()

    def forbidden(**request):
        pytest.fail("Stopped tick wrote authority")

    monkeypatch.setattr(world[5], "transact_write_items", forbidden)
    assert worker(world, ec2).handle(TICK)["state"] == "stopped"
    assert world[4].observation_token() == before


def test_tick_recovers_valid_unclaimed_wake_without_browser_or_duplicate_start(world, ec2):
    world[4].wake(world[3])  # Accepted intent; dispatch notification never arrives.
    describe(ec2, "stopped", 80)
    ec2[1].add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle(TICK)["state"] == "starting"
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "ready"
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "ready"


def test_closed_browser_idle_drain_stop_and_observed_stopped(world, ec2):
    now, _, _, _, life, _ = world
    make_ready(world)
    now[0] += 3600
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "draining"
    now[0] += 60
    describe(ec2)
    ec2[1].add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle(TICK)["state"] == "stopping"
    describe(ec2, "stopped", 80)
    assert worker(world, ec2).handle(TICK)["state"] == "stopped"
    assert life.status()["generation"] == 1


@pytest.mark.parametrize("reason", ["revoked", "expired", "deadline"])
def test_tick_cannot_dispatch_invalid_start(world, ec2, reason):
    now, store, invitation, code, life, _ = world
    life.wake(code)
    if reason == "revoked":
        store.revoke(invitation)
    elif reason == "expired":
        now[0] = 20001
    else:
        now[0] += 300
    describe(ec2, "stopped", 80)
    if reason == "revoked":
        with pytest.raises(LifecycleUnavailable):
            worker(world, ec2).handle(TICK)
    else:
        assert worker(world, ec2).handle(TICK)["state"] == "failed"


@pytest.mark.parametrize("uncertain", [True, False])
def test_tick_never_takes_over_claimed_or_uncertain_command(world, ec2, uncertain):
    life = world[4]
    life.wake(world[3])
    receipt = life.claim_command()
    if uncertain:
        life.complete_command(receipt, certain=False)
    describe(ec2, "stopped", 80)
    worker(world, ec2).handle(TICK)
    assert life.claim_command() is None


def test_meaningful_work_cancels_drain_and_finite_lease_delays_stop(world, ec2):
    now, _, _, _, life, _ = world
    make_ready(world)
    now[0] += 3600
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "draining"
    lease = life.begin_work(meaningful=True, generation=1)
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "ready"
    now[0] += 3600
    # The old lease has expired; it cannot be resurrected by the timer.
    describe(ec2)
    assert worker(world, ec2).handle(TICK)["state"] == "draining"
    with pytest.raises(LifecycleUnavailable):
        life.renew_work(lease)


def runtime(world, ec2, lines):
    def health(request):
        value = readiness_reply(
            request.headers, secret=SECRET, release=RELEASE, generation=1, ready=True
        )
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value).encode()))

    return create_controller_runtime(
        settings(world, "controller"),
        sdk_factory=lambda name: {"dynamodb": world[5], "ec2": ec2[0]}[name],
        clock=lambda: world[0][0],
        http_transport=httpx.MockTransport(health),
        tick_writer=lines.append,
    )


def test_only_completed_trusted_ticks_emit_one_bounded_constant_metric(world, ec2):
    lines = []
    controller = runtime(world, ec2, lines)
    assert controller(TICK, None)["state"] == "stopped"
    assert len(lines) == 1 and len(lines[0].encode()) < 512
    metric = json.loads(lines[0])
    assert set(metric) == {"_aws", "Component", "TickCompleted"}
    assert metric["Component"] == "Controller" and metric["TickCompleted"] == 1
    assert metric["_aws"]["Timestamp"] == 1000000
    assert metric["_aws"]["CloudWatchMetrics"] == [
        {
            "Namespace": "ShoppingCopilot/Lifecycle",
            "Dimensions": [["Component"]],
            "Metrics": [{"Name": "TickCompleted", "Unit": "Count"}],
        }
    ]
    for bad in (
        {"kind": "tick", "generation": 1},
        {"kind": "tick", "instance": INSTANCE},
        {"kind": []},
    ):
        assert controller(bad, None) == {"state": "unavailable"}
    assert len(lines) == 1
    make_ready(world)
    describe(ec2)
    assert controller({"kind": "observe", "generation": 1}, None)["state"] == "ready"
    assert len(lines) == 1


def test_tick_failure_crosses_runtime_and_lazy_entry_as_redacted_error(world, ec2, monkeypatch):
    configuration = {
        "version": 1,
        "table": world[1].table,
        "namespace": world[1].namespace,
        "invitation_identity": world[1].identity,
        "lifecycle_identity": world[4].identity,
        "instance": INSTANCE,
        "release": RELEASE,
    }
    lines = []
    entry = make_entry(
        "controller",
        environment={
            "COPILOT_CONTROL_CONFIG": json.dumps(configuration),
            "COPILOT_READINESS_KEY_HEX": SECRET.hex(),
        },
        factory=lambda _: runtime(world, ec2, lines),
    )
    assert entry(TICK, None)["state"] == "stopped"

    def broken(**request):
        raise RuntimeError("private data must not escape")

    monkeypatch.setattr(world[5], "get_item", broken)
    with pytest.raises(RuntimeError, match="^Scheduled observation unavailable$"):
        entry(TICK, None)
    assert len(lines) == 1


def test_tick_initialization_failure_is_latched_but_visible_to_lambda_errors():
    entry = make_entry("controller", environment={})
    for _ in range(2):
        with pytest.raises(RuntimeError, match="^Scheduled observation unavailable$"):
            entry(TICK, None)
    assert entry({"kind": "observe", "generation": 1}, None) == {"state": "unavailable"}


def test_live_work_lease_survives_health_loss_and_no_early_stop(world, ec2):
    now, _, _, _, life, _ = world
    make_ready(world)
    now[0] += 3599
    token = life.begin_work(generation=1)
    now[0] += 1
    describe(ec2)
    assert worker(world, ec2, Probe(False)).handle(TICK)["state"] == "unhealthy"
    assert life.renew_work(token) is None
    now[0] += 46
    describe(ec2)
    assert worker(world, ec2, Probe(False)).handle(TICK)["state"] == "draining"


def test_activity_during_external_probe_fences_stale_tick_before_command(world, ec2):
    life = make_ready(world)
    world[0][0] += 3600

    class ChangedProbe:
        def check(self, generation):
            life.begin_work(meaningful=True, generation=1)
            return True

    describe(ec2)
    with pytest.raises(LifecycleUnavailable):
        worker(world, ec2, ChangedProbe()).handle(TICK)
    assert life.status()["state"] == "ready"


def test_concurrent_duplicate_ticks_dispatch_no_more_than_once(world, ec2, monkeypatch):
    world[4].wake(world[3])
    barrier, calls = Barrier(2), []

    def concurrent_describe(**request):
        barrier.wait(timeout=5)
        return described("stopped", 80)

    def start(**request):
        calls.append(request)
        return reply()

    monkeypatch.setattr(ec2[0], "describe_instances", concurrent_describe)
    monkeypatch.setattr(ec2[0], "start_instances", start)

    def run(_):
        try:
            return worker(world, ec2).handle(TICK)
        except LifecycleUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert any(result is not None for result in results)
    assert calls == [{"InstanceIds": [INSTANCE]}]


def test_acknowledged_late_start_receives_cleanup_stop_not_another_start(world, ec2):
    life = world[4]
    life.wake(world[3])
    life.complete_command(life.claim_command(), certain=True)
    world[0][0] += 300
    describe(ec2)
    ec2[1].add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle(TICK)["state"] == "failed"
    describe(ec2, "stopped", 80)
    worker(world, ec2).handle(TICK)
    assert life.claim_command() is None


@pytest.mark.parametrize(
    "case", ["stopped", "unclaimed-start", "ready128", "drain", "stop", "uncertain"]
)
def test_intercepted_operation_and_item_size_profile(world, ec2, monkeypatch, case):
    now, _, _, code, life, client = world
    if case == "unclaimed-start":
        life.wake(code)
        describe(ec2, "stopped", 80)
        ec2[1].add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    elif case == "uncertain":
        life.wake(code)
        life.complete_command(life.claim_command(), certain=False)
        describe(ec2, "stopped", 80)
    elif case != "stopped":
        make_ready(world)
        if case == "ready128":
            for _ in range(128):
                life.begin_work(generation=1)
        elif case == "drain":
            now[0] += 3600
        elif case == "stop":
            idle_stop_intent(world)
            ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
            ec2[1].add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
        if case != "stop":
            describe(ec2)
    stats = {
        "case": case,
        "get_count": 0,
        "transactions": 0,
        "put_count": 0,
        "condition_count": 0,
        "max_item_json_bytes": 0,
        "conservative_write_units": 0,
    }
    read, write = client.get_item, client.transact_write_items

    def measured_read(**request):
        result = read(**request)
        stats["get_count"] += 1
        size = len(json.dumps(result.get("Item", {}), separators=(",", ":")).encode())
        stats["max_item_json_bytes"] = max(size, stats["max_item_json_bytes"])
        return result

    def measured_write(**request):
        stats["transactions"] += 1
        for operation in request["TransactItems"]:
            if "Put" in operation:
                stats["put_count"] += 1
                size = len(json.dumps(operation["Put"]["Item"], separators=(",", ":")).encode())
                stats["max_item_json_bytes"] = max(size, stats["max_item_json_bytes"])
                stats["conservative_write_units"] += 2 * ceil(size / 1024)
            else:
                stats["condition_count"] += 1
                stats["conservative_write_units"] += (
                    2  # extra planning headroom, not billing evidence
                )
        return write(**request)

    monkeypatch.setattr(client, "get_item", measured_read)
    monkeypatch.setattr(client, "transact_write_items", measured_write)
    worker(world, ec2).handle(TICK)
    # Legacy construction now proves both metadata and finite-window absence.
    # Captured worst tick:35 reads plus six cold-constructor reads, below42.
    assert stats["get_count"] + 6 <= 42
    assert stats["transactions"] <= 4 and stats["max_item_json_bytes"] <= 16384
    assert stats["conservative_write_units"] <= 144
    if case == "stopped":
        assert stats["get_count"] == 4 and stats["transactions"] == 0
    print("COST_SAMPLE " + json.dumps(stats, sort_keys=True))
