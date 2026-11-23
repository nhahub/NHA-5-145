"""Real durable claims with entirely stubbed EC2; no credential lookup or network."""

from concurrent.futures import ThreadPoolExecutor
from itertools import count
from threading import Barrier, Lock

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ReadTimeoutError
from botocore.stub import Stubber

from agent.lifecycle.executor import EC2CommandExecutor
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lifecycle_dynamodb import idle_stop_intent, make_ready, observe
from agent.tests.test_lifecycle_dynamodb import world as _world_fixture

world = _world_fixture

INSTANCE = "i-0123456789abcdef0"
CODES = {"pending": 0, "running": 16, "stopping": 64, "stopped": 80}


@pytest.fixture
def ec2():
    client = boto3.client(
        "ec2",
        region_name="eu-north-1",
        aws_access_key_id="offline-dummy",
        aws_secret_access_key="offline-dummy",
        config=Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1}),
    )
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()
    client.close()


def reply(operation="start", *, current=None):
    before = "stopped" if operation == "start" else "running"
    after = current or ("pending" if operation == "start" else "stopping")
    return {
        "ResponseMetadata": {"HTTPStatusCode": 200},
        "StartingInstances" if operation == "start" else "StoppingInstances": [
            {
                "InstanceId": INSTANCE,
                "PreviousState": {"Name": before, "Code": CODES[before]},
                "CurrentState": {"Name": after, "Code": CODES[after]},
            }
        ],
    }


def test_executor_claims_once_and_ack_is_not_readiness(world, ec2):
    _, _, _, code, life, _ = world
    client, stub = ec2
    life.wake(code)
    stub.add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() == "acknowledged"
    assert life.status()["state"] == "starting"
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() is None
    assert observe(life)["state"] == "ready"


def test_executor_stop_requires_observed_stopped(world, ec2):
    life = make_ready(world)
    idle_stop_intent(world)
    client, stub = ec2
    stub.add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() == "acknowledged"
    assert life.status()["state"] == "stopping"
    assert observe(life, "stopped", False)["state"] == "stopped"


@pytest.mark.parametrize("lost", [False, True])
def test_executor_service_or_lost_success_is_uncertain_without_retry(world, ec2, monkeypatch, lost):
    _, _, _, code, life, _ = world
    client, stub = ec2
    life.wake(code)
    calls = []
    if lost:
        stub.add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
        original = client.start_instances

        def timeout(**request):
            calls.append(request)
            original(**request)
            raise ReadTimeoutError(endpoint_url="https://ec2.eu-north-1.amazonaws.com")

        monkeypatch.setattr(client, "start_instances", timeout)
    else:
        stub.add_client_error("start_instances", "UnauthorizedOperation", "private details")
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() == "uncertain"
    assert life.status()["state"] == "failed"
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() is None
    if lost:
        assert calls == [{"InstanceIds": [INSTANCE]}]


@pytest.mark.parametrize("mutation", ["wrong_id", "two", "code", "http", "current", "missing"])
def test_executor_malformed_acknowledgements_stay_locked(world, ec2, mutation):
    _, _, _, code, life, _ = world
    client, stub = ec2
    life.wake(code)
    response = reply()
    item = response["StartingInstances"][0]
    if mutation == "wrong_id":
        item["InstanceId"] = "i-11111111111111111"
    elif mutation == "two":
        response["StartingInstances"].append(item.copy())
    elif mutation == "code":
        item["CurrentState"]["Code"] = 16
    elif mutation == "http":
        response["ResponseMetadata"]["HTTPStatusCode"] = 202
    elif mutation == "current":
        item["CurrentState"] = {"Name": "stopped", "Code": 80}
    else:
        del response["StartingInstances"]
    stub.add_response("start_instances", response, {"InstanceIds": [INSTANCE]})
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() == "uncertain"
    assert life.claim_command() is None


@pytest.mark.parametrize("violation", ["revoked", "deadline", "policy"])
def test_executor_refreshes_authority_after_claim_before_api(world, ec2, monkeypatch, violation):
    now, invitations, invitation, code, life, _ = world
    client, _ = ec2
    life.wake(code)
    original = life.claim_command

    def changed():
        receipt = original()
        if violation == "revoked":
            invitations.revoke(invitation)
        elif violation == "deadline":
            now[0] += 300
        else:
            monkeypatch.setattr(client.meta.config, "retries", {"total_max_attempts": 2})
        return receipt

    monkeypatch.setattr(life, "claim_command", changed)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(life, client, INSTANCE).execute_once()
    assert original() is None


