"""The native probe's external authority obeys the real read-only store protocol."""

import pytest

from agent.admission.dynamodb import DynamoInvitationStore
from agent.lifecycle.dynamodb import DynamoLifecycle
from eval.native_agent_probe import INVITATIONS, LIFECYCLE, ReadOnlyAuthority


def bindings(authority):
    store = DynamoInvitationStore(authority, "offline-control", "offline", INVITATIONS)
    return store, DynamoLifecycle(store, LIFECYCLE)


@pytest.mark.parametrize("generation,state", [(1, "ready"), (0, "stopped")])
def test_authority_is_consumed_by_real_stockholm_store_and_lifecycle(generation, state):
    authority = ReadOnlyAuthority(generation=generation)
    store, lifecycle = bindings(authority)
    store.check()
    assert lifecycle.status()["generation"] == generation
    assert lifecycle.status()["state"] == state
    assert authority.reads > 0 and authority.forbidden == 0


def test_authority_returns_isolated_rows_and_closes_once():
    authority = ReadOnlyAuthority()
    kwargs = {
        "TableName": "offline-control",
        "Key": {"pk": {"S": "offline"}, "sk": {"S": "meta"}},
        "ConsistentRead": True,
    }
    authority.get_item(**kwargs)["Item"]["identity"]["S"] = "changed"
    assert authority.get_item(**kwargs)["Item"]["identity"]["S"] == INVITATIONS
    authority.close()
    assert authority.closed == 1
    with pytest.raises(ValueError):
        authority.get_item(**kwargs)


@pytest.mark.parametrize("change", ["table", "namespace", "key", "consistency", "extra"])
def test_authority_rejects_unbound_or_unexpected_reads(change):
    authority = ReadOnlyAuthority()
    kwargs = {
        "TableName": "offline-control",
        "Key": {"pk": {"S": "offline"}, "sk": {"S": "meta"}},
        "ConsistentRead": True,
    }
    if change == "table":
        kwargs["TableName"] = "unbound"
    elif change == "namespace":
        kwargs["Key"]["pk"]["S"] = "unbound"
    elif change == "key":
        kwargs["Key"]["sk"]["S"] = "unbound"
    elif change == "consistency":
        kwargs["ConsistentRead"] = False
    else:
        kwargs["ProjectionExpression"] = "identity"
    with pytest.raises(ValueError):
        authority.get_item(**kwargs)
    assert authority.reads == 0


def test_authority_refuses_control_store_mutation():
    authority = ReadOnlyAuthority()
    with pytest.raises(ValueError):
        authority.transact_write_items(TransactItems=[])
    assert authority.forbidden == 1
