"""Controlled model timing through the real Agent HTTP/inference boundary."""

from decimal import Decimal

import pytest

from agent.admission.runtime import AdmissionPolicy
from agent.admission.store import InvitationStore
from agent.inference.ledger import AllowanceLedger
from agent.tests.http_client import TestClient
from agent.tests.test_cart_task import snapshot
from agent.tests.test_inference_runtime import configure
from eval.capacity.application import capacity_app


@pytest.mark.parametrize("telemetry_failure", [False, True])
def test_capacity_fixture_uses_real_admission_and_durable_inference_not_network(
    tmp_path,
    monkeypatch,
    telemetry_failure,
):
    import time

    ledger_path = tmp_path / "allowance.sqlite"
    ledger_id = AllowanceLedger.initialize(ledger_path, Decimal("1"))
    configure(monkeypatch, ledger_path, ledger_id)
    invites_path = tmp_path / "admission.sqlite"
    invites = InvitationStore(invites_path, InvitationStore.initialize(invites_path))
    _, code = invites.issue(time.time() - 1, time.time() + 100, redemptions=1, sessions=2)
    if telemetry_failure:

        def broken_observer(*_args):
            raise OSError("Telemetry unavailable")

        monkeypatch.setattr(
            "eval.capacity.application.DelayedDecision.observe_queue", broken_observer
        )
    app = capacity_app(tmp_path, delay_seconds=0.01, admission=AdmissionPolicy(invites))
    with TestClient(app) as client:
        assert client.post("/sessions").status_code == 403
        assert client.post("/shopper/admission", json={"code": code}).status_code == 200
        sid = client.post("/sessions").json()["session_id"]
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={
                    "text": "fixture shopping request",
                    "snapshot": snapshot().model_dump(by_alias=True, exclude_none=True),
                },
            ).status_code
            == 202
        )
        from agent.tests.test_sessions import parse_sse

        events = parse_sse(client.get(f"/sessions/{sid}/events?once=true").text)
        assert (
            next(e["data"]["action"]["type"] for e in events if e["event"] == "action") == "click"
        )
        ledger = AllowanceLedger(ledger_path, ledger_id)
        assert ledger.status()["attempts"] == 1
        import json

        measured = json.loads((tmp_path / "provider.json").read_text())
        if telemetry_failure:
            assert measured["queue"] == []
        else:
            assert len(measured["queue"]) == 1
            assert measured["queue"][0]["outcome"] == "acquired"
            assert measured["queue"][0]["milliseconds"] >= 0

        assert ledger.status()["uncertain"] == 1
        ledger.set_enabled(False)
        assert client.post(f"/sessions/{sid}/stop").status_code == 202
        assert (
            client.post(
                f"/sessions/{sid}/messages",
                json={
                    "text": "fixture shopping request",
                    "snapshot": snapshot().model_dump(by_alias=True, exclude_none=True),
                },
            ).status_code
            == 202
        )
        assert "event: action" not in client.get(f"/sessions/{sid}/events?once=true&after=5").text
        assert ledger.status()["attempts"] == 1


