"""Captured qualification only: no runtime disk worker, network or allowance change."""

import asyncio
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from agent.inference.client import InferencePrices
from agent.inference.config import configured_guard
from agent.llm.config import load_llm_settings
from agent.llm.openrouter import OpenRouterClient
from eval.tests.test_host_openrouter import PROVIDER_KEY
from eval.tests.test_host_openrouter import openrouter_config as _host
from eval.tests.test_provider_binding import binding_world as _binding


@pytest.fixture
def qualified_world(tmp_path, monkeypatch):
    world = _binding.__wrapped__(_host.__wrapped__(tmp_path), monkeypatch)
    _, settings, _, ledger, now, load = world
    binding = load()
    client = OpenRouterClient(
        load_llm_settings(settings.environment()),
        transport=httpx.MockTransport(lambda _: pytest.fail("Qualification made provider request")),
    )
    guard = configured_guard(client, client._settings, settings.environment())
    return binding, guard, ledger, now


def test_captured_binding_observes_and_rechecks_without_provider_or_budget_use(qualified_world):
    from deploy.provider_qualification import ProviderQualification

    binding, guard, ledger, _ = qualified_world
    before = ledger.status()

    async def scenario():
        verifier = ProviderQualification(binding, guard)
        proof = await verifier.observe()
        assert proof is not None and await verifier.recheck(proof) is True
        assert PROVIDER_KEY not in repr(verifier) + repr(proof)
        await verifier.close()
        assert await verifier.observe() is None and await verifier.recheck(proof) is False
        await verifier.close()

    asyncio.run(scenario())
    assert ledger.status() == before and guard.client.call_metadata == []


def test_operating_qualification_rejects_an_unbounded_actual_guard(tmp_path, monkeypatch):
    from agent.lifecycle.operating import OperatingPolicy
    from deploy.provider_qualification import ProviderQualification

    configuration = _host.__wrapped__(tmp_path)
    path, data, _ = configuration
    data.update(
        version=3,
        operating=OperatingPolicy(str(uuid4()), "a" * 64, "i-0123456789abcdef0", 100, 200).values(),
        operating_attempt_ceiling=101,
    )
    data["admission_limits"]["maximum_sessions"] = 8
    path.write_text(json.dumps(data))
    world = _binding.__wrapped__(configuration, monkeypatch)
    binding = world[5]()
    client = OpenRouterClient(
        load_llm_settings(binding.settings.environment()),
        transport=httpx.MockTransport(lambda _: pytest.fail("Qualification sent a request")),
    )
    unbounded = configured_guard(client, client._settings, binding.settings.environment())
    with pytest.raises(ValueError, match="Provider qualification refused"):
        ProviderQualification(binding, unbounded)
    bounded = configured_guard(
        client, client._settings, binding.settings.environment(), maximum_attempts=101
    )

    async def verify():
        verifier = ProviderQualification(binding, bounded)
        assert await verifier.observe() is not None
        object.__setattr__(binding.settings, "operating_attempt_ceiling", 999)
        assert await verifier.observe() is None

    asyncio.run(verify())


def test_runtime_verifier_never_reenters_file_validation(qualified_world, monkeypatch):
    from deploy import provider_binding
    from deploy.provider_qualification import ProviderQualification

    binding, guard, _, _ = qualified_world

    def forbidden(*_):
        pytest.fail("Runtime evidence/key/source I/O")

    monkeypatch.setattr(provider_binding, "_entry", forbidden)
    monkeypatch.setattr(provider_binding, "production_release", forbidden)
    monkeypatch.setattr(provider_binding.ProviderBinding, "_startup", forbidden)

    async def scenario():
        verifier = ProviderQualification(binding, guard)
        proof = await verifier.observe()
        for _ in range(3):
            assert await verifier.recheck(proof) is True
        await verifier.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mutation",
    [
        "client",
        "settings",
        "key",
        "ledger",
        "ledger_path",
        "identity",
        "pages",
        "prices",
        "price_values",
        "receipt",
        "capacity",
        "wait",
        "semaphore",
        "lock",
        "transport",
        "ceiling",
        "attempt_limit",
    ],
)
def test_changed_actual_client_or_authority_is_rejected_in_memory(qualified_world, mutation):
    from deploy.provider_qualification import ProviderQualification

    binding, guard, _, _ = qualified_world

    async def scenario():
        verifier = ProviderQualification(binding, guard)
        proof = await verifier.observe()
        if mutation == "client":
            guard.client = object()
        elif mutation == "settings":
            guard.client._settings = replace(guard.client._settings)
        elif mutation == "key":
            from pydantic import SecretStr

            object.__setattr__(
                guard.client._settings, "api_key", SecretStr("changed-synthetic-key")
            )
        elif mutation == "ledger":
            guard.ledger = object()
        elif mutation == "ledger_path":
            guard.ledger.path = guard.ledger.path.with_name("other.sqlite")
        elif mutation == "identity":
            guard.ledger.identity = "00000000-0000-4000-8000-000000000000"
        elif mutation == "pages":
            guard.ledger.maximum_pages += 1
        elif mutation == "prices":
            guard.prices = InferencePrices(
                guard.prices.input_per_million, guard.prices.output_per_million
            )
        elif mutation == "price_values":
            object.__setattr__(
                guard.prices, "input_per_million", guard.prices.input_per_million + 1
            )
        elif mutation == "receipt":
            guard.receipt = lambda *_: 0
        elif mutation == "capacity":
            guard._capacity += 1
        elif mutation == "wait":
            guard._wait_seconds += 1
        elif mutation == "semaphore":
            guard._semaphore = asyncio.Semaphore(1)
        elif mutation == "lock":
            guard.client._lock = asyncio.Lock()
        elif mutation == "transport":
            guard.client._transport = httpx.MockTransport(lambda _: None)
        elif mutation == "ceiling":
            guard.client.price_ceiling = ("0.4", "2.5")
        elif mutation == "attempt_limit":
            guard._maximum_attempts = 999
        assert await verifier.recheck(proof) is False
        assert await verifier.observe() is None
        await verifier.close()

    asyncio.run(scenario())


