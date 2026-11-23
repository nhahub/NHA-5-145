"""Connection pooling must never become cached shopper authorization."""

import asyncio
import json

import httpx

from agent.shopper_access import ShopperBinding
from agent.storefront_service import StorefrontService


def test_private_connections_are_reused_but_every_shopper_check_reaches_store(monkeypatch):
    clients, bindings = [], []
    original = httpx.AsyncClient
    revoked = False

    def handler(request):
        bindings.append(json.loads(request.content))
        assert request.headers["x-service-secret"] == "s" * 32
        return httpx.Response(403 if revoked else 200, json={"valid": not revoked})

    def client(**kwargs):
        result = original(**kwargs, transport=httpx.MockTransport(handler))
        clients.append(result)
        return result

    monkeypatch.setattr(httpx, "AsyncClient", client)

    async def scenario():
        nonlocal revoked
        service = StorefrontService(
            dict(
                secret="s" * 32,
                panel_origin="http://localhost:4100",
                store_origin="http://localhost:4000",
                private_url="http://127.0.0.1:4000",
            )
        )
        a, b = ShopperBinding("a" * 64, "1" * 64), ShopperBinding("b" * 64, "2" * 64)
        assert await service.validate(a)
        assert await service.validate(b)
        revoked = True
        assert not await service.validate(a)
        assert len(clients) == 1
        assert not clients[0].is_closed
        await service.aclose()
        assert clients[0].is_closed
        assert [x["shopper_id"] for x in bindings] == [a.shopper_id, b.shopper_id, a.shopper_id]

    asyncio.run(scenario())
