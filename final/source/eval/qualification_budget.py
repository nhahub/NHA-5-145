"""Qualification allowance; explicit continuation retains durable prior charges."""

import asyncio
import json
import os
from contextlib import aclosing
from contextvars import ContextVar
from dataclasses import replace
from decimal import Decimal
from math import isfinite
from pathlib import Path
from uuid import uuid4

import httpx

from agent.inference.ledger import InferenceRefused
from agent.llm.openrouter import OpenRouterBudgetError, OpenRouterClient


class QualificationClient(OpenRouterClient):
    def __init__(
        self,
        settings,
        *,
        journal: Path,
        maximum_cost=0.25,
        maximum_calls=120,
        transport=None,
        durable_ledger=None,
    ):
        if (
            not isfinite(maximum_cost)
            or not 0 < maximum_cost <= 0.25
            or not 1 <= maximum_calls <= 200
        ):
            raise ValueError("Qualification bounds exceed the approved set")
        journal.parent.mkdir(parents=True, exist_ok=True)
        if durable_ledger is None:
            journal.touch(exist_ok=False)
        elif not journal.is_file():
            raise ValueError("Explicit continuation requires the existing journal")
        self.ledger = durable_ledger
        self.journal = journal
        self.maximum_cost, self.maximum_calls = maximum_cost, maximum_calls
        self.accounted_cost, self.posts = 0.0, 0
        self.reservations = {}
        self._budget_lock = asyncio.Lock()
        self._attempt = ContextVar("qualification_attempt")
        self._disabled = False
        self._candidate = settings.model
        if self.ledger is not None:
            if Decimal(self.ledger.status()["allowance_usd"]) != Decimal(str(maximum_cost)):
                raise ValueError("Continuation cannot replace its allowance")
            self._sync_ledger()
        super().__init__(
            settings, transport=_LimitedTransport(self, transport or httpx.AsyncHTTPTransport())
        )

    def summary(self):
        if self.ledger:
            self._sync_ledger()
        return {
            "accounted_cost": self.accounted_cost,
            "posts": self.posts,
            "maximum_cost": self.maximum_cost,
            "maximum_calls": self.maximum_calls,
            "unsettled": self.ledger.status()["uncertain"]
            if self.ledger
            else len(self.reservations),
            "disabled": self._disabled,
        }

    def _sync_ledger(self):
        status = self.ledger.status()
        self.accounted_cost = float(status["accounted_usd"])
        self.posts = status["attempts"]
        self._disabled = self._disabled or not status["enabled"]

    def _record(self, event, attempt, amount):
        try:
            with self.journal.open("a", encoding="utf-8") as file:
                file.write(
                    json.dumps(
                        {"event": event, "attempt": attempt, "amount": amount, **self.summary()}
                    )
                    + "\n"
                )
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            self._disabled = True
            if self.ledger:
                self.ledger.set_enabled(False)
            raise

    async def _reserve(self, request):
        payload = json.loads(request.content)
        if (
            request.url != httpx.URL("https://openrouter.ai/api/v1/chat/completions")
            or payload.get("model") != self._candidate
            or payload.get("provider", {}).get("max_price") != {"prompt": 0.3, "completion": 2.5}
        ):
            raise OpenRouterBudgetError(
                "Qualification request exceeds the frozen model/price policy"
            )
        bound = ((len(request.content) + 4096) * 0.3 + payload["max_tokens"] * 2.5) / 1_000_000
        async with self._budget_lock:
            if self.ledger:
                self._sync_ledger()
            if (
                self._disabled
                or self.posts >= self.maximum_calls
                or self.accounted_cost + bound > self.maximum_cost
            ):
                raise OpenRouterBudgetError(
                    "Qualification allowance exhausted; no additional POST allowed"
                )
            attempt = self._attempt.get()
            if attempt in self.reservations:
                raise OpenRouterBudgetError("Duplicate qualification attempt")
            if self.ledger:
                try:
                    self.ledger.reserve(
                        attempt, Decimal(str(bound)), maximum_attempts=self.maximum_calls
                    )
                except InferenceRefused as error:
                    raise OpenRouterBudgetError(
                        "Existing qualification allowance refuses POST"
                    ) from error
                self._sync_ledger()
            else:
                self.accounted_cost += bound
                self.posts += 1
            self.reservations[attempt] = bound
            self._record("reserved", attempt, bound)

    async def complete(self, request):
        attempt = request.attempt_id or str(uuid4())
        token = self._attempt.set(attempt)
        try:
            async with aclosing(super().complete(replace(request, attempt_id=attempt))) as stream:
                async for chunk in stream:
                    yield chunk
        finally:
            self._attempt.reset(token)
            async with self._budget_lock:
                metadata = next(
                    (m for m in reversed(self.call_metadata) if m.attempt_id == attempt), None
                )
                cost = metadata.usage.get("cost") if metadata and metadata.usage else None
                bound = self.reservations.get(attempt)
                if (
                    bound is not None
                    and isinstance(cost, int | float)
                    and not isinstance(cost, bool)
                    and isfinite(cost)
                    and cost >= 0
                ):
                    if self.ledger:
                        try:
                            self.ledger.settle(attempt, Decimal(str(cost)))
                        except InferenceRefused as error:
                            raise OpenRouterBudgetError(
                                "Durable qualification settlement failed"
                            ) from error
                        self.reservations.pop(attempt)
                        self._sync_ledger()
                    else:
                        self.accounted_cost += cost - self.reservations.pop(attempt)
                    if cost > bound:
                        self._disabled = True
                    self._record("settled", attempt, cost)
                elif bound is not None and self.ledger:
                    try:
                        self.ledger.ensure_accounted(attempt)
                    except InferenceRefused as error:
                        raise OpenRouterBudgetError(
                            "Durable qualification accounting unavailable"
                        ) from error


class _LimitedTransport(httpx.AsyncBaseTransport):
    def __init__(self, owner, transport):
        self.owner, self.transport = owner, transport

    async def handle_async_request(self, request):
        if request.method == "POST":
            await self.owner._reserve(request)
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()
