"""Explicit injected remote admission, with event-loop ownership and bounded I/O."""

from agent.admission.runtime import AdmissionPolicy
from agent.admission.store import AdmissionDenied
from agent.async_boundary import BoundedIO


class AsyncAdmissionPolicy(AdmissionPolicy):
    def __init__(self, store, **limits):
        super().__init__(store, **limits)
        self._io = BoundedIO(workers=4, capacity=64)

    async def _call(self, method, *args):
        try:
            return await self._io.call(getattr(self.store, method), *args)
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    async def allowed(self, record):
        if record.shopper is None:
            return False
        subject = self.subject(record)
        try:
            result = await self._call("allowed", subject)
            return result is True and record.shopper is not None and self.subject(record) == subject
        except AdmissionDenied:
            return False

    async def ready(self):
        try:
            return await self._call("check") is None
        except AdmissionDenied:
            return False

    async def redeem(self, record, code):
        subject = self.subject(record)
        await self._call("redeem", code, subject)
        if record.shopper is None or self.subject(record) != subject:
            raise AdmissionDenied()

    async def allocate_session(self, record):
        subject = self.subject(record)
        invitation = await self._call("allocate_session", subject)
        if record.shopper is None or self.subject(record) != subject:
            raise AdmissionDenied()
        return invitation

    async def close(self):
        await self._io.close()
