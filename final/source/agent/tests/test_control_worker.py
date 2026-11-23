"""Trusted controller events, intercepted EC2 and durable in-process test authority."""

import pytest

from agent.lifecycle.controller import ControlObserver, ControlWorker
from agent.lifecycle.executor import EC2CommandExecutor
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lifecycle_dynamodb import idle_stop_intent, make_ready
from agent.tests.test_lifecycle_dynamodb import world as _world
from agent.tests.test_lifecycle_executor import INSTANCE, reply
from agent.tests.test_lifecycle_executor import ec2 as _ec2

world, ec2 = _world, _ec2


class Probe:
    def __init__(self, ready=True):
        self.ready, self.calls = ready, []

    def check(self, generation):
        self.calls.append(generation)
        return self.ready


def described(state="running", code=16):
    return {
        "ResponseMetadata": {"HTTPStatusCode": 200},
        "Reservations": [
            {"Instances": [{"InstanceId": INSTANCE, "State": {"Name": state, "Code": code}}]}
        ],
    }


def worker(world, ec2, probe=None):
    life, client = world[4], ec2[0]
    return ControlWorker(
        life,
        EC2CommandExecutor(life, client, INSTANCE),
        ControlObserver(life, client, INSTANCE, probe or Probe()),
    )


def test_filtered_claim_cannot_start_or_affect_newer_generation(world):
    life = world[4]
    life.wake(world[3])
    assert life.claim_command(operation="stop", generation=1) is None
    with pytest.raises(LifecycleUnavailable):
        life.claim_command(operation="start", generation=2)
    assert life.claim_command(operation="start", generation=1)["operation"] == "start"


def test_dispatch_starts_once_and_observation_admits_only_after_proof(world, ec2):
    world[4].wake(world[3])
    ec2[1].add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    value = worker(world, ec2).handle({"kind": "dispatch", "generation": 1})
    assert value["state"] == "ready"
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle({"kind": "dispatch", "generation": 1})["state"] == "ready"


@pytest.mark.parametrize("state,code", [("stopped", 80), ("running", 16)])
def test_observe_never_claims_pending_start(world, ec2, state, code):
    life = world[4]
    life.wake(world[3])
    ec2[1].add_response("describe_instances", described(state, code), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle({"kind": "observe", "generation": 1})["state"] == "starting"
    assert life.claim_command()["operation"] == "start"


@pytest.mark.parametrize("proof", [False, {"ready": True}])
def test_observe_plain_or_unhealthy_proof_never_admits(world, ec2, proof):
    life = world[4]
    life.wake(world[3])
    life.complete_command(life.claim_command(), certain=True)
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    assert (
        worker(world, ec2, Probe(proof)).handle({"kind": "observe", "generation": 1})["state"]
        == "starting"
    )


def test_observer_fences_health_result_after_intervening_revision(world, ec2):
    life = make_ready(world)

    class Changed:
        def check(self, generation):
            life.begin_work(generation=generation)
            return True

    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    with pytest.raises(LifecycleUnavailable):
        worker(world, ec2, Changed()).handle({"kind": "observe", "generation": 1})


def test_observe_executes_only_committed_idle_stop(world, ec2):
    make_ready(world)
    idle_stop_intent(world)
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    ec2[1].add_response("stop_instances", reply("stop"), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle({"kind": "observe", "generation": 1})["state"] == "stopping"
    ec2[1].add_response("describe_instances", described("stopped", 80), {"InstanceIds": [INSTANCE]})
    assert worker(world, ec2).handle({"kind": "observe", "generation": 1})["state"] == "stopped"


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"kind": "observe", "generation": True},
        {"kind": "dispatch", "generation": 2},
        {"kind": "observe", "generation": 1, "instance": "another"},
        {"kind": "start", "generation": 1},
        {"kind": [], "generation": 1},
    ],
)
def test_controller_bad_or_stale_event_has_no_ec2_entry(world, ec2, event):
    world[4].wake(world[3])
    with pytest.raises(LifecycleUnavailable):
        worker(world, ec2).handle(event)


def test_observer_unknown_describe_never_proves_stopped_or_ready(world, ec2):
    life = world[4]
    life.wake(world[3])
    life.complete_command(life.claim_command(), certain=True)
    ec2[1].add_client_error("describe_instances", "UnauthorizedOperation", "private")
    assert worker(world, ec2).handle({"kind": "observe", "generation": 1})["state"] == "starting"


@pytest.mark.parametrize("mutation", ["wrong_id", "extra", "code", "http", "pagination"])
def test_observer_malformed_describe_is_unhealthy(world, ec2, mutation):
    life = world[4]
    life.wake(world[3])
    life.complete_command(life.claim_command(), certain=True)
    response = described()
    instance = response["Reservations"][0]["Instances"][0]
    if mutation == "wrong_id":
        instance["InstanceId"] = "i-11111111111111111"
    elif mutation == "extra":
        response["Reservations"].append(response["Reservations"][0].copy())
    elif mutation == "code":
        instance["State"]["Code"] = 80
    elif mutation == "pagination":
        response["NextToken"] = "more"
    else:
        response["ResponseMetadata"]["HTTPStatusCode"] = 202
    ec2[1].add_response("describe_instances", response, {"InstanceIds": [INSTANCE]})
    probe = Probe()
    assert (
        worker(world, ec2, probe).handle({"kind": "observe", "generation": 1})["state"]
        == "starting"
    )
    assert probe.calls == []


def test_observer_refreshes_client_policy_after_authority_io(world, ec2, monkeypatch):
    life = world[4]
    life.wake(world[3])
    original = life.observation_token

    def changed():
        token = original()
        monkeypatch.setattr(ec2[0].meta.config, "read_timeout", 100)
        return token

    monkeypatch.setattr(life, "observation_token", changed)
    with pytest.raises(LifecycleUnavailable):
        ControlObserver(life, ec2[0], INSTANCE, Probe()).observe(1)
