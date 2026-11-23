import asyncio
from decimal import Decimal

import pytest

from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.config import configured_guard
from agent.inference.ledger import AllowanceLedger, InferenceRefused
from agent.llm import LLMSettings
from agent.llm.contract import LLMChunk, LLMRequest


def test_absolute_attempt_limit_survives_concurrent_clients_and_reconstruction(tmp_path):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("2"))
    ledger = AllowanceLedger(path, identity)
    ledger.reserve("historical-known", Decimal("0.01"))
    ledger.settle("historical-known", Decimal("0.001"))
    ledger.reserve("historical-uncertain", Decimal("0.01"))
    baseline = ledger.status()
    ceiling = baseline["attempts"] + 4
    calls = []

    class Provider:
        async def complete(self, request):
            calls.append(request.attempt_id)
            await asyncio.sleep(0)
            yield LLMChunk(text="ok")

    def guard():
        return GuardedClient(
            Provider(),
            AllowanceLedger(path, identity),
            InferencePrices(Decimal("0.3"), Decimal("2.5")),
            maximum_active=1,
            maximum_waiting=0,
            wait_seconds=1,
            maximum_attempts=ceiling,
        )

    async def consume(client):
        try:
            return [chunk.text async for chunk in client.complete(LLMRequest("test", ()))]
        except InferenceRefused as error:
            assert str(error) == "budget"
            return None

    async def scenario():
        results = await asyncio.gather(*(consume(guard()) for _ in range(12)))
        assert results.count(["ok"]) == 4
        assert results.count(None) == 8
        assert await consume(guard()) is None

    asyncio.run(scenario())
    assert len(calls) == 4
    after = ledger.status()
    assert after["attempts"] == ceiling
    assert after["uncertain"] == baseline["uncertain"] + 4
    assert after["allowance_usd"] == baseline["allowance_usd"]


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.5, "4", 1_000_001])
def test_invalid_attempt_limit_is_rejected(tmp_path, limit):
    path = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("2"))
    with pytest.raises(ValueError):
        GuardedClient(
            object(),
            AllowanceLedger(path, identity),
            InferencePrices(Decimal("0.3"), Decimal("2.5")),
            maximum_active=1,
            maximum_waiting=0,
            wait_seconds=1,
            maximum_attempts=limit,
        )


def test_attempt_limit_cannot_silently_return_an_unguarded_client():
    with pytest.raises(ValueError):
        configured_guard(
            object(), LLMSettings(provider="scripted", model="test"), {}, maximum_attempts=4
        )
