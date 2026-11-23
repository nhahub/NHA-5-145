"""Structured event records that can never carry what the Shopper typed.

Every record is one JSON object. Each event has a fixed allow-list of fields, and
every value must be a number, a boolean, a value from a fixed set, or a short
token (ids, route templates, type names). Free text is rejected, so a later change
cannot leak Shopper words into the log by accident.

The one exception is debug records: free text (the Shopper's message, model output,
full error text) written only while the owner's debug switch is on, only to a sink
that keeps them on the host, and marked ``debug: true`` so they are never shipped.
"""

import hashlib
import json
import math
import os
import re
import stat
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

from starlette.routing import Match

from agent.llm.intent import Dialect, IntentName
from agent.schemas import Action, ActionResult
from agent.session_state import EventType, InterpretationPauseReason

TOKEN = re.compile(r"[A-Za-z0-9_.:/{}\-]{1,200}")
SESSION_ID = re.compile(r"session-[0-9a-f]{32}")
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OTHER"})


def _token(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def _session_id(value):
    return isinstance(value, str) and SESSION_ID.fullmatch(value) is not None


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_count(value) -> bool:
    return _int(value) and value >= 0


def is_cost(value) -> bool:
    """A finite, non-negative dollar amount."""
    number = isinstance(value, int | float) and not isinstance(value, bool)
    return number and math.isfinite(value) and value >= 0


TASK_ID = re.compile(r"task-[0-9a-f]{32}")
PLAN_ID = re.compile(r"plan-[0-9a-f]{32}")
SHOPPER = re.compile(r"[0-9a-f]{16}")
INVITATION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TASK_EVENTS = frozenset(get_args(EventType))
ACTION_TYPES = frozenset(
    get_args(variant.model_fields["type"].annotation)[0]
    for variant in get_args(get_args(Action)[0])
)
INTENTS = frozenset(get_args(IntentName))
DIALECTS = frozenset(get_args(Dialect))
# Interpretation failures, plus pauses the task engine makes on its own.
PAUSE_REASONS = frozenset(get_args(InterpretationPauseReason)) | {
    "refresh",
    "cart_navigation_failed",
    "cart_edit_unavailable",
    "guarded_control_missing",
    "swap_remove_failed",
}
# Why one catalogue decision was rejected. A closed set: never the error text.
REJECTION_CODES = frozenset(
    {
        "decision_schema",  # the model's search/details/recommend/execute/clarify JSON
        "final_schema",  # the last decision, restricted to recommend or clarify
        "intent_schema",  # the action interpreter's intent JSON, or a recommend's intent
        "model_response",  # tool call, oversize or incomplete model output
        "query_invalid",  # a read query that cannot be built or revalidated
        "incomplete_evidence",
        "unknowns_omitted",
        "evidence_too_large",
        "blank_advice",
        "selection_before_read",
        "ids_not_retrieved",
        "duplicate_ids",
        "action_with_cards",
        "product_gone",
        "evidence_changed",
        "missing_execution_field",
        "unsupported_currency",
        "unsupported_catalogue_value",
        "unknown_destination",
        "unknown_product",
        "cart_edit_invalid",
        "mutation_invalid",
        "source_not_in_message",
        "undo_without_button",  # an undo reading while no enabled Undo control was visible
        "unsupported_reading",  # a reading of "unsupported", refused once for a repair
        "this_mismatch",  # "this" named a product that code did not allow
        "execute_after_handoff",  # execute chosen again after the interpreter handed back
        "action_in_advice",  # a recommend that carried a cart/checkout target, not execute
        "unknown_filter_value",  # a filter value that names no Storefront vocabulary key
        "repeated_empty_search",  # the same search as an earlier read that found nothing
        "other",
    }
)
MAX_REJECTIONS = 3
ROUTE = re.compile(r"[A-Za-z0-9_.\-]{1,40}")
RESULT_STATUSES = frozenset(get_args(ActionResult.model_fields["status"].annotation))


def _matches(pattern):
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


def _one_of(values):
    return lambda value: value in values


def shopper_tag(binding) -> str | None:
    """A short scrambled id that groups one Shopper's records without identifying them."""
    if binding is None:
        return None
    return hashlib.sha256(b"event-log:" + binding.context.encode()).hexdigest()[:16]


_SEQUENCE = is_count
_LANGUAGE = _one_of({"ar", "en"})

_TASK_CONTEXT = {
    "session_id": lambda v: _session_id(v),
    "task_id": _matches(TASK_ID),
    "shopper": _matches(SHOPPER),
    "invitation_id": _matches(INVITATION_ID),
}

EVENTS: dict[str, dict[str, Callable[[Any], bool]]] = {
    "task": {
        **_TASK_CONTEXT,
        "kind": _one_of(TASK_EVENTS),
        "action_type": _one_of(ACTION_TYPES),
        "sequence": _SEQUENCE,
        "question_kind": _one_of({"confirmation", "question"}),
        "language": _LANGUAGE,
    },
    "intent": {
        **_TASK_CONTEXT,
        "intent": _one_of(INTENTS),
        "language": _LANGUAGE,
        "dialect": _one_of(DIALECTS),
        "needs_clarification": lambda v: isinstance(v, bool),
    },
    "confirmation": {
        **_TASK_CONTEXT,
        "outcome": _one_of(
            {"consumed", "stopped", "stale", "expired", "unregistered", "invalidated"}
        ),
        "mutation_kind": _one_of({"clear_cart", "submit_checkout"}),
    },
    # Plans: identifiers, positions, types, outcomes and counts only; never step text.
    "plan_created": {
        **_TASK_CONTEXT,
        "plan_id": _matches(PLAN_ID),
        "step_count": is_count,
        "skipped_count": is_count,
        "language": _LANGUAGE,
        "dialect": _one_of(DIALECTS),
    },
    "plan_step": {
        **_TASK_CONTEXT,
        "plan_id": _matches(PLAN_ID),
        "position": is_count,
        "outcome": _one_of({"done", "failed", "skipped"}),
        "intent_type": _one_of(INTENTS),
        "guarded": lambda v: isinstance(v, bool),
    },
    "plan_finished": {
        **_TASK_CONTEXT,
        "plan_id": _matches(PLAN_ID),
        "outcome": _one_of({"done", "failed", "cancelled"}),
        "done_count": is_count,
        "failed_count": is_count,
        "skipped_count": is_count,
    },
    "plan_cancelled": {
        **_TASK_CONTEXT,
        "plan_id": _matches(PLAN_ID),
        "reason": _one_of({"stop", "new_request", "takeover"}),
    },
    "model_call": {
        **_TASK_CONTEXT,
        "provider": _token,
        "model": _token,
        "prompt_version": _token,
        "schema_version": _SEQUENCE,
        "latency_ms": _SEQUENCE,
        "outcome": _one_of({"ok", "failed"}),
        "failure": _one_of(PAUSE_REASONS),
        "prompt_tokens": _SEQUENCE,
        "completion_tokens": _SEQUENCE,
        "cost_usd": is_cost,
        "attempt_id": _token,
        "route": _matches(ROUTE),
    },
    "retrieval_turn": {
        **_TASK_CONTEXT,
        "outcome": _one_of(
            {"recommend", "best_found", "clarify", "execute", "exhausted", "failed"}
        ),
        "decisions": _SEQUENCE,
        "reads": _SEQUENCE,
        "advice": _SEQUENCE,
        "rejections": lambda v: (
            isinstance(v, list)
            and len(v) <= MAX_REJECTIONS
            and all(isinstance(code, str) and code in REJECTION_CODES for code in v)
        ),
    },
    "error": {
        **_TASK_CONTEXT,
        "error_type": _token,
        "location": _token,
    },
    "task_paused": {
        **_TASK_CONTEXT,
        "reason": _one_of(PAUSE_REASONS),
    },
    "action_result": {
        **_TASK_CONTEXT,
        "action_type": _one_of(ACTION_TYPES),
        "sequence": _SEQUENCE,
        "status": _one_of(RESULT_STATUSES),
    },
    "http_request": {
        "method": lambda v: v in METHODS,
        "route": _token,
        "status": _int,
        "duration_ms": lambda v: _int(v) and v >= 0,
        "session_id": _session_id,
    },
}


class MemorySink:
    """Keeps records in memory; for tests."""

    keeps_debug_local = True

    def __init__(self):
        self.records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self.records.append(record)


class StreamSink:
    """Writes one JSON line per record to a text stream (the terminal by default)."""

    keeps_debug_local = False  # a terminal can be shared or captured; debug text never goes here

    def __init__(self, stream=None):
        self.stream = stream

    def write(self, record: dict[str, Any]) -> None:
        stream = self.stream if self.stream is not None else sys.stderr
        stream.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        stream.flush()


DEBUG_KINDS = frozenset({"shopper_message", "model_output", "error_detail", "retrieval_rejection"})
DEBUG_TEXT_LIMIT = 8000
DEBUG_WINDOW_SECONDS = 60 * 60


class DebugSwitch:
    """Owner-only, time-limited permission to record free text while chasing one bug.

    The switch is a marker file in a folder the Agent can read but not write, owned by
    ``owner`` (root on the host), so the Agent itself can never turn it on. It is on
    while the marker was touched less than an hour ago and not in the future, so it
    turns itself off. The file is checked through a descriptor like the host's other
    private files: no symlink, a single link, a regular file, and nobody else may write
    it or its folder. ``owner=None`` skips the owner check, for tests and laptops.
    """

    def __init__(
        self, marker, *, owner: int | None = 0, window_seconds: int = DEBUG_WINDOW_SECONDS
    ):
        self.marker = Path(marker)
        self.owner = owner
        self.window_seconds = window_seconds

    def active(self) -> bool:
        try:
            info = self._checked_info()
        except OSError:
            return False
        if info is None:
            return False
        return 0 <= time.time() - info.st_mtime < self.window_seconds

    def _checked_info(self):
        if self.marker.is_symlink():
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(self.marker, flags)
        try:
            info = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            return None
        if os.name != "posix":
            return info
        folder = self.marker.parent.lstat()
        owner_ok = self.owner is None or (
            info.st_uid == self.owner and folder.st_uid in {0, self.owner}
        )
        safe = (
            owner_ok
            and not info.st_mode & 0o022
            and stat.S_ISDIR(folder.st_mode)
            and not folder.st_mode & 0o022
        )
        return info if safe else None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class EventLog:
    def __init__(self, sink, *, release: str = "local", debug: DebugSwitch | None = None):
        if not _token(release):
            raise ValueError("Release id must be a token")
        self.sink = sink
        self.release = release
        self.debug = debug
        self.failures = 0

    def emit(self, event: str, **fields: Any) -> None:
        allowed = EVENTS.get(event)
        if allowed is None:
            raise ValueError(f"Unknown event: {event}")
        for name, value in fields.items():
            check = allowed.get(name)
            if check is None:
                raise ValueError(f"Field {name} is not allowed on {event}")
            if value is not None and not check(value):
                raise ValueError(f"Field {name} on {event} is not an allowed value")
        self._write(
            {
                "time": _now(),
                "release": self.release,
                "event": event,
                **{name: value for name, value in fields.items() if value is not None},
            }
        )

    def emit_debug(self, kind: str, text: str, **context: Any) -> None:
        """Record free text, only while the debug switch is on and only to a local sink.

        Debug records are marked ``debug: true`` so nothing ever ships them off the host.
        """
        if (
            self.debug is None
            or kind not in DEBUG_KINDS
            or not getattr(self.sink, "keeps_debug_local", False)
            or not self.debug.active()
        ):
            return
        for name, value in context.items():
            check = _TASK_CONTEXT.get(name)
            if check is None or (value is not None and not check(value)):
                raise ValueError(f"Field {name} is not allowed on a debug record")
        self._write(
            {
                "time": _now(),
                "release": self.release,
                "event": "debug",
                "debug": True,
                "kind": kind,
                "text": str(text)[:DEBUG_TEXT_LIMIT],
                **{name: value for name, value in context.items() if value is not None},
            }
        )

    def emit_error(self, error: BaseException, **context: Any) -> None:
        """Record an error by type and place; its full text only as a debug record."""
        self.emit(
            "error", error_type=type(error).__name__, location=error_location(error), **context
        )
        self.emit_debug("error_detail", f"{type(error).__name__}: {error}", **context)

    def _write(self, record: dict[str, Any]) -> None:
        try:
            self.sink.write(record)
        except Exception:
            # Logging must never fail or slow the request it describes.
            self.failures += 1


# Fixed paths the Shopper middleware answers itself, before routing.
_FIXED_PATHS = frozenset(
    {"/shopper/bootstrap", "/shopper/challenge", "/shopper/link", "/shopper/admission"}
)
# Liveness and keep-alive traffic that would bury the useful records.
_NOISE = frozenset({"/health", "/shopper/activity"})


class RequestLog:
    """ASGI middleware recording one http_request per completed request."""

    def __init__(self, app, events: EventLog, routes=()):
        self.app = app
        self.events = events
        # Requests rejected before routing still name the endpoint they targeted.
        self.routes = routes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in _NOISE or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        status = 499  # client went away before any response started
        started = time.monotonic()

        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        except Exception as error:
            session_id = scope.get("path_params", {}).get("session_id")
            try:
                self.events.emit_error(
                    error, session_id=session_id if _session_id(session_id) else None
                )
            except Exception:
                self.events.failures += 1
            raise
        finally:
            try:
                template, params = self._route(scope)
                session_id = params.get("session_id")
                self.events.emit(
                    "http_request",
                    method=scope["method"] if scope["method"] in METHODS else "OTHER",
                    route=template if _token(template) else "unmatched",
                    status=status,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    session_id=session_id if _session_id(session_id) else None,
                )
            except Exception:
                # Logging must never fail or slow the request it describes.
                self.events.failures += 1

    def _route(self, scope):
        route = scope.get("route")
        if route is not None:
            return route.path, scope.get("path_params", {})
        if scope["path"] in _FIXED_PATHS:
            return scope["path"], {}
        for candidate in self.routes:
            match, child = candidate.matches(scope)
            if match is not Match.NONE:
                return candidate.path, child.get("path_params", {})
        return "unmatched", {}


# The session and task a piece of work belongs to, so records made deep inside a
# turn (model calls, retrieval) are tied to it without threading ids through.
_scope: ContextVar[tuple[EventLog, dict[str, Any]] | None] = ContextVar("event_scope", default=None)


@contextmanager
def bind(events: EventLog | None, **context: Any):
    token = _scope.set(None if events is None else (events, context))
    try:
        yield
    finally:
        _scope.reset(token)


def record(event: str, **fields: Any) -> None:
    """Emit a record in the current scope; a no-op outside one, never raises."""
    scope = _scope.get()
    if scope is None:
        return
    events, context = scope
    try:
        events.emit(event, **context, **fields)
    except Exception:
        events.failures += 1


_ROOT = Path(__file__).resolve().parents[1]


def error_location(error: BaseException) -> str:
    """Where an error was raised in this project's code, as ``path:function``; never its text."""
    frame, chosen = error.__traceback__, None
    while frame is not None:
        path = Path(frame.tb_frame.f_code.co_filename)
        if path.is_absolute() and path.resolve().is_relative_to(_ROOT):
            chosen = frame
        frame = frame.tb_next
    if chosen is None:
        return "unknown"
    code = chosen.tb_frame.f_code
    relative = Path(code.co_filename).resolve().relative_to(_ROOT).as_posix()
    location = f"{relative}:{code.co_name}"
    return location if _token(location) else "unknown"


def debug_text(kind: str, text: str) -> None:
    """Record free text in the current scope while the debug switch is on; never raises."""
    scope = _scope.get()
    if scope is None:
        return
    events, context = scope
    try:
        events.emit_debug(kind, text, **context)
    except Exception:
        events.failures += 1


def record_error(error: BaseException) -> None:
    """Record an error in the current scope; never raises."""
    scope = _scope.get()
    if scope is None:
        return
    events, context = scope
    try:
        events.emit_error(error, **context)
    except Exception:
        events.failures += 1
