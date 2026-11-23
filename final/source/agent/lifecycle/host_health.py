"""Authenticated host readiness; deployment must supply every trusted async check."""

import asyncio
from inspect import iscoroutinefunction

from starlette.responses import JSONResponse

from agent.lifecycle.readiness import _config, readiness_reply

CHECKS = frozenset({"release", "storefront", "admission", "allowance", "provider"})


class HostReadiness:
    def __init__(self, work, secret, release, checks):
        _config(secret, release)
        if set(checks) != CHECKS or not all(
            iscoroutinefunction(check) for check in checks.values()
        ):
            raise ValueError("Every trusted async readiness check is required")
        self.work, self._secret, self.release = work, secret, release
        self._checks = tuple(checks.values())
        self._flight, self._closed = None, False

    @staticmethod
    def _eligible(state, generation):
        return (
            state["generation"] == generation
            and state["state"] in {"starting", "ready", "draining", "unhealthy"}
            and (state["state"] != "starting" or state["remaining_seconds"] > 0)
        )

    async def _aggregate(self, generation):
        try:
            state = await self.work.readiness_state()
            if not self._eligible(state, generation) or self.work.failed:
                return False
            results = await asyncio.gather(
                *(check() for check in self._checks), return_exceptions=True
            )
            state = await self.work.readiness_state()
            return (
                all(result is True for result in results)
                and self._eligible(state, generation)
                and self.work.generation == generation
                and not self.work.failed
            )
        except Exception:
            return False

    @staticmethod
    def _done(task):
        if not task.cancelled():
            task.exception()

    async def close(self):
        self._closed = True
        if self._flight is not None:
            if not self._flight.done():
                self._flight.cancel()
            await asyncio.shield(asyncio.gather(self._flight, return_exceptions=True))

    async def response(self, headers):
        generation = self.work.generation
        if generation is None:
            return JSONResponse(
                {"detail": "Readiness unavailable"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        try:
            # Authenticate before datastore or dependency I/O. Never trust header generation.
            readiness_reply(
                headers,
                secret=self._secret,
                release=self.release,
                generation=generation,
                ready=False,
            )
        except ValueError:
            return JSONResponse(
                {"detail": "Readiness refused"},
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        ready = False
        if not self._closed and (self._flight is None or self._flight.done()):
            task = self._flight = asyncio.create_task(self._aggregate(generation))
            task.add_done_callback(self._done)
            try:
                # wait() bounds the response without awaiting slow cancellation cleanup.
                done, _ = await asyncio.wait({task}, timeout=1.5)
                if task in done and not task.cancelled():
                    ready = task.result() is True
            finally:
                if not task.done():
                    task.cancel()
                # Retain the single slot until actual completion, including cleanup.
        ready = (
            ready
            and not self._closed
            and not self.work.failed
            and self.work.generation == generation
        )
        return JSONResponse(
            readiness_reply(
                headers,
                secret=self._secret,
                release=self.release,
                generation=generation,
                ready=ready,
            ),
            headers={"Cache-Control": "no-store"},
        )
