"""Bounded private reads from the configured Storefront; never model-selected URLs."""

import asyncio
import json
from collections import OrderedDict
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from agent.catalogue_contract import DetailsQuery, DetailsResult, SearchQuery, SearchResult


class CatalogueReadError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__("Catalogue read failed: " + code)


class CatalogueClient:
    """Create once per interpretation. Conditional reuse still performs an authenticated read."""

    def __init__(
        self, *, secret: str, origin: str = "http://127.0.0.1:4000", transport=None, encoder=None
    ):
        parsed = urlsplit(origin)
        if (
            len(secret) < 32
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("Invalid private catalogue configuration")
        self.origin, self.secret, self.transport, self.encoder = origin, secret, transport, encoder
        self.cache: OrderedDict[str, tuple[str, Any]] = OrderedDict()

    async def search(self, query: SearchQuery) -> SearchResult:
        body = query.model_dump(mode="json")
        if self.encoder is not None:
            body["query_embedding"] = await asyncio.to_thread(self.encoder.query, query.query)
        return await self._read("search", body, SearchResult)

    async def details(self, query: DetailsQuery) -> DetailsResult:
        return await self._read("details", query.model_dump(mode="json"), DetailsResult)

    async def _read(self, kind, body, schema):
        key = kind + json.dumps(body, sort_keys=True, ensure_ascii=False)
        headers = {"x-service-secret": self.secret}
        cached = self.cache.get(key)
        if cached:
            headers["if-none-match"] = cached[0]
        async with (
            httpx.AsyncClient(
                timeout=5, follow_redirects=False, transport=self.transport, trust_env=False
            ) as client,
            client.stream(
                "POST", self.origin + "/__internal/catalogue/" + kind, headers=headers, json=body
            ) as response,
        ):
            if response.status_code == 304 and cached:
                return cached[1].model_copy(deep=True)
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                data.extend(chunk)
                if len(data) > 32768:
                    raise CatalogueReadError("record_too_large")
            if response.status_code != 200:
                try:
                    code = json.loads(data).get("code")
                except (ValueError, AttributeError):
                    code = None
                raise CatalogueReadError(
                    code
                    if code in {"invalid_query", "stale_cursor", "stale_index", "record_too_large"}
                    else "unavailable"
                )
            try:
                result = schema.model_validate_json(data)
            except (ValidationError, ValueError) as error:
                raise CatalogueReadError("invalid_response") from error
            etag = response.headers.get("etag")
            if etag:
                self.cache[key] = (etag, result.model_copy(deep=True))
                while len(self.cache) > 4:
                    self.cache.popitem(last=False)
            return result
