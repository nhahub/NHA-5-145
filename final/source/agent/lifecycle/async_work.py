"""Serialized event-loop lease bookkeeping with retained bounded remote I/O."""

import asyncio
from contextlib import suppress
from time import monotonic

from agent.async_boundary import BoundedIO
from agent.lifecycle.store import LifecycleUnavailable


class AsyncLifecycleWork:
    def __init__(self, lifecycle, sessions, *, clock=monotonic):
        self.lifecycle, self.sessions, self.clock = lifecycle, sessions, clock
        self.generation, self.pending = None, None
        self.requests, self._jobs, self._cleanup = set(), set(), set()
        self.failed, self._closed = False, False
        self._last_renew = None
        self._lock, self._io = asyncio.Lock(), BoundedIO(workers=1, capacity=64)

    def _done(self, task):
        self._jobs.discard(task)
        if not task.cancelled():
            task.exception()

    async def _run(self, operation, *args):
        if self._closed or len(self._jobs) >= 64:
            raise LifecycleUnavailable()

        async def execute():
            async with self._lock:
                return await getattr(self, "_" + operation)(*args)

        task = asyncio.create_task(execute())
        self._jobs.add(task)
        task.add_done_callback(self._done)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if operation == "begin":
                cleanup = asyncio.create_task(self._abandoned_begin(task))
                self._cleanup.add(cleanup)
                cleanup.add_done_callback(self._cleanup.discard)
            raise

    async def _abandoned_begin(self, task):
        try:
            token = await asyncio.shield(task)
            await self.finish(token)
        except Exception:
            self.failed = True

    async def _backend(self, method, *args, **options):
        try:
            return await self._io.call(getattr(self.lifecycle, method), *args, **options)
        except Exception:
            raise LifecycleUnavailable() from None

    async def _initialize(self):
        if self.generation is not None:
            return
        state = await self._backend("status")
        if (
            self.sessions.has_pending_work()
            or state["generation"] < 1
            or state["state"] not in {"starting", "ready", "draining", "unhealthy"}
        ):
            raise LifecycleUnavailable()
        self.generation = state["generation"]

    async def _readiness_state(self):
        if self.failed or self.generation is None:
            raise LifecycleUnavailable()
        state = await self._backend("status")
        if state["generation"] != self.generation:
            self.failed = True
            raise LifecycleUnavailable()
        return state

    async def _refresh(self):
        if self.failed or self.generation is None:
            raise LifecycleUnavailable()
        now = self.clock()
        if self._last_renew is None or now - self._last_renew >= 10:
            try:
                for token in self.requests | ({self.pending} if self.pending else set()):
                    await self._backend("renew_work", token)
            except LifecycleUnavailable:
                self.failed = True
                raise
            self._last_renew = self.clock()
        if self.sessions.has_pending_work():
            if self.pending is None:
                self.pending = next(iter(self.requests), None)
                if self.pending is None:
                    self.pending = await self._backend("begin_work", generation=self.generation)
        elif self.pending is not None:
            if self.pending not in self.requests:
                await self._backend("end_work", self.pending, generation=self.generation)
            self.pending = None

    async def _check(self):
        await self._refresh()
        await self._readiness_state()
        await self._backend("check_work", generation=self.generation)

    async def _begin(self):
        await self._check()
        token = await self._backend("begin_work", generation=self.generation)
        self.requests.add(token)
        return token

    async def _finish(self, token, meaningful):
        try:
            await self._refresh()
            if meaningful:
                await self._check()
                activity = await self._backend(
                    "begin_work", meaningful=True, generation=self.generation
                )
                await self._backend("end_work", activity, generation=self.generation)
        finally:
            self.requests.discard(token)
            if token != self.pending:
                await self._backend("end_work", token, generation=self.generation)

    async def initialize(self):
        return await self._run("initialize")

    async def readiness_state(self):
        return await self._run("readiness_state")

    async def check(self):
        return await self._run("check")

    async def begin(self):
        return await self._run("begin")

    async def finish(self, token, *, meaningful=False):
        return await self._run("finish", token, meaningful)

    async def refresh(self):
        return await self._run("refresh")

    async def maintain(self):
        while True:
            with suppress(LifecycleUnavailable):
                await self.refresh()
            await asyncio.sleep(10)

    async def close(self):
        self._closed = True
        while self._jobs or self._cleanup:
            await asyncio.shield(
                asyncio.gather(*tuple(self._jobs | self._cleanup), return_exceptions=True)
            )
        try:
            if not self.sessions.has_pending_work():
                for token in self.requests - {self.pending}:
                    with suppress(LifecycleUnavailable):
                        await self._backend("end_work", token, generation=self.generation)
        finally:
            await self._io.close()
