"""Injected host integration only: dummy keys, intercepted ASGI and Moto authority."""

import asyncio

import httpx
import pytest

from agent.admission.async_runtime import AsyncAdmissionPolicy
from agent.app import create_app
from agent.lifecycle.async_work import AsyncLifecycleWork
from agent.lifecycle.host_health import HostReadiness
from agent.lifecycle.readiness import _mac, readiness_reply
from agent.llm import LLMChunk, LLMSettings
from agent.tests.http_client import TestClient
from agent.tests.test_lifecycle_dynamodb import make_ready
from agent.tests.test_lifecycle_dynamodb import world as _world
from agent.tests.test_real_task import navigation_intent
from agent.tests.test_step import home_snapshot

world = _world
SECRET, RELEASE = b"offline-test-key-32-bytes-exact!!!", "a" * 64
NAMES = {"release", "storefront", "admission", "allowance", "provider"}


def headers():
    nonce = "b" * 64
    return {
        "x-copilot-generation": "1",
        "x-copilot-release": RELEASE,
        "x-copilot-nonce": nonce,
        "x-copilot-proof": _mac(SECRET, "request", RELEASE, 1, nonce),
    }


class Work:
    generation, failed = 1, False

    def __init__(self, *_):
        self.calls = []
        self.state = {"state": "starting", "generation": 1, "remaining_seconds": 10}

    async def initialize(self):
        self.calls.append("initialize")

    async def readiness_state(self):
        self.calls.append("readiness")
        return dict(self.state)

    async def maintain(self):
        await asyncio.Event().wait()

    async def close(self):
        self.calls.append("close")


def checks(callback=None):
    async def good():
        return True

    return {name: callback or good for name in NAMES}


def app_with(work, dependencies):
    return create_app(
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
        lifecycle=object(),
        lifecycle_work_factory=lambda *_: work,
        readiness_factory=lambda app, work: HostReadiness(work, SECRET, RELEASE, dependencies),
    )


def test_signed_asgi_health_requires_all_checks_and_keeps_liveness_separate():
    work = Work()
    app = app_with(work, checks())
    with TestClient(app) as client:
        assert work.calls == ["initialize"]
        assert client.get("/health").json() == {"status": "ok", "service": "agent"}
        result = client.get("/health", headers=headers())
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json() == readiness_reply(
            headers(), secret=SECRET, release=RELEASE, generation=1, ready=True
        )
        assert work.calls == ["initialize", "readiness", "readiness"]
    assert work.calls[-1] == "close"


@pytest.mark.parametrize("bad", [False, 1, "true", None, RuntimeError("private detail")])
def test_dependency_failure_is_signed_false_without_error_disclosure(bad):
    async def unavailable():
        if isinstance(bad, Exception):
            raise bad
        return bad

    dependencies = checks()
    dependencies["provider"] = unavailable
    with TestClient(app_with(Work(), dependencies)) as client:
        result = client.get("/health", headers=headers())
        assert result.status_code == 200
        assert result.json()["ready"] is False
        assert "private detail" not in result.text


def test_invalid_proof_never_reaches_authority_or_dependencies():
    async def forbidden():
        pytest.fail("Invalid proof reached dependency")

    work = Work()
    with TestClient(app_with(work, checks(forbidden))) as client:
        bad = headers() | {"x-copilot-proof": "0" * 64}
        assert client.get("/health", headers=bad).status_code == 403
        assert work.calls == ["initialize"]


@pytest.mark.parametrize("state", ["stopping", "stopped", "failed"])
def test_authority_change_while_dependencies_await_invalidates_ready(state):
    work = Work()

    async def changed():
        await asyncio.sleep(0)
        work.state["state"] = state
        return True

    dependencies = checks()
    dependencies["provider"] = changed
    with TestClient(app_with(work, dependencies)) as client:
        assert client.get("/health", headers=headers()).json()["ready"] is False


def test_readiness_requires_exact_explicit_async_dependencies():
    with pytest.raises(ValueError):
        HostReadiness(Work(), SECRET, RELEASE, {})
    with pytest.raises(ValueError):
        HostReadiness(Work(), SECRET, RELEASE, {name: lambda: True for name in NAMES})


