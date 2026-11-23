"""Offline-prepared HTTP-v2 adapter; deployment must enforce IAM/OAC externally."""

import base64
import json
import re
import secrets
from pathlib import Path
from time import time

from agent.admission.dynamodb import _count, _encode, _number
from agent.admission.store import AdmissionDenied
from agent.lifecycle.dynamodb import STATES
from agent.lifecycle.store import LifecycleUnavailable

LIMITS = {"http": 240, "wake": 10, "poll": 120}


class DynamoStartupRates:
    def __init__(self, invitations, *, clock=time):
        self.invitations, self.clock = invitations, clock

    def rate(self, lane):
        try:
            if type(lane) is not str or lane not in LIMITS:
                raise ValueError("Fixed rate lane required")
            limit = LIMITS[lane]
            store = self.invitations
            store._configuration(store.client, store.table, store.namespace)
            store._metadata()
            metadata = store._read("meta")
            marker = "startup_" + lane
            now = _number(self.clock())
            minute = _count(now // 60, 2**53 - 1)
            key = "startup-rate#" + lane
            before = store._read(key)
            count = 0
            if before is None:
                if marker in metadata:
                    raise ValueError("Deleted rate authority cannot be reset")
                condition = "attribute_not_exists(pk)"
                names, values = {}, {}
                guard = store._condition(
                    "meta",
                    f"#schema=:schema AND #identity=:identity AND attribute_not_exists(#{marker})",
                    {":schema": 1, ":identity": store.identity, ":yes": True},
                    update=f"SET #{marker}=:yes",
                )
            else:
                if (
                    metadata.get(marker) is not True
                    or set(before)
                    != {"pk", "sk", "schema", "identity", "minute", "count", "observed"}
                    or before["identity"] != store.identity
                ):
                    raise ValueError("Invalid rate authority")
                _count(before["schema"], 1, minimum=1)
                previous = _count(before["minute"], 2**53 - 1)
                used = _count(before["count"], limit, minimum=1)
                observed = _number(before["observed"])
                if not previous * 60 <= observed < (previous + 1) * 60 or now < observed:
                    raise ValueError("Invalid or backward rate time")
                count = used if minute == previous else 0
                condition = (
                    "#schema=:schema AND #identity=:identity AND #minute=:minute "
                    "AND #count=:count AND #observed=:observed"
                )
                names = {
                    "#" + key: key for key in ("schema", "identity", "minute", "count", "observed")
                }
                values = _encode({":" + key: before[key] for key in names.values()})
                guard = store._meta_condition()
            if count >= limit:
                raise ValueError("Rate exhausted")
            put = {
                "TableName": store.table,
                "Item": _encode(
                    {
                        "pk": store.namespace,
                        "sk": key,
                        "schema": 1,
                        "identity": store.identity,
                        "minute": minute,
                        "count": count + 1,
                        "observed": now,
                    }
                ),
                "ConditionExpression": condition,
            }
            if names:
                put.update(ExpressionAttributeNames=names, ExpressionAttributeValues=values)
            store._write([guard, {"Put": put}])
        except Exception:
            raise LifecycleUnavailable() from None


def _transport(event):
    if type(event) is not dict or event.get("version") != "2.0":
        raise ValueError("HTTP v2 required")
    http = event.get("requestContext", {}).get("http", {})
    path, method = event.get("rawPath"), http.get("method")
    headers = event.get("headers")
    if (
        type(path) is not str
        or len(path) > 128
        or type(method) is not str
        or len(method) > 16
        or http.get("path") != path
        or event.get("rawQueryString") != ""
        or event.get("queryStringParameters") not in (None, {})
        or event.get("cookies")
        or type(headers) is not dict
        or len(headers) > 64
    ):
        raise ValueError("Bounded transport required")
    size = 0
    for key, value in headers.items():
        if (
            type(key) is not str
            or re.fullmatch(r"[a-z0-9-]{1,64}", key) is None
            or type(value) is not str
            or any(ord(char) < 32 or ord(char) > 126 for char in value)
        ):
            raise ValueError("Unambiguous headers required")
        size += len(key) + len(value)
    if size > 4096:
        raise ValueError("Headers too large")
    body = event.get("body")
    encoded = event.get("isBase64Encoded", False)
    if type(encoded) is not bool or body is not None and type(body) is not str:
        raise ValueError("Invalid body encoding")
    body = body or ""
    if len(body) > 1368:
        raise ValueError("Body too large")
    raw = base64.b64decode(body, validate=True) if encoded else body.encode("utf-8")
    if len(raw) > 1024 or method == "GET" and raw:
        raise ValueError("Body too large or unexpected")
    return path, method, headers, raw.decode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _view(value):
    if type(value) is not dict or set(value) != {
        "state",
        "generation",
        "remaining_seconds",
        "retry_after",
    }:
        raise LifecycleUnavailable()
    if (
        type(value["state"]) is not str
        or value["state"] not in STATES
        or any(
            type(value[key]) is not int
            for key in ("generation", "remaining_seconds", "retry_after")
        )
        or not 0 <= value["generation"] <= 2**53 - 1
        or not 0 <= value["remaining_seconds"] <= 300
        or value["retry_after"] not in {5, 60}
    ):
        raise LifecycleUnavailable()
    return value


def create_startup_handler(lifecycle, rates, *, origin, notify=None):
    if (
        type(origin) is not str
        or re.fullmatch(r"https://[a-z0-9]{1,63}\.cloudfront\.net", origin) is None
    ):
        raise ValueError("Exact generated CloudFront HTTPS origin required")
    template = Path(__file__).with_name("waiting.html").read_text(encoding="utf-8")
    template = template.replace("http://localhost:4100/", "https://app.scpilot.tech/")

    def response(code, payload, *, html=False, extra=None):
        return {
            "statusCode": code,
            "headers": {
                "Content-Type": "text/html; charset=utf-8" if html else "application/json",
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Retry-After": "5",
                **(extra or {}),
            },
            "body": payload if html else json.dumps(payload, separators=(",", ":")),
        }

    def handler(event, context):
        try:
            path, method, headers, body = _transport(event)
        except Exception:
            return response(400, {"state": "denied"})
        try:
            rates.rate("http")
            if (path, method) == ("/", "GET"):
                nonce = secrets.token_urlsafe(24)
                return response(
                    200,
                    template.replace("NONCE", nonce),
                    html=True,
                    extra={
                        "Content-Security-Policy": (
                            "default-src 'none'; connect-src 'self'; form-action 'self'; "
                            f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                            "frame-ancestors 'none'; base-uri 'none'"
                        )
                    },
                )
            if (path, method) == ("/status", "GET"):
                rates.rate("poll")
                view = _view(lifecycle.status())
                if notify is not None and view["generation"] > 0 and view["state"] != "stopped":
                    notify("observe", view["generation"])
                return response(200, view)
            if (path, method) != ("/wake", "POST"):
                return response(404, {"state": "denied"})
            rates.rate("wake")
            if headers.get("origin") != origin or headers.get("content-type") != "application/json":
                return response(403, {"state": "denied"})
            try:
                payload = json.loads(body, object_pairs_hook=_pairs)
                if type(payload) is not dict or set(payload) != {"code"}:
                    raise ValueError("Exact code object required")
                lifecycle.invitations.wake_invitation(payload["code"])
                view = lifecycle.wake(payload["code"])
            except AdmissionDenied as error:
                if error.reason == "access_unavailable":
                    return response(503, {"state": "unavailable"})
                return response(403, {"state": "denied"})
            except ValueError:
                return response(403, {"state": "denied"})
            view = _view(view)
            if notify is not None:
                notify("dispatch", view["generation"])
            return response(202, view)
        except Exception:
            return response(503, {"state": "unavailable"})

    return handler
