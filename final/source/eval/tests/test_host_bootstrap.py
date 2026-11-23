import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.inference.client import GuardedClient
from agent.lifecycle.readiness import _mac
from agent.schemas import Snapshot
from agent.shopper_access import ShopperBinding
from agent.tests.test_lifecycle_dynamodb import make_ready
from agent.tests.test_step import home_snapshot
from deploy.host_bootstrap import create_host_app
from deploy.host_config import load_host_settings
from deploy.host_event_log import HostFileSink
from eval.tests.test_host_checks import catalogue_source as _catalogue_source
from eval.tests.test_host_checks import prepared as _prepared
from eval.tests.test_host_checks import reply, search
from eval.tests.test_host_checks import world as _world
from eval.tests.test_host_config import config_file as _config_file
from eval.tests.test_host_config import fixture_reader

catalogue_source, prepared, world, config_file = _catalogue_source, _prepared, _world, _config_file


def test_operating_host_admission_expires_without_restart_or_provider_call(config_file, world):
    from agent.lifecycle.operating import OperatingAuthority, OperatingPolicy

    make_ready(world)
    policy = OperatingPolicy(str(uuid4()), "a" * 64, "i-0123456789abcdef0", 900, 40000)
    OperatingAuthority.initialize(world[1], policy)
    path, data = config_file
    key = path.with_name("provider.key")
    key.write_text("synthetic-provider-key-" + "x" * 64)
    data.update(
        version=3,
        provider="openrouter",
        model="google/gemini-3.5-flash-lite",
        provider_key_file=str(key),
        operating=policy.values(),
        operating_attempt_ceiling=100,
    )
    data["admission_limits"]["maximum_sessions"] = 8
    data["inference"].update(
        INFERENCE_PROVIDER="openrouter",
        INFERENCE_MODEL=data["model"],
        INFERENCE_INPUT_USD_PER_MILLION="0.3",
        INFERENCE_OUTPUT_USD_PER_MILLION="2.5",
    )
    path.write_text(json.dumps(data))
    settings = load_host_settings(path, read_private=fixture_reader)
    with pytest.raises(ValueError, match="Host startup refused"):
        create_host_app(
            settings,
            maximum_attempts=101,
            sdk_factory=lambda _: pytest.fail("SDK before ceiling validation"),
        )
    model = Model()
    logs = object()
    app = create_host_app(
        settings,
        sdk_factory=lambda _: world[-1],
        logs_factory=lambda: logs,
        model_client=model,
        http_transport=httpx.MockTransport(lambda _: reply(value=search())),
        clock=lambda: world[0][0],
    )
    before = app.state.llm_client.ledger.status()
    assert app.state.llm_client._maximum_attempts == 100
    # Records go to the host's private log folder, stamped with the installed release.
    assert app.state.events.release == settings.fingerprint[:12]
    assert isinstance(app.state.events.sink, HostFileSink)
    assert app.state.events.sink.directory == Path("/var/log/shopping-copilot/agent")
    # Only root can turn debug text on: the Agent cannot write /etc/shopping-copilot.
    assert app.state.events.debug.marker == Path("/etc/shopping-copilot/debug-logging")
    assert app.state.events.debug.owner == 0
    # Ordinary records are shipped to CloudWatch from that file, per release.
    shipper = app.state.log_shipper
    assert shipper.client is logs and shipper.running
    assert (shipper.group, shipper.stream) == (
        "/scpilot/agent-events",
        "agent-" + settings.fingerprint[:12],
    )
    assert shipper.directory == Path("/var/log/shopping-copilot/agent")
    assert shipper.checkpoint == Path("/var/lib/shopping-copilot/agent/log-shipper.json")
    with TestClient(app, base_url="https://app.scpilot.tech") as client:

        async def validate(_):
            return True

        app.state.storefront_service.validate = validate
        bootstrap = client.post(
            "/shopper/bootstrap", headers={"origin": "https://app.scpilot.tech"}
        )
        assert bootstrap.status_code == 200
        record = next(iter(app.state.shopper_access.records.values()))
        record.shopper = ShopperBinding("owner", "generation")
        auth = {"origin": "https://app.scpilot.tech", "x-csrf-token": bootstrap.json()["csrf"]}
        assert (
            client.post("/shopper/admission", json={"code": world[3]}, headers=auth).json()[
                "admitted"
            ]
            is True
        )
        world[0][0] = policy.closes
        assert (
            client.post("/shopper/admission", json={"code": world[3]}, headers=auth).status_code
            >= 400
        )
        assert client.get("/speech/availability", headers=auth).status_code == 403
        assert app.state.llm_client.ledger.status() == before
        assert model.calls == 0


@pytest.fixture(autouse=True)
def synthetic_runtime_root(prepared, monkeypatch):
    import deploy.host_bootstrap as module

    # Synthetic artifacts do not claim execution from a packaged release.
    monkeypatch.setattr(module, "_runtime_root", lambda: prepared["release"])


