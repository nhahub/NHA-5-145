import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agent.tests.test_lifecycle_dynamodb import make_ready
from deploy.host_bootstrap import create_host_app
from deploy.host_config import load_host_settings
from eval.tests.test_host_bootstrap import Model, proof
from eval.tests.test_host_checks import catalogue_source as _catalogue_source
from eval.tests.test_host_checks import prepared as _prepared
from eval.tests.test_host_checks import world as _world
from eval.tests.test_host_config import config_file as _config_file
from eval.tests.test_host_config import fixture_reader

catalogue_source, prepared, world, config_file = _catalogue_source, _prepared, _world, _config_file


@pytest.fixture
def launcher():
    from deploy import host_agent

    return host_agent


def test_preloop_assembly_and_fixed_server(launcher, monkeypatch):
    events = []

    def before_loop(value):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        events.append(value)

    settings = object()

    def load(path):
        before_loop("load")
        assert path == Path("/protected/host.json")
        return settings

    async def cleanup():
        events.append("cleanup")

    app = SimpleNamespace(state=SimpleNamespace(host_cleanup=cleanup))

    def factory(value):
        before_loop("factory")
        assert value is settings
        return app

    class Server:
        def __init__(self, config):
            assert config.app is app
            assert config.host == "127.0.0.1" and config.port == 8000
            assert config.workers == 1 and config.reload is False
            assert config.lifespan == "on" and config.proxy_headers is False
            assert config.access_log is False and config.server_header is False
            self.started = False

        async def serve(self):
            events.append("serve")
            self.started = True

    monkeypatch.setattr(launcher, "load_host_settings", load)
    monkeypatch.setattr(launcher, "create_host_app", factory)
    monkeypatch.setattr(launcher, "Server", Server)
    assert launcher.main(["--config", "/protected/host.json"]) == 0
    assert events == ["load", "factory", "serve", "cleanup"]


def test_running_loop_refuses_before_loading(launcher, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "load_host_settings", lambda _: pytest.fail("Read keys in loop"))

    async def scenario():
        assert launcher.main(["--config", "/protected/host.json"]) == 1

    asyncio.run(scenario())
    assert capsys.readouterr().err == "Host startup refused\n"


@pytest.mark.parametrize("stage", ["load", "factory", "server", "logging", "interrupt"])
def test_failure_is_redacted(launcher, monkeypatch, capsys, stage):
    closed = []

    async def cleanup():
        closed.append(True)

    app = SimpleNamespace(state=SimpleNamespace(host_cleanup=cleanup))

    def load(_):
        if stage == "load":
            raise ValueError("private-key/path")
        return object()

    def factory(_):
        if stage == "factory":
            raise ValueError("private-key/path")
        return app

    class Server:
        def __init__(self, _):
            if stage == "server":
                raise ValueError("private-key/path")
            self.started = False

        async def serve(self):
            if stage == "interrupt":
                raise KeyboardInterrupt("private-key/path")
            try:
                raise ValueError("private-key/path")
            except ValueError:
                logging.getLogger("uvicorn.error").exception("private-key/path")

    monkeypatch.setattr(launcher, "load_host_settings", load)
    monkeypatch.setattr(launcher, "create_host_app", factory)
    monkeypatch.setattr(launcher, "Server", Server)
    assert launcher.main(["--config", "/protected/host.json"]) == (
        130 if stage == "interrupt" else 1
    )
    output = capsys.readouterr()
    assert output.err == "Host startup refused\n" and output.out == ""
    assert closed == ([] if stage in {"load", "factory"} else [True])


def test_server_never_started_is_failure(launcher, monkeypatch):
    class Server:
        started = False

        def __init__(self, _):
            pass

        async def serve(self):
            pass

    async def cleanup():
        pass

    monkeypatch.setattr(launcher, "Server", Server)
    with pytest.raises(RuntimeError):
        asyncio.run(launcher._serve(SimpleNamespace(state=SimpleNamespace(host_cleanup=cleanup))))


@pytest.fixture
def owned_host(config_file, world, prepared, monkeypatch):
    import deploy.host_bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "_runtime_root", lambda: prepared["release"])
    make_ready(world)
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    closed, model = [], Model()
    monkeypatch.setattr(world[5], "close", lambda: closed.append("sdk"))
    app = create_host_app(settings, sdk_factory=lambda _: world[5], model_client=model)
    return app, closed, settings, model


@pytest.mark.parametrize("phase", ["config", "construction", "before-lifespan"])
def test_cleanup_without_lifespan(launcher, owned_host, monkeypatch, phase):
    app, closed, _, _ = owned_host

    class Server:
        def __init__(self, _):
            if phase == "construction":
                raise ValueError("private")

        async def serve(self):
            raise ValueError("private")

    def broken_config(*_, **__):
        raise ValueError("private")

    if phase == "config":
        monkeypatch.setattr(launcher, "Config", broken_config)
    monkeypatch.setattr(launcher, "Server", Server)
    with pytest.raises(ValueError):
        asyncio.run(launcher._serve(app))
    assert closed == ["sdk"]
    assert app.state.host_readiness.checks_owner._closed


