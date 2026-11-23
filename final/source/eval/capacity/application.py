"""Explicit injected model fixture. No API client, language matching or live calls."""

import asyncio
import json
import os
from contextvars import ContextVar
from math import isfinite
from pathlib import Path
from time import monotonic

from agent.app import create_app
from agent.llm import LLMChunk, LLMSettings

entered_at = ContextVar("capacity_http_entered", default=None)


class DelayedDecision:
    def __init__(self, root, delay_seconds):
        if not isfinite(delay_seconds) or not 0 <= delay_seconds <= 2:
            raise ValueError("Fixture delay must be between zero and two seconds")
        self.root, self.delay = Path(root), delay_seconds
        self.active = self.peak = 0
        self.calls = []
        self.queue = []

    def observe_queue(self, outcome, milliseconds):
        if len(self.queue) < 128:
            self.queue.append({"outcome": outcome, "milliseconds": milliseconds})

    def save(self):
        # Finite, content-free, exclusive-owner telemetry; never serialize requests.
        stage = self.root / "provider.tmp"
        stage.write_text(
            json.dumps(
                {
                    "active": self.active,
                    "peak": self.peak,
                    "calls": self.calls,
                    "queue": self.queue,
                    "paid_calls": 0,
                }
            ),
            encoding="utf-8",
        )
        stage.replace(self.root / "provider.json")

    async def complete(self, request):
        if len(self.calls) >= 64:
            raise RuntimeError("Capacity fixture exhausted its finite call bound")
        started = monotonic()
        row = {"pre_provider_ms": (started - (entered_at.get() or started)) * 1000}
        self.calls.append(row)
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.save()
        try:
            deadline = monotonic() + 10
            while (self.root / "hold").exists():
                if monotonic() >= deadline:
                    raise TimeoutError("Bounded fixture hold expired")
                await asyncio.sleep(0.02)
            await asyncio.sleep(self.delay)
            await request.authorize()
            yield LLMChunk(
                text=json.dumps(
                    {
                        "v": 8,
                        "language": "en",
                        "dialect": "english",
                        "intent": "cart_edit",
                        "cart_operation": "add",
                        "cart_source": "fixture shopping request",
                        "product_id": "shoe-09",
                        "constraints": {},
                        "missing_fields": [],
                        "conflicting_fields": [],
                        "needs_clarification": False,
                    }
                )
            )
        finally:
            row["provider_ms"] = (monotonic() - started) * 1000
            self.active -= 1
            self.save()


def capacity_app(root, *, delay_seconds=0.4, admission=None):
    root = Path(root).resolve(strict=True)
    model = DelayedDecision(root, delay_seconds)
    app = create_app(
        llm_settings=LLMSettings(provider="groq", model="test-model"),
        llm_client=model,
        inference_queue_observer=model.observe_queue,
        admission=admission,
        catalogue_retrieval_enabled=False,
    )

    @app.middleware("http")
    async def timing(request, call_next):
        token = entered_at.set(monotonic())
        try:
            return await call_next(request)
        finally:
            entered_at.reset(token)

    return app


def create_capacity_app():
    if os.environ.get("COPILOT_CAPACITY_REHEARSAL") != "1":
        raise ValueError("Capacity fixtures require explicit rehearsal configuration")
    return capacity_app(Path(os.environ["CAPACITY_OUTPUT"]))
