"""Operating bounds at the real startup, EC2 and host configuration seams."""

import json
from dataclasses import replace

import pytest

from agent.admission.dynamodb import DynamoInvitationStore
from agent.lifecycle.dynamodb import DynamoLifecycle
from agent.lifecycle.executor import EC2CommandExecutor
from agent.lifecycle.lambda_runtime import create_startup_runtime
from agent.lifecycle.operating import OperatingAuthority
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lambda_runtime import enqueue, settings
from agent.tests.test_lambda_runtime import queue as _queue_fixture
from agent.tests.test_lifecycle_dynamodb import idle_stop_intent, make_ready
from agent.tests.test_lifecycle_dynamodb import world as _world_fixture
from agent.tests.test_lifecycle_executor import INSTANCE, reply
from agent.tests.test_lifecycle_executor import ec2 as _ec2_fixture
from agent.tests.test_operating import initialized
from agent.tests.test_startup import event

world, queue, ec2 = _world_fixture, _queue_fixture, _ec2_fixture


def test_warm_startup_stops_admitting_after_operating_expiry(world, queue):
    policy, _ = initialized(world)
    selected = replace(settings(world), operating=policy)
    clients = {"dynamodb": world[-1], "lambda": queue[0]}
    handler = create_startup_runtime(
        selected, sdk_factory=clients.__getitem__, clock=lambda: world[0][0]
    )
    enqueue(queue[1])
    assert (
        handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)["statusCode"] == 202
    )
    world[0][0] = policy.closes
    assert handler(event("/status"), None)["statusCode"] == 503
    assert (
        handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)["statusCode"] == 503
    )


def test_executor_start_reserves_once_and_preserves_uncertain_hold(world, ec2):
    _, authority = initialized(world)
    life, client, stub = world[4], *ec2
    life.wake(world[3])
    stub.add_client_error("start_instances", "UnauthorizedOperation", "synthetic refusal")
    worker = EC2CommandExecutor(life, client, INSTANCE, operating=authority)
    assert worker.execute_once() == "uncertain"
    assert authority.status()["starts"] == 1
    assert worker.execute_once() is None
    assert authority.status()["starts"] == 1


def test_executor_cannot_omit_or_change_required_operating_identity(world, ec2):
    policy, authority = initialized(world)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(world[4], ec2[0], INSTANCE)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(world[4], ec2[0], "i-abcdef01234567890", operating=authority)
    assert authority.policy == policy


def test_closed_operating_controller_can_finish_stop_but_never_start(world, ec2):
    policy, authority = initialized(world)
    make_ready(world)
    idle_stop_intent(world)
    authority.close("owner")
    store = world[1]
    observer_store = DynamoInvitationStore(
        store.client,
        store.table,
        store.namespace,
        store.identity,
        clock=store.clock,
        operating=policy,
        operating_control=True,
    )
    life = DynamoLifecycle(observer_store, world[4].identity, clock=store.clock)
    client, stub = ec2
    stub.add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
    assert (
        EC2CommandExecutor(
            life, client, INSTANCE, operating=OperatingAuthority(observer_store, policy)
        ).execute_once()
        == "acknowledged"
    )


def test_atomic_admission_write_losing_race_with_close_is_denied(world, monkeypatch):
    _, authority = initialized(world)
    store = world[1]
    original = store._write

    def close_before_write(operations, **kwargs):
        monkeypatch.setattr(store, "_write", original)
        authority.close("owner")
        return original(operations, **kwargs)

    monkeypatch.setattr(store, "_write", close_before_write)
    with pytest.raises(LifecycleUnavailable):
        world[4].wake(world[3])
    assert authority.status()["closed"] is True


def test_runtime_stop_fences_current_work_and_allows_only_fresh_wake_after_stopped(world):
    _, authority = initialized(world)
    life = make_ready(world)
    token = life.begin_work(generation=1)
    life.request_stop(generation=1)
    assert life.status()["state"] == "stopping"
    with pytest.raises(LifecycleUnavailable):
        life.check_work(generation=1)
    with pytest.raises(LifecycleUnavailable):
        life.renew_work(token)
    receipt = life.claim_command(operation="stop", generation=1)
    life.complete_command(receipt, certain=True)
    life.reconcile(life.observation_token(), instance_state="stopped", healthy=False)
    assert life.status()["state"] == "stopped"
    assert authority.status()["closed"] is False
    assert life.wake(world[3])["generation"] == 2
