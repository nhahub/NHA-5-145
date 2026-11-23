"""Concrete readiness with local artifacts/SQLite and intercepted private HTTP."""

import asyncio
import copy
import hashlib
import json
import shutil
import sqlite3
from decimal import Decimal

import httpx
import pytest

from agent.admission.async_runtime import AsyncAdmissionPolicy
from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.ledger import AllowanceLedger
from agent.lifecycle.host_health import HostReadiness
from agent.storefront_service import StorefrontService
from agent.tests.http_client import TestClient
from agent.tests.test_host_boundaries import RELEASE, SECRET, Work, app_with, headers
from agent.tests.test_lifecycle_dynamodb import world as _world
from deploy.artifact import files
from deploy.host_checks import HostChecks, unqualified_provider
from eval.tests.test_release import seed_catalogue

world = _world


class Body(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data


def reply(status=200, *, value=None, body=None, headers=None):
    data = json.dumps(value).encode() if value is not None else body or b""
    return httpx.Response(status, stream=Body(data), headers=headers)


@pytest.fixture(scope="module")
def catalogue_source(tmp_path_factory):
    path = tmp_path_factory.mktemp("host-catalogue") / "catalogue.sqlite"
    seed_catalogue(path)
    return path


def search(revision=1):
    return {
        "v": 1,
        "catalogue_revision": revision,
        "candidates": [],
        "ranking": "lexical",
        "exact_count": 0,
        "next_cursor": None,
        "truncated": False,
        "unverified_requirements": [],
    }


@pytest.fixture
def prepared(tmp_path, catalogue_source, world):
    release = tmp_path / "release"
    release.mkdir()
    (release / "app.py").write_text("# synthetic release fixture\n")
    manifest = {
        "format": 1,
        "catalogue_schema": 1,
        "files": files(release),
        "local_rehearsal": False,
        "public_origins": {
            "panel": "https://app.scpilot.tech",
            "store": "https://store.scpilot.tech",
            "agent": "https://app.scpilot.tech",
        },
    }
    (release / "release.json").write_text(json.dumps(manifest))
    catalogue = tmp_path / "catalogue.sqlite"
    shutil.copyfile(catalogue_source, catalogue)
    ledger_path = tmp_path / "ledger.sqlite"
    ledger = AllowanceLedger(ledger_path, AllowanceLedger.initialize(ledger_path, Decimal("1")))
    guard = GuardedClient(
        object(),
        ledger,
        InferencePrices(Decimal("1"), Decimal("1")),
        maximum_active=1,
        maximum_waiting=0,
        wait_seconds=1,
    )
    service = StorefrontService(
        {
            "secret": "s" * 32,
            "panel_origin": "https://app.scpilot.tech",
            "store_origin": "https://store.scpilot.tech",
            "private_url": "http://127.0.0.1:4000",
        }
    )
    admission = AsyncAdmissionPolicy(world[1])
    return {
        "release": release,
        "fingerprint": hashlib.sha256((release / "release.json").read_bytes()).hexdigest(),
        "catalogue": catalogue,
        "guard": guard,
        "service": service,
        "admission": admission,
    }


async def close(checks, prepared):
    await checks.close()
    await prepared["admission"].close()


def test_four_concrete_checks_pass_but_unqualified_provider_never_signs_ready(prepared):
    seen = []

    def serve(request):
        seen.append(request)
        assert str(request.url) == "http://127.0.0.1:4000/__internal/catalogue/search"
        assert request.headers["x-service-secret"] == "s" * 32
        assert request.headers["accept-encoding"] == "identity"
        assert json.loads(request.content)["query"] == ""
        return reply(value=search())

    async def scenario():
        checks = HostChecks(**prepared, transport=httpx.MockTransport(serve))
        try:
            before = prepared["guard"].ledger.status()
            mapping = checks.checks(unqualified_provider)
            assert all(
                await asyncio.gather(*(mapping[name]() for name in mapping if name != "provider"))
            )
            work = Work()
            health = HostReadiness(work, SECRET, RELEASE, mapping)
            try:
                assert json.loads((await health.response(headers())).body)["ready"] is False
            finally:
                await health.close()
            assert prepared["guard"].ledger.status() == before
            assert not prepared["admission"].store.status()[0]["used_sessions"]
        finally:
            await close(checks, prepared)
        assert await checks.release() is False
        assert await checks.storefront() is False
        assert len(seen) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("changed", ["code", "manifest", "deleted", "wrong-hash", "local-mode"])
def test_release_check_never_rebaselines_mutated_or_wrong_artifact(prepared, changed):
    if changed == "code":
        (prepared["release"] / "app.py").write_text("changed")
    elif changed == "manifest":
        (prepared["release"] / "release.json").write_text("{}")
    elif changed == "deleted":
        (prepared["release"] / "app.py").unlink()
    elif changed == "wrong-hash":
        prepared["fingerprint"] = "0" * 64
    else:
        path = prepared["release"] / "release.json"
        data = json.loads(path.read_text()) | {"local_rehearsal": True}
        path.write_text(json.dumps(data))
        prepared["fingerprint"] = hashlib.sha256(path.read_bytes()).hexdigest()

    async def scenario():
        checks = HostChecks(**prepared)
        try:
            assert await checks.release() is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kind",
    ["disabled", "exhausted", "rebound-identity", "rebound-prices", "rebound-client", "missing"],
)
def test_allowance_check_preserves_held_charges_and_refuses_changed_authority(prepared, kind):
    async def scenario():
        checks = HostChecks(**prepared)
        ledger = prepared["guard"].ledger
        if kind == "disabled":
            ledger.set_enabled(False)
        elif kind == "exhausted":
            ledger.reserve("retained-uncertain", Decimal("0.99"))
        elif kind == "rebound-identity":
            ledger.identity = "changed"
        elif kind == "rebound-prices":
            prepared["guard"].prices = InferencePrices(Decimal("0.1"), Decimal("0.1"))
        elif kind == "rebound-client":
            prepared["guard"].client = object()
        else:
            ledger.path.unlink()
        try:
            assert await checks.allowance() is False
            if kind == "exhausted":
                assert ledger.status()["accounted_usd"] == "0.990000000"
                assert ledger.status()["uncertain"] == 1
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,body,extra",
    [
        (302, b"", {"location": "https://evil.test"}),
        (403, b"denied", {}),
        (200, b"x" * 32769, {}),
        (200, b"{}", {}),
        (200, json.dumps(search(2)).encode(), {}),
        (200, json.dumps(search()).encode(), {"content-encoding": "gzip"}),
        (200, json.dumps(search()).replace('"v": 1', '"v": 1, "v": 1').encode(), {}),
    ],
    ids=["redirect", "denied", "oversize", "schema", "stale", "compressed", "duplicate"],
)
def test_private_http_unhealthy_responses_fail_closed(prepared, status, body, extra):
    async def scenario():
        checks = HostChecks(
            **prepared,
            transport=httpx.MockTransport(lambda _: reply(status, body=body, headers=extra)),
        )
        try:
            assert await checks.storefront() is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


