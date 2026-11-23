"""Offline real-SDK invitation transactions; Moto never contacts an AWS account."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

from agent.admission.dynamodb import DynamoInvitationStore
from agent.admission.store import AdmissionDenied, digest

moto = pytest.importorskip("moto", reason="Install optional eval/requirements-cloud.txt")
TABLE, NAMESPACE = "copilot-control-test", "demo"


@pytest.fixture
def authority(monkeypatch):
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
        client.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": name, "AttributeType": "S"} for name in ("pk", "sk")
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # Moto 5.2.4 snapshots/restores whole tables without transaction isolation.
        # A losing concurrent transaction can otherwise erase a successful write.
        # Serialize only the emulated service transaction, never the store caller
        # or its reads; DynamoDB itself supplies this isolation in production.
        transaction_lock = Lock()
        transact = client.transact_write_items

        def isolated_transaction(**request):
            with transaction_lock:
                return transact(**request)

        monkeypatch.setattr(client, "transact_write_items", isolated_transaction)
        identity = DynamoInvitationStore.initialize(client, TABLE, NAMESPACE)
        now = [100.0]
        store = DynamoInvitationStore(client, TABLE, NAMESPACE, identity, clock=lambda: now[0])
        yield store, client, now
        client.close()


def rows(store):
    return {row["id"]: row for row in store.status()}


def raw_key(sk):
    return {"pk": {"S": NAMESPACE}, "sk": {"S": sk}}


def reopen(store, client, now):
    return DynamoInvitationStore(client, TABLE, NAMESPACE, store.identity, clock=lambda: now[0])


def synchronize_transactions(client, monkeypatch):
    """Both callers must finish their reads before either transaction commits."""
    barrier = Barrier(2, timeout=10)
    transact = client.transact_write_items

    def concurrent_transaction(**request):
        barrier.wait()
        return transact(**request)

    monkeypatch.setattr(client, "transact_write_items", concurrent_transaction)


def test_remote_window_quota_revocation_and_reopen(authority):
    store, client, now = authority
    invitation, code = store.issue(110, 150, redemptions=1, sessions=1)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "fictional-browser-a")
    now[0] = 110
    store.redeem(code, "fictional-browser-a")
    store.redeem(code, "fictional-browser-a")
    other = reopen(store, client, now)
    assert other.allowed("fictional-browser-a")
    with pytest.raises(AdmissionDenied):
        other.redeem(code, "fictional-browser-b")
    other.allocate_session("fictional-browser-a")
    with pytest.raises(AdmissionDenied):
        other.allocate_session("fictional-browser-a")
    assert rows(store)[invitation]["used_sessions"] == 1
    assert rows(store)[invitation]["used_redemptions"] == 1
    other.revoke(invitation)
    assert not store.allowed("fictional-browser-a")
    assert not store.valid_invitation(invitation)
    encoded = json.dumps(client.scan(TableName=TABLE)["Items"])
    assert code not in encoded and "fictional-browser-a" not in encoded
    assert digest(code) not in json.dumps(store.status())


def test_remote_wake_never_consumes_application_authority(authority):
    store, _, now = authority
    invitation, code = store.issue(100, 150, redemptions=1, sessions=1)
    assert store.wake_invitation(code) == invitation
    assert store.wake_invitation(code) == invitation
    assert not store.allowed("browser")
    assert rows(store)[invitation]["used_redemptions"] == 0
    store.redeem(code, "browser")
    now[0] = 150
    assert not store.allowed("browser")
    with pytest.raises(AdmissionDenied):
        store.wake_invitation(code)


def test_remote_replacement_preserves_old_usage(authority):
    store, _, _ = authority
    first, code = store.issue(90, 120, redemptions=1, sessions=2)
    store.redeem(code, "browser")
    second, replacement = store.issue(90, 140, redemptions=1, sessions=2)
    with pytest.raises(AdmissionDenied):
        store.redeem(replacement, "browser")
    store.revoke(first)
    store.redeem(replacement, "browser")
    assert rows(store)[first]["used_redemptions"] == 1
    assert rows(store)[second]["used_redemptions"] == 1


def test_remote_initialization_is_exclusive_even_when_metadata_was_deleted(authority):
    store, client, _ = authority
    with pytest.raises((ValueError, AdmissionDenied)):
        DynamoInvitationStore.initialize(client, TABLE, NAMESPACE)
    store.issue(90, 120, redemptions=1, sessions=1)
    client.delete_item(TableName=TABLE, Key=raw_key("meta"))
    with pytest.raises((ValueError, AdmissionDenied)):
        DynamoInvitationStore.initialize(client, TABLE, NAMESPACE)
    assert not store.allowed("browser")
    with pytest.raises(AdmissionDenied):
        store.issue(90, 120, redemptions=1, sessions=1)


def test_remote_metadata_identity_is_rechecked_for_existing_objects(authority):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    client.update_item(
        TableName=TABLE,
        Key=raw_key("meta"),
        UpdateExpression="SET #identity=:identity",
        ExpressionAttributeNames={"#identity": "identity"},
        ExpressionAttributeValues={":identity": {"S": str(uuid4())}},
    )
    assert not store.allowed("browser")
    assert not store.valid_invitation(invitation)
    with pytest.raises(AdmissionDenied):
        store.wake_invitation(code)
    with pytest.raises(AdmissionDenied):
        store.status()


def test_remote_capacity_does_not_reset_on_reopen(authority):
    store, client, now = authority
    client.update_item(
        TableName=TABLE,
        Key=raw_key("meta"),
        UpdateExpression="SET issued=:count",
        ExpressionAttributeValues={":count": {"N": "1000"}},
    )
    other = reopen(store, client, now)
    with pytest.raises(AdmissionDenied):
        other.issue(90, 120, redemptions=1, sessions=1)


@pytest.mark.parametrize(
    "starts,ends,redemptions,sessions",
    [
        (True, 120, 1, 1),
        (90, float("inf"), 1, 1),
        (90, 90, 1, 1),
        (90, 90 + 32 * 86400, 1, 1),
        (90, 120, 21, 1),
        (90, 120, 1, 101),
        (90, 120, True, 1),
    ],
)
def test_remote_invalid_issue_input_never_writes(authority, starts, ends, redemptions, sessions):
    store, _, _ = authority
    with pytest.raises(ValueError):
        store.issue(starts, ends, redemptions=redemptions, sessions=sessions)
    assert store.status() == []


def test_remote_concurrent_final_redemption_is_atomic(authority, monkeypatch):
    store, client, now = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=2)
    synchronize_transactions(client, monkeypatch)

    def redeem(subject):
        try:
            reopen(store, client, now).redeem(code, subject)
            return True
        except AdmissionDenied:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(redeem, ("first", "second"))) == [False, True]
    assert rows(store)[invitation]["used_redemptions"] == 1


def test_remote_boolean_schema_is_corrupt_not_schema_one(authority):
    store, client, _ = authority
    _, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    client.update_item(
        TableName=TABLE,
        Key=raw_key("meta"),
        UpdateExpression="SET #schema=:bad",
        ExpressionAttributeNames={"#schema": "schema"},
        ExpressionAttributeValues={":bad": {"BOOL": True}},
    )
    assert not store.allowed("browser")


def test_remote_revocation_during_write_response_refuses_committed_grant(authority, monkeypatch):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    original = client.transact_write_items

    def revoked_response(**request):
        response = original(**request)
        client.update_item(
            TableName=TABLE,
            Key=raw_key("invitation#" + invitation),
            UpdateExpression="SET revoked=:true",
            ExpressionAttributeValues={":true": {"BOOL": True}},
        )
        return response

    monkeypatch.setattr(client, "transact_write_items", revoked_response)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser")
    assert not store.allowed("browser")
    assert rows(store)[invitation]["used_redemptions"] == 1


def test_remote_changed_invitation_limit_cannot_bypass_validated_authority(authority, monkeypatch):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    original = client.transact_write_items

    def changed_limit(**request):
        client.update_item(
            TableName=TABLE,
            Key=raw_key("invitation#" + invitation),
            UpdateExpression="SET redemptions=:two",
            ExpressionAttributeValues={":two": {"N": "2"}},
        )
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", changed_limit)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser")
    assert not store.allowed("browser")
    assert rows(store)[invitation]["used_redemptions"] == 0


def test_remote_final_session_slot_is_atomic(authority, monkeypatch):
    store, client, now = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    synchronize_transactions(client, monkeypatch)

    def allocate(_):
        try:
            reopen(store, client, now).allocate_session("browser")
            return True
        except AdmissionDenied:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(allocate, range(2))) == [False, True]
    assert rows(store)[invitation]["used_sessions"] == 1


@pytest.mark.parametrize(
    "operation,counter", [("redeem", "used_redemptions"), ("allocate", "used_sessions")]
)
def test_remote_lost_response_is_not_replayed_or_refunded(
    authority, monkeypatch, operation, counter
):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=2, sessions=2)
    if operation == "allocate":
        store.redeem(code, "browser")
    original = client.transact_write_items
    calls = []

    def committed_but_lost(**request):
        calls.append(request)
        original(**request)
        raise ReadTimeoutError(endpoint_url="https://dynamodb.eu-north-1.amazonaws.com")

    monkeypatch.setattr(client, "transact_write_items", committed_but_lost)
    with pytest.raises(AdmissionDenied) as failure:
        if operation == "redeem":
            store.redeem(code, "browser")
        else:
            store.allocate_session("browser")
    assert failure.value.reason == "access_unavailable"
    assert len(calls) == 1
    assert rows(store)[invitation][counter] == 1


@pytest.mark.parametrize(
    "code", ["TransactionCanceledException", "AccessDeniedException", "InternalServerError"]
)
def test_remote_provider_failure_has_no_replay_or_sensitive_error(authority, monkeypatch, code):
    store, client, _ = authority
    invitation, access_code = store.issue(90, 120, redemptions=1, sessions=1)
    calls = []

    def denied(**request):
        calls.append(request)
        raise ClientError(
            {"Error": {"Code": code, "Message": "PRIVATE-ERROR-" + access_code}},
            "TransactWriteItems",
        )

    monkeypatch.setattr(client, "transact_write_items", denied)
    with pytest.raises(AdmissionDenied) as failure:
        store.redeem(access_code, "browser")
    assert len(calls) == 1
    assert "PRIVATE" not in str(failure.value) and access_code not in str(failure.value)
    assert failure.value.__suppress_context__
    assert not store.allowed("browser")
    assert rows(store)[invitation]["used_redemptions"] == 0


@pytest.mark.parametrize(
    "operation,counter", [("redeem", "used_redemptions"), ("allocate", "used_sessions")]
)
def test_remote_expiry_during_sdk_response_refuses_without_refund(
    authority, monkeypatch, operation, counter
):
    store, client, now = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    if operation == "allocate":
        store.redeem(code, "browser")
    original = client.transact_write_items

    def expired_response(**request):
        result = original(**request)
        now[0] = 120
        return result

    monkeypatch.setattr(client, "transact_write_items", expired_response)
    with pytest.raises(AdmissionDenied):
        if operation == "redeem":
            store.redeem(code, "browser")
        else:
            store.allocate_session("browser")
    assert not store.allowed("browser")
    assert rows(store)[invitation][counter] == 1


def test_remote_stale_grant_cannot_allocate_old_invitation(authority, monkeypatch):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    replacement, _ = store.issue(90, 120, redemptions=1, sessions=1)
    original = client.transact_write_items

    def rebound(**request):
        client.update_item(
            TableName=TABLE,
            Key=raw_key("grant#" + digest("browser")),
            UpdateExpression="SET invitation=:new",
            ExpressionAttributeValues={":new": {"S": replacement}},
        )
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", rebound)
    with pytest.raises(AdmissionDenied):
        store.allocate_session("browser")
    assert rows(store)[invitation]["used_sessions"] == 0


def test_remote_revocation_between_read_and_write_cannot_consume_slot(authority, monkeypatch):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    original = client.transact_write_items

    def revoked(**request):
        client.update_item(
            TableName=TABLE,
            Key=raw_key("invitation#" + invitation),
            UpdateExpression="SET revoked=:true",
            ExpressionAttributeValues={":true": {"BOOL": True}},
        )
        return original(**request)

    monkeypatch.setattr(client, "transact_write_items", revoked)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser")
    assert rows(store)[invitation]["used_redemptions"] == 0


def test_remote_consistent_reads_bounded_queries_and_transaction_tokens(authority, monkeypatch):
    store, client, _ = authority
    reads, writes = [], []
    original_get, original_query, original_write = (
        client.get_item,
        client.query,
        client.transact_write_items,
    )

    def get(**request):
        reads.append(request)
        return original_get(**request)

    def query(**request):
        reads.append(request)
        assert request["Limit"] == 100
        return original_query(**request)

    def write(**request):
        writes.append(request)
        return original_write(**request)

    monkeypatch.setattr(client, "get_item", get)
    monkeypatch.setattr(client, "query", query)
    monkeypatch.setattr(client, "transact_write_items", write)
    first, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    store.redeem(code, "browser")
    store.allocate_session("browser")
    store.revoke(first)
    store.status()
    assert reads and all(request["ConsistentRead"] is True for request in reads)
    assert len(writes) == 5
    tokens = [request["ClientRequestToken"] for request in writes]
    assert len(set(tokens)) == len(tokens) and all(len(token) == 32 for token in tokens)
    for request in writes:
        assert 2 <= len(request["TransactItems"]) <= 4
        operations = [next(iter(operation.values())) for operation in request["TransactItems"]]
        assert all("ConditionExpression" in operation for operation in operations)
        metadata = [
            operation
            for operation in operations
            if operation.get("Key", {}).get("sk") == {"S": "meta"}
        ]
        assert len(metadata) == 1
        assert metadata[0]["ExpressionAttributeValues"][":identity"] == {"S": store.identity}


def test_remote_status_continued_pages_are_bounded(authority, monkeypatch):
    store, client, _ = authority
    calls = []

    def continued(**request):
        calls.append(request)
        return {"Items": [], "LastEvaluatedKey": raw_key("invitation#missing")}

    monkeypatch.setattr(client, "query", continued)
    with pytest.raises(AdmissionDenied):
        store.status()
    assert len(calls) == 11


@pytest.mark.parametrize("bad_clock", [float("nan"), float("inf"), True, -1])
def test_remote_bad_clock_refuses(authority, bad_clock):
    store, _, now = authority
    _, code = store.issue(90, 120, redemptions=1, sessions=1)
    now[0] = bad_clock
    with pytest.raises(AdmissionDenied):
        store.wake_invitation(code)
    assert not store.allowed("browser")


def test_remote_missing_or_corrupt_invitation_fails_closed(authority):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)
    store.redeem(code, "browser")
    client.update_item(
        TableName=TABLE,
        Key=raw_key("invitation#" + invitation),
        UpdateExpression="SET created_sessions=:bad",
        ExpressionAttributeValues={":bad": {"N": "-1"}},
    )
    assert not store.allowed("browser")
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser")
    client.delete_item(TableName=TABLE, Key=raw_key("invitation#" + invitation))
    assert not store.allowed("browser")


def test_remote_read_outage_never_creates_or_grants_access(authority, monkeypatch):
    store, client, _ = authority
    invitation, code = store.issue(90, 120, redemptions=1, sessions=1)

    def unavailable(**request):
        raise ReadTimeoutError(endpoint_url="https://dynamodb.eu-north-1.amazonaws.com")

    monkeypatch.setattr(client, "get_item", unavailable)
    assert not store.allowed("browser") and not store.valid_invitation(invitation)
    with pytest.raises(AdmissionDenied):
        store.redeem(code, "browser")


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("retries", None),
        ("retries", {"total_max_attempts": True}),
        ("connect_timeout", True),
        ("read_timeout", True),
    ],
)
def test_remote_invalid_client_bounds_refuse_before_read(authority, monkeypatch, attribute, value):
    store, client, now = authority
    monkeypatch.setattr(client.meta.config, attribute, value)
    reads = []

    def forbidden(**request):
        reads.append(request)
        raise AssertionError("No SDK entry with invalid client configuration")

    monkeypatch.setattr(client, "get_item", forbidden)
    with pytest.raises(ValueError):
        reopen(store, client, now)
    assert not reads


def test_remote_status_refuses_malformed_row_pointing_to_healthy_invitation(authority):
    store, client, _ = authority
    invitation, _ = store.issue(90, 120, redemptions=1, sessions=1)
    client.put_item(
        TableName=TABLE,
        Item={
            **raw_key("invitation#malformed"),
            "id": {"S": invitation},
        },
    )
    with pytest.raises(AdmissionDenied):
        store.status()
