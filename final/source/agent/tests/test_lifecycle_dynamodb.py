"""Offline DynamoDB lifecycle arbitration; never executes an EC2 command."""

import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

from agent.admission.dynamodb import DynamoInvitationStore
from agent.admission.store import AdmissionDenied
from agent.lifecycle.dynamodb import DynamoLifecycle
from agent.lifecycle.store import LifecycleUnavailable

moto = pytest.importorskip("moto", reason="Install optional eval/requirements-cloud.txt")


@pytest.fixture
def world():
    with moto.mock_aws():
        client = boto3.client(
            "dynamodb",
            region_name="eu-north-1",
            aws_access_key_id="offline-dummy",
            aws_secret_access_key="offline-dummy",
            config=Config(
                connect_timeout=5,
                read_timeout=15,
                retries={"total_max_attempts": 1},
                ignore_configured_endpoint_urls=True,
            ),
        )
        # Moto rolls back an entire table backup without thread isolation. Give
        # its server operations atomicity, while controller read/CAS workflows
        # still race normally (and barriers still force shared revisions).
        server = Lock()

        def atomic(function):
            def call(**request):
                with server:
                    return function(**request)

            return call

        for method in ("get_item", "query", "transact_write_items"):
            setattr(client, method, atomic(getattr(client, method)))
        client.create_table(
            TableName="lifecycle-test",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": key, "AttributeType": "S"} for key in ("pk", "sk")
            ],
        )
        now = [1000.0]
        invitations = DynamoInvitationStore(
            client,
            "lifecycle-test",
            "demo",
            DynamoInvitationStore.initialize(client, "lifecycle-test", "demo"),
            clock=lambda: now[0],
        )
        invitation, code = invitations.issue(999, 20000, redemptions=5, sessions=10)
        identity = DynamoLifecycle.initialize(invitations)
        life = DynamoLifecycle(invitations, identity, clock=lambda: now[0])
        yield now, invitations, invitation, code, life, client
        client.close()


def observe(life, state="running", healthy=True):
    return life.reconcile(life.observation_token(), instance_state=state, healthy=healthy)


def make_ready(world):
    _, _, _, code, life, _ = world
    life.wake(code)
    receipt = life.claim_command()
    assert receipt["operation"] == "start"
    life.complete_command(receipt, certain=True)
    assert observe(life)["state"] == "ready"
    return life


def idle_stop_intent(world):
    now, _, _, _, life, _ = world
    now[0] += 3600
    assert observe(life)["state"] == "draining"
    now[0] += 5
    assert observe(life)["state"] == "stopping"


def test_remote_lifecycle_reads_do_not_wake_and_initialization_is_exclusive(world):
    _, invitations, _, code, life, client = world
    assert life.status()["state"] == "stopped"
    assert life.claim_command() is None
    with pytest.raises(LifecycleUnavailable):
        DynamoLifecycle.initialize(invitations)
    assert life.wake(code)["generation"] == 1
    other = DynamoLifecycle(invitations, life.identity, clock=life.clock)
    assert other.status() == life.status()
    assert other.wake(code)["generation"] == 1
    assert invitations.status()[0]["used_redemptions"] == 0
    client.delete_item(TableName=invitations.table, Key=invitations._key("lifecycle#host"))
    with pytest.raises(LifecycleUnavailable):
        other.status()


def test_remote_lifecycle_start_requires_invitation_and_certain_command(world):
    _, invitations, invitation, code, life, _ = world
    with pytest.raises((AdmissionDenied, LifecycleUnavailable)):
        life.wake("bad-code")
    life.wake(code)
    assert observe(life)["state"] == "starting"
    invitations.revoke(invitation)
    with pytest.raises(LifecycleUnavailable):
        life.claim_command()
    assert life.status()["state"] != "ready"


def test_remote_lifecycle_idle_drain_and_work_serialize(world):
    now, _, _, _, _, _ = world
    life = make_ready(world)
    now[0] += 3600
    assert observe(life)["state"] == "draining"
    generation = life.status()["generation"]
    token = life.begin_work(meaningful=True, generation=generation)
    assert life.status()["state"] == "ready"
    for _ in range(121):
        now[0] += 30
        life.renew_work(token)
        assert observe(life)["state"] == "ready"
    life.end_work(token, generation=generation)
    assert observe(life)["state"] == "draining"
    now[0] += 5
    assert observe(life)["state"] == "stopping"
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(meaningful=True, generation=generation)
    receipt = life.claim_command()
    assert receipt["operation"] == "stop"
    life.complete_command(receipt, certain=True)
    assert observe(life, "stopped", False)["state"] == "stopped"


