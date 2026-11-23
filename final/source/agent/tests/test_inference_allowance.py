import asyncio
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest

from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.ledger import AllowanceLedger, InferenceRefused
from agent.llm.contract import LLMChunk, LLMMessage, LLMRequest


def test_reservation_and_known_settlement_survive_restart_without_refunding_unknown(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.03"))
    ledger = AllowanceLedger(path, identity)
    ledger.reserve("known", Decimal("0.02"))
    ledger.settle("known", Decimal("0.005"))
    ledger.settle("known", Decimal("0.005"))
    ledger.reserve("interrupted", Decimal("0.02"))
    reopened = AllowanceLedger(path, identity)
    assert reopened.status()["remaining_usd"] == "0.005000000"
    with pytest.raises(InferenceRefused, match="budget"):
        reopened.reserve("next", Decimal("0.006"))
    with pytest.raises(InferenceRefused, match="duplicate"):
        reopened.reserve("known", Decimal("0.001"))
    with pytest.raises(FileExistsError):
        AllowanceLedger.initialize(path, Decimal("0.03"))


def test_separate_ledger_objects_cannot_over_reserve_and_kill_switch_persists(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.02"))

    def reserve(attempt):
        ledger = AllowanceLedger(path, identity)
        try:
            ledger.reserve(str(attempt), Decimal("0.02"))
            return "accepted"
        except InferenceRefused as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve, range(4)))
    assert sorted(outcomes) == ["accepted", "budget", "budget", "budget"]
    ledger = AllowanceLedger(path, identity)
    ledger.set_enabled(False)
    with pytest.raises(InferenceRefused, match="disabled"):
        AllowanceLedger(path, identity).reserve("after-kill", Decimal("0.001"))
    ledger.set_enabled(True)
    assert ledger.status()["remaining_usd"] == "0.000000000"