def test_factory_refuses_execution_from_another_release(config_file, monkeypatch):
    import deploy.host_bootstrap as module

    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    monkeypatch.setattr(module, "_runtime_root", lambda: settings.release.parent)
    with pytest.raises(ValueError, match="^Host startup refused$"):
        create_host_app(settings, sdk_factory=lambda _: pytest.fail("SDK before release binding"))


class Model:
    calls = 0

    async def complete(self, request):
        self.calls += 1
        pytest.fail("Unqualified host reached the provider")
        yield


def proof(settings):
    nonce = "a" * 64
    return {
        "x-copilot-generation": "1",
        "x-copilot-release": settings.fingerprint,
        "x-copilot-nonce": nonce,
        "x-copilot-proof": _mac(
            settings.readiness_secret, "request", settings.fingerprint, 1, nonce
        ),
    }


@pytest.mark.parametrize("provider", ["bedrock", "openrouter"])
def test_host_factory_wires_owned_resources_and_blocks_unqualified_requests(
    config_file, world, monkeypatch, provider
):
    make_ready(world)
    if provider == "openrouter":
        path, data = config_file
        provider_key = path.with_name("provider.key")
        provider_key.write_text("synthetic-provider-key-" + "x" * 64)
        data.update(
            version=2,
            provider="openrouter",
            model="google/gemini-3.5-flash-lite",
            provider_key_file=str(provider_key),
        )
        data["inference"].update(
            INFERENCE_PROVIDER="openrouter",
            INFERENCE_MODEL="google/gemini-3.5-flash-lite",
            INFERENCE_INPUT_USD_PER_MILLION="0.3",
            INFERENCE_OUTPUT_USD_PER_MILLION="2.5",
        )
        path.write_text(json.dumps(data))
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    sdk = world[5]
    closed = []
    monkeypatch.setattr(sdk, "close", lambda: closed.append("sdk"))
    model = Model()
    selected = []

    def clients(service):
        selected.append(service)
        return sdk

    app = create_host_app(
        settings,
        sdk_factory=clients,
        model_client=model,
        http_transport=httpx.MockTransport(lambda _: reply(value=search())),
        clock=lambda: world[0][0],
    )
    assert selected == ["dynamodb"]
    assert isinstance(app.state.llm_client, GuardedClient)
    assert app.state.llm_client.client is model
    assert settings.environment()["LLM_PROVIDER"] == provider
    before = app.state.llm_client.ledger.status()
    with TestClient(app, base_url="https://app.scpilot.tech") as client:
        result = client.get("/health", headers=proof(settings))
        assert result.status_code == 200 and result.json()["ready"] is False
        assert app.state.lifecycle_work.generation == 1

        async def validate(_):
            return True

        app.state.storefront_service.validate = validate
        bootstrap = client.post(
            "/shopper/bootstrap", headers={"origin": "https://app.scpilot.tech"}
        )
        assert bootstrap.status_code == 200
        record = next(iter(app.state.shopper_access.records.values()))
        record.shopper = ShopperBinding("owner", "generation")
        auth = {"origin": "https://app.scpilot.tech", "x-csrf-token": bootstrap.json()["csrf"]}
        code = world[3]
        assert (
            client.post("/shopper/admission", json={"code": code}, headers=auth).json()["admitted"]
            is True
        )
        speech = client.get("/speech/availability", headers=auth)
        assert speech.status_code == 503 and speech.json()["code"] == "demo_waiting"
        assert settings.provider_key == "" or settings.provider_key not in speech.text
        assert client.post("/sessions", headers=auth).status_code == 503
        session = app.state.lifecycle_work.sessions.create()
        session.shopper = record.shopper
        record.sessions.add(session.session_id)
        assert (
            client.post(
                f"/sessions/{session.session_id}/messages",
                headers=auth,
                json={"text": "Open my cart", "snapshot": home_snapshot()},
            ).status_code
            == 503
        )
        app.state.lifecycle_work.sessions.submit_message(
            session.session_id, "Open my cart", Snapshot.model_validate(home_snapshot())
        )
        assert client.post(f"/sessions/{session.session_id}/stop", headers=auth).status_code == 202
        assert client.post("/step", headers=auth).status_code == 404
        assert app.state.llm_client.ledger.status() == before
        assert model.calls == 0
    assert closed == ["sdk"]
    assert app.state.lifecycle_work._closed and app.state.admission._io._closed
    assert app.state.host_readiness.checks_owner._closed


def test_factory_refuses_inside_event_loop_before_any_sdk_call(config_file):
    settings = load_host_settings(config_file[0], read_private=fixture_reader)

    async def scenario():
        with pytest.raises(ValueError, match="Host startup refused"):
            create_host_app(settings, sdk_factory=lambda _: pytest.fail("Called SDK in loop"))

    asyncio.run(scenario())


def test_factory_failure_closes_sdk_and_hides_dependency_details(config_file, world, monkeypatch):
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    sdk, closed = world[5], []
    monkeypatch.setattr(sdk, "close", lambda: closed.append(True))
    sdk.delete_item(TableName=settings.table, Key=world[1]._key("meta"))
    with pytest.raises(ValueError, match="^Host startup refused$") as caught:
        create_host_app(settings, sdk_factory=lambda _: sdk)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert closed == [True]


