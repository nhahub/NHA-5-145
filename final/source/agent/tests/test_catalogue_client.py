import asyncio

import httpx
import pytest

from agent.catalogue_client import CatalogueClient, CatalogueReadError
from agent.catalogue_contract import SearchQuery


def result():
    return {
        "v": 1,
        "catalogue_revision": 1,
        "candidates": [],
        "ranking": "lexical",
        "exact_count": None,
        "next_cursor": None,
        "truncated": False,
        "unverified_requirements": [],
    }


def test_private_fixed_route_conditional_revalidation_and_explicit_failures():
    seen = []

    def handle(request):
        seen.append(request)
        assert request.url == "http://127.0.0.1:4000/__internal/catalogue/search"
        assert request.headers["x-service-secret"] == "s" * 32
        if len(seen) == 1:
            return httpx.Response(200, json=result(), headers={"etag": '"revision1"'})
        assert request.headers["if-none-match"] == '"revision1"'
        return httpx.Response(304)

    async def scenario():
        client = CatalogueClient(secret="s" * 32, transport=httpx.MockTransport(handle))
        first = await client.search(SearchQuery(query="هل فيه حاجه مش جلد؟"))
        second = await client.search(SearchQuery(query="هل فيه حاجه مش جلد؟"))
        assert first == second and len(seen) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,body",
    [(302, b""), (409, b'{"code":"stale_index"}'), (200, b"x" * 32769), (200, b"not json")],
    ids=["redirect", "stale-index", "oversize", "bad-json"],
)
def test_redirect_errors_and_oversized_records_never_become_empty_results(status, body):
    async def scenario():
        client = CatalogueClient(
            secret="s" * 32,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    status, content=body, headers={"location": "https://evil.test"}
                )
            ),
        )
        with pytest.raises(CatalogueReadError):
            await client.search(SearchQuery(query="anything"))

    asyncio.run(scenario())


def test_shared_wire_fixtures_match_the_storefront_contract():
    import json
    from pathlib import Path

    from pydantic import ValidationError

    rows = json.loads(
        (Path(__file__).resolve().parents[2] / "protocol/catalogue/fixtures.json").read_text(
            encoding="utf-8"
        )
    )
    for row in rows:
        if row["valid"]:
            SearchQuery.model_validate(row["query"])
        else:
            with pytest.raises(ValidationError):
                SearchQuery.model_validate(row["query"])