def test_guarded_calls_reserve_every_attempt_and_settle_only_known_cost(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.02"))
    ledger = AllowanceLedger(path, identity)
    observed = []

    class FakeProvider:
        async def complete(self, request):
            assert request.provider_attempt_limit == 1
            observed.append((request.prompt_version, ledger.status()["uncertain"]))
            yield LLMChunk(text="{}")

    receipts = iter([Decimal("0.001"), None, Decimal("0.002")])
    client = GuardedClient(
        FakeProvider(),
        ledger,
        InferencePrices(Decimal("0.3"), Decimal("2.5")),
        receipt=lambda _client, _attempt: next(receipts),
        maximum_active=1,
        maximum_waiting=1,
        wait_seconds=0.1,
    )
    request = LLMRequest(system="Extract", messages=(LLMMessage("shopper", "fixture"),))

    async def run():
        for version in ["intent-v9", "intent-v9-repair", "advice-v4"]:
            assert [
                c.text async for c in client.complete(replace(request, prompt_version=version))
            ] == ["{}"]

    asyncio.run(run())
    assert [version for version, _ in observed] == ["intent-v9", "intent-v9-repair", "advice-v4"]
    assert all(count >= 1 for _, count in observed)
    assert ledger.status()["attempts"] == 3
    assert ledger.status()["uncertain"] == 1
    assert Decimal(ledger.status()["accounted_usd"]) >= Decimal("0.0055")


def test_full_queue_and_persisted_kill_switch_never_enter_another_provider_call(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.1"))
    ledger = AllowanceLedger(path, identity)

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        class HeldProvider:
            async def complete(self, request):
                calls.append(request.attempt_id)
                entered.set()
                await release.wait()
                yield LLMChunk(text="{}")

        guarded = GuardedClient(
            HeldProvider(),
            ledger,
            InferencePrices(Decimal("0.3"), Decimal("2.5")),
            maximum_active=1,
            maximum_waiting=1,
            wait_seconds=1,
        )

        async def consume():
            return [c async for c in guarded.complete(LLMRequest(system="", messages=()))]

        active = asyncio.create_task(consume())
        await entered.wait()
        queued = asyncio.create_task(consume())
        await asyncio.sleep(0.02)
        with pytest.raises(InferenceRefused, match="busy"):
            await consume()
        ledger.set_enabled(False)
        release.set()
        await active
        with pytest.raises(InferenceRefused, match="disabled"):
            await queued
        assert len(calls) == 1
        assert ledger.status()["attempts"] == 1
        assert ledger.status()["uncertain"] == 1

    asyncio.run(run())


def test_killed_provider_process_retains_charge_after_reopen(tmp_path):
    path, entered = tmp_path / "allowance.sqlite", tmp_path / "entered"
    identity = AllowanceLedger.initialize(path, Decimal("0.003"))
    script = """
import asyncio,sys
from pathlib import Path
from decimal import Decimal
from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.ledger import AllowanceLedger
from agent.llm.contract import LLMRequest
class HeldProvider:
 async def complete(self,request):
  Path(sys.argv[3]).touch()
  await asyncio.Event().wait()
  yield
async def main():
 c=GuardedClient(HeldProvider(),AllowanceLedger(Path(sys.argv[1]),sys.argv[2]),
 InferencePrices(Decimal("0.3"),Decimal("2.5")),maximum_active=1,maximum_waiting=0,wait_seconds=1)
 async for _ in c.complete(LLMRequest(system="",messages=())): pass
asyncio.run(main())
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(path), identity, str(entered)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while not entered.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert entered.exists(), "Owned fake provider did not enter"
        child.kill()
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stderr.close()
    ledger = AllowanceLedger(path, identity)
    assert ledger.status()["uncertain"] == 1
    assert Decimal(ledger.status()["accounted_usd"]) > Decimal("0.002")
    with pytest.raises(InferenceRefused, match="budget"):
        ledger.reserve("after-restart", Decimal("0.001"))


def test_cancelled_call_and_queue_timeout_keep_the_uncertain_reservation(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.003"))
    ledger = AllowanceLedger(path, identity)

    async def run():
        entered = asyncio.Event()
        closed = []

        class HeldProvider:
            async def complete(self, request):
                try:
                    entered.set()
                    await asyncio.Event().wait()
                    yield LLMChunk(text="{}")
                finally:
                    closed.append(True)

        guard = GuardedClient(
            HeldProvider(),
            ledger,
            InferencePrices(Decimal("0.3"), Decimal("2.5")),
            maximum_active=1,
            maximum_waiting=1,
            wait_seconds=0.02,
        )

        async def consume():
            return [c async for c in guard.complete(LLMRequest(system="", messages=()))]

        active = asyncio.create_task(consume())
        await entered.wait()
        with pytest.raises(InferenceRefused, match="busy"):
            await consume()
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        assert closed == [True]
        with pytest.raises(InferenceRefused, match="budget"):
            await consume()
        assert ledger.status()["attempts"] == 1
        assert ledger.status()["uncertain"] == 1

    asyncio.run(run())


@pytest.mark.parametrize("fault", ["lost-storage", "lost-storage-unknown", "cost-overrun"])
def test_settlement_failure_does_not_expose_completion_or_refund(tmp_path, fault):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.1"))
    ledger = AllowanceLedger(path, identity)

    class FakeProvider:
        async def complete(self, request):
            if fault.startswith("lost-storage"):
                path.rename(tmp_path / "retained.sqlite")
            yield LLMChunk(text="{}")

    guard = GuardedClient(
        FakeProvider(),
        ledger,
        InferencePrices(Decimal("0.3"), Decimal("2.5")),
        receipt=lambda _c, _a: None if fault.endswith("unknown") else Decimal("0.01"),
        maximum_active=1,
        maximum_waiting=0,
        wait_seconds=0.1,
    )
    exposed = []

    async def run():
        with pytest.raises(InferenceRefused):
            async for chunk in guard.complete(LLMRequest(system="", messages=())):
                exposed.append(chunk)

    asyncio.run(run())
    assert exposed == []
    if fault.startswith("lost-storage"):
        assert not path.exists()
        status = AllowanceLedger(tmp_path / "retained.sqlite", identity).status()
        assert status["uncertain"] == 1
    else:
        status = ledger.status()
        assert not status["enabled"]
        assert status["accounted_usd"] == "0.010000000"


@pytest.mark.parametrize("fault", ["missing", "corrupt", "readonly", "full"])
def test_storage_failure_refuses_new_inference_without_reinitializing(tmp_path, fault):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("1"))
    ledger = AllowanceLedger(path, identity, maximum_pages=5)
    try:
        if fault == "missing":
            path.unlink()
        elif fault == "corrupt":
            path.write_bytes(b"corrupt storage")
        elif fault == "readonly":
            path.chmod(stat.S_IREAD)
        else:
            for i in range(300):
                try:
                    ledger.reserve(str(i) + "x" * 180, Decimal("0.001"))
                except InferenceRefused as error:
                    assert error.reason == "unavailable"
                    break
            else:
                pytest.fail("Configured finite storage bound never refused a write")
        with pytest.raises(InferenceRefused, match="unavailable"):
            ledger.reserve("later" + "x" * 180, Decimal("0.001"))
        if fault == "missing":
            assert not path.exists()
    finally:
        if path.exists():
            path.chmod(stat.S_IWRITE | stat.S_IREAD)
