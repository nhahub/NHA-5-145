"""Explicit synthetic host binding, preserving default-false and all budget state."""

import asyncio
import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from agent.lifecycle.async_work import AsyncLifecycleWork
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lifecycle_dynamodb import make_ready
from deploy.host_bootstrap import create_host_app
from deploy.host_config import load_host_settings
from eval.tests.test_host_bootstrap import Model, proof
from eval.tests.test_host_checks import catalogue_source as _catalogue_source
from eval.tests.test_host_checks import prepared as _prepared
from eval.tests.test_host_checks import reply, search
from eval.tests.test_host_checks import world as _world
from eval.tests.test_host_config import config_file as _config_file
from eval.tests.test_host_config import fixture_reader

catalogue_source, prepared, world, config_file = _catalogue_source, _prepared, _world, _config_file


@pytest.fixture
def qualified_host(config_file, prepared, world, monkeypatch):
    from deploy import host_bootstrap, provider_binding

    make_ready(world)
    path, data = config_file
    key = path.with_name("provider.key")
    key.write_text("synthetic-provider-key-" + "x" * 64)
    data.update(
        version=2,
        provider="openrouter",
        model="google/gemini-3.5-flash-lite",
        provider_key_file=str(key),
    )
    data["inference"].update(
        INFERENCE_PROVIDER="openrouter",
        INFERENCE_MODEL="google/gemini-3.5-flash-lite",
        INFERENCE_INPUT_USD_PER_MILLION="0.3",
        INFERENCE_OUTPUT_USD_PER_MILLION="2.5",
    )
    path.write_text(json.dumps(data))
    settings = load_host_settings(path, read_private=fixture_reader)
    directory = path.parent / "qualification"
    directory.mkdir()

    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    report = json.dumps(
        dict(
            model=settings.model,
            accepted_for_local_replacement=True,
            automated_passed=True,
            milestone_summary=dict(gate_passed=True),
        )
    ).encode()
    reconciliation = json.dumps(
        dict(
            status="verified_offline_attribution_not_current_host_qualification",
            runtime_qualification_granted=False,
            accepted_report=dict(sha256=sha(report)),
        )
    ).encode()
    monkeypatch.setattr(provider_binding, "ACCEPTED_REPORT_SHA256", sha(report))
    monkeypatch.setattr(provider_binding, "RECONCILIATION_SHA256", sha(reconciliation))
    (directory / "accepted-report.json").write_bytes(report)
    (directory / "reconciliation.json").write_bytes(reconciliation)
    binding_path = directory / "binding.json"
    now = int(world[0][0])
    binding_path.write_bytes(
        provider_binding.candidate_binding(settings, issued_at=now, expires_at=now + 300)
    )
    binding = provider_binding.load_provider_binding(
        settings,
        binding_path,
        sha(binding_path.read_bytes()),
        read_private=fixture_reader,
        clock=lambda: world[0][0],
    )
    monkeypatch.setattr(host_bootstrap, "_runtime_root", lambda: prepared["release"])
    closed = []
    monkeypatch.setattr(world[5], "close", lambda: closed.append("sdk"))
    return settings, binding, directory, closed


def app_for(qualified_host, world, **kwargs):
    settings, binding, _, _ = qualified_host
    return create_host_app(
        settings,
        qualification=binding,
        sdk_factory=lambda _: world[5],
        http_transport=httpx.MockTransport(lambda _: reply(value=search())),
        clock=lambda: world[0][0],
        **kwargs,
    )


def test_explicit_binding_uses_actual_client_and_preserves_existing_allowance(
    qualified_host, world
):
    app = app_for(qualified_host, world)
    settings, _, _, closed = qualified_host
    before = app.state.llm_client.ledger.status()
    with TestClient(app) as client:
        response = client.get("/health", headers=proof(settings))
        assert response.status_code == 200 and response.json()["ready"] is True
        assert client.get("/speech/availability").status_code == 401
        client.portal.call(app.state.lifecycle_work.check)
        assert app.state.llm_client.client.call_metadata == []
        assert app.state.llm_client.ledger.status() == before
    assert closed == ["sdk"]


def test_changed_disk_evidence_is_a_restart_boundary_not_a_runtime_watch(qualified_host, world):
    app = app_for(qualified_host, world)
    settings, binding, directory, _ = qualified_host
    with TestClient(app) as client:
        (directory / "accepted-report.json").unlink()
        assert client.get("/health", headers=proof(settings)).json()["ready"] is True
        client.portal.call(app.state.lifecycle_work.check)
    from deploy.provider_binding import load_provider_binding

    with pytest.raises(ValueError, match="^Provider qualification refused$"):
        load_provider_binding(
            settings,
            binding._path,
            binding._expected,
            read_private=fixture_reader,
            clock=lambda: world[0][0],
        )


@pytest.mark.parametrize("count", [2, 5, 8])
def test_parallel_captured_work_checks_preserve_each_valid_authorization(
    qualified_host, world, count
):
    app = app_for(qualified_host, world)
    before = app.state.llm_client.ledger.status()

    async def parallel_checks():
        return await asyncio.gather(
            *(app.state.lifecycle_work.check() for _ in range(count)),
            return_exceptions=True,
        )

    with TestClient(app) as client:
        results = client.portal.call(parallel_checks)
        assert results == [None] * count
        assert app.state.llm_client.client.call_metadata == []
        assert app.state.llm_client.ledger.status() == before


