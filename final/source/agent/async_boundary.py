"""Bounded retained synchronous I/O and sync/async boundary invocation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from inspect import isawaitable, iscoroutinefunction


class BoundaryUnavailable(RuntimeError):
    pass


async def invoke(target, method, *args, **kwargs):
    result = getattr(target, method)(*args, **kwargs)
    return await result if isawaitable(result) else result


class BoundedIO:
    def __init__(self, *, workers=1, capacity=64):
        if (
            type(workers) is not int
            or not 1 <= workers <= 4
            or type(capacity) is not int
            or not 1 <= capacity <= 128
        ):
            raise ValueError("Finite authority worker bounds required")
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="copilot-authority"
        )
        self._capacity, self._active, self._closed = capacity, set(), False

    def _done(self, future):
        self._active.discard(future)
        if not future.cancelled():
            future.exception()

    async def call(self, function, *args, **kwargs):
        if self._closed or len(self._active) >= self._capacity or iscoroutinefunction(function):
            raise BoundaryUnavailable()
        future = asyncio.wrap_future(self._executor.submit(partial(function, *args, **kwargs)))
        self._active.add(future)
        future.add_done_callback(self._done)
        return await asyncio.shield(future)

    async def close(self):
        self._closed = True
        try:
            if self._active:
                await asyncio.shield(asyncio.gather(*tuple(self._active), return_exceptions=True))
        finally:
            self._executor.shutdown(wait=False, cancel_futures=False)
