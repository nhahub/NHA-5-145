"""Concrete host health observations; no backend activation or model qualification."""

import asyncio
import hashlib
import json
import re
from decimal import Decimal
from inspect import iscoroutinefunction
from pathlib import Path

import httpx

from agent.admission.async_runtime import AsyncAdmissionPolicy
from agent.async_boundary import BoundedIO
from agent.catalogue_contract import SearchQuery, SearchResult
from agent.inference.client import GuardedClient
from deploy.artifact import verify
from deploy.catalogue import catalogue_status
from deploy.host_files import ORIGINS

CATALOGUE_URL = "http://127.0.0.1:4000/__internal/catalogue/search"


async def unqualified_provider():
    """Current Bedrock candidate is blocked; never infer qualification from access."""
    return False


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate response field")
        result[key] = value
    return result


class HostChecks:
    def __init__(
        self, *, release, fingerprint, catalogue, admission, guard, service, transport=None
    ):
        if (
            type(fingerprint) is not str
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or not isinstance(admission, AsyncAdmissionPolicy)
            or not isinstance(guard, GuardedClient)
        ):
            raise ValueError("Explicit host readiness bindings required")
        service.validate_configuration()
        expected = {
            "panel_origin": ORIGINS["panel"],
            "store_origin": ORIGINS["store"],
            "private_url": "http://127.0.0.1:4000",
            "secret": service.config["secret"],
        }
        if service.config != expected:
            raise ValueError("Fixed production Storefront configuration required")
        self._release, self._catalogue = Path(release), Path(catalogue)
        if not self._release.is_absolute() or not self._catalogue.is_absolute():
            raise ValueError("Absolute host paths required")
        self._fingerprint = fingerprint
        self._admission, self._guard, self._service = admission, guard, service
        self._store = admission.store
        self._authority = self._admission_binding()
        self._service_config = dict(service.config)
        self._ledger, self._prices, self._client = guard.ledger, guard.prices, guard.client
        self._ledger_path, self._identity = self._ledger.path, self._ledger.identity
        self._transport = transport
        self._io, self._closed = BoundedIO(workers=2, capacity=8), False

    def _admission_binding(self):
        store = self._admission.store
        return store.client, store.table, store.namespace, store.identity

    def _bindings(self):
        return (
            not self._closed
            and self._admission.store is self._store
            and self._admission_binding() == self._authority
            and self._guard.ledger is self._ledger
            and self._guard.prices is self._prices
            and self._guard.client is self._client
            and self._ledger.path == self._ledger_path
            and self._ledger.identity == self._identity
            and self._service.config == self._service_config
        )

    def _paths(self):
        release = self._release.resolve(strict=True)
        catalogue = self._catalogue.resolve(strict=True)
        ledger = self._ledger_path.resolve(strict=True)
        if (
            not release.is_dir()
            or not catalogue.is_file()
            or not ledger.is_file()
            or catalogue == ledger
            or catalogue.is_relative_to(release)
            or ledger.is_relative_to(release)
        ):
            raise ValueError("Distinct existing external state required")
        return release, catalogue

    def _release_check(self):
        release, _ = self._paths()
        manifest_path = release / "release.json"
        before = manifest_path.read_bytes()
        if hashlib.sha256(before).hexdigest() != self._fingerprint:
            return False
        manifest = verify(release)
        return (
            manifest.get("local_rehearsal") is False
            and manifest.get("public_origins") == ORIGINS
            and manifest_path.read_bytes() == before
        )

    def _catalogue_check(self):
        _, catalogue = self._paths()
        return catalogue_status(catalogue)

    def _allowance_check(self):
        self._paths()
        status = self._ledger.status()
        # Same maximum encoded input/overhead/output as GuardedClient reservation.
        maximum = (
            Decimal(260096) * self._prices.input_per_million
            + Decimal(2048) * self._prices.output_per_million
        ) / Decimal(1_000_000)
        return (
            status["identity"] == self._identity
            and status["enabled"] is True
            and Decimal(status["remaining_usd"]) >= maximum
        )

    async def _local(self, function):
        if not self._bindings():
            return False
        try:
            result = await self._io.call(function)
            return result is True and self._bindings()
        except Exception:
            return False

    async def release(self):
        return await self._local(self._release_check)

    async def allowance(self):
        return await self._local(self._allowance_check)

    async def admission(self):
        return self._bindings() and await self._admission.ready() and self._bindings()

    async def storefront(self):
        if not self._bindings():
            return False
        try:
            async with asyncio.timeout(1):
                before = await self._io.call(self._catalogue_check)
                async with (
                    httpx.AsyncClient(
                        timeout=1,
                        trust_env=False,
                        follow_redirects=False,
                        transport=self._transport,
                    ) as client,
                    client.stream(
                        "POST",
                        CATALOGUE_URL,
                        json=SearchQuery(query="").model_dump(mode="json"),
                        headers={
                            "x-service-secret": self._service_config["secret"],
                            "Accept-Encoding": "identity",
                        },
                    ) as response,
                ):
                    if (
                        response.status_code != 200
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        return False
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > 32768:
                            return False
                        body.extend(chunk)
                    result = SearchResult.model_validate(
                        json.loads(body.decode("utf-8"), object_pairs_hook=_pairs)
                    )
                after = await self._io.call(self._catalogue_check)
                return (
                    self._bindings()
                    and before == after
                    and result.catalogue_revision == before["revision"]
                    and result.ranking == "lexical"
                    and not result.unverified_requirements
                )
        except Exception:
            return False

    def checks(self, provider):
        if not iscoroutinefunction(provider):
            raise ValueError("Explicit async provider qualification verifier required")
        return {
            "release": self.release,
            "storefront": self.storefront,
            "admission": self.admission,
            "allowance": self.allowance,
            "provider": provider,
        }

    async def close(self):
        self._closed = True
        await self._io.close()
