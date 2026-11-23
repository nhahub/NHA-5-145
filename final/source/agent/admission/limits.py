"""ASGI request bounds, including chunked bodies and the whole SSE lifetime."""

import asyncio
import hashlib
from time import monotonic

from starlette.responses import JSONResponse


def denied(reason, status=403):
    return JSONResponse(
        {"detail": "Demo access unavailable", "code": reason},
        status_code=status,
        headers={"Cache-Control": "no-store", **({"Retry-After": "5"} if status == 429 else {})},
    )


def is_owner_stop(method, path):
    parts = path.strip("/").split("/")
    return method == "POST" and len(parts) == 3 and parts[0] == "sessions" and parts[2] == "stop"


class AdmissionLimits:
    def __init__(self, app, policy):
        self.app, self.policy = app, policy
        self.requests = self.streams = self.count = 0
        self.window = monotonic()
        self.browser_streams = {}
        self.stops = self.stop_count = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/health" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        policy = self.policy
        now = monotonic()
        if now - self.window >= 60:
            self.window, self.count = now, 0
            self.stop_count = 0
        stop = is_owner_stop(scope["method"], scope["path"])
        if stop:
            self.stop_count += 1
        else:
            self.count += 1
        stream = scope["path"].endswith("/events")
        cookie = next((v for k, v in scope["headers"] if k == b"cookie"), b"")
        credentials = [
            p.strip().split(b"=", 1)[1]
            for p in cookie.split(b";")
            if p.strip().startswith(b"copilot_agent=")
        ]
        credential = credentials[0] if len(credentials) == 1 else b""
        subject = hashlib.sha256(credential).hexdigest()
        if stop and (self.stop_count > 100 or self.stops >= 4):
            return await denied("access_busy", 429)(scope, receive, send)
        if not stop and (
            self.count > policy.global_rate
            or (
                self.streams >= policy.maximum_streams
                if stream
                else self.requests >= policy.maximum_requests
            )
            or (stream and self.browser_streams.get(subject, 0) >= policy.browser_sessions)
        ):
            return await denied("access_busy", 429)(scope, receive, send)
        if stop:
            self.stops += 1
        elif stream:
            self.streams += 1
            self.browser_streams[subject] = self.browser_streams.get(subject, 0) + 1
        else:
            self.requests += 1
        try:
            chunks, size = [], 0
            try:
                async with asyncio.timeout(5):
                    while True:
                        part = await receive()
                        if part["type"] == "http.disconnect":
                            return
                        size += len(part.get("body", b""))
                        if size > (
                            min(4096, policy.maximum_bytes) if stop else policy.maximum_bytes
                        ):
                            return await denied("request_too_large", 413)(scope, receive, send)
                        chunks.append(part.get("body", b""))
                        if not part.get("more_body", False):
                            break
            except TimeoutError:
                return await denied("request_timeout", 408)(scope, receive, send)
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, send)
        finally:
            if stop:
                self.stops -= 1
            elif stream:
                self.streams -= 1
                self.browser_streams[subject] -= 1
                if not self.browser_streams[subject]:
                    del self.browser_streams[subject]
            else:
                self.requests -= 1
