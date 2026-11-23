"""Records one event-log entry per model completion made during a Shopping Task."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import replace
from uuid import uuid4

from agent.event_log import ROUTE, debug_text, is_cost, is_count, record


class RecordedClient:
    """Wraps the turn's model client; the inference guard underneath is left as configured.

    Each completion gets an attempt id before it reaches the guard and the provider
    adapter, both of which keep an id they are given. Usage is then read from the
    adapter's call details by that id, so concurrent calls are never mixed up.
    """

    def __init__(self, client, *, provider: str, model: str, classify: Callable[[Exception], str]):
        self.client = client
        self.provider = provider
        self.model = model
        self.classify = classify

    async def complete(self, request):
        attempt = request.attempt_id or str(uuid4())
        request = replace(request, attempt_id=attempt)
        started = time.monotonic()
        failure = None
        output = []
        try:
            async for chunk in self.client.complete(request):
                output.append(chunk.text or "")
                yield chunk
        except (asyncio.CancelledError, GeneratorExit):
            failure = "interrupted"
            raise
        except Exception as error:
            failure = self.classify(error)
            raise
        finally:
            if output or failure is None:
                debug_text("model_output", "".join(output))
            usage = _usage(self.client, attempt)
            record(
                "model_call",
                provider=self.provider,
                model=self.model,
                prompt_version=request.prompt_version,
                schema_version=request.schema_version,
                attempt_id=attempt,
                latency_ms=int((time.monotonic() - started) * 1000),
                outcome="ok" if failure is None else "failed",
                failure=failure,
                prompt_tokens=_kept(usage.get("prompt_tokens"), is_count),
                completion_tokens=_kept(usage.get("completion_tokens"), is_count),
                cost_usd=_kept(usage.get("cost"), is_cost),
                route=_kept(_route(self.client, attempt), _is_route),
            )


def _usage(client, attempt: str) -> dict:
    """The provider-reported usage for one attempt, or nothing if it is unknown."""
    adapter = getattr(client, "client", client)  # the guard keeps its provider adapter here
    for item in reversed(tuple(getattr(adapter, "call_metadata", ()) or ())):
        if getattr(item, "attempt_id", None) == attempt:
            return getattr(item, "usage", None) or {}
    return {}


def _route(client, attempt: str):
    """The upstream provider that served one attempt, when the adapter reports it."""
    adapter = getattr(client, "client", client)
    for item in reversed(tuple(getattr(adapter, "call_metadata", ()) or ())):
        if getattr(item, "attempt_id", None) == attempt:
            return getattr(item, "route", None)
    return None


def _is_route(value) -> bool:
    return isinstance(value, str) and ROUTE.fullmatch(value) is not None


def _kept(value, valid):
    return value if valid(value) else None