def test_busy_occupancy_does_not_change_the_bound_queue_configuration(qualified_world):
    from deploy.provider_qualification import ProviderQualification

    binding, guard, _, _ = qualified_world

    async def scenario():
        verifier = ProviderQualification(binding, guard)
        proof = await verifier.observe()
        await guard._semaphore.acquire()
        guard._admitted += 1
        try:
            assert await verifier.recheck(proof) is True
        finally:
            guard._admitted -= 1
            guard._semaphore.release()
            await verifier.close()

    asyncio.run(scenario())


def test_expiry_closure_and_foreign_proof_refuse_after_an_await(qualified_world):
    from deploy.provider_qualification import ProviderQualification

    binding, guard, _, now = qualified_world

    async def scenario():
        verifier = ProviderQualification(binding, guard)
        other = ProviderQualification(binding, guard)
        proof = await verifier.observe()
        assert await other.recheck(proof) is False
        assert await verifier.recheck(True) is False
        await asyncio.sleep(0)
        now[0] = 200
        assert await verifier.recheck(proof) is False
        assert await verifier.observe() is None
        await other.close()
        await verifier.close()

    asyncio.run(scenario())


def test_wrong_initial_queue_or_receipt_refuses_before_verification(qualified_world):
    from deploy.provider_qualification import ProviderQualification

    binding, guard, _, _ = qualified_world
    guard._capacity += 1
    with pytest.raises(ValueError, match="^Provider qualification refused$"):
        ProviderQualification(binding, guard)


@pytest.mark.parametrize("expire_at", ["key", "output"])
def test_expiry_at_real_adapter_boundaries_never_exposes_output(qualified_world, expire_at):
    from agent.admission.runtime import AdmissionClient
    from agent.inference.ledger import InferenceRefused
    from agent.llm.contract import LLMMessage, LLMRequest
    from deploy.provider_qualification import ProviderQualification

    binding, guard, ledger, now = qualified_world
    before = ledger.status()
    posts = []

    def transport(request):
        if request.method == "GET":
            assert request.url.path == "/api/v1/key"
            if expire_at == "key":
                now[0] = 200
            return httpx.Response(
                200, json={"data": {"limit": 2, "limit_remaining": 2, "limit_reset": None}}
            )
        posts.append(True)
        now[0] = 200
        return httpx.Response(
            200,
            json={
                "id": "synthetic-generation",
                "choices": [{"message": {"content": "synthetic output"}, "finish_reason": "stop"}],
                "usage": {"cost": 0.0001, "prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    guard.client._transport = httpx.MockTransport(transport)

    async def scenario():
        verifier = ProviderQualification(binding, guard)

        async def authorize():
            proof = await verifier.observe()
            if proof is None or not await verifier.recheck(proof):
                raise InferenceRefused("unavailable")

        client = AdmissionClient(guard, authorize)
        request = LLMRequest(
            system="Synthetic", messages=(LLMMessage("shopper", "hello"),), max_tokens=32
        )
        chunks = []
        with pytest.raises(InferenceRefused):
            async for chunk in client.complete(request):
                chunks.append(chunk)
        assert chunks == [] and guard._admitted == 0 and guard._semaphore._value == 1
        await verifier.close()

    asyncio.run(scenario())
    assert len(posts) == (0 if expire_at == "key" else 1)
    assert ledger.status()["uncertain"] == before["uncertain"] + (1 if expire_at == "key" else 0)
