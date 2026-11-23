"""Generated Lambda entry configuration; no live SDK or credential access."""

import importlib
import json
from concurrent.futures import ThreadPoolExecutor

import boto3
import pytest

from agent.lifecycle.lambda_entry import make_entry


def configuration(role="startup"):
    value = {
        "version": 1,
        "table": "demo-table",
        "namespace": "demo",
        "invitation_identity": "00000000-0000-4000-8000-000000000001",
        "lifecycle_identity": "00000000-0000-4000-8000-000000000002",
    }
    if role == "startup":
        value.update(
            origin="https://example.cloudfront.net",
            controller_arn="arn:aws:lambda:eu-north-1:123456789012:function:controller",
        )
    else:
        value.update(instance="i-0123456789abcdef0", release="a" * 64)
    return value


def environment(role="startup"):
    result = {"COPILOT_CONTROL_CONFIG": json.dumps(configuration(role))}
    if role == "controller":
        result["COPILOT_READINESS_KEY_HEX"] = "ab" * 32
    return result


def test_import_and_creation_have_no_sdk_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("SDK construction during import")

    monkeypatch.setattr(boto3, "client", forbidden)
    module = importlib.import_module("agent.lifecycle.lambda_entry")
    importlib.reload(module)
    module.make_entry("startup")
    module.make_entry("controller")


@pytest.mark.parametrize("role", ["startup", "controller"])
def test_entry_snapshots_on_first_invocation_and_caches(role, monkeypatch):
    source, seen, events = environment(role), [], []

    def factory(settings):
        seen.append(settings)
        return lambda event, context: events.append((event, context)) or {"ok": role}

    entry = make_entry(role, environment=source, factory=factory)
    source["COPILOT_CONTROL_CONFIG"] = json.dumps({**configuration(role), "namespace": "late"})
    assert not seen
    assert entry({"hello": "world"}, "context") == {"ok": role}
    source.clear()
    assert entry({}, None) == {"ok": role}
    assert len(seen) == 1
    assert seen[0].role == role and seen[0].namespace == "late"
    assert events == [({"hello": "world"}, "context"), ({}, None)]
    assert "abababab" not in repr(seen[0])


def test_default_environment_is_lazy(monkeypatch):
    monkeypatch.delenv("COPILOT_CONTROL_CONFIG", raising=False)
    monkeypatch.delenv("COPILOT_READINESS_KEY_HEX", raising=False)
    entry = make_entry("startup", factory=lambda settings: lambda *_: {"ok": True})
    monkeypatch.setenv("COPILOT_CONTROL_CONFIG", environment()["COPILOT_CONTROL_CONFIG"])
    assert entry({}, None) == {"ok": True}


def test_initialization_is_single_and_failure_latched():
    calls = []

    def factory(settings):
        calls.append(settings)
        raise RuntimeError("private-key-material")

    entry = make_entry("startup", environment=environment(), factory=factory)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: entry({}, None), range(16)))
    assert len(calls) == 1
    assert {result["statusCode"] for result in results} == {503}
    assert all("private-key-material" not in json.dumps(result) for result in results)
    assert all(result["headers"]["cache-control"] == "no-store" for result in results)


@pytest.mark.parametrize("role", ["startup", "controller"])
def test_invocation_error_never_reinitializes(role):
    calls = []

    def factory(settings):
        calls.append(settings)

        def handler(*_):
            raise RuntimeError("private failure")

        return handler

    entry = make_entry(role, environment=environment(role), factory=factory)
    for _ in range(2):
        result = entry({}, None)
        assert "private" not in json.dumps(result)
        assert (
            result == {"state": "unavailable"}
            if role == "controller"
            else result["statusCode"] == 503
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: {},
        lambda x: {**x, "extra": "unwanted"},
        lambda x: {**x, "version": True},
        lambda x: {**x, "version": 2},
        lambda x: {**x, "role": "controller"},
        lambda x: {**x, "table": "x"},
        lambda x: {**x, "namespace": ["demo"]},
        lambda x: {**x, "invitation_identity": "wrong"},
        lambda x: {**x, "origin": "https://elsewhere.example"},
        lambda x: {**x, "controller_arn": "arn:aws:lambda:us-east-1:123456789012:function:x"},
        lambda x: {**x, "instance": "i-0123456789abcdef0"},
    ],
)
def test_bad_configuration_refuses_before_factory(mutation):
    def forbidden(settings):
        pytest.fail("Invalid config reached factory")

    source = {"COPILOT_CONTROL_CONFIG": json.dumps(mutation(configuration()))}
    assert (
        make_entry("startup", environment=source, factory=forbidden)({}, None)["statusCode"] == 503
    )


@pytest.mark.parametrize(
    "raw", ["[]", "null", "{", " " * 3073, '{"version":1,"version":1}', "é" * 1600]
)
def test_bounded_unambiguous_json(raw):
    entry = make_entry("startup", environment={"COPILOT_CONTROL_CONFIG": raw})
    assert entry({}, None)["statusCode"] == 503


@pytest.mark.parametrize("key", [None, "", "ab" * 31, "ab" * 65, "AB" * 32, " ab" * 32, "z" * 64])
def test_controller_key_is_canonical_and_separate(key):
    source = environment("controller")
    if key is None:
        source.pop("COPILOT_READINESS_KEY_HEX")
    else:
        source["COPILOT_READINESS_KEY_HEX"] = key
    entry = make_entry("controller", environment=source)
    assert entry({}, None) == {"state": "unavailable"}


def test_startup_refuses_controller_secret_and_role_event_cannot_switch():
    source = {**environment(), "COPILOT_READINESS_KEY_HEX": "ab" * 32}
    assert make_entry("startup", environment=source)({}, None)["statusCode"] == 503
    for role in ("other", None, True):
        with pytest.raises(ValueError):
            make_entry(role)
    seen = []
    entry = make_entry(
        "startup",
        environment=environment(),
        factory=lambda s: seen.append(s.role) or (lambda *_: {}),
    )
    entry({"role": "controller"}, None)
    assert seen == ["startup"]
