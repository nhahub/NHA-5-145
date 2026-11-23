"""HTTP authority boundary shared by all Agent routes, including streaming delivery."""

import secrets

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from agent.admission.limits import AdmissionLimits, denied, is_owner_stop
from agent.admission.store import AdmissionDenied
from agent.async_boundary import invoke
from agent.lifecycle.store import LifecycleUnavailable
from agent.session_state import SessionExpired, SessionNotFound
from agent.sessions import SessionStore
from agent.shopper_access import ShopperAccess
from agent.storefront_service import StorefrontService


def install_shopper_http(
    app: FastAPI,
    sessions: SessionStore,
    service: StorefrontService,
    *,
    panel_origin: str,
    evaluation: bool,
    admission=None,
    lifecycle_work=None,
) -> None:
    access = ShopperAccess()
    app.state.shopper_access = access
    app.state.storefront_service = service
    app.state.lifecycle_work = lifecycle_work

    async def alive(record) -> bool:
        if record.shopper is None:
            return False
        try:
            return await app.state.storefront_service.validate(record.shopper)
        except Exception:
            return False

    @app.middleware("http")
    async def authorize(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path == "/health":
            return await call_next(request)
        if (path.startswith("/__test/") or path == "/step") and not evaluation:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        cookie_values = [
            part.strip().split("=", 1)[1]
            for part in request.headers.get("cookie", "").split(";")
            if part.strip().startswith("copilot_agent=")
        ]
        credential = cookie_values[0] if len(cookie_values) == 1 else ""
        record = access.resolve(credential)
        if admission is not None and record is not None:
            try:
                admission.browser_request(record, stop=is_owner_stop(request.method, path))
            except AdmissionDenied:
                return denied("access_busy", 429)
        new_cookie = None
        if path == "/shopper/bootstrap" and request.method == "POST":
            if request.headers.get("origin") != panel_origin:
                return JSONResponse({"detail": "Invalid origin"}, status_code=403)
            if record is None:
                try:
                    new_cookie, record = access.create()
                except OverflowError:
                    return JSONResponse({"detail": "Capacity reached"}, status_code=503)
            result = JSONResponse({"csrf": record.csrf})
            if new_cookie:
                result.set_cookie(
                    "copilot_agent",
                    new_cookie,
                    httponly=True,
                    secure=panel_origin.startswith("https:"),
                    samesite="strict",
                    path="/",
                )
            result.headers["Cache-Control"] = "no-store"
            return result
        if record is None:
            return JSONResponse({"detail": "Shopper identity required"}, status_code=401)
        if request.method not in {"GET", "HEAD"} and (
            request.headers.get("origin") != panel_origin
            or not secrets.compare_digest(request.headers.get("x-csrf-token", ""), record.csrf)
        ):
            return JSONResponse({"detail": "Invalid browser authority"}, status_code=403)
        if path == "/shopper/challenge" and request.method == "POST":
            try:
                result = JSONResponse({"challenge": access.challenge(record)})
            except OverflowError:
                return JSONResponse({"detail": "Too many pending links"}, status_code=429)
            result.headers["Cache-Control"] = "no-store"
            return result
        if path == "/shopper/link" and request.method == "POST":
            try:
                payload = await request.json()
                challenge, ticket = payload["challenge"], payload["ticket"]
                if (
                    not isinstance(challenge, str)
                    or not isinstance(ticket, str)
                    or len(ticket) != 64
                ):
                    raise ValueError()
                if not access.consume_challenge(record, challenge):
                    raise ValueError()
                binding = await app.state.storefront_service.redeem(ticket, challenge)
                if record.shopper is not None and record.shopper != binding:
                    # A changed Storefront identity requires discarding old task references.
                    record.sessions.clear()
                    record.shopper = None
                    result = JSONResponse(
                        {"detail": "Storefront reset; reload to link again"}, status_code=409
                    )
                else:
                    record.shopper = binding
                    result = JSONResponse({"linked": True, "shopper_context": binding.context})
            except Exception:
                result = JSONResponse({"detail": "Shopper linking failed"}, status_code=409)
            result.headers["Cache-Control"] = "no-store"
            return result
        bound_shopper = record.shopper
        if not await alive(record) or record.shopper != bound_shopper:
            return JSONResponse(
                {"detail": "Storefront identity expired or unavailable"}, status_code=401
            )
        if path == "/shopper/admission":
            if request.method == "POST" and admission is not None:
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise AdmissionDenied()
                    await invoke(admission, "redeem", record, payload.get("code"))
                except (ValueError, AdmissionDenied):
                    return denied("access_required")
            elif request.method != "GET":
                return JSONResponse({"detail": "Method not allowed"}, status_code=405)
            return JSONResponse(
                {
                    "required": admission is not None,
                    "admitted": admission is None or await invoke(admission, "allowed", record),
                },
                headers={"Cache-Control": "no-store"},
            )
        if (
            admission is not None
            and not is_owner_stop(request.method, path)
            and not await invoke(admission, "allowed", record)
        ):
            return denied("access_required")
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "sessions":
            if parts[1] not in record.sessions and sessions.adopt(parts[1], record.shopper):
                # A Session this process restored after a restart: its stored owner binding
                # proves it is this Shopper's.
                record.sessions.add(parts[1])
            if parts[1] not in record.sessions:
                return JSONResponse({"detail": "Session not found"}, status_code=404)
            try:
                session = sessions.get(parts[1])
                if session.shopper != record.shopper or parts[1] not in record.sessions:
                    raise SessionNotFound(parts[1])
            except SessionExpired:
                return JSONResponse({"detail": "Session expired"}, status_code=410)
            except SessionNotFound:
                return JSONResponse({"detail": "Session not found"}, status_code=404)
        access.resolve(credential, touch=True)
        request.state.shopper = record.shopper
        request.state.browser_authority = record

        async def lifecycle_authorized():
            if lifecycle_work is not None:
                try:
                    await invoke(lifecycle_work, "check")
                except LifecycleUnavailable:
                    # Not a revocation: an event stream closes without shopper_reset
                    # and its reconnect is re-authorized by this middleware.
                    request.state.authority_unavailable = True
                    return False
            return True

        async def still_authorized():
            if not await lifecycle_authorized():
                return False
            if access.resolve(credential) is not record or record.shopper != bound_shopper:
                return False
            if admission is not None and not await invoke(admission, "allowed", record):
                return False
            valid = await alive(record)
            return (
                valid
                and access.resolve(credential) is record
                and record.shopper == bound_shopper
                and (admission is None or await invoke(admission, "allowed", record))
                and await lifecycle_authorized()
                and access.resolve(credential) is record
                and record.shopper == bound_shopper
            )

        request.state.shopper_authorized = still_authorized
        token = None
        meaningful = False
        try:
            if lifecycle_work is not None and not is_owner_stop(request.method, path):
                await invoke(lifecycle_work, "check")
                if request.method == "POST":
                    token = await invoke(lifecycle_work, "begin")
            if access.resolve(credential) is not record or record.shopper != bound_shopper:
                return JSONResponse(
                    {"detail": "Shopper identity changed"},
                    status_code=409,
                    headers={"Cache-Control": "no-store"},
                )
            if len(parts) >= 2 and parts[0] == "sessions" and parts[1] not in record.sessions:
                return JSONResponse(
                    {"detail": "Session not found"},
                    status_code=404,
                    headers={"Cache-Control": "no-store"},
                )
            response = await call_next(request)
            meaningful = (
                request.method == "POST"
                and response.status_code < 300
                and (
                    path == "/shopper/activity"
                    or path == "/sessions"
                    or path.endswith(("/messages", "/answers", "/retry"))
                )
            )
        except LifecycleUnavailable:
            response = denied("demo_waiting", 503)
        finally:
            if token is not None:
                try:
                    await invoke(lifecycle_work, "finish", token, meaningful=meaningful)
                except LifecycleUnavailable:
                    response = denied("demo_waiting", 503)
        response.headers["Cache-Control"] = "no-store"
        return response

    if admission is not None:
        app.add_middleware(AdmissionLimits, policy=admission)
