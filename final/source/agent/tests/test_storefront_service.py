import asyncio

import httpx
import pytest

from agent.shopper_access import ShopperBinding
from agent.storefront_service import StorefrontService


def config(**changes):
    return dict(
        secret="s" * 64,
        panel_origin="http://localhost:4100",
        store_origin="http://localhost:4000",
        private_url="http://127.0.0.1:4000",
        **changes,
    )


def test_private_confirmation_uses_configured_destination_and_owner(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(201)

    monkeypatch.setattr(httpx, "post", post)
    service = StorefrontService(config())
    owner = ShopperBinding("a" * 64, "b" * 64)
    assert not service.register_confirmation(
        owner, "https://hostile.example/cart", "t", "task", "clear_cart", 1
    )
    assert not calls
    assert service.register_confirmation(
        owner, "http://localhost:4000/cart", "t", "task", "clear_cart", 1
    )
    assert calls[0][0] == "http://127.0.0.1:4000/__internal/confirmations"
    assert calls[0][1]["json"]["shopper"] == {
        "shopper_id": owner.shopper_id,
        "generation": owner.generation,
    }
    assert calls[0][1]["follow_redirects"] is False


def test_redemption_rejects_redirects_and_unexpected_binding_fields(monkeypatch):
    client = httpx.AsyncClient

    def response(request):
        return httpx.Response(
            200, json={"shopper_id": "a" * 64, "generation": "b" * 64, "extra": True}
        )

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client(transport=httpx.MockTransport(response), **kw)
    )
    with pytest.raises(ValueError, match="Invalid service binding"):
        asyncio.run(StorefrontService(config()).redeem("ticket", "challenge"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("secret", ""),
        ("panel_origin", "http://public.example"),
        ("store_origin", "https://example.com/path"),
        ("private_url", "https://user:password@example.com"),
    ],
)
def test_invalid_runtime_configuration_is_rejected(field, value):
    settings = config()
    settings[field] = value
    with pytest.raises(ValueError):
        StorefrontService(settings).validate_configuration()
