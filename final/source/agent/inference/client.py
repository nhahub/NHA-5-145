"""Bounded provider-neutral complete() boundary; no language interpretation."""

import asyncio
import json
from contextlib import aclosing, suppress
from dataclasses import dataclass, replace
from decimal import Decimal
from math import isfinite
from time import monotonic
from uuid import uuid4

from agent.inference.ledger import InferenceRefused, units
from agent.llm.provider_schema import inline_schema_references


@dataclass(frozen=True)
class InferencePrices:
    input_per_million: Decimal
    output_per_million: Decimal

    def __post_init__(self):
        if units(self.input_per_million) + units(self.output_per_million) <= 0:
            raise ValueError("Explicit positive inference prices are required")

    def reservation(self, request) -> Decimal:
        if request.tools or not 0 < request.max_tokens <= 2048:
            raise InferenceRefused("unavailable")
        schema = request.response_schema or {}
        try:
            body = json.dumps(
                {
                    "system": request.system,
                    "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                    "response_schema": inline_schema_references(schema),
                }
            ).encode()
        except (ValueError, KeyError, TypeError, RecursionError) as error:
            raise InferenceRefused("unavailable") from error
        if len(body) > 256_000:
            raise InferenceRefused("unavailable")
        # One input byte per token is deliberately conservative. Include protocol
        # overhead and fully expanded local schema references before reserving.
        return (
            Decimal(len(body) + 4096) * self.input_per_million
            + Decimal(request.max_tokens) * self.output_per_million
        ) / Decimal(1_000_000)


class GuardedClient:
    def __init__(
        self,
        client,
        ledger,
        prices: InferencePrices,
        *,
        receipt=None,
        maximum_active: int,
        maximum_waiting: int,
        wait_seconds: float,
        queue_observer=None,
        maximum_attempts: int | None = None,
    ):
        if (
            isinstance(maximum_active, bool)
            or not isinstance(maximum_active, int)
            or not 1 <= maximum_active <= 32
            or isinstance(maximum_waiting, bool)
            or not isinstance(maximum_waiting, int)
            or not 0 <= maximum_waiting <= 64
            or not isfinite(wait_seconds)
            or not 0 < wait_seconds <= 30
        ):
            raise ValueError("Finite inference concurrency and queue bounds are required")
        if maximum_attempts is not None and (
            type(maximum_attempts) is not int or not 1 <= maximum_attempts <= 1_000_000
        ):
            raise ValueError("Absolute finite inference attempt ceiling required")
        self.client, self.ledger, self.prices = client, ledger, prices
        self.receipt = receipt or (lambda _client, _attempt: None)
        self._semaphore = asyncio.Semaphore(maximum_active)
        self._admission_lock = asyncio.Lock()
        self._admitted = 0
        self._capacity = maximum_active + maximum_waiting
        self._wait_seconds = wait_seconds
        self._queue_observer = queue_observer
        self._maximum_attempts = maximum_attempts

    def _observe_queue(self, outcome, started):
        if self._queue_observer is not None:
            # Trusted local telemetry must never change execution or authority.
            with suppress(Exception):
                self._queue_observer(outcome, (monotonic() - started) * 1000)

    async def complete(self, request):
        started = monotonic()
        async with self._admission_lock:
            if self._admitted >= self._capacity:
                self._observe_queue("full", started)
                raise InferenceRefused("busy")
            self._admitted += 1
        acquired = False
        try:
            try:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_seconds)
            except TimeoutError as error:
                self._observe_queue("timeout", started)
                raise InferenceRefused("busy") from error
            acquired = True
            self._observe_queue("acquired", started)
            await request.authorize()
            attempt = request.attempt_id or str(uuid4())
            bound = self.prices.reservation(request)
            await asyncio.to_thread(
                self.ledger.reserve, attempt, bound, maximum_attempts=self._maximum_attempts
            )
            chunks = []
            try:
                await request.authorize()
                async with aclosing(
                    self.client.complete(
                        replace(request, attempt_id=attempt, provider_attempt_limit=1)
                    )
                ) as response:
                    async for chunk in response:
                        chunks.append(chunk)
            finally:
                cost = self.receipt(self.client, attempt)
                if cost is not None:
                    await asyncio.to_thread(self.ledger.settle, attempt, cost)
                else:
                    await asyncio.to_thread(self.ledger.ensure_accounted, attempt)
            # Do not expose a completion if durable settlement fails.
            for chunk in chunks:
                yield chunk
        finally:
            if acquired:
                self._semaphore.release()
            async with self._admission_lock:
                self._admitted -= 1
