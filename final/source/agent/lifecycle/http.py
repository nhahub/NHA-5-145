"""Always-available local waiting service; it never waits for a host to boot."""

import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse, JSONResponse

from agent.admission.limits import AdmissionLimits
from agent.admission.runtime import AdmissionPolicy
from agent.admission.store import AdmissionDenied
from agent.lifecycle.store import LifecycleUnavailable


def create_waiting_app(lifecycle, *, origin, shopping_url="http://localhost:4100/"):
    if origin not in {"http://localhost:4200", "http://127.0.0.1:4200", "http://testserver"}:
        raise ValueError("This adapter is for the loopback rehearsal only")
    if shopping_url != "http://localhost:4100/":
        raise ValueError("Fixed local shopping destination required")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def bounds(request: Request, call_next):
        try:
            lifecycle.rate("http", 240)
            if request.url.path == "/wake" and request.method == "POST":
                lifecycle.rate("wake", 10)
            elif request.url.path == "/status":
                lifecycle.rate("poll", 120)
            response = await call_next(request)
        except LifecycleUnavailable:
            response = JSONResponse({"state": "unavailable"}, status_code=429)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Retry-After": "5",
            }
        )
        return response

    @app.get("/")
    async def page():
        nonce = secrets.token_urlsafe(24)
        html = (Path(__file__).with_name("waiting.html")).read_text(encoding="utf-8")
        return HTMLResponse(
            html.replace("NONCE", nonce),
            headers={
                "Content-Security-Policy": (
                    "default-src 'none'; connect-src 'self'; form-action 'self'; "
                    f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                    "frame-ancestors 'none'; base-uri 'none'"
                )
            },
        )

    @app.get("/status")
    async def status():
        return lifecycle.status()

    @app.post("/wake", status_code=202)
    async def wake(request: Request):
        if request.headers.get("origin") != origin or request.url.query:
            return JSONResponse({"state": "denied"}, status_code=403)
        try:
            payload = await request.json()
            if not isinstance(payload, dict) or set(payload) != {"code"}:
                raise AdmissionDenied()
            return lifecycle.wake(payload["code"])
        except (ValueError, AdmissionDenied):
            return JSONResponse({"state": "denied"}, status_code=403)

    app.add_middleware(
        AdmissionLimits,
        policy=AdmissionPolicy(
            lifecycle.invitations,
            maximum_bytes=1024,
            global_rate=240,
            maximum_requests=8,
            maximum_streams=1,
            browser_sessions=1,
        ),
    )
    return app