@pytest.mark.parametrize("mutation", ["expiry", "client", "closed"])
def test_captured_authority_is_rechecked_after_lifecycle_await(
    qualified_host, world, monkeypatch, mutation
):
    app = app_for(qualified_host, world)
    original = AsyncLifecycleWork.check

    async def changed(work):
        await original(work)
        if mutation == "expiry":
            world[0][0] += 301
        elif mutation == "client":
            app.state.llm_client.client._settings = replace(app.state.llm_client.client._settings)
        else:
            await work._provider.close()

    with TestClient(app) as client:
        monkeypatch.setattr(AsyncLifecycleWork, "check", changed)
        with pytest.raises(LifecycleUnavailable):
            client.portal.call(app.state.lifecycle_work.check)
        assert app.state.llm_client.client.call_metadata == []


def test_actual_wrong_client_is_refused_and_constructed_sdk_is_closed(qualified_host, world):
    with pytest.raises(ValueError, match="^Host startup refused$"):
        app_for(qualified_host, world, model_client=Model())
    assert qualified_host[3] == ["sdk"]


@pytest.mark.parametrize("mutation", ["expiry", "client", "closed"])
def test_signed_readiness_rechecks_after_the_final_lifecycle_read(
    qualified_host, world, monkeypatch, mutation
):
    app = app_for(qualified_host, world)
    settings = qualified_host[0]
    with TestClient(app) as client:
        work = app.state.lifecycle_work
        original = work.readiness_state
        calls = 0

        async def changed():
            nonlocal calls
            state = await original()
            calls += 1
            if calls == 2:
                if mutation == "expiry":
                    world[0][0] += 301
                elif mutation == "client":
                    app.state.llm_client.client._settings = replace(
                        app.state.llm_client.client._settings
                    )
                else:
                    await work._provider.close()
            return state

        monkeypatch.setattr(work, "readiness_state", changed)
        response = client.get("/health", headers=proof(settings))
        assert calls == 2
        assert response.status_code == 200 and response.json()["ready"] is False
        assert app.state.llm_client.client.call_metadata == []


@pytest.mark.parametrize("mutation", ["expiry", "client", "closed", "cancel"])
def test_request_entry_rechecks_after_lease_acquisition_and_releases_on_refusal(
    qualified_host, world, monkeypatch, mutation
):
    app = app_for(qualified_host, world)
    original = AsyncLifecycleWork.begin
    acquired = []

    async def changed(work):
        token = await original(work)
        acquired.append(token)
        if mutation == "expiry":
            world[0][0] += 301
        elif mutation == "client":
            app.state.llm_client.client._settings = replace(app.state.llm_client.client._settings)
        elif mutation == "closed":
            await work._provider.close()
        return token

    with TestClient(app) as client:
        monkeypatch.setattr(AsyncLifecycleWork, "begin", changed)
        work = app.state.lifecycle_work
        original_recheck = work._provider.recheck

        async def recheck(proof):
            if mutation == "cancel" and acquired:
                raise asyncio.CancelledError()
            return await original_recheck(proof)

        monkeypatch.setattr(work._provider, "recheck", recheck)

        async def refused():
            blocked = False
            try:
                await work.begin()
            except (LifecycleUnavailable, asyncio.CancelledError):
                blocked = True
            if work._cleanup:
                await asyncio.gather(*tuple(work._cleanup))
            remaining = bool(work.requests)
            if not blocked:
                await work.finish(acquired[0])
            return blocked, remaining

        blocked, remaining = client.portal.call(refused)
        assert acquired and blocked and not remaining
        assert app.state.llm_client.client.call_metadata == []


def test_qualification_cannot_be_combined_with_a_trusted_true_callback(qualified_host, world):
    async def bypass():
        return True

    with pytest.raises(ValueError, match="^Host startup refused$"):
        app_for(qualified_host, world, provider_ready=bypass)
    assert qualified_host[3] == []


def test_cli_requires_the_pair_and_preflights_it_before_host_assembly(monkeypatch):
    from deploy import host_agent

    settings, binding, app = object(), object(), object()
    events = []
    monkeypatch.setattr(host_agent, "load_host_settings", lambda _: settings)

    def load(s, path, pin):
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        assert (
            s is settings
            and str(path).replace("\\", "/") == "/protected/binding.json"
            and pin == "a" * 64
        )
        events.append("binding")
        return binding

    def factory(s, **kwargs):
        assert s is settings and kwargs == dict(qualification=binding)
        events.append("factory")
        return app

    async def serve(value):
        assert value is app
        events.append("serve")

    monkeypatch.setattr(host_agent, "load_provider_binding", load, raising=False)
    monkeypatch.setattr(host_agent, "create_host_app", factory)
    monkeypatch.setattr(host_agent, "_serve", serve)
    assert (
        host_agent.main(
            [
                "--config",
                "/protected/host.json",
                "--qualification",
                "/protected/binding.json",
                "--qualification-sha256",
                "a" * 64,
            ]
        )
        == 0
    )
    assert events == ["binding", "factory", "serve"]


@pytest.mark.parametrize(
    "argument",
    [["--qualification", "/protected/binding.json"], ["--qualification-sha256", "a" * 64]],
)
def test_partial_cli_pair_refuses_before_reading_any_keys(monkeypatch, capsys, argument):
    from deploy import host_agent

    monkeypatch.setattr(
        host_agent, "load_host_settings", lambda _: pytest.fail("Read keys for invalid CLI pair")
    )
    assert host_agent.main(["--config", "/protected/host.json", *argument]) == 1
    assert capsys.readouterr().err == "Host startup refused\n"
