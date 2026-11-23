import pytest
from fastapi.testclient import TestClient

from agent.app import create_app
from agent.llm import LLMSettings, ScriptedLLMClient
from agent.storefront_service import StorefrontService, identity_config
from agent.tests.test_admission_http import policy


def test_production_excludes_evaluation_routes_even_when_requested(monkeypatch, tmp_path):
    monkeypatch.setenv("COPILOT_ENV", "production")
    monkeypatch.setenv("COPILOT_PANEL_ORIGIN", "https://app.scpilot.tech")
    monkeypatch.setenv("COPILOT_STORE_ORIGIN", "https://store.scpilot.tech")
    monkeypatch.setenv("COPILOT_SERVICE_SECRET", "test-only-service-credential-for-public-runtime")
    monkeypatch.setenv("COPILOT_EVALUATION", "1")
    app = create_app(
        evaluation=True,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
        admission=policy(tmp_path)[0],
    )
    client = TestClient(app)
    assert client.post("/step", json={}).status_code == 404
    assert client.post("/__test/advance-time", json={"seconds": 1}).status_code == 404


def test_production_requires_admission_even_for_scripted_rehearsals(monkeypatch):
    monkeypatch.setenv("COPILOT_ENV", "production")
    with pytest.raises(ValueError, match="admission"):
        create_app(llm_settings=LLMSettings(provider="scripted", model="scripted-v1"))


def test_production_requires_explicit_service_secret(monkeypatch):
    monkeypatch.setenv("COPILOT_ENV", "production")
    monkeypatch.delenv("COPILOT_SERVICE_SECRET", raising=False)
    with pytest.raises(ValueError, match="production"):
        identity_config()


def test_production_real_provider_cannot_start_without_durable_allowance(monkeypatch):
    monkeypatch.setenv("COPILOT_ENV", "production")
    monkeypatch.setenv("COPILOT_SERVICE_SECRET", "test-only-production-service-secret")
    for name in list(__import__("os").environ):
        if name.startswith("INFERENCE_"):
            monkeypatch.delenv(name)
    with pytest.raises(ValueError, match="inference allowance"):
        create_app(
            llm_settings=LLMSettings(provider="nvidia", model="test-model"),
            llm_client=ScriptedLLMClient(),
        )


@pytest.mark.parametrize(
    "origin",
    [
        "https://APP.scpilot.tech",
        "https://app.scpilot.tech:443",
        "https://app.scpilot.tech\\evil",
        "https://app%2fscpilot.tech",
    ],
)
def test_public_service_origin_is_canonical(origin):
    config = {
        "secret": "test-only-service-secret-long-enough",
        "panel_origin": origin,
        "store_origin": "https://store.scpilot.tech",
        "private_url": "http://127.0.0.1:4000",
    }
    with pytest.raises(ValueError):
        StorefrontService(config).validate_configuration()
