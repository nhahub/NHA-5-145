"""HTTP/SSE delivery adapter for session events; no task transition policy."""

import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic

import httpx
from fastapi import HTTPException, Request
from starlette.responses import StreamingResponse

from agent.session_state import EventType, SessionNotFound
from agent.sessions import SessionStore

# Every delivered event is re-authorized; an idle stream re-checks at this interval.
AUTHORITY_RECHECK_SECONDS = 5.0
_RESET = "event: shopper_reset\ndata: {}\n\n"


async def _authorized(request: Request) -> bool | None:
    """True or False from the authority check, None when it could not complete."""
    request.state.authority_unavailable = False
    try:
        authorized = await request.state.shopper_authorized()
    except httpx.HTTPError:
        return None
    if not authorized and getattr(request.state, "authority_unavailable", False):
        return None
    return authorized


def encode_sse(event_id: int, event: EventType, data: dict[str, object]) -> str:
    return f"id: {event_id}\nevent: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def session_event_response(
    sessions: SessionStore,
    session_id: str,
    request: Request,
    after: int = 0,
    once: bool = False,
    tab_id: str | None = None,
) -> StreamingResponse:
    try:
        sessions.get(session_id)
    except SessionNotFound as error:
        raise HTTPException(status_code=404, detail="Session not found") from error

    last_event_id = request.headers.get("last-event-id")
    if last_event_id is not None:
        if not last_event_id.isascii() or not last_event_id.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid event cursor")
        after = max(after, int(last_event_id))

    async def event_stream() -> AsyncIterator[str]:
        cursor = after
        next_heartbeat = 0.0
        next_authority_check = 0.0
        while True:
            try:
                pending = sessions.events_after(session_id, cursor)
            except SessionNotFound:
                yield _RESET
                return
            if pending or monotonic() >= next_authority_check:
                authorized = await _authorized(request)
                if authorized is None:
                    # Unverifiable is not revoked: close without reset so the browser
                    # reconnects from Last-Event-ID through the authorizing middleware.
                    return
                if not authorized:
                    yield _RESET
                    return
                next_authority_check = monotonic() + AUTHORITY_RECHECK_SECONDS
            if not pending and not once and monotonic() >= next_heartbeat:
                # SSE comments do not advance the cursor or touch shopper activity.
                yield ": keepalive\n\n"
                next_heartbeat = monotonic() + 10
            for event in pending:
                authorized = await _authorized(request)
                if authorized is None:
                    return
                if not authorized:
                    yield _RESET
                    return
                cursor = event.id
                try:
                    sessions.get(session_id)
                    if event.event == "action" and not sessions.owns_lease(session_id, tab_id):
                        continue
                except SessionNotFound:
                    yield _RESET
                    return
                yield encode_sse(event.id, event.event, event.data)
            if once or await request.is_disconnected():
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
