"""Configured admission policy; retains Shopper authority as a separate boundary."""

import os
from contextlib import aclosing
from dataclasses import replace
from pathlib import Path
from time import monotonic

from agent.admission.store import AdmissionDenied, InvitationStore, digest


class AdmissionPolicy:
    def __init__(
        self,
        store: InvitationStore,
        *,
        maximum_bytes=2621440,
        global_rate=1000,
        browser_rate=120,
        maximum_requests=16,
        maximum_streams=16,
        maximum_sessions=20,
        browser_sessions=2,
    ):
        self.store = store
        values = (
            maximum_bytes,
            global_rate,
            browser_rate,
            maximum_requests,
            maximum_streams,
            maximum_sessions,
            browser_sessions,
        )
        if any(type(v) is not int or v <= 0 for v in values) or (
            maximum_bytes > 4_000_000
            or global_rate > 10000
            or browser_rate > global_rate
            or maximum_requests > 64
            or maximum_streams > 100
            or maximum_sessions > 800
            or browser_sessions > 8
        ):
            raise ValueError("Finite admission limits are required")
        (
            self.maximum_bytes,
            self.global_rate,
            self.browser_rate,
            self.maximum_requests,
            self.maximum_streams,
            self.maximum_sessions,
            self.browser_sessions,
        ) = values
        self._browsers = {}

    @staticmethod
    def subject(record):
        if record.shopper is None:
            raise AdmissionDenied()
        return digest(record.csrf + ":" + record.shopper.context)

    def allowed(self, record):
        return record.shopper is not None and self.store.allowed(self.subject(record))

    def redeem(self, record, code):
        return self.store.redeem(code, self.subject(record))

    def allocate_session(self, record):
        return self.store.allocate_session(self.subject(record))

    def browser_request(self, record, *, stop=False):
        now = monotonic()
        self._browsers = {k: v for k, v in self._browsers.items() if now - v[0] < 60}
        key = digest(record.csrf) + (":stop" if stop else "")
        start, count = self._browsers.get(key, (now, 0))
        if count >= (10 if stop else self.browser_rate) or (
            key not in self._browsers and len(self._browsers) >= 200
        ):
            raise AdmissionDenied("access_busy")
        self._browsers[key] = (start, count + 1)


FIELDS = {
    "maximum_bytes": "MAX_REQUEST_BYTES",
    "global_rate": "REQUESTS_PER_MINUTE",
    "browser_rate": "BROWSER_REQUESTS_PER_MINUTE",
    "maximum_requests": "MAX_ACTIVE_REQUESTS",
    "maximum_streams": "MAX_STREAMS",
    "maximum_sessions": "MAX_SESSIONS",
    "browser_sessions": "MAX_BROWSER_SESSIONS",
}


def configured_admission(environment=None):
    values = os.environ if environment is None else environment
    selected = any(key.startswith("ADMISSION_") for key in values)
    if not selected and values.get("COPILOT_ENV") != "production":
        return None
    names = ["ADMISSION_DB_PATH", "ADMISSION_DB_ID", *("ADMISSION_" + k for k in FIELDS.values())]
    if not all(values.get(k, "").strip() for k in names):
        raise ValueError("Explicit invited admission configuration is required")
    return AdmissionPolicy(
        InvitationStore(Path(values["ADMISSION_DB_PATH"]), values["ADMISSION_DB_ID"]),
        **{key: int(values["ADMISSION_" + name]) for key, name in FIELDS.items()},
    )


class AdmissionClient:
    """Recheck a bound live session before each model entry and before exposing output."""

    def __init__(self, client, verify):
        self.client, self.verify = client, verify

    async def complete(self, request):
        await self.verify()
        chunks = []
        async with aclosing(
            self.client.complete(replace(request, authorization_check=self.verify))
        ) as response:
            async for chunk in response:
                chunks.append(chunk)
        await self.verify()
        for chunk in chunks:
            yield chunk
