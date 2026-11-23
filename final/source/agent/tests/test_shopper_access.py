import pytest
from fastapi.testclient import TestClient

from agent.app import create_app
from agent.tests.http_client import FakeStorefrontService
from agent.tests.http_client import TestClient as BrowserClient
from agent.tests.test_step import home_snapshot


def test_agent_rejects_session_creation_without_shopper_authority():
    with TestClient(create_app(storefront_service=FakeStorefrontService())) as client:
        response = client.post("/sessions", json={"tab_id": "known"})
    assert response.status_code == 401


def test_agent_rejects_forged_browser_cookie_before_session_lookup():
    with TestClient(create_app(storefront_service=FakeStorefrontService())) as client:
        client.cookies.set("copilot_agent", "forged")
        response = client.get("/sessions/known/state?tab_id=known")
    assert response.status_code == 401


def test_foreign_session_state_events_and_takeover_are_denied():
    app = create_app()
    a, b = BrowserClient(app), BrowserClient(app)
    session_id = a.post("/sessions", json={"tab_id": "known"}).json()["session_id"]
    assert a.get(f"/sessions/{session_id}/state?tab_id=known").status_code == 200
    for suffix in ["state?tab_id=known", "events?once=true&tab_id=known"]:
        assert b.get(f"/sessions/{session_id}/{suffix}").status_code == 404
    for suffix, payload in [("takeover", {"tab_id": "known"}), ("stop", {})]:
        assert b.post(f"/sessions/{session_id}/{suffix}", json=payload).status_code == 404
    payloads = [
        ("messages", {"text": "open cart", "snapshot": home_snapshot()}),
        ("reconcile", {"snapshot": home_snapshot()}),
        (
            "tasks/task-known/answers",
            {"question_id": "question-known", "text": "Confirm", "snapshot": home_snapshot()},
        ),
        ("tasks/task-known/retry", {"snapshot": home_snapshot()}),
        (
            "action-results",
            {
                "v": 1,
                "task_id": "task-known",
                "action_id": "action-known",
                "sequence_number": 1,
                "status": "ok",
                "snapshot": home_snapshot(),
            },
        ),
    ]
    for suffix, payload in payloads:
        assert b.post(f"/sessions/{session_id}/{suffix}", json=payload).status_code == 404
    assert a.get(f"/sessions/{session_id}/state?tab_id=known").status_code == 200


def test_revoked_storefront_binding_denies_existing_session():
    app = create_app()
    a = BrowserClient(app)
    session_id = a.post("/sessions").json()["session_id"]
    app.state.storefront_service.revoked = True
    assert a.get(f"/sessions/{session_id}/state?tab_id=a").status_code == 401


def test_wrong_origin_or_csrf_cannot_create_sessions():
    app = create_app()
    a = BrowserClient(app)
    assert a.post("/sessions", headers={"origin": "https://hostile.example"}).status_code == 403
    assert a.post("/sessions", headers={"x-csrf-token": "wrong"}).status_code == 403


def test_session_limit_and_deleted_cookie_never_reuse_saved_session():
    app = create_app()
    a = BrowserClient(app)
    identifiers = [a.post("/sessions").json()["session_id"] for _ in range(8)]
    assert a.post("/sessions").status_code == 429
    a.cookies.clear()
    assert a.get(f"/sessions/{identifiers[0]}/state").status_code == 401
    assert a.post("/speech/transcribe", content=b"unused").status_code == 401


def test_revocation_during_interpretation_discards_the_late_action():
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from agent.llm import LLMChunk, LLMSettings
    from agent.sessions import SessionStore
    from agent.tests.http_client import authorize_async
    from agent.tests.test_real_task import intent_payload

    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        class Delayed:
            async def complete(self, request):
                started.set()
                await release.wait()
                yield LLMChunk(text=intent_payload(category="shoes"))

        store = SessionStore()
        app = create_app(
            session_store=store,
            llm_settings=LLMSettings(provider="groq", model="unused"),
            llm_client=Delayed(),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await authorize_async(client, app)
            sid = (await client.post("/sessions")).json()["session_id"]
            pending = asyncio.create_task(
                client.post(
                    f"/sessions/{sid}/messages", json={"text": "shoes", "snapshot": home_snapshot()}
                )
            )
            await asyncio.wait_for(started.wait(), 2)
            app.state.storefront_service.revoked = True
            release.set()
            await asyncio.wait_for(pending, 2)
            assert not any(event.event == "action" for event in store.events_after(sid, 0))
            assert (await client.get(f"/sessions/{sid}/events?once=true")).status_code == 401

    asyncio.run(scenario())


@pytest.mark.parametrize("expire_session", [False, True])
def test_open_stream_closes_at_revocation_without_releasing_pending_actions(expire_session):
    import asyncio

    from starlette.requests import Request

    from agent.session_stream import session_event_response
    from agent.sessions import SessionStore

    async def scenario():
        now = [0.0]
        store = SessionStore(clock=lambda: now[0])
        session = store.create()
        sid = session.session_id
        from agent.session_state import SessionEvent

        session.events.extend(
            [
                SessionEvent(1, "narration", {"text": "first"}),
                SessionEvent(2, "narration", {"text": "must not leak"}),
            ]
        )
        valid = [True]

        async def authorized():
            return valid[0]

        async def receive():
            return {"type": "http.request"}

        request = Request(
            {"type": "http", "headers": [], "state": {"shopper_authorized": authorized}}, receive
        )
        response = await session_event_response(store, sid, request)
        stream = response.body_iterator
        assert "first" in await anext(stream)
        if expire_session:
            now[0] = 7 * 24 * 60 * 60 + 1  # the session lifetime is seven days
        else:
            valid[0] = False
        assert await anext(stream) == "event: shopper_reset\ndata: {}\n\n"
        try:
            await anext(stream)
        except StopAsyncIteration:
            return
        raise AssertionError("Revoked stream remained open")

    asyncio.run(scenario())