def test_remote_lifecycle_background_reads_and_leases_do_not_reset_idle(world):
    now, _, _, _, _, _ = world
    life = make_ready(world)
    now[0] += 3600
    life.status()
    assert observe(life)["state"] == "draining"
    token = life.begin_work(generation=1)
    assert observe(life)["state"] == "ready"
    now[0] += 46
    with pytest.raises(LifecycleUnavailable):
        life.renew_work(token)
    assert observe(life)["state"] == "draining"


def test_remote_lifecycle_stale_observation_does_not_override_activity(world):
    now, _, _, _, _, _ = world
    life = make_ready(world)
    now[0] += 3600
    old = life.observation_token()
    life.begin_work(meaningful=True, generation=1)
    with pytest.raises(LifecycleUnavailable):
        life.reconcile(old, instance_state="running", healthy=True)
    assert life.status()["state"] == "ready"


def test_remote_lifecycle_one_command_claim_and_exact_receipt(world):
    _, _, _, code, life, _ = world
    life.wake(code)
    claim = life.claim_command()
    assert life.claim_command() is None
    stale = {**claim, "generation": claim["generation"] + 1}
    with pytest.raises(LifecycleUnavailable):
        life.complete_command(stale, certain=True)
    life.complete_command(claim, certain=True)
    with pytest.raises(LifecycleUnavailable):
        life.complete_command(claim, certain=True)
    assert observe(life)["state"] == "ready"


def test_remote_lifecycle_claimed_timeout_and_unknown_completion_block_restart(world):
    now, _, _, code, life, _ = world
    life.wake(code)
    claim = life.claim_command()
    now[0] += 301
    assert observe(life, "stopped", False)["state"] == "failed"
    now[0] += 600
    with pytest.raises(LifecycleUnavailable):
        life.wake(code)
    assert life.claim_command() is None
    life.complete_command(claim, certain=False)
    assert observe(life, "stopped", False)["state"] == "failed"
    with pytest.raises(LifecycleUnavailable):
        life.wake(code)
    assert life.status()["generation"] == 1


def test_remote_lifecycle_late_certain_start_requires_cleanup_stop(world):
    now, _, _, code, life, _ = world
    life.wake(code)
    claim = life.claim_command()
    now[0] += 301
    observe(life, "stopped", False)
    life.complete_command(claim, certain=True)
    stop = life.claim_command()
    assert stop["operation"] == "stop"
    life.complete_command(stop, certain=True)
    assert observe(life, "stopped", False)["state"] == "failed"
    now[0] += 61
    assert life.wake(code)["generation"] == 2


def test_remote_lifecycle_unclaimed_deadline_never_dispatches_expired_start(world):
    now, _, _, code, life, _ = world
    life.wake(code)
    now[0] += 300
    assert observe(life, "stopped", False)["state"] == "failed"
    assert life.claim_command() is None
    now[0] += 60
    assert life.wake(code)["generation"] == 2


def test_remote_lifecycle_leases_are_bounded_and_generation_fenced(world):
    now, _, _, code, _, _ = world
    life = make_ready(world)
    tokens = [life.begin_work(generation=1) for _ in range(128)]
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(generation=1)
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(generation=2)
    now[0] += 46
    assert life.begin_work(generation=1) not in tokens
    with pytest.raises(LifecycleUnavailable):
        life.renew_work(tokens[0])
    now[0] += 3601
    observe(life)
    now[0] += 5
    observe(life)
    receipt = life.claim_command()
    life.complete_command(receipt, certain=True)
    observe(life, "stopped", False)
    assert life.wake(code)["generation"] == 2
    with pytest.raises(LifecycleUnavailable):
        life.end_work(tokens[0], generation=1)


def test_remote_lifecycle_concurrent_wakes_cas_never_create_two_generations(world, monkeypatch):
    _, _, _, code, life, client = world
    barrier = Barrier(2)
    original = client.transact_write_items

    def simultaneous(**request):
        barrier.wait(timeout=10)
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", simultaneous)

    def wake(_):
        try:
            return life.wake(code)["generation"]
        except LifecycleUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(wake, range(2)))
    assert 1 in results and set(results) <= {1, None}
    assert life.status()["generation"] == 1


