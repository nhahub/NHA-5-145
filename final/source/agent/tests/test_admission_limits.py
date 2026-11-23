import asyncio
from contextlib import suppress

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from agent.admission.limits import AdmissionLimits
from agent.tests.test_admission_http import policy


def test_global_request_slots_are_finite_and_release_after_cancellation(tmp_path):
    async def scenario():
        admission, _ = policy(tmp_path, maximum_requests=1)
        app = FastAPI()
        app.add_middleware(AdmissionLimits, policy=admission)
        entered, release = asyncio.Event(), asyncio.Event()

        @app.get("/slow")
        async def slow():
            entered.set()
            await release.wait()
            return {"ok": True}

        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            first = asyncio.create_task(client.get("/slow"))
            await entered.wait()
            assert (await client.get("/slow")).status_code == 429
            first.cancel()
            with suppress(asyncio.CancelledError):
                await first
            release.set()
            assert (await client.get("/slow")).status_code == 200

    asyncio.run(scenario())


def test_stream_slots_cover_entire_body_and_cookie_variations_cannot_bypass(tmp_path):
    async def scenario():
        admission, _ = policy(tmp_path, maximum_streams=2, browser_sessions=1)
        app = FastAPI()
        app.add_middleware(AdmissionLimits, policy=admission)
        entered, release = asyncio.Event(), asyncio.Event()

        @app.get("/sessions/a/events")
        async def stream():
            async def body():
                entered.set()
                yield ": ready\n\n"
                await release.wait()

            return StreamingResponse(body(), media_type="text/event-stream")

        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            first = asyncio.create_task(
                client.get("/sessions/a/events", headers={"cookie": "copilot_agent=a; other=x"})
            )
            await entered.wait()
            assert (
                await client.get(
                    "/sessions/a/events", headers={"cookie": "other=y; copilot_agent=a"}
                )
            ).status_code == 429
            release.set()
            assert (await first).status_code == 200
            assert (
                await client.get("/sessions/a/events", headers={"cookie": "copilot_agent=a"})
            ).status_code == 200

    asyncio.run(scenario())
