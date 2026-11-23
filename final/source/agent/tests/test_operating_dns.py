"""Portable authoritative DNS absence: exact wire questions, no public lookups."""

import importlib
import importlib.util
import struct

import pytest


def module():
    if importlib.util.find_spec("agent.lifecycle.operating_dns") is None:
        pytest.fail("Portable authoritative DNS proof is not implemented")
    return importlib.import_module("agent.lifecycle.operating_dns")


def test_authoritative_response_requires_exact_question_no_answers_and_aa():
    m = module()
    query = m.question(123, "app.scpilot.tech", 1)
    good = struct.pack("!6H", 123, 0x8400, 1, 0, 0, 0) + query[12:]
    assert m.empty_answer(good, query) is True
    for response in (
        struct.pack("!6H", 124, 0x8400, 1, 0, 0, 0) + query[12:],
        struct.pack("!6H", 123, 0x8000, 1, 0, 0, 0) + query[12:],
        struct.pack("!6H", 123, 0x8402, 1, 0, 0, 0) + query[12:],
        struct.pack("!6H", 123, 0x8400, 1, 1, 0, 0) + query[12:],
        struct.pack("!6H", 123, 0x8400, 1, 0, 0, 0) + m.question(123, "store.scpilot.tech", 1)[12:],
        b"truncated",
    ):
        assert m.empty_answer(response, query) is False


def test_absence_requires_all_24_queries_and_unchanged_four_server_delegation():
    m = module()
    servers = tuple((f"ns{i}.example.net", f"192.0.2.{i}") for i in range(1, 5))
    calls = []

    def exchange(ip, name, kind):
        calls.append((ip, name, kind))
        return True

    assert (
        m.authoritative_absence(
            servers, exchange=exchange, delegation=lambda: {x[0] for x in servers}
        )
        is True
    )
    assert len(calls) == 24 and len(set(calls)) == 24
    assert (
        m.authoritative_absence(
            servers, exchange=exchange, delegation=lambda: {"other.example.net"}
        )
        is False
    )


def test_any_positive_or_unknown_dns_answer_blocks_release():
    m = module()
    servers = tuple((f"ns{i}.example.net", f"192.0.2.{i}") for i in range(1, 5))

    def exchange(ip, name, kind):
        if ip == "192.0.2.3" and name == "app.scpilot.tech" and kind == 5:
            raise TimeoutError("no absence proof")
        return True

    assert (
        m.authoritative_absence(
            servers, exchange=exchange, delegation=lambda: {x[0] for x in servers}
        )
        is False
    )
