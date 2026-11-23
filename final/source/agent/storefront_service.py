"""Authenticated private Storefront calls; destinations never come from browser Snapshots."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from agent.shopper_access import ShopperBinding


def identity_config(environment=None) -> dict[str, str]:
    values = os.environ if environment is None else environment
    production = values.get("COPILOT_ENV") == "production"
    if production and len(values.get("COPILOT_SERVICE_SECRET", "")) < 32:
        raise ValueError("Explicit production service secret is required")
    path = Path(__file__).resolve().parents[1] / "work" / "local-identity.json"
    saved = (
        json.loads(path.read_text(encoding="utf-8"))
        if environment is None and not production and path.exists()
        else {}
    )
    return {
        "secret": values.get("COPILOT_SERVICE_SECRET", saved.get("secret", "")),
        "panel_origin": values.get("COPILOT_PANEL_ORIGIN", "http://localhost:4100"),
        "store_origin": values.get("COPILOT_STORE_ORIGIN", "http://localhost:4000"),
        "private_url": values.get("COPILOT_STORE_PRIVATE_URL", "http://127.0.0.1:4000"),
    }


class StorefrontService:
    def __init__(self, config: dict[str, str] | None = None, *, environment=None):
        self.config = config or identity_config(environment)
        self._environment = None if environment is None else dict(environment)
        self.headers = {"x-service-secret": self.config["secret"]}
        self._client: httpx.AsyncClient | None = None

    def _connection(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=2, follow_redirects=False, trust_env=False)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def validate_configuration(self) -> None:
        environment = os.environ if self._environment is None else self._environment
        if len(self.config["secret"]) < 32:
            raise ValueError("Run scripts/init_local_identity.py before starting services")
        for name in ("panel_origin", "store_origin", "private_url"):
            value = urlsplit(self.config[name])
            host = value.hostname or ""
            host = f"[{host}]" if ":" in host else host
            port = value.port
            canonical = f"{value.scheme}://{host}"
            if port is not None and port != {"http": 80, "https": 443}.get(value.scheme):
                canonical += f":{port}"
            local = value.hostname in {"localhost", "127.0.0.1", "::1"}
            if (
                value.scheme not in {"http", "https"}
                or not value.hostname
                or value.username
                or value.password
                or value.query
                or value.fragment
                or value.path
                or canonical != self.config[name]
                or any(c.isspace() or c in '\\"<>' for c in self.config[name])
                or not value.hostname.isascii()
                or any(not (c.isalnum() or c in "._-:") for c in value.hostname)
                or (value.scheme == "http" and not local)
                or (
                    name != "private_url"
                    and environment.get("COPILOT_ENV") == "production"
                    and value.scheme != "https"
                )
            ):
                raise ValueError("Invalid configured service origin")
        if self.config["panel_origin"] == self.config["store_origin"]:
            raise ValueError("Panel and Storefront origins must differ")

    def _url(self, path: str) -> str:
        self.validate_configuration()
        return self.config["private_url"].rstrip("/") + "/__internal/" + path

    async def redeem(self, ticket: str, challenge: str) -> ShopperBinding:
        response = await self._connection().post(
            self._url("link/redeem"),
            headers=self.headers,
            json={
                "ticket": ticket,
                "challenge": challenge,
                "audience": self.config["panel_origin"],
            },
        )
        response.raise_for_status()
        data = response.json()
        if (
            not isinstance(data, dict)
            or set(data) != {"shopper_id", "generation"}
            or any(
                not isinstance(value, str)
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
                for value in data.values()
            )
        ):
            raise ValueError("Invalid service binding")
        return ShopperBinding(**data)

    async def validate(self, binding: ShopperBinding) -> bool:
        response = await self._connection().post(
            self._url("shopper/validate"), headers=self.headers, json=asdict(binding)
        )
        return response.status_code == 200 and response.json() == {"valid": True}

    def register_confirmation(
        self,
        binding: ShopperBinding | None,
        snapshot_url: str,
        token: str,
        task_id: str,
        kind: str,
        cart_revision: int,
    ) -> bool:
        parsed = urlsplit(snapshot_url)
        if binding is None or f"{parsed.scheme}://{parsed.netloc}" != self.config["store_origin"]:
            return False
        try:
            response = httpx.post(
                self._url("confirmations"),
                headers=self.headers,
                json={
                    "shopper": asdict(binding),
                    "confirmation": {
                        "token": token,
                        "task_id": task_id,
                        "kind": kind,
                        "cart_revision": cart_revision,
                    },
                },
                timeout=2,
                follow_redirects=False,
                trust_env=False,
            )
            return response.status_code == 201
        except (httpx.HTTPError, ValueError):
            return False
