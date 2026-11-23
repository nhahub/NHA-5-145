"""Public lifecycle authority with real durable state and a fake designated host."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from agent.admission.store import AdmissionDenied, InvitationStore
from agent.lifecycle import Lifecycle, LifecycleUnavailable


class Host:
    """EC2-shaped fake: commands return before boot; readiness is independent."""

    def __init__(self):
        self.state, self.healthy = "stopped", False
        self.starts, self.stops = [], []

    def observe(self):
        return self.state, self.healthy

    def start(self, generation):
        if generation not in self.starts:
            self.starts.append(generation)
        self.state = "pending"

    def stop(self, generation):
        if generation not in self.stops:
            self.stops.append(generation)
        self.state, self.healthy = "stopped", False


@pytest.fixture
def world(tmp_path):
    now = [1000.0]
    invitations = InvitationStore(
        tmp_path / "invitations.sqlite",
        InvitationStore.initialize(tmp_path / "invitations.sqlite"),
        clock=lambda: now[0],
    )
    invitation, code = invitations.issue(999, 20000, redemptions=5, sessions=10)
    path = tmp_path / "lifecycle.sqlite"
    identity = Lifecycle.initialize(path)
    life = Lifecycle(path, identity, invitations, clock=lambda: now[0])
    return now, invitations, invitation, code, life, Host()


def ready(world):
    now, _, _, code, life, host = world
    life.wake(code)
    life.tick(host)
    host.state, host.healthy = "running", True
    life.tick(host)
    assert life.status()["state"] == "ready"
    return now, life, host


def test_only_valid_invitations_wake_and_concurrent_requests_coalesce(world):
    now, invitations, invitation, code, life, host = world
    assert life.status()["state"] == "stopped"
    with pytest.raises(AdmissionDenied):
        life.wake("invalid-code")
    assert host.starts == []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: life.wake(code), range(8)))
    assert {r["generation"] for r in results} == {1}
    life.tick(host)
    assert host.starts == [1]
    assert life.status()["state"] == "starting"
    # A running VM alone is not application readiness.
    host.state = "running"
    life.tick(host)
    assert life.status()["state"] == "starting"
    invitations.revoke(invitation)
    with pytest.raises(AdmissionDenied):
        life.wake(code)
    now[0] += 301
    life.tick(host)
    assert life.status()["state"] == "failed"
    assert host.stops == [1]


def test_idle_drain_rechecks_work_and_committed_stop_fences_arrivals(world):
    now, life, host = ready(world)
    now[0] += 3600
    life.tick(host)
    assert life.status()["state"] == "draining"
    token = life.begin_work(meaningful=True)
    life.tick(host)
    assert life.status()["state"] == "ready"
    assert not host.stops
    # Accepted/queued work is protected even beyond the inactivity threshold.
    for _ in range(121):
        now[0] += 30
        life.renew_work(token)
        life.tick(host)
    assert not host.stops
    life.end_work(token)
    life.tick(host)
    assert life.status()["state"] == "draining"
    now[0] += 5
    life.tick(host)
    assert life.status()["state"] == "stopping"
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(meaningful=True)
    life.tick(host)
    assert host.stops == [1]
    life.tick(host)
    assert life.status()["state"] == "stopped"


def test_restart_stale_leases_deadline_and_missing_storage_fail_closed(world):
    now, _, _, code, life, host = world
    life.wake(code)
    life.tick(host)
    # Reopen while booting, with the same external state; no renewed deadline.
    reopened = Lifecycle(life.path, life.identity, life.invitations, clock=life.clock)
    now[0] += 301
    reopened.tick(host)
    assert reopened.status()["state"] == "failed"
    with pytest.raises(LifecycleUnavailable):
        reopened.wake(code)
    now[0] += 61
    reopened.tick(host)  # Cleanup must be observed stopped before another boot.
    reopened.wake(code)
    reopened.tick(host)
    host.state, host.healthy = "running", True
    reopened.tick(host)
    token = reopened.begin_work(meaningful=True)
    now[0] += 3601  # Crashed worker cannot retain a lease forever.
    with pytest.raises(LifecycleUnavailable):
        reopened.renew_work(token)
    reopened.tick(host)
    assert reopened.status()["state"] == "draining"
    life.path.unlink()
    with pytest.raises(LifecycleUnavailable):
        reopened.wake(code)
    assert not life.path.exists()


def test_manual_prewarming_keeps_idle_stop_and_does_not_extend_invitation(world):
    now, invitations, _, code, life, host = world
    life.manual_start()
    life.tick(host)
    host.state, host.healthy = "running", True
    life.tick(host)
    now[0] = 20001
    with pytest.raises(AdmissionDenied):
        life.wake(code)
    assert not invitations.allowed("new-browser")
    life.tick(host)
    assert life.status()["state"] == "draining"
    now[0] += 5
    life.tick(host)
    life.tick(host)
    assert host.stops == [1]


def test_waiting_http_never_wakes_on_visits_and_bounds_secret_bearing_requests(world):
    from fastapi.testclient import TestClient

    from agent.lifecycle.http import create_waiting_app

    _, _, _, code, life, host = world
    with TestClient(create_waiting_app(life, origin="http://testserver")) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert page.headers["cache-control"] == "no-store"
        assert "content-security-policy" in page.headers
        assert client.get("/status").json()["state"] == "stopped"
        assert client.get("/wake?code=" + code).status_code == 405
        assert client.post("/wake", json={"code": code}).status_code == 403
        headers = {"origin": "http://testserver"}
        assert client.post("/wake", json={"code": "wrong"}, headers=headers).status_code == 403
        response = client.post("/wake", json={"code": code}, headers=headers)
        assert response.status_code == 202
        assert code not in response.text
        assert host.starts == []  # HTTP returns before any EC2 boot operation.
        life.tick(host)
        assert host.starts == [1]
        assert client.post("/wake", content=b"x" * 1025, headers=headers).status_code == 413
        for _ in range(12):
            response = client.post("/wake", json={"code": "wrong"}, headers=headers)
        assert response.status_code == 429
    assert code not in life.path.read_bytes().decode("latin1")
    with TestClient(create_waiting_app(life, origin="http://testserver")) as client:
        assert client.post("/wake", json={"code": code}, headers=headers).status_code == 429


def test_agent_activity_and_pending_actions_serialize_with_shutdown(world):
    from agent.admission.runtime import AdmissionPolicy
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_step import home_snapshot

    now, life, host = ready(world)
    _, invitations, _, code, _, _ = world
    app = create_app(
        admission=AdmissionPolicy(invitations),
        lifecycle=life,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
    )
    with TestClient(app) as client:
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = client.post("/sessions").json()["session_id"]
        now[0] += 3599
        assert client.get("/health").status_code == 200
        assert client.get(f"/sessions/{sid}/state?tab_id=a").status_code == 200
        now[0] += 1
        life.tick(host)
        assert life.status()["state"] == "draining"
        # Explicit admitted interaction wins before stop commitment.
        assert client.post("/shopper/activity").status_code == 204
        assert life.status()["state"] == "ready"
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={"text": "Open my cart", "snapshot": home_snapshot()},
            ).status_code
            == 202
        )
        # A delivered Action still protects the host after its HTTP request ends.
        now[0] += 30
        app.state.lifecycle_work.refresh()
        now[0] += 3570
        # Renewal after a crashed worker's deadline cannot silently reacquire authority.
        app.state.lifecycle_work.refresh()
        assert client.post("/shopper/activity").status_code == 503
        life.tick(host)
        assert life.status()["state"] == "draining"
        now[0] += 5
        life.tick(host)
        assert life.status()["state"] == "stopping"
        assert client.post("/sessions").status_code == 503


def test_admitted_model_and_delivered_action_keep_work_lease_until_stopped(world):
    from agent.admission.runtime import AdmissionPolicy
    from agent.app import create_app
    from agent.llm import LLMChunk, LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_real_task import navigation_intent
    from agent.tests.test_step import home_snapshot

    now, life, host = ready(world)
    _, invitations, _, code, _, _ = world

    class Model:
        async def complete(self, request):
            for _ in range(121):
                now[0] += 30
                app.state.lifecycle_work.refresh()
                life.tick(host)
            assert not host.stops
            yield LLMChunk(text=navigation_intent("navigate", "cart"))

    app = create_app(
        admission=AdmissionPolicy(invitations),
        lifecycle=life,
        llm_client=Model(),
        llm_settings=LLMSettings(provider="groq", model="test"),
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
        for _ in range(121):
            now[0] += 30
            app.state.lifecycle_work.refresh()
            life.tick(host)
        assert not host.stops
        assert client.post(f"/sessions/{sid}/stop").status_code == 202
        app.state.lifecycle_work.refresh()
        life.tick(host)
        assert life.status()["state"] == "draining"


def test_shutdown_commit_and_new_request_have_one_serialized_winner(world):
    now, life, host = ready(world)
    now[0] += 3600
    life.tick(host)
    now[0] += 5

    def accept():
        try:
            return life.begin_work(meaningful=True)
        except LifecycleUnavailable:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        arrival = pool.submit(accept)
        shutdown = pool.submit(life.tick, host)
        token = arrival.result()
        shutdown.result()
    if token:
        assert life.status()["state"] == "ready"
        life.end_work(token)
    else:
        assert life.status()["state"] == "stopping"
    assert host.stops == []  # stop is a subsequent committed command


def test_an_old_host_generation_cannot_admit_work_after_a_fresh_start(world):
    now, life, host = ready(world)
    old_generation = life.status()["generation"]
    now[0] += 3600
    life.tick(host)
    now[0] += 5
    life.tick(host)
    life.tick(host)
    life.tick(host)
    life.manual_start()
    life.tick(host)
    host.state, host.healthy = "running", True
    life.tick(host)
    with pytest.raises(LifecycleUnavailable):
        life.begin_work(meaningful=True, generation=old_generation)


def test_slow_health_observation_does_not_block_admitted_work(world):
    import threading

    _, life, host = ready(world)
    entered, release = threading.Event(), threading.Event()

    class SlowHost(Host):
        def observe(self):
            entered.set()
            assert release.wait(5)
            return host.observe()

    with ThreadPoolExecutor(max_workers=2) as pool:
        observation = pool.submit(life.tick, SlowHost())
        assert entered.wait(2)
        try:
            token = life.begin_work(meaningful=True)
            life.renew_work(token)
            life.end_work(token)
        finally:
            release.set()
        observation.result()


def test_readiness_is_withdrawn_on_health_failure_without_stopping_active_work(world):
    _, life, host = ready(world)
    token = life.begin_work()
    host.healthy = False
    life.tick(host)
    assert life.status()["state"] == "unhealthy"
    life.renew_work(token)
    with pytest.raises(LifecycleUnavailable):
        life.begin_work()
    assert host.stops == []
    host.healthy = True
    life.tick(host)
    assert life.status()["state"] == "ready"
    life.end_work(token)


def test_failed_stop_is_bounded_and_never_reported_as_stopped(world):
    now, life, host = ready(world)
    now[0] += 3600
    life.tick(host)
    now[0] += 5
    life.tick(host)
    calls = []

    def fail_stop(generation):
        calls.append(generation)
        raise OSError("control unavailable")

    host.stop = fail_stop
    for _ in range(100):
        now[0] += 1
        life.tick(host)
    assert len(calls) == 3
    assert life.status()["state"] == "failed"
    with pytest.raises(LifecycleUnavailable):
        life.manual_start()


def test_shutdown_during_awaited_ownership_check_cannot_deliver_action(world):
    from fastapi import Request

    from agent.admission.runtime import AdmissionPolicy
    from agent.app import create_app
    from agent.llm import LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_step import home_snapshot

    now, life, host = ready(world)
    _, invitations, _, code, _, _ = world
    app = create_app(
        admission=AdmissionPolicy(invitations),
        lifecycle=life,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
    )

    @app.get("/authority-probe")
    async def authority_probe(request: Request):
        return {"authorized": await request.state.shopper_authorized()}

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
        original = app.state.storefront_service.validate
        calls = [0]

        async def commit_stop_during_validation(binding):
            valid = await original(binding)
            calls[0] += 1
            if calls[0] == 2:
                now[0] += 3601
                life.tick(host)
                now[0] += 5
                life.tick(host)
                assert life.status()["state"] == "stopping"
            return valid

        app.state.storefront_service.validate = commit_stop_during_validation
        result = client.get("/authority-probe")
        assert calls[0] == 2
        assert result.json() == {"authorized": False}
        result = client.get(f"/sessions/{sid}/events?once=true")
        assert result.status_code == 503


def test_failed_async_host_stop_is_unknown_not_stopped(monkeypatch, tmp_path):
    import time

    from deploy.lifecycle import LocalHost

    class Runtime:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            return self

        def check_health(self):
            pass

        def close(self):
            raise OSError("could not stop owned host")

    monkeypatch.setattr("deploy.lifecycle.ReleaseRuntime", Runtime)
    host = LocalHost("release", "config", tmp_path)
    try:
        host.start(1)
        deadline = time.monotonic() + 2
        while host.observe()[0] != "running" and time.monotonic() < deadline:
            time.sleep(0.01)
        host.stop(1)
        while host.observe()[0] == "stopping" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert host.observe() == ("unknown", False)
    finally:
        with pytest.raises(OSError):
            host.close()


def test_health_loss_during_an_admitted_model_call_preserves_its_work_lease(world):
    from agent.admission.runtime import AdmissionPolicy
    from agent.app import create_app
    from agent.llm import LLMChunk, LLMSettings
    from agent.tests.http_client import TestClient
    from agent.tests.test_real_task import navigation_intent
    from agent.tests.test_step import home_snapshot

    now, life, host = ready(world)
    _, invitations, _, code, _, _ = world

    class Model:
        async def complete(self, request):
            host.healthy = False
            life.tick(host)
            assert life.status()["state"] == "unhealthy"
            for _ in range(121):
                now[0] += 30
                app.state.lifecycle_work.refresh()
                life.tick(host)
            assert life.status()["state"] == "unhealthy"
            assert not host.stops
            host.healthy = True
            life.tick(host)
            yield LLMChunk(text=navigation_intent("navigate", "cart"))

    app = create_app(
        admission=AdmissionPolicy(invitations),
        lifecycle=life,
        llm_client=Model(),
        llm_settings=LLMSettings(provider="groq", model="test"),
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
        assert life.status()["state"] == "ready"
        assert not host.stops


def test_degraded_readiness_between_task_creation_and_lease_handoff_keeps_work(world):
    from agent.lifecycle.work import LifecycleWork
    from agent.schemas import Snapshot
    from agent.sessions import SessionStore
    from agent.tests.test_step import home_snapshot

    now, life, host = ready(world)
    sessions = SessionStore()
    work = LifecycleWork(life, sessions)
    token = work.begin()
    sid = sessions.create().session_id
    sessions.begin_interpretation(sid, "Open my cart", Snapshot.model_validate(home_snapshot()))
    host.healthy = False
    life.tick(host)
    for _ in range(121):
        now[0] += 30
        work.refresh()
        life.tick(host)
    assert life.status()["state"] == "unhealthy"
    assert host.stops == []
    work.finish(token)
    work.close()
