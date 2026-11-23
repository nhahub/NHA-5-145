"""Agent work leases; background traffic never advances meaningful activity."""

import asyncio
from contextlib import suppress
from pathlib import Path

from agent.lifecycle.store import Lifecycle, LifecycleUnavailable


def configured_lifecycle(environment, admission):
    selected = any(key.startswith("LIFECYCLE_") for key in environment)
    if not selected:
        return None
    if environment.get("COPILOT_ENV") != "local-rehearsal" or admission is None:
        raise ValueError("Lifecycle transport is qualified only for local rehearsal")
    return Lifecycle(
        Path(environment["LIFECYCLE_DB_PATH"]), environment["LIFECYCLE_DB_ID"], admission.store
    )


class LifecycleWork:
    def __init__(self, lifecycle, sessions):
        self.lifecycle, self.sessions = lifecycle, sessions
        self.generation = lifecycle.status()["generation"]
        self.requests = set()
        self.pending = None
        self.failed = False

    def check(self):
        self.refresh()
        state = self.lifecycle.status()
        if (
            self.failed
            or state["generation"] != self.generation
            or state["state"] not in {"ready", "draining"}
        ):
            raise LifecycleUnavailable()

    def begin(self):
        self.refresh()
        self.check()
        token = self.lifecycle.begin_work(generation=self.generation)
        self.requests.add(token)
        return token

    def finish(self, token, *, meaningful=False):
        try:
            self.refresh()
            if meaningful:
                self.check()
                activity = self.lifecycle.begin_work(meaningful=True, generation=self.generation)
                self.lifecycle.end_work(activity)
        finally:
            self.requests.discard(token)
            if token != self.pending:
                with suppress(LifecycleUnavailable):
                    self.lifecycle.end_work(token)

    def refresh(self):
        if self.failed:
            return
        try:
            for token in self.requests:
                self.lifecycle.renew_work(token)
            if self.sessions.has_pending_work():
                if self.pending is None:
                    # Hand already accepted protection to the pending Task. This
                    # is not new admission, so degraded readiness cannot revoke
                    # the request while we create its post-response protection.
                    self.pending = next(iter(self.requests), None)
                    if self.pending is None:
                        self.pending = self.lifecycle.begin_work(generation=self.generation)
                else:
                    self.lifecycle.renew_work(self.pending)
            elif self.pending is not None:
                if self.pending not in self.requests:
                    self.lifecycle.end_work(self.pending)
                self.pending = None
        except LifecycleUnavailable:
            # Never resurrect expired worker authority. A fresh process/link is
            # required; uncertain Actions stay uncertain and are never replayed.
            self.failed = True

    async def maintain(self):
        while True:
            self.refresh()
            await asyncio.sleep(10)

    def close(self):
        for token in {*self.requests, self.pending} - {None}:
            with suppress(LifecycleUnavailable):
                self.lifecycle.end_work(token)