def test_late_factory_failure_drains_constructed_resources(config_file, world, monkeypatch):
    import deploy.host_bootstrap as module

    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    closed = []
    monkeypatch.setattr(world[5], "close", lambda: closed.append(True))

    def failed(**_):
        raise ValueError("private-secret")

    monkeypatch.setattr(module, "HostChecks", failed)
    with pytest.raises(ValueError, match="^Host startup refused$") as caught:
        create_host_app(settings, sdk_factory=lambda _: world[5], model_client=Model())
    assert caught.value.__context__ is None and closed == [True]


def test_failed_lifespan_initialization_closes_all_factory_resources(
    config_file, world, monkeypatch
):
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    closed = []
    monkeypatch.setattr(world[5], "close", lambda: closed.append(True))
    app = create_host_app(settings, sdk_factory=lambda _: world[5], model_client=Model())
    with pytest.raises(RuntimeError), TestClient(app):
        pytest.fail("Generation0 must not serve")
    assert closed == [True]
    assert app.state.host_readiness.checks_owner._closed


def test_provider_wait_rechecks_generation_before_granting_work(config_file, world):
    make_ready(world)
    settings = load_host_settings(config_file[0], read_private=fixture_reader)

    async def changed():
        app.state.lifecycle_work.failed = True
        return True

    app = create_host_app(
        settings,
        sdk_factory=lambda _: world[5],
        provider_ready=changed,
        model_client=Model(),
        clock=lambda: world[0][0],
    )
    with TestClient(app) as client, pytest.raises(RuntimeError):
        client.portal.call(app.state.lifecycle_work.check)


def test_slow_provider_does_not_hold_pending_lease_bookkeeping(config_file, world):
    make_ready(world)
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    release, entered = asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await release.wait()
        return False

    app = create_host_app(
        settings,
        sdk_factory=lambda _: world[5],
        provider_ready=slow,
        model_client=Model(),
        clock=lambda: world[0][0],
    )

    async def scenario():
        work = app.state.lifecycle_work
        token = world[4].begin_work(generation=1)
        work.pending = token
        work.sessions.has_pending_work = lambda: True
        work._last_renew = work.clock()
        task = asyncio.create_task(work.check())
        refresh = None
        try:
            await entered.wait()
            world[0][0] += 30
            work._last_renew -= 30
            refresh = asyncio.create_task(work.refresh())
            done, _ = await asyncio.wait({refresh}, timeout=0.2)
            assert refresh in done, "Provider wait held the lease lock"
            assert world[1]._read("lifecycle#host")["leases"][token] > world[0][0]
        finally:
            release.set()
            await asyncio.gather(task, *([refresh] if refresh else []), return_exceptions=True)

    with TestClient(app) as client:
        client.portal.call(scenario)


def test_provider_timeout_retains_single_cleanup_slot():
    from deploy.host_bootstrap import _ProviderGate

    async def scenario():
        release, cleaning = asyncio.Event(), asyncio.Event()
        calls = []

        async def slow():
            calls.append(True)
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()

        gate = _ProviderGate(slow)
        try:
            assert await asyncio.wait_for(gate.ready(), 1.3) is False
            await cleaning.wait()
            assert await gate.ready() is False and len(calls) == 1
        finally:
            release.set()
            await gate.close()

    asyncio.run(scenario())


def test_cancelled_close_never_closes_sdk_before_worker_drains():
    from threading import Event
    from types import SimpleNamespace

    from deploy.host_bootstrap import _OwnedAdmission

    entered, release = Event(), Event()
    closed = []

    def blocked():
        entered.set()
        assert release.wait(3)

    async def scenario():
        policy = _OwnedAdmission(
            SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append(True)))
        )
        task = asyncio.create_task(policy._io.call(blocked))
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        closing = asyncio.create_task(policy.close())
        while not policy._io._closed:
            await asyncio.sleep(0)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        try:
            assert not closed, "Shared SDK closed while its worker was still running"
        finally:
            release.set()
            await task
            await policy.close()
        assert closed == [True]

    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_sdk_close_also_waits_for_lifecycle_workers(config_file, world, monkeypatch):
    from threading import Event

    make_ready(world)
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    entered, release = Event(), Event()
    closed = []
    monkeypatch.setattr(world[5], "close", lambda: closed.append(True))
    app = create_host_app(settings, sdk_factory=lambda _: world[5], clock=lambda: world[0][0])

    def blocked():
        entered.set()
        assert release.wait(3)

    async def scenario():
        work = app.state.lifecycle_work
        task = asyncio.create_task(work._io.call(blocked))
        while not entered.is_set():
            await asyncio.sleep(0.001)
        closing = asyncio.create_task(app.state.admission.close())
        await asyncio.sleep(0.05)
        try:
            assert not closed, "SDK closed before lifecycle worker drain"
        finally:
            release.set()
            await task
            await closing
        assert work._closed and closed == [True]

    try:
        with TestClient(app) as client:
            client.portal.call(scenario)
    finally:
        release.set()
