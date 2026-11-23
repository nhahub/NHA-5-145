from time import time

import pytest
from fastapi.testclient import TestClient as RawClient

from agent.admission.runtime import AdmissionPolicy
from agent.admission.store import InvitationStore
from agent.app import create_app
from agent.llm import LLMChunk, LLMSettings
from agent.sessions import SessionStore
from agent.tests.http_client import TestClient
from agent.tests.test_real_task import navigation_intent
from agent.tests.test_sessions import parse_sse
from agent.tests.test_step import home_snapshot


def policy(tmp_path, **changes):
    path = tmp_path / "admission.sqlite"
    clock = [time()]
    store = InvitationStore(path, InvitationStore.initialize(path), clock=lambda: clock[0])
    return AdmissionPolicy(store, **changes), clock


def test_code_admission_preserves_ownership_and_revocation_blocks_all_task_routes(tmp_path):
    admission, clock = policy(tmp_path)
    invitation, code = admission.store.issue(
        clock[0] - 1, clock[0] + 100, redemptions=2, sessions=4
    )
    app = create_app(
        admission=admission, llm_settings=LLMSettings(provider="scripted", model="scripted-v1")
    )
    with TestClient(app) as a, TestClient(app) as b:
        assert a.post("/sessions").status_code == 403
        assert a.get("/shopper/admission").json() == {"required": True, "admitted": False}
        assert a.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = a.post("/sessions").json()["session_id"]
        assert b.post("/shopper/admission", json={"code": code}).status_code == 200
        assert b.get(f"/sessions/{sid}/state?tab_id=b").status_code == 404
        result = a.post(
            f"/sessions/{sid}/messages", json={"text": "Open my cart", "snapshot": home_snapshot()}
        )
        assert result.status_code == 202
        assert any(
            e["event"] == "action"
            for e in parse_sse(a.get(f"/sessions/{sid}/events?once=true").text)
        )
        admission.store.revoke(invitation)
        for path, payload in (
            (f"/sessions/{sid}/messages", {}),
            (f"/sessions/{sid}/action-results", {}),
        ):
            assert a.post(path, json=payload).status_code == 403
        assert a.get(f"/sessions/{sid}/events?once=true").status_code == 403
        assert a.post(f"/sessions/{sid}/stop").status_code == 202


def test_expiry_and_durable_session_quota_apply_before_task_creation(tmp_path):
    admission, clock = policy(tmp_path)
    _, code = admission.store.issue(clock[0] - 1, clock[0] + 10, redemptions=1, sessions=1)
    app = create_app(
        admission=admission, llm_settings=LLMSettings(provider="scripted", model="scripted-v1")
    )
    with TestClient(app) as client:
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        assert client.post("/sessions").status_code == 201
        assert client.post("/sessions").status_code == 429
        clock[0] += 11
        assert client.get("/shopper/admission").json()["admitted"] is False
        assert client.post("/sessions").status_code == 403


def test_global_rate_survives_new_cookies_and_chunked_body_limit(tmp_path):
    admission, _ = policy(tmp_path, global_rate=4, browser_rate=4, maximum_bytes=128)
    app = create_app(
        admission=admission,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
        environment={"COPILOT_SERVICE_SECRET": "admission-http-test-secret-00000000"},
    )
    with RawClient(app) as client:
        oversized = client.post("/shopper/bootstrap", content=iter([b"x" * 80, b"y" * 80]))
        assert oversized.status_code == 413
        for _ in range(3):
            client.cookies.clear()
            assert (
                client.post(
                    "/shopper/bootstrap", headers={"origin": "http://localhost:4100"}
                ).status_code
                == 200
            )
        client.cookies.clear()
        assert (
            client.post(
                "/shopper/bootstrap", headers={"origin": "http://localhost:4100"}
            ).status_code
            == 429
        )
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("revoke", [False, True])
def test_revocation_during_provider_call_suppresses_action_and_further_model_work(tmp_path, revoke):
    admission, clock = policy(tmp_path)
    invitation, code = admission.store.issue(
        clock[0] - 1, clock[0] + 100, redemptions=1, sessions=2
    )
    store = SessionStore()

    class Model:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            if revoke:
                admission.store.revoke(invitation)
            yield LLMChunk(text=navigation_intent("navigate", "cart"))

    model = Model()
    app = create_app(
        session_store=store,
        admission=admission,
        llm_settings=LLMSettings(provider="groq", model="test"),
        llm_client=model,
    )
    with TestClient(app) as client:
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = client.post("/sessions").json()["session_id"]
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={"text": "Open my cart", "snapshot": home_snapshot()},
            ).status_code
            == 202
        )
        assert model.calls == 1
        assert any(e.event == "action" for e in store.events_after(sid, 0)) is (not revoke)
        if revoke:
            assert (
                client.post(
                    f"/sessions/{sid}/messages", json={"text": "Again", "snapshot": home_snapshot()}
                ).status_code
                == 403
            )
        assert model.calls == 1


def test_revocation_during_stream_ownership_validation_cannot_deliver_action(tmp_path):
    admission, clock = policy(tmp_path)
    invitation, code = admission.store.issue(
        clock[0] - 1, clock[0] + 100, redemptions=1, sessions=2
    )
    sessions = SessionStore()
    app = create_app(
        session_store=sessions,
        admission=admission,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
    )
    with TestClient(app) as client:
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = client.post("/sessions").json()["session_id"]
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={"text": "Open my cart", "snapshot": home_snapshot()},
            ).status_code
            == 202
        )
        action = next(e for e in sessions.events_after(sid, 0) if e.event == "action")
        original = app.state.storefront_service.validate
        calls = [0]

        async def revoke_during_validation(binding):
            valid = await original(binding)
            calls[0] += 1
            if calls[0] == 3:
                admission.store.revoke(invitation)
            return valid

        app.state.storefront_service.validate = revoke_during_validation
        response = client.get(f"/sessions/{sid}/events?once=true&after={action.id - 1}")
        assert response.status_code == 200 and calls[0] == 3
        assert "event: action" not in response.text
        assert "shopper_reset" in response.text


@pytest.mark.parametrize("limits", [{"browser_rate": 8}, {"global_rate": 8, "browser_rate": 8}])
def test_owner_stop_has_reserved_access_when_regular_browser_rate_exhausted(tmp_path, limits):
    admission, clock = policy(tmp_path, **limits)
    _, code = admission.store.issue(clock[0] - 1, clock[0] + 100, redemptions=1, sessions=2)
    app = create_app(
        admission=admission, llm_settings=LLMSettings(provider="scripted", model="scripted-v1")
    )
    with TestClient(app) as client:
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = client.post("/sessions").json()["session_id"]
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={"text": "Open my cart", "snapshot": home_snapshot()},
            ).status_code
            == 202
        )
        for _ in range(4):
            client.get("/shopper/admission")
        assert client.get("/shopper/admission").status_code == 429
        assert client.post(f"/sessions/{sid}/stop").status_code == 202
        assert (
            client.post(f"/sessions/{sid}/stop", headers={"x-csrf-token": "wrong"}).status_code
            == 403
        )
