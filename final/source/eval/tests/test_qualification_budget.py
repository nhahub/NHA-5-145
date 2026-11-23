import asyncio
import json
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from agent.inference.ledger import AllowanceLedger
from agent.llm.contract import LLMMessage, LLMRequest
from agent.llm.openrouter import OpenRouterBudgetError
from agent.tests.test_openrouter import settings
from eval.qualification_budget import QualificationClient
from eval.qualification_claim import claim_qualification


def test_launcher_restart_cannot_create_another_qualification_set(tmp_path):
    marker = tmp_path / "claim.json"
    claim_qualification(marker, tmp_path / "first-run")
    with pytest.raises(FileExistsError):
        claim_qualification(marker, tmp_path / "second-run")
    assert json.loads(marker.read_text())["report"].endswith("first-run")


def test_claim_records_the_actual_smaller_allowance_and_cannot_be_replaced(tmp_path):
    marker = tmp_path / "claim.json"
    claim_qualification(marker, tmp_path / "approved-run", maximum_cost=0.12)
    with pytest.raises(FileExistsError):
        claim_qualification(marker, tmp_path / "replacement", maximum_cost=0.25)
    assert json.loads(marker.read_text())["maximum_cost_usd"] == 0.12


def test_qualification_reserves_before_post_and_retains_unknown_cost(tmp_path):
    posts = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        posts.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        )

    async def scenario():
        client = QualificationClient(
            replace(settings(), model="google/gemini-3.5-flash-lite"),
            journal=tmp_path / "budget.jsonl",
            maximum_cost=0.006,
            maximum_calls=5,
            transport=httpx.MockTransport(handler),
        )
        req = LLMRequest(
            system="fixture", messages=(LLMMessage("shopper", "add"),), max_tokens=1536
        )
        assert [chunk async for chunk in client.complete(req)]
        with pytest.raises(OpenRouterBudgetError):
            [chunk async for chunk in client.complete(req)]

    asyncio.run(scenario())
    assert len(posts) == 1
    with pytest.raises(FileExistsError):
        QualificationClient(
            settings(), journal=tmp_path / "budget.jsonl", maximum_cost=0.006, maximum_calls=5
        )


@pytest.mark.parametrize("settled", [False, True])
def test_explicit_continuation_uses_existing_durable_charges_and_attempt_count(tmp_path, settled):
    path = tmp_path / "remaining.sqlite"
    identity = AllowanceLedger.initialize(path, Decimal("0.006"))
    ledger = AllowanceLedger(path, identity)
    ledger.reserve("prior-post", Decimal("0.0045"))
    if settled:
        ledger.settle("prior-post", Decimal("0.0001"))
    journal = tmp_path / "existing.jsonl"
    journal.touch()
    posts = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        posts.append(True)
        return httpx.Response(200, json={})

    client = QualificationClient(
        settings(),
        journal=journal,
        maximum_cost=0.006,
        maximum_calls=1 if settled else 3,
        durable_ledger=ledger,
        transport=httpx.MockTransport(handler),
    )

    async def run():
        with pytest.raises(OpenRouterBudgetError):
            [
                c
                async for c in client.complete(
                    LLMRequest(system="fixture", messages=(), max_tokens=512)
                )
            ]

    asyncio.run(run())
    assert posts == []
    assert client.summary()["posts"] == 1
    assert client.summary()["accounted_cost"] == pytest.approx(0.0001 if settled else 0.0045)


def test_known_cost_settles_once_and_call_count_still_bounds_requests(tmp_path):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": {"limit": 0.25, "limit_remaining": 0.25, "limit_reset": None}}
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"cost": 0.0001},
            },
        )

    async def scenario():
        client = QualificationClient(
            settings(),
            journal=tmp_path / "budget.jsonl",
            maximum_cost=0.006,
            maximum_calls=2,
            transport=httpx.MockTransport(handler),
        )
        req = LLMRequest(system="fixture", messages=(), max_tokens=1536)
        for _ in range(2):
            assert [chunk async for chunk in client.complete(req)]
        with pytest.raises(OpenRouterBudgetError):
            [chunk async for chunk in client.complete(req)]
        assert client.summary()["accounted_cost"] == pytest.approx(0.0002)

    asyncio.run(scenario())