def test_remote_http_admission_and_work_are_awaited_and_closed(world):
    _, store, _, code, _, _ = world
    life = make_ready(world)
    admission = AsyncAdmissionPolicy(store)
    app = create_app(
        admission=admission,
        lifecycle=life,
        lifecycle_work_factory=AsyncLifecycleWork,
        llm_settings=LLMSettings(provider="scripted", model="scripted-v1"),
    )
    with TestClient(app) as client:
        assert client.post("/sessions").status_code == 403
        assert client.post("/shopper/admission", json={"code": code}).json()["admitted"] is True
        sid = client.post("/sessions").json()["session_id"]
        assert client.get(f"/sessions/{sid}/state?tab_id=a").status_code == 200
        assert app.state.lifecycle_work.generation == 1
    assert app.state.lifecycle_work._closed
    assert admission._io._closed


def test_async_revocation_during_model_suppresses_action(world):
    _, store, invitation, code, _, _ = world
    admission = AsyncAdmissionPolicy(store)

    class Model:
        calls = 0

        async def complete(self, request):
            self.calls += 1
            await admission._io.call(store.revoke, invitation)
            yield LLMChunk(text=navigation_intent("navigate", "cart"))

    model = Model()
    app = create_app(
        admission=admission,
        llm_client=model,
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
        assert model.calls == 1
        assert "event: action" not in client.get(f"/sessions/{sid}/events?once=true").text


def test_readiness_rechecks_generation_after_await():
    async def scenario():
        work = Work()

        async def changed():
            work.state["generation"] = 2
            return True

        app = app_with(work, checks(changed))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agent"
        ) as client:
            assert (await client.get("/health", headers=headers())).json()["ready"] is False

    asyncio.run(scenario())


def test_slow_readiness_times_out_without_cancelling_authority_or_activity():
    async def slow():
        await asyncio.Event().wait()

    with TestClient(app_with(Work(), checks(slow))) as client:
        assert client.get("/health", headers=headers()).json()["ready"] is False


def test_readiness_deadline_does_not_await_slow_cancellation_cleanup():
    async def scenario():
        cleaning, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def slow():
            calls.append(True)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleaning.set()
                await release.wait()
                raise

        dependencies = checks()
        dependencies["provider"] = slow
        health = HostReadiness(Work(), SECRET, RELEASE, dependencies)
        task = asyncio.create_task(health.response(headers()))
        try:
            done, _ = await asyncio.wait({task}, timeout=2)
            assert task in done, "Readiness waited for dependency cancellation cleanup"
            assert task.result().status_code == 200
            await cleaning.wait()
            assert (await health.response(headers())).body == task.result().body
            assert len(calls) == 1, "Outstanding cleanup must retain aggregate capacity"
        finally:
            release.set()
            await task
        await health.close()

    asyncio.run(scenario())


def test_readiness_rechecks_local_fence_after_aggregate_task_completion():
    import json

    class FailedBetween(Work):
        async def readiness_state(self):
            state = await super().readiness_state()
            if self.calls.count("readiness") == 2:
                asyncio.get_running_loop().call_soon(setattr, self, "failed", True)
            return state

    async def scenario():
        work = FailedBetween()
        health = HostReadiness(work, SECRET, RELEASE, checks())
        try:
            result = await health.response(headers())
            assert work.failed
            assert json.loads(result.body)["ready"] is False
        finally:
            await health.close()

    asyncio.run(scenario())


def test_failed_lifespan_initialization_still_drains_work():
    class Failed(Work):
        async def initialize(self):
            raise RuntimeError("unavailable")

    work = Failed()
    with pytest.raises(RuntimeError, match="unavailable"), TestClient(app_with(work, checks())):
        pytest.fail("Must not serve with uninitialized work")
    assert work.calls == ["close"]


def test_owner_change_during_lifecycle_await_cannot_create_session():
    class Changed(Work):
        async def check(self):
            next(iter(app.state.shopper_access.records.values())).shopper = None

        async def begin(self):
            return "token"

        async def finish(self, *_, **__):
            pass

    work = Changed()
    app = app_with(work, checks())
    with TestClient(app) as client:
        assert client.post("/sessions").status_code == 409