def test_remote_lifecycle_unknown_write_never_replays_command_claim(world, monkeypatch):
    _, _, _, code, life, client = world
    life.wake(code)
    original = client.transact_write_items
    calls = []

    def lost(**request):
        calls.append(request)
        original(**request)
        raise ReadTimeoutError(endpoint_url="https://dynamodb.eu-north-1.amazonaws.com")

    monkeypatch.setattr(client, "transact_write_items", lost)
    with pytest.raises(LifecycleUnavailable):
        life.claim_command()
    assert len(calls) == 1
    monkeypatch.setattr(client, "transact_write_items", original)
    assert life.claim_command() is None
    assert life.status()["generation"] == 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, -1, 999])
def test_remote_lifecycle_bad_or_backward_clock_refuses(world, bad):
    now, _, _, code, life, _ = world
    life.wake(code)
    now[0] = bad
    with pytest.raises(LifecycleUnavailable):
        life.status()


def test_remote_lifecycle_revocation_between_wake_read_and_commit(world, monkeypatch):
    _, invitations, invitation, code, life, client = world
    original = client.transact_write_items

    def revoked(**request):
        monkeypatch.setattr(client, "transact_write_items", original)
        invitations.revoke(invitation)
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", revoked)
    with pytest.raises(LifecycleUnavailable):
        life.wake(code)
    assert life.status()["generation"] == 0


def test_remote_lifecycle_mutated_sdk_policy_refuses_before_storage(world, monkeypatch):
    _, _, _, _, life, client = world
    monkeypatch.setattr(client.meta.config, "retries", {"total_max_attempts": 2})
    with pytest.raises(LifecycleUnavailable):
        life.status()


def test_remote_lifecycle_stop_claim_blocks_recovery_even_when_observed_stopped(world):
    now, _, _, code, _, _ = world
    life = make_ready(world)
    idle_stop_intent(world)
    claim = life.claim_command()
    assert observe(life, "stopped", False)["state"] == "stopping"
    now[0] += 121
    assert observe(life, "stopped", False)["state"] == "failed"
    with pytest.raises(LifecycleUnavailable):
        life.wake(code)
    life.complete_command(claim, certain=True)
    observe(life, "stopped", False)
    now[0] += 61
    assert life.wake(code)["generation"] == 2


def test_remote_lifecycle_missing_state_cannot_be_reinitialized_to_reset_fence(world):
    _, invitations, _, code, life, client = world
    life.wake(code)
    life.claim_command()
    client.delete_item(TableName=invitations.table, Key=invitations._key("lifecycle#host"))
    with pytest.raises(LifecycleUnavailable):
        DynamoLifecycle.initialize(invitations)


def test_remote_lifecycle_invalid_ready_state_with_unfinished_command_refuses(world):
    _, invitations, _, code, life, client = world
    life.wake(code)
    client.update_item(
        TableName=invitations.table,
        Key=invitations._key("lifecycle#host"),
        UpdateExpression="SET #state=:ready",
        ExpressionAttributeNames={"#state": "state"},
        ExpressionAttributeValues={":ready": {"S": "ready"}},
    )
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(generation=1)


def test_remote_lifecycle_revoked_claim_response_does_not_deliver_dispatch_receipt(
    world, monkeypatch
):
    _, invitations, invitation, code, life, client = world
    life.wake(code)
    original = client.transact_write_items

    def revoked_response(**request):
        response = original(**request)
        monkeypatch.setattr(client, "transact_write_items", original)
        invitations.revoke(invitation)
        return response

    monkeypatch.setattr(client, "transact_write_items", revoked_response)
    with pytest.raises(LifecycleUnavailable):
        life.claim_command()
    assert life.claim_command() is None


@pytest.mark.parametrize("token", [None, [], "bad", True])
def test_remote_lifecycle_invalid_renewal_token_returns_fixed_failure(world, token):
    life = make_ready(world)
    with pytest.raises(LifecycleUnavailable):
        life.renew_work(token)


