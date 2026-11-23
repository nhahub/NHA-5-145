"""Bounded TCP questions to the four pinned authoritative servers; no shell."""

import ipaddress
import secrets
import socket
import struct
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import httpx

NAMES = ("app.scpilot.tech", "store.scpilot.tech")
KINDS = (1, 28, 5)


def question(identity, name, kind):
    if (
        type(identity) is not int
        or not 0 <= identity <= 65535
        or name not in NAMES
        or kind not in KINDS
    ):
        raise ValueError("Fixed public DNS question required")
    labels = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.split("."))
    return (
        struct.pack("!6H", identity, 0, 1, 0, 0, 0) + labels + b"\0" + struct.pack("!2H", kind, 1)
    )


def empty_answer(response, query):
    try:
        identity, flags, questions, answers, _, _ = struct.unpack("!6H", response[:12])
        return (
            12 <= len(query) <= len(response) <= 8192
            and identity == struct.unpack("!H", query[:2])[0]
            and flags & 0x8000 != 0
            and flags & 0x0400 != 0
            and flags & 0x0200 == 0
            and flags & 0x000F in {0, 3}
            and questions == 1
            and answers == 0
            and response[12 : len(query)] == query[12:]
        )
    except (ValueError, TypeError, struct.error):
        return False


def _read(sock, count, deadline):
    result = bytearray()
    while len(result) < count:
        left = deadline - monotonic()
        if left <= 0:
            raise TimeoutError("DNS deadline")
        sock.settimeout(left)
        chunk = sock.recv(count - len(result))
        if not chunk:
            raise OSError("Incomplete DNS response")
        result.extend(chunk)
    return bytes(result)


def _exchange(ip, name, kind):
    ipaddress.IPv4Address(ip)
    wire = question(secrets.randbelow(65536), name, kind)
    deadline = monotonic() + 2
    with socket.create_connection((ip, 53), timeout=1) as sock:
        sock.settimeout(max(0.001, deadline - monotonic()))
        sock.sendall(struct.pack("!H", len(wire)) + wire)
        length = struct.unpack("!H", _read(sock, 2, deadline))[0]
        if not 12 <= length <= 8192:
            return False
        return empty_answer(_read(sock, length, deadline), wire)


def _delegation():
    # A separate recursive observation detects a changed registrar delegation.
    # Authoritative absence itself is established by the direct TCP checks.
    with httpx.Client(timeout=2, follow_redirects=False, trust_env=False) as client:
        response = client.get(
            "https://dns.google/resolve", params={"name": "scpilot.tech", "type": "NS"}
        )
        response.raise_for_status()
        if len(response.content) > 8192:
            raise ValueError("Bounded DNS delegation required")
        value = response.json()
        if value.get("Status") != 0:
            raise ValueError("Delegation unavailable")
        rows = value.get("Answer")
        if type(rows) is not list or len(rows) != 4:
            raise ValueError("Exact four-server delegation required")
        result = set()
        for row in rows:
            if row.get("type") != 2 or row.get("name", "").rstrip(".").lower() != "scpilot.tech":
                raise ValueError("Unexpected delegation")
            result.add(row["data"].rstrip(".").lower())
        return result


def authoritative_absence(servers, *, exchange=_exchange, delegation=_delegation):
    try:
        if type(servers) is not tuple or len(servers) != 4 or len(set(servers)) != 4:
            return False
        if delegation() != {name for name, _ in servers}:
            return False

        def probe(item):
            ip, name, kind = item
            try:
                return exchange(ip, name, kind) is True
            except Exception:
                return False

        queries = [(ip, name, kind) for _, ip in servers for name in NAMES for kind in KINDS]
        with ThreadPoolExecutor(max_workers=4) as pool:
            return all(list(pool.map(probe, queries)))
    except Exception:
        return False
