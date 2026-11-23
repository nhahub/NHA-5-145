import asyncio
from threading import Event

import pytest

from agent.lifecycle.async_work import AsyncLifecycleWork
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lifecycle_dynamodb import make_ready, observe
from agent.tests.test_lifecycle_dynamodb import world as _world

world = _world


class Sessions:
    pending = False

    def has_pending_work(self):
        return self.pending


def test_remote_work_transfers_pending_lease_through_degraded_health(world):
    now, store, _, _, _, _ = world
    life = make_ready(world)
    sessions = Sessions()

    async def scenario():
        work = AsyncLifecycleWork(life, sessions, clock=lambda: now[0])
        await work.initialize()
        token = await work.begin()
        sessions.pending = True
        observe(life, "unknown", False)
        await work.finish(token)
        assert work.pending == token
        now[0] += 30
        await work.refresh()
        assert token in store._read("lifecycle#host")["leases"]
        sessions.pending = False
        await work.refresh()
        assert store._read("lifecycle#host")["leases"] == {}
        await work.close()

    asyncio.run(scenario())


def test_remote_work_only_explicit_activity_touches_idle_clock(world):
    now, store, *_ = world
    life = make_ready(world)

    async def scenario():
        work = AsyncLifecycleWork(life, Sessions(), clock=lambda: now[0])
        await work.initialize()
        before = store._read("lifecycle#host")["activity"]
        now[0] += 10
        await work.check()
        await work.readiness_state()
        assert store._read("lifecycle#host")["activity"] == before
        token = await work.begin()
        await work.finish(token, meaningful=True)
        assert store._read("lifecycle#host")["activity"] == now[0]
        await work.close()

    asyncio.run(scenario())


def test_remote_work_expired_renewal_never_reacquires(world):
    now = world[0]
    life = make_ready(world)

    async def scenario():
        work = AsyncLifecycleWork(life, Sessions(), clock=lambda: now[0])
        await work.initialize()
        await work.begin()
        now[0] += 46
        with pytest.raises(LifecycleUnavailable):
            await work.refresh()
        assert work.failed
        with pytest.raises(LifecycleUnavailable):
            await work.begin()
        await work.close()

    asyncio.run(scenario())


def test_remote_work_cancelled_begin_retains_fence_then_cleans_known_lease(world, monkeypatch):
    life = make_ready(world)
    entered, release = Event(), Event()
    original = life.begin_work

    def blocked(**options):
        result = original(**options)
        entered.set()
        assert release.wait(3)
        return result

    monkeypatch.setattr(life, "begin_work", blocked)

    async def scenario():
        work = AsyncLifecycleWork(life, Sessions(), clock=lambda: world[0][0])
        await work.initialize()
        task = asyncio.create_task(work.begin())
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(world[1]._read("lifecycle#host")["leases"]) == 1
        release.set()
        for _ in range(200):
            if not work.requests and not work._jobs and not work._cleanup:
                break
            await asyncio.sleep(0.005)
        assert not work.requests
        assert world[1]._read("lifecycle#host")["leases"] == {}
        await work.close()

    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_remote_work_close_keeps_pending_protection_to_finite_expiry(world):
    life = make_ready(world)
    sessions = Sessions()

    async def scenario():
        work = AsyncLifecycleWork(life, sessions)
        await work.initialize()
        token = await work.begin()
        sessions.pending = True
        await work.finish(token)
        await work.close()
        assert token in world[1]._read("lifecycle#host")["leases"]

    asyncio.run(scenario())


@pytest.mark.parametrize("pending", [False, True])
def test_remote_work_refuses_cold_or_reconstructed_authority(world, pending):
    life = world[4]
    sessions = Sessions()
    sessions.pending = pending
    if pending:
        life = make_ready(world)

    async def scenario():
        work = AsyncLifecycleWork(life, sessions)
        with pytest.raises(LifecycleUnavailable):
            await work.initialize()
        assert work.generation is None
        await work.close()

    asyncio.run(scenario())


def test_remote_work_generation_change_permanently_fences_process(world):
    now, store, *_ = world
    life = make_ready(world)

    async def scenario():
        work = AsyncLifecycleWork(life, Sessions())
        await work.initialize()
        store.client.update_item(
            TableName=store.table,
            Key=store._key("lifecycle#host"),
            UpdateExpression="SET generation=:next",
            ExpressionAttributeValues={":next": {"N": "2"}},
        )
        with pytest.raises(LifecycleUnavailable):
            await work.readiness_state()
        assert work.failed and work.generation == 1
        with pytest.raises(LifecycleUnavailable):
            await work.begin()
        await work.close()

    asyncio.run(scenario())


def test_cancelled_queued_jobs_still_count_towards_actor_capacity():
    entered, release = Event(), Event()

    class Backend:
        def status(self):
            return {"state": "ready", "generation": 1}

        def check_work(self, **_):
            entered.set()
            assert release.wait(3)

    async def scenario():
        work = AsyncLifecycleWork(Backend(), Sessions())
        await work.initialize()
        tasks = [asyncio.create_task(work.check()) for _ in range(64)]
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set() and len(work._jobs) == 64
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        with pytest.raises(LifecycleUnavailable):
            await work.check()
        release.set()
        await work.close()
        assert not work._jobs

    try:
        asyncio.run(scenario())
    finally:
        release.set()
