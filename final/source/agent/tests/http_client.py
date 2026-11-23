"""Explicit HTTP fixtures exercising the real cookie/CSRF/ownership boundary."""

import secrets

from fastapi.testclient import TestClient as RawClient

from agent.shopper_access import ShopperBinding


class FakeStorefrontService:
    def __init__(self):
        self.tickets: dict[str, ShopperBinding] = {}
        self.bindings: set[ShopperBinding] = set()
        self.revoked = False

    def validate_configuration(self):
        pass

    def issue(self) -> str:
        ticket = secrets.token_hex(32)
        owner = ShopperBinding(secrets.token_hex(32), "a" * 64)
        self.tickets[ticket] = owner
        self.bindings.add(owner)
        return ticket

    async def redeem(self, ticket, challenge):
        return self.tickets.pop(ticket)

    async def validate(self, binding):
        return not self.revoked and binding in self.bindings

    def register_confirmation(self, *args):
        return True


class TestClient(RawClient):
    __test__ = False

    def __init__(self, app, **kwargs):
        if not isinstance(app.state.storefront_service, FakeStorefrontService):
            app.state.storefront_service = FakeStorefrontService()
        super().__init__(app, **kwargs)
        self.headers["origin"] = "http://localhost:4100"
        bootstrap = self.post("/shopper/bootstrap")
        assert bootstrap.status_code == 200
        self.headers["x-csrf-token"] = bootstrap.json()["csrf"]
        challenge = self.post("/shopper/challenge").json()["challenge"]
        ticket = app.state.storefront_service.issue()
        assert (
            self.post("/shopper/link", json={"ticket": ticket, "challenge": challenge}).status_code
            == 200
        )


async def authorize_async(client, app):
    app.state.storefront_service = FakeStorefrontService()
    client.headers["origin"] = "http://localhost:4100"
    bootstrap = await client.post("/shopper/bootstrap")
    client.headers["x-csrf-token"] = bootstrap.json()["csrf"]
    challenge = (await client.post("/shopper/challenge")).json()["challenge"]
    ticket = app.state.storefront_service.issue()
    assert (
        await client.post("/shopper/link", json={"ticket": ticket, "challenge": challenge})
    ).status_code == 200
