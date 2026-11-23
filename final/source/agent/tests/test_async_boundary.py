import asyncio
from threading import Event

import pytest

from agent.admission.async_runtime import AsyncAdmissionPolicy
from agent.async_boundary import BoundaryUnavailable, BoundedIO, invoke
from agent.shopper_access import ShopperAccess, ShopperBinding
from agent.tests.test_lifecycle_dynamodb import world as _world

world = _world


def test_cancelled_io_retains_capacity_and_event_loop_keeps_running():
    entered, release = Event(), Event()

    async def scenario():
        io = BoundedIO(workers=1, capacity=1)

        def blocked():
            entered.set()
            assert release.wait(3)
            return True

        task = asyncio.create_task(io.call(blocked))
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(BoundaryUnavailable):
            await io.call(lambda: False)
        release.set()
        await io.close()
        with pytest.raises(BoundaryUnavailable):
            await io.call(lambda: True)

    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_async_policy_remote_redemption_and_allocation_preserve_counts(world):
    _, store, _, code, _, _ = world
    _, record = ShopperAccess().create()
    record.shopper = ShopperBinding("owner", "generation")

    async def scenario():
        policy = AsyncAdmissionPolicy(store)
        assert await invoke(policy, "allowed", record) is False
        await invoke(policy, "redeem", record, code)
        await invoke(policy, "redeem", record, code)
        assert await invoke(policy, "allowed", record) is True
        await invoke(policy, "allocate_session", record)
        await policy.close()

    asyncio.run(scenario())
    row = store.status()[0]
    assert row["used_redemptions"] == 1 and row["used_sessions"] == 1


def test_async_owner_is_revalidated_after_remote_grant_await():
    access = ShopperAccess()
    credential, record = access.create()
    owner = record.shopper = ShopperBinding("owner", "generation")
    record.sessions.add("session")

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def granted(_):
            entered.set()
            await release.wait()
            return True

        task = asyncio.create_task(access.owns_session_async("session", owner, granted))
        await entered.wait()
        record.shopper = ShopperBinding("other", "generation")
        release.set()
        assert await task is False
        assert access.resolve(credential) is record

    asyncio.run(scenario())


def test_async_admission_readiness_only_checks_bound_metadata(world):
    _, store, _, _, _, client = world
    before = store.status()

    async def scenario():
        policy = AsyncAdmissionPolicy(store)
        try:
            assert await policy.ready() is True
            assert store.status() == before
            client.delete_item(TableName=store.table, Key=store._key("meta"))
            assert await policy.ready() is False
        finally:
            await policy.close()

    asyncio.run(scenario())