def test_five_inference_requests_and_actions_block_idle_stop_then_drain_is_fenced(
    tmp_path,
    monkeypatch,
):
    import asyncio
    import json

    import httpx

    from agent.admission.runtime import AdmissionPolicy
    from agent.app import create_app
    from agent.lifecycle import Lifecycle
    from agent.llm import LLMChunk, LLMSettings
    from agent.tests.http_client import FakeStorefrontService
    from agent.tests.test_lifecycle import Host

    ledger_path = tmp_path / "combined-allowance.sqlite"
    ledger_id = AllowanceLedger.initialize(ledger_path, Decimal("1"))
    configure(monkeypatch, ledger_path, ledger_id)
    monkeypatch.setenv("INFERENCE_MAX_ACTIVE", "2")
    monkeypatch.setenv("INFERENCE_MAX_WAITING", "3")
    monkeypatch.setenv("INFERENCE_WAIT_SECONDS", "8")
    now = [1000.0]
    path = tmp_path / "combined-admission.sqlite"
    invites = InvitationStore(path, InvitationStore.initialize(path), clock=lambda: now[0])
    policy = AdmissionPolicy(invites)
    life_path = tmp_path / "combined-lifecycle.sqlite"
    life = Lifecycle(life_path, Lifecycle.initialize(life_path), invites, clock=lambda: now[0])
    host = Host()
    life.manual_start()
    life.tick(host)
    host.state, host.healthy = "running", True
    life.tick(host)

    async def scenario():
        gate = asyncio.Event()

        class Model:
            calls = 0

            async def complete(self, request):
                self.calls += 1
                await gate.wait()
                yield LLMChunk(
                    text=json.dumps(
                        {
                            "v": 8,
                            "language": "en",
                            "dialect": "english",
                            "intent": "cart_edit",
                            "cart_operation": "add",
                            "cart_source": "fixture shopping request",
                            "product_id": "shoe-09",
                            "constraints": {},
                            "missing_fields": [],
                            "needs_clarification": False,
                        }
                    )
                )

        model = Model()
        app = create_app(
            admission=policy,
            lifecycle=life,
            llm_client=model,
            llm_settings=LLMSettings(provider="groq", model="test-model"),
        )
        service = FakeStorefrontService()
        app.state.storefront_service = service
        clients = []
        async with app.router.lifespan_context(app):
            try:
                sessions = []
                for _ in range(5):
                    _, code = invites.issue(999, 20000, redemptions=2, sessions=2)
                    client = httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                    )
                    clients.append(client)
                    client.headers["origin"] = "http://localhost:4100"
                    bootstrap = await client.post("/shopper/bootstrap")
                    client.headers["x-csrf-token"] = bootstrap.json()["csrf"]
                    challenge = (await client.post("/shopper/challenge")).json()["challenge"]
                    assert (
                        await client.post(
                            "/shopper/link",
                            json={"challenge": challenge, "ticket": service.issue()},
                        )
                    ).status_code == 200
                    assert (
                        await client.post("/shopper/admission", json={"code": code})
                    ).status_code == 200
                    sessions.append((await client.post("/sessions")).json()["session_id"])
                requests = [
                    asyncio.create_task(
                        client.post(
                            f"/sessions/{sid}/messages",
                            json={
                                "text": "fixture shopping request",
                                "snapshot": snapshot().model_dump(by_alias=True, exclude_none=True),
                            },
                        )
                    )
                    for client, sid in zip(clients, sessions, strict=True)
                ]
                for _ in range(100):
                    if model.calls == 2:
                        break
                    await asyncio.sleep(0.01)
                assert model.calls == 2
                for _ in range(121):
                    now[0] += 30
                    app.state.lifecycle_work.refresh()
                    life.tick(host)
                    await asyncio.sleep(0)
                assert life.status()["state"] == "ready" and not host.stops
                gate.set()
                assert all(r.status_code == 202 for r in await asyncio.gather(*requests))
                assert model.calls == 5
                # Requests finished, but their five unacknowledged Actions still
                # retain protection. Nothing is replayed by lifecycle maintenance.
                for _ in range(121):
                    now[0] += 30
                    app.state.lifecycle_work.refresh()
                    life.tick(host)
                assert not host.stops
                for client, sid in zip(clients, sessions, strict=True):
                    assert (await client.post(f"/sessions/{sid}/stop")).status_code == 202
                app.state.lifecycle_work.refresh()
                life.tick(host)
                assert life.status()["state"] == "draining"
                # A new admitted interaction wins before shutdown commitment.
                assert (await clients[0].post("/shopper/activity")).status_code == 204
                assert life.status()["state"] == "ready"
                now[0] += 3600
                life.tick(host)
                now[0] += 5
                life.tick(host)
                assert life.status()["state"] == "stopping"
                assert (await clients[0].post("/sessions")).status_code == 503
                life.tick(host)
                life.tick(host)
                assert life.status()["state"] == "stopped"
                ledger = AllowanceLedger(ledger_path, ledger_id)
                before = ledger.status()
                assert before["attempts"] == 5 and before["uncertain"] == 5
                life.manual_start()
                life.tick(host)
                host.state, host.healthy = "running", True
                life.tick(host)
                assert AllowanceLedger(ledger_path, ledger_id).status() == before
                assert all(row["used_sessions"] == 1 for row in invites.status())
                assert model.calls == 5
                # The surviving old Agent cannot enter a new lifecycle generation.
                assert (await clients[0].post("/sessions")).status_code == 503
            finally:
                gate.set()
                for client in clients:
                    await client.aclose()

    asyncio.run(scenario())