@pytest.mark.parametrize("fail", [False, True])
def test_cleanup_after_lifespan(launcher, owned_host, monkeypatch, fail):
    app, closed, _, _ = owned_host

    class Server:
        started = True

        def __init__(self, _):
            pass

        async def serve(self):
            async with app.router.lifespan_context(app):
                assert app.state.lifecycle_work.generation == 1
                if fail:
                    raise ValueError("private")

    monkeypatch.setattr(launcher, "Server", Server)
    if fail:
        with pytest.raises(ValueError):
            asyncio.run(launcher._serve(app))
    else:
        asyncio.run(launcher._serve(app))
    assert closed == ["sdk"]


def test_cancelled_server_drains_resources(launcher, owned_host, monkeypatch):
    app, closed, _, _ = owned_host

    class Server:
        def __init__(self, _):
            pass

        async def serve(self):
            async with app.router.lifespan_context(app):
                raise asyncio.CancelledError()

    monkeypatch.setattr(launcher, "Server", Server)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(launcher._serve(app))
    assert closed == ["sdk"]


def test_closed_provider_stays_closed(launcher, owned_host, monkeypatch):
    app, closed, settings, model = owned_host
    before = app.state.llm_client.ledger.status()

    class Server:
        started = True

        def __init__(self, _):
            pass

        async def serve(self):
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="https://app.scpilot.tech"
                ) as client:
                    result = await client.get("/health", headers=proof(settings))
                    assert result.status_code == 200 and result.json()["ready"] is False
                with pytest.raises(RuntimeError):
                    await app.state.lifecycle_work.begin()

    monkeypatch.setattr(launcher, "Server", Server)
    asyncio.run(launcher._serve(app))
    assert model.calls == 0 and app.state.llm_client.ledger.status() == before
    assert closed == ["sdk"]


@pytest.mark.parametrize("phase", ["lifespan", "bind"])
def test_real_uvicorn_failure_cleans_and_redacts(launcher, owned_host, monkeypatch, capsys, phase):
    app, closed, settings, _ = owned_host

    async def failed(*_, **__):
        raise OSError("private-key/path")

    if phase == "lifespan":
        monkeypatch.setattr(app.state.lifecycle_work, "initialize", failed)
    else:
        # Real Uvicorn startup and lifespan; fail the bind seam before any socket.
        monkeypatch.setattr(asyncio.BaseEventLoop, "create_server", failed)
    monkeypatch.setattr(launcher, "load_host_settings", lambda _: settings)
    monkeypatch.setattr(launcher, "create_host_app", lambda _: app)
    assert launcher.main(["--config", "/protected/host.json"]) == 1
    output = capsys.readouterr()
    assert output.err == "Host startup refused\n" and output.out == ""
    assert closed == ["sdk"]


@pytest.mark.parametrize("option", ["--provider-ready", "--workers", "--host", "--conf"])
def test_unknown_switch_cannot_bypass_gate(launcher, monkeypatch, capsys, option):
    monkeypatch.setattr(launcher, "load_host_settings", lambda _: pytest.fail("Invalid CLI loaded"))
    assert launcher.main(["--config", "/protected/host.json", option, "private"]) == 1
    assert capsys.readouterr().err == "Host startup refused\n"


def test_prepared_unit_and_release():
    root = Path(__file__).resolve().parents[2]
    unit = (root / "deploy/shopping-copilot-agent.service").read_text()
    assert "-m deploy.host_agent --config /etc/shopping-copilot/agent/host.json" in unit
    for value in ("User=copilot", "NoNewPrivileges=yes", "ProtectSystem=strict", "UMask=0077"):
        assert value in unit
    assert "Conflicts=shopping-copilot.service" in unit
    assert "-m deploy run" in (root / "deploy/shopping-copilot.service").read_text()


def test_pinned_attempt_ceiling_reaches_qualified_factory(launcher, monkeypatch):
    settings, binding, app = object(), object(), object()
    observed = []
    monkeypatch.setattr(launcher, "load_host_settings", lambda _: settings)
    monkeypatch.setattr(launcher, "load_provider_binding", lambda *_: binding)

    def factory(value, **kwargs):
        assert value is settings
        observed.append(kwargs)
        return app

    async def serve(value):
        assert value is app

    monkeypatch.setattr(launcher, "create_host_app", factory)
    monkeypatch.setattr(launcher, "_serve", serve)
    assert (
        launcher.main(
            [
                "--config",
                "/protected/host.json",
                "--qualification",
                "/protected/binding.json",
                "--qualification-sha256",
                "a" * 64,
                "--maximum-attempts",
                "252",
            ]
        )
        == 0
    )
    assert observed == [{"qualification": binding, "maximum_attempts": 252}]


@pytest.mark.parametrize("limit", ["0", "-1", "1000001", "four", "4.0", "252"])
def test_ceiling_without_qualified_custody_is_refused_before_settings(launcher, monkeypatch, limit):
    monkeypatch.setattr(launcher, "load_host_settings", lambda _: pytest.fail("Unsafe CLI loaded"))
    assert launcher.main(["--config", "/protected/host.json", "--maximum-attempts", limit]) == 1


def test_actual_host_factory_preserves_absolute_attempt_ceiling(
    config_file, world, prepared, monkeypatch
):
    import deploy.host_bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "_runtime_root", lambda: prepared["release"])
    settings = load_host_settings(config_file[0], read_private=fixture_reader)
    app = create_host_app(
        settings, sdk_factory=lambda _: world[5], model_client=Model(), maximum_attempts=252
    )
    assert app.state.llm_client._maximum_attempts == 252
    asyncio.run(app.state.host_cleanup())
