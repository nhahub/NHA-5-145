"""Inactive host proof helper and fixed-origin authenticated readiness probe."""

import hashlib
import hmac
import json
import re
import secrets
from time import monotonic

import httpx

URL = "https://app.scpilot.tech/health"


def _hex(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Exact proof field required")
    return value


def _config(secret, release, generation=None):
    if type(secret) is not bytes or not 32 <= len(secret) <= 64:
        raise ValueError("Restricted readiness key required")
    _hex(release)
    if generation is not None and (type(generation) is not int or not 1 <= generation <= 2**53 - 1):
        raise ValueError("Exact wake generation required")


def _mac(secret, direction, release, generation, nonce, ready=None):
    fields = [direction, release, str(generation), nonce]
    if ready is not None:
        fields.append("1" if ready else "0")
    return hmac.new(secret, "\n".join(fields).encode("ascii"), hashlib.sha256).hexdigest()


def readiness_reply(headers, *, secret, release, generation, ready):
    """Caller supplies trusted local generation/release and aggregate readiness."""
    _config(secret, release, generation)
    if generation is None or type(ready) is not bool:
        raise ValueError("Explicit trusted readiness required")
    try:
        nonce = _hex(headers.get("x-copilot-nonce"))
        proof = _hex(headers.get("x-copilot-proof"))
        if (
            headers.get("x-copilot-generation") != str(generation)
            or headers.get("x-copilot-release") != release
            or not hmac.compare_digest(proof, _mac(secret, "request", release, generation, nonce))
        ):
            raise ValueError("Readiness request refused")
    except Exception:
        raise ValueError("Readiness request refused") from None
    return {
        "generation": generation,
        "release": release,
        "nonce": nonce,
        "ready": ready,
        "mac": _mac(secret, "response", release, generation, nonce, ready),
    }


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate proof field")
        value[key] = item
    return value


class HTTPSReadinessProbe:
    def __init__(self, secret, release, *, transport=None):
        _config(secret, release)
        self._secret, self.release, self.transport = secret, release, transport

    def check(self, generation):
        try:
            _config(self._secret, self.release, generation)
            if generation is None:
                return False
            nonce = secrets.token_hex(32)
            headers = {
                "x-copilot-generation": str(generation),
                "x-copilot-release": self.release,
                "x-copilot-nonce": nonce,
                "x-copilot-proof": _mac(self._secret, "request", self.release, generation, nonce),
                "Accept-Encoding": "identity",
            }
            deadline = monotonic() + 2
            with (
                httpx.Client(
                    verify=True,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=2,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
                    transport=self.transport,
                ) as client,
                client.stream("GET", URL, headers=headers) as response,
            ):
                if (
                    response.status_code != 200
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    return False
                body = bytearray()
                for chunk in response.iter_raw():
                    if len(body) + len(chunk) > 1024 or monotonic() >= deadline:
                        return False
                    body.extend(chunk)
                value = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs)
            if (
                type(value) is not dict
                or set(value) != {"generation", "release", "nonce", "ready", "mac"}
                or type(value["generation"]) is not int
                or value["generation"] != generation
                or value["release"] != self.release
                or value["nonce"] != nonce
                or type(value["ready"]) is not bool
                or monotonic() >= deadline
            ):
                return False
            return (
                hmac.compare_digest(
                    _hex(value["mac"]),
                    _mac(self._secret, "response", self.release, generation, nonce, value["ready"]),
                )
                and value["ready"]
            )
        except Exception:
            return False
