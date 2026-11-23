import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from agent.app import create_app
from agent.llm import LLMSettings
from agent.storefront_service import identity_config
from agent.tests.test_admission_http import policy


def test_import_does_not_build_default_app_or_read_ambient_provider():
    environment = dict(os.environ)
    environment.update({"LLM_PROVIDER": "invalid-ambient-provider", "LLM_MODEL": "invalid"})
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import agent.app as m; assert 'app' not in vars(m); print('lazy')",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "lazy"


def test_explicit_environment_ignores_ambient_settings_and_disables_test_routes(
    tmp_path, monkeypatch
):
    admission, _ = policy(tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "invalid")
    monkeypatch.setenv("EVAL_TEST_CLOCK", "1")
    monkeypatch.setenv("COPILOT_EVALUATION", "1")
    monkeypatch.setenv("COPILOT_PANEL_ORIGIN", "http://evil.test")
    before = dict(os.environ)
    values = {
        "LLM_PROVIDER": "scripted",
        "LLM_MODEL": "scripted-v1",
        "COPILOT_ENV": "production",
        "COPILOT_PANEL_ORIGIN": "https://app.scpilot.tech",
        "COPILOT_STORE_ORIGIN": "https://store.scpilot.tech",
        "COPILOT_STORE_PRIVATE_URL": "http://127.0.0.1:4000",
        "COPILOT_SERVICE_SECRET": "s" * 32,
    }
    app = create_app(environment=values, admission=admission)
    values["COPILOT_PANEL_ORIGIN"] = "https://changed.test"
    assert app.state.llm_settings.provider == "scripted"
    assert app.state.storefront_service.config["panel_origin"] == "https://app.scpilot.tech"
    assert "/__test/advance-time" not in {route.path for route in app.routes}
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        result = client.options(
            "/sessions",
            headers={"origin": "https://app.scpilot.tech", "access-control-request-method": "POST"},
        )
        assert result.headers["access-control-allow-origin"] == "https://app.scpilot.tech"
    assert dict(os.environ) == before


def test_explicit_identity_never_reads_local_identity_file(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Explicit identity read local fallback")

    monkeypatch.setattr(Path, "read_text", forbidden)
    assert identity_config({})["secret"] == ""


def test_legacy_environment_snapshot_follows_settings_loading(tmp_path, monkeypatch):
    import agent.app as module

    admission, _ = policy(tmp_path)
    monkeypatch.setenv("COPILOT_ENV", "local-rehearsal")
    monkeypatch.setenv("COPILOT_SERVICE_SECRET", "s" * 32)
    monkeypatch.setenv("COPILOT_PANEL_ORIGIN", "https://app.scpilot.tech")
    monkeypatch.setenv("COPILOT_STORE_ORIGIN", "https://store.scpilot.tech")

    def load(_):
        monkeypatch.setenv("COPILOT_ENV", "production")
        return LLMSettings(provider="scripted", model="scripted-v1")

    monkeypatch.setattr(module, "load_llm_settings", load)
    app = create_app(admission=admission, evaluation=True)
    with TestClient(app) as client:
        assert client.post("/step").status_code == 404


def test_explicit_service_mode_does_not_use_ambient_production_flag(monkeypatch):
    from agent.storefront_service import StorefrontService

    monkeypatch.setenv("COPILOT_ENV", "local-rehearsal")
    config = {
        "secret": "s" * 32,
        "panel_origin": "http://localhost:4100",
        "store_origin": "http://localhost:4000",
        "private_url": "http://127.0.0.1:4000",
    }
    import pytest

    with pytest.raises(ValueError):
        StorefrontService(
            config, environment={"COPILOT_ENV": "production"}
        ).validate_configuration()
    monkeypatch.setenv("COPILOT_ENV", "production")
    StorefrontService(
        config, environment={"COPILOT_ENV": "local-rehearsal"}
    ).validate_configuration()


def test_private_service_transport_never_routes_secret_through_environment_proxy(monkeypatch):
    import asyncio

    import httpx

    from agent.storefront_service import StorefrontService

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "")
    service = StorefrontService({"secret": "s" * 32})
    connection = service._connection()
    try:
        assert (
            connection._transport_for_url(
                httpx.URL("http://127.0.0.1:4000/__internal/shopper/validate")
            )
            is connection._transport
        )
    finally:
        asyncio.run(service.aclose())


def test_explicit_catalogue_environment_never_selects_ambient_encoder(monkeypatch):
    import asyncio

    from agent.catalogue_turn import configured_client

    monkeypatch.setenv("CATALOGUE_RANKING", "hybrid")
    monkeypatch.delenv("CATALOGUE_MODEL_CACHE", raising=False)
    client = asyncio.run(
        configured_client(
            {"secret": "s" * 32, "private_url": "http://127.0.0.1:4000"},
            environment={"CATALOGUE_RANKING": "lexical"},
        )
    )
    assert client.encoder is None


def test_sync_confirmation_disables_environment_proxy(monkeypatch):
    import httpx

    from agent.shopper_access import ShopperBinding
    from agent.storefront_service import StorefrontService

    def post(url, **options):
        assert url == "http://127.0.0.1:4000/__internal/confirmations"
        assert options.get("trust_env") is False
        return httpx.Response(201)

    monkeypatch.setattr(httpx, "post", post)
    service = StorefrontService(
        {
            "secret": "s" * 32,
            "panel_origin": "http://localhost:4100",
            "store_origin": "http://localhost:4000",
            "private_url": "http://127.0.0.1:4000",
        },
        environment={},
    )
    assert service.register_confirmation(
        ShopperBinding("owner", "generation"),
        "http://localhost:4000/",
        "token",
        "task",
        "checkout",
        1,
    )
