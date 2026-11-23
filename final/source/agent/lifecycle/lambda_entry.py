"""Lazy fixed-role Lambda entry; runtime configuration never enters the ZIP."""

import json
import os
import re
from threading import Lock

from agent.lifecycle.controller import is_tick
from agent.lifecycle.lambda_runtime import (
    ControlSettings,
    create_controller_runtime,
    create_startup_runtime,
)
from agent.lifecycle.operating import OperatingPolicy

COMMON = {"version", "table", "namespace", "invitation_identity", "lifecycle_identity"}
ROLE_FIELDS = {
    "startup": {"origin", "controller_arn"},
    "controller": {"instance", "release"},
}


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


def _settings(role, environment):
    raw = environment.get("COPILOT_CONTROL_CONFIG")
    key = environment.get("COPILOT_READINESS_KEY_HEX")
    if type(raw) is not str or not 1 <= len(raw.encode("utf-8")) <= 3072:
        raise ValueError()
    value = json.loads(raw, object_pairs_hook=_pairs)
    version = value.get("version") if type(value) is dict else None
    if (
        type(value) is not dict
        or set(value) != COMMON | ROLE_FIELDS[role] | ({"operating"} if version == 2 else set())
        or type(value["version"]) is not int
        or value.pop("version") not in (1, 2)
    ):
        raise ValueError()
    if version == 2:
        value["operating"] = OperatingPolicy.parse(value["operating"])
    if role == "startup":
        if key is not None:
            raise ValueError()
    else:
        if type(key) is not str or re.fullmatch(r"[0-9a-f]{64,128}", key) is None or len(key) % 2:
            raise ValueError()
        value["readiness_secret"] = bytes.fromhex(key)
    return ControlSettings(role=role, **value)


def _unavailable(role):
    if role == "controller":
        return {"state": "unavailable"}
    return {
        "statusCode": 503,
        "headers": {
            "cache-control": "no-store",
            "content-type": "application/json",
            "x-content-type-options": "nosniff",
        },
        "body": '{"state":"unavailable"}',
        "isBase64Encoded": False,
    }


def make_entry(role, *, environment=None, factory=None):
    """One initialization attempt per execution environment, no import-time I/O."""
    if type(role) is not str or role not in ROLE_FIELDS:
        raise ValueError("Fixed Lambda role required")
    initialized, runtime, lock = False, None, Lock()

    def handler(event, context):
        nonlocal initialized, runtime
        try:
            with lock:
                if not initialized:
                    # Latch before any parse/factory work, including uncertain failure.
                    initialized = True
                    source = os.environ if environment is None else environment
                    settings = _settings(role, source)
                    creator = factory or (
                        create_startup_runtime if role == "startup" else create_controller_runtime
                    )
                    candidate = creator(settings)
                    if not callable(candidate):
                        raise ValueError()
                    runtime = candidate
            if runtime is not None:
                result = runtime(event, context)
                if not (
                    role == "controller" and is_tick(event) and result == {"state": "unavailable"}
                ):
                    return result
        except Exception:
            pass
        if role == "controller" and is_tick(event):
            raise RuntimeError("Scheduled observation unavailable") from None
        return _unavailable(role)

    return handler
