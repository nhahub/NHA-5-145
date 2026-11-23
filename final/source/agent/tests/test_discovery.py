from decimal import Decimal

import pytest

from agent.discovery import (
    DiscoveryConstraints,
    build_discovery_url,
    parse_discovery_url,
)
from agent.storefront import Money, load_storefront_definition


@pytest.fixture
def storefront():
    return load_storefront_definition()


def test_discovery_constraints_build_one_canonical_category_navigation(storefront):
    constraints = DiscoveryConstraints(
        category="shoes",
        query="Nile جري",
        product_type="running",
        min_price=Money(Decimal("1000.50"), "EGP"),
        max_price=Money(Decimal("2000"), "EGP"),
        size="42",
        color="black",
        availability=True,
        sort="cheapest",
    )

    assert build_discovery_url(storefront, constraints) == (
        "/c/shoes?q=Nile+%D8%AC%D8%B1%D9%8A&type=running&min_price=1000.50"
        "&max_price=2000&size=42&color=black&availability=available&sort=cheapest"
    )


def test_discovery_url_round_trips_store_state_without_broadening(storefront):
    url = (
        "/c/clothing?q=jacket&type=outerwear&min_price=900&max_price=1800"
        "&size=L&color=black&availability=unavailable&sort=newest"
    )

    assert parse_discovery_url(storefront, url) == DiscoveryConstraints(
        category="clothing",
        query="jacket",
        product_type="outerwear",
        min_price=Money(Decimal("900"), "EGP"),
        max_price=Money(Decimal("1800"), "EGP"),
        size="L",
        color="black",
        availability=False,
        sort="newest",
    )


def test_unknown_category_is_rejected_before_navigation(storefront):
    with pytest.raises(ValueError, match="unknown category"):
        build_discovery_url(storefront, DiscoveryConstraints(category="toys"))


def test_non_egp_constraint_is_rejected_before_navigation(storefront):
    with pytest.raises(ValueError, match="must use EGP"):
        build_discovery_url(
            storefront,
            DiscoveryConstraints(category="shoes", max_price=Money(Decimal("10"), "USD")),
        )


@pytest.mark.parametrize("sort", ["popular", "price_desc"])
def test_unsupported_sort_is_rejected(storefront, sort):
    with pytest.raises(ValueError, match="unsupported sort"):
        build_discovery_url(storefront, DiscoveryConstraints(category="shoes", sort=sort))