def test_executor_lost_settlement_does_not_replay(world, ec2, monkeypatch):
    _, _, _, code, life, _ = world
    client, stub = ec2
    life.wake(code)
    stub.add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    original = life.complete_command
    calls = []

    def lost(*args, **kwargs):
        calls.append(kwargs)
        raise LifecycleUnavailable()

    monkeypatch.setattr(life, "complete_command", lost)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(life, client, INSTANCE).execute_once()
    monkeypatch.setattr(life, "complete_command", original)
    assert calls == [{"certain": True}]
    assert EC2CommandExecutor(life, client, INSTANCE).execute_once() is None


def test_executor_competing_workers_dispatch_at_most_once(world, ec2, monkeypatch):
    _, _, _, code, life, dynamodb = world
    client, stub = ec2
    life.wake(code)
    stub.add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    original = dynamodb.transact_write_items
    barrier, guard, sequence = Barrier(2), Lock(), count()

    def atomic_mock_transaction(**request):
        with guard:
            index = next(sequence)
        if index < 2:
            # Both controllers submit claims from the same revision.
            barrier.wait(timeout=10)
        # The shared Moto fixture serializes only mock server operations.
        return original(**request)

    monkeypatch.setattr(dynamodb, "transact_write_items", atomic_mock_transaction)

    def run(_):
        try:
            return EC2CommandExecutor(life, client, INSTANCE).execute_once()
        except LifecycleUnavailable:
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results.count("acknowledged") == 1
    assert life.claim_command() is None


@pytest.mark.parametrize("setting,value", [("connect_timeout", True), ("read_timeout", 16)])
def test_executor_configuration_refuses_without_consuming_claim(
    world, ec2, monkeypatch, setting, value
):
    _, _, _, code, life, _ = world
    client, _ = ec2
    life.wake(code)
    monkeypatch.setattr(client.meta.config, setting, value)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(life, client, INSTANCE).execute_once()
    assert life.claim_command()["operation"] == "start"


@pytest.mark.parametrize("instance", [None, "", "i-123", [INSTANCE], INSTANCE + " "])
def test_executor_only_accepts_fixed_instance_configuration(world, ec2, instance):
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(world[4], ec2[0], instance)


def test_executor_rechecks_deadline_after_slow_invitation_read(world, ec2, monkeypatch):
    now, invitations, _, code, life, _ = world
    life.wake(code)
    original_claim = life.claim_command
    original_valid = invitations.valid_invitation

    def claim():
        receipt = original_claim()

        def slow(invitation):
            result = original_valid(invitation)
            now[0] += 300
            return result

        monkeypatch.setattr(invitations, "valid_invitation", slow)
        return receipt

    monkeypatch.setattr(life, "claim_command", claim)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(life, ec2[0], INSTANCE).execute_once()
    assert original_claim() is None


def test_executor_refreshes_client_policy_after_authority_io(world, ec2, monkeypatch):
    _, _, _, code, life, _ = world
    life.wake(code)
    original = life.check_command

    def check(receipt):
        original(receipt)
        monkeypatch.setattr(ec2[0].meta.config, "read_timeout", 100)

    monkeypatch.setattr(life, "check_command", check)
    with pytest.raises(LifecycleUnavailable):
        EC2CommandExecutor(life, ec2[0], INSTANCE).execute_once()
    assert life.claim_command() is None


def test_executor_ignores_ec2_documented_internal_state_high_byte(world, ec2):
    _, _, _, code, life, _ = world
    life.wake(code)
    response = reply()
    response["StartingInstances"][0]["PreviousState"]["Code"] |= 256
    response["StartingInstances"][0]["CurrentState"]["Code"] |= 256
    ec2[1].add_response("start_instances", response, {"InstanceIds": [INSTANCE]})
    assert EC2CommandExecutor(life, ec2[0], INSTANCE).execute_once() == "acknowledged"