def test_catalogue_change_during_private_read_invalidates_check(prepared):
    def serve(_):
        with sqlite3.connect(prepared["catalogue"]) as database:
            database.execute("UPDATE catalogue_meta SET revision=revision+1")
        return reply(value=search())

    async def scenario():
        checks = HostChecks(**prepared, transport=httpx.MockTransport(serve))
        try:
            assert await checks.storefront() is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


def test_signed_asgi_proof_with_concrete_checks_stays_unqualified(prepared):
    checks = HostChecks(**prepared, transport=httpx.MockTransport(lambda _: reply(value=search())))
    app = app_with(Work(), checks.checks(unqualified_provider))
    with TestClient(app) as client:
        result = client.get("/health", headers=headers())
        assert result.status_code == 200 and result.json()["ready"] is False
        client.portal.call(checks.close)
        client.portal.call(prepared["admission"].close)


def test_private_http_deadline_cancels_slow_read(prepared):
    async def slow(_):
        await asyncio.Event().wait()

    async def scenario():
        checks = HostChecks(**prepared, transport=httpx.MockTransport(slow))
        try:
            result = await asyncio.wait_for(checks.storefront(), 1.4)
            assert result is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


@pytest.mark.parametrize("binding", ["store", "identity", "namespace", "service"])
def test_changed_admission_or_service_binding_is_not_silently_accepted(prepared, binding):
    async def scenario():
        checks = HostChecks(**prepared)
        if binding == "store":
            prepared["admission"].store = copy.copy(prepared["admission"].store)
        elif binding == "identity":
            prepared["admission"].store.identity = "changed"
        elif binding == "namespace":
            prepared["admission"].store.namespace = "another"
        else:
            prepared["service"].config["secret"] = "t" * 32
        try:
            assert await checks.admission() is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


def test_provider_verifier_must_be_explicit_and_async(prepared):
    async def scenario():
        checks = HostChecks(**prepared)
        try:
            with pytest.raises(ValueError):
                checks.checks(lambda: True)
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())


def test_external_state_cannot_alias_release_or_each_other(prepared):
    prepared["catalogue"] = prepared["guard"].ledger.path

    async def scenario():
        checks = HostChecks(**prepared)
        try:
            assert await checks.release() is False
            assert await checks.allowance() is False
            assert await checks.storefront() is False
        finally:
            await close(checks, prepared)

    asyncio.run(scenario())