def test_remote_lifecycle_drain_vs_new_work_has_only_one_cas_winner(world, monkeypatch):
    now, _, _, _, _, client = world
    life = make_ready(world)
    now[0] += 3600
    observe(life)
    now[0] += 5
    old = life.observation_token()
    barrier = Barrier(2)
    original = client.transact_write_items

    def simultaneous(**request):
        barrier.wait(timeout=10)
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", simultaneous)

    def compete(operation):
        try:
            if operation == "work":
                life.begin_work(meaningful=True, generation=1)
            else:
                life.reconcile(old, instance_state="running", healthy=True)
            return operation
        except LifecycleUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ("work", "stop")))
    assert sum(result is not None for result in results) == 1
    assert life.status()["state"] == ("ready" if "work" in results else "stopping")


@pytest.mark.parametrize(
    "error_code", ["TransactionCanceledException", "AccessDeniedException", "InternalServerError"]
)
def test_remote_lifecycle_failure_never_replays_or_exposes_service_body(
    world, monkeypatch, error_code
):
    _, _, _, code, life, client = world
    calls = []

    def rejected(**request):
        calls.append(request)
        raise ClientError(
            {"Error": {"Code": error_code, "Message": "PRIVATE-" + code}}, "TransactWriteItems"
        )

    monkeypatch.setattr(client, "transact_write_items", rejected)
    with pytest.raises(LifecycleUnavailable) as failure:
        life.wake(code)
    assert len(calls) == 1
    assert code not in str(failure.value) and "PRIVATE" not in str(failure.value)
    assert failure.value.__suppress_context__
    assert life.status()["generation"] == 0


def test_remote_lifecycle_pending_stop_cannot_wake_and_manual_start_preserves_admission(world):
    now, invitations, _, code, life, _ = world
    life.manual_start()
    claim = life.claim_command()
    life.complete_command(claim, certain=True)
    observe(life)
    assert not invitations.allowed("browser")
    idle_stop_intent(world)
    assert life.wake(code)["state"] == "stopping"
    assert life.status()["generation"] == 1
    stop = life.claim_command()
    life.complete_command(stop, certain=True)
    observe(life, "stopped", False)
    now[0] += 1
    assert life.wake(code)["generation"] == 2


def test_remote_lifecycle_reopen_keeps_claimed_command_and_stale_claim_refuses(world):
    _, invitations, _, code, life, _ = world
    life.wake(code)
    receipt = life.claim_command()
    other = DynamoLifecycle(invitations, life.identity, clock=life.clock)
    assert other.claim_command() is None
    forged = copy.deepcopy(receipt)
    forged["claim"] = "0" * 32
    with pytest.raises(LifecycleUnavailable):
        other.complete_command(forged, certain=True)
    other.complete_command(receipt, certain=True)
    assert observe(other)["state"] == "ready"


def test_remote_lifecycle_unhealthy_observation_keeps_accepted_work(world):
    now, _, _, _, _, _ = world
    life = make_ready(world)
    token = life.begin_work(generation=1)
    now[0] += 30
    assert observe(life, "unknown", False)["state"] == "unhealthy"
    life.renew_work(token)
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(generation=1)
    assert life.claim_command() is None
    assert observe(life)["state"] == "ready"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", {"BOOL": True}),
        ("generation", {"N": "-1"}),
        ("activity", {"N": "999999999"}),
        ("changed", {"N": "999999999"}),
    ],
)
def test_remote_lifecycle_corrupt_state_refuses(world, field, value):
    _, invitations, _, code, life, client = world
    life.wake(code)
    client.update_item(
        TableName=invitations.table,
        Key=invitations._key("lifecycle#host"),
        UpdateExpression="SET #field=:value",
        ExpressionAttributeNames={"#field": field},
        ExpressionAttributeValues={":value": value},
    )
    with pytest.raises(LifecycleUnavailable):
        life.status()


def test_remote_lifecycle_idle_unhealthy_drain_never_reopens_admission(world):
    now, _, _, _, _, _ = world
    life = make_ready(world)
    now[0] += 3600
    assert observe(life, "unknown", False)["state"] == "draining"
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(meaningful=True, generation=1)
    now[0] += 5
    assert observe(life, "unknown", False)["state"] == "stopping"


def test_remote_lifecycle_malformed_host_observation_refuses(world):
    _, _, _, _, life, _ = world
    with pytest.raises(LifecycleUnavailable):
        life.reconcile(life.observation_token(), instance_state=[], healthy=False)
