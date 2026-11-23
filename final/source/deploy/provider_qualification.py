"""Lightweight captured qualification. Runtime observations do not read files."""

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.config import openrouter_receipt
from agent.inference.ledger import AllowanceLedger
from agent.llm.config import LLMSettings, load_llm_settings
from agent.llm.openrouter import OpenRouterClient
from deploy.provider_binding import REFUSAL, ProviderBinding


@dataclass(frozen=True, repr=False)
class QualificationProof:
    _owner: object
    _snapshot: object

    def __repr__(self):
        return "QualificationProof()"


class ProviderQualification:
    def __init__(self, binding, guard):
        try:
            if type(binding) is not ProviderBinding or type(guard) is not GuardedClient:
                raise ValueError()
            binding.snapshot()
            settings = binding.settings
            values = settings.inference
            client = guard.client
            expected = load_llm_settings(settings.environment())
            if (
                type(client) is not OpenRouterClient
                or type(client._settings) is not LLMSettings
                or client._settings != expected
                or tuple(client.price_ceiling) != ("0.3", "2.5")
                or type(guard.ledger) is not AllowanceLedger
                or guard.ledger.path != Path(values["INFERENCE_LEDGER_PATH"]).resolve(strict=True)
                or guard.ledger.identity != values["INFERENCE_LEDGER_ID"]
                or guard.ledger.maximum_pages != int(values["INFERENCE_MAXIMUM_PAGES"])
                or type(guard.prices) is not InferencePrices
                or guard.prices.input_per_million
                != Decimal(values["INFERENCE_INPUT_USD_PER_MILLION"])
                or guard.prices.output_per_million
                != Decimal(values["INFERENCE_OUTPUT_USD_PER_MILLION"])
                or guard.receipt is not openrouter_receipt
                or type(guard._semaphore) is not asyncio.Semaphore
                or type(guard._admission_lock) is not asyncio.Lock
                or type(client._lock) is not asyncio.Lock
                or guard._semaphore._value != int(values["INFERENCE_MAX_ACTIVE"])
                or guard._admitted != 0
                or guard._capacity
                != int(values["INFERENCE_MAX_ACTIVE"]) + int(values["INFERENCE_MAX_WAITING"])
                or guard._wait_seconds != float(values["INFERENCE_WAIT_SECONDS"])
                or (
                    settings.operating is not None
                    and guard._maximum_attempts != settings.operating_attempt_ceiling
                )
            ):
                raise ValueError()
            self._binding, self._guard = binding, guard
            self._closed, self._owner = False, object()
            # Keep strong references as well as IDs; an object replacement cannot
            # evade the identity seal through address reuse.
            self._references = (
                guard,
                client,
                client._settings,
                client._lock,
                client._transport,
                guard.ledger,
                guard.prices,
                guard._semaphore,
                guard._admission_lock,
                guard.receipt,
                guard._queue_observer,
                binding,
                binding.settings,
                binding._initial,
            )
            self._signature_at_start = self._signature()
            return
        except Exception:
            pass
        raise ValueError(REFUSAL)

    def __repr__(self):
        return "ProviderQualification()"

    def _signature(self):
        guard, binding = self._guard, self._binding
        client, settings = guard.client, binding.settings
        llm = client._settings
        references = (
            guard,
            client,
            llm,
            client._lock,
            client._transport,
            guard.ledger,
            guard.prices,
            guard._semaphore,
            guard._admission_lock,
            guard.receipt,
            guard._queue_observer,
            binding,
            settings,
            binding._initial,
        )
        return (
            tuple(id(value) for value in references),
            (
                llm.provider,
                llm.model,
                llm.endpoint,
                llm.timeout_seconds,
                llm.stream,
                llm.reasoning_effort,
                llm.openrouter_total_limit,
                llm.region,
                llm.api_key.get_secret_value(),
                tuple(client.price_ceiling),
            ),
            (
                guard.ledger.path,
                guard.ledger.identity,
                guard.ledger.maximum_pages,
                guard.prices.input_per_million,
                guard.prices.output_per_million,
                guard._capacity,
                guard._wait_seconds,
                guard._maximum_attempts,
            ),
            (
                settings.provider,
                settings.model,
                settings.provider_key,
                settings.fingerprint,
                settings.operating.values() if settings.operating is not None else None,
                settings.operating_attempt_ceiling,
                tuple(sorted(settings.inference.items())),
            ),
        )

    def _intact(self):
        try:
            return not self._closed and self._signature() == self._signature_at_start
        except Exception:
            return False

    async def observe(self):
        try:
            if not self._intact():
                return None
            snapshot = self._binding.snapshot()
            if self._intact():
                return QualificationProof(self._owner, snapshot)
        except Exception:
            pass
        return None

    async def recheck(self, proof):
        if type(proof) is not QualificationProof or proof._owner is not self._owner:
            return False
        current = await self.observe()
        return current is not None and current == proof

    async def close(self):
        self._closed = True
