import asyncio
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from agent.admission.store import AdmissionDenied
from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.ledger import AllowanceLedger
from agent.llm import LLMChunk, LLMRequest
from agent.llm.openrouter import OpenRouterClient
from agent.tests.test_openrouter import settings


@pytest.mark.parametrize("stream", [False, True])
def test_expiry_after_free_key_check_prevents_openrouter_post(stream):
    entered = []
    active = [True]

    def handler(request):
        entered.append(request.method)
        active[0] = False
        return httpx.Response(
            200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
        )

    async def verify():
        if not active[0]:
            raise AdmissionDenied()

    async def run():
        client = OpenRouterClient(
            replace(settings(), stream=stream), transport=httpx.MockTransport(handler)
        )
        with pytest.raises(AdmissionDenied):
            [
                c
                async for c in client.complete(
                    LLMRequest(system="", messages=(), authorization_check=verify)
                )
            ]

    asyncio.run(run())
    assert entered == ["GET"]


def test_waiting_request_rechecks_revocation_before_provider_entry(tmp_path):
    async def run():
        path = tmp_path / "ledger.sqlite"
        ledger = AllowanceLedger(path, AllowanceLedger.initialize(path, Decimal("1")))
        started, release = asyncio.Event(), asyncio.Event()
        active = [True]

        class Provider:
            calls = 0

            async def complete(self, request):
                self.calls += 1
                started.set()
                await release.wait()
                yield LLMChunk(text="{}")

        provider = Provider()
        client = GuardedClient(
            provider,
            ledger,
            InferencePrices(Decimal(".3"), Decimal("2.5")),
            maximum_active=1,
            maximum_waiting=1,
            wait_seconds=1,
        )

        async def consume(request):
            return [c async for c in client.complete(request)]

        first = asyncio.create_task(consume(LLMRequest(system="", messages=())))
        await started.wait()
        checked = asyncio.Event()

        async def verify():
            checked.set()
            if not active[0]:
                raise AdmissionDenied()

        pending = asyncio.create_task(
            consume(LLMRequest(system="", messages=(), authorization_check=verify))
        )
        active[0] = False
        release.set()
        assert await first
        with pytest.raises(AdmissionDenied):
            await pending
        assert provider.calls == 1
        assert ledger.status()["attempts"] == 1
        assert checked.is_set()

    asyncio.run(run())
