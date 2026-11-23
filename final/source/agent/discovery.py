from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from agent.storefront import Money, StorefrontDefinition, normalize_money

DiscoverySort = Literal["cheapest", "newest"]


@dataclass(frozen=True)
class DiscoveryConstraints:
    category: str
    query: str | None = None
    product_type: str | None = None
    min_price: Money | None = None
    max_price: Money | None = None
    size: str | None = None
    color: str | None = None
    availability: bool | None = None
    sort: DiscoverySort | str | None = None


def _validate_constraints(
    storefront: StorefrontDefinition, constraints: DiscoveryConstraints
) -> None:
    if constraints.category not in storefront.categories:
        raise ValueError(f"unknown category: {constraints.category}")
    if constraints.sort not in (None, "cheapest", "newest"):
        raise ValueError(f"unsupported sort: {constraints.sort}")
    for name, money in (
        ("min_price", constraints.min_price),
        ("max_price", constraints.max_price),
    ):
        if money is not None and money.currency != storefront.currency:
            raise ValueError(f"{name} must use {storefront.currency}")
    if (
        constraints.min_price is not None
        and constraints.max_price is not None
        and constraints.min_price.amount > constraints.max_price.amount
    ):
        raise ValueError("min_price must not exceed max_price")


def _money_text(money: Money) -> str:
    return format(money.amount, "f")


def build_discovery_url(storefront: StorefrontDefinition, constraints: DiscoveryConstraints) -> str:
    _validate_constraints(storefront, constraints)
    path = storefront.category_route.replace("{category}", quote(constraints.category, safe=""))
    parameters: list[tuple[str, str]] = []
    if constraints.query:
        parameters.append(("q", constraints.query))
    if constraints.product_type:
        parameters.append(("type", constraints.product_type))
    if constraints.min_price is not None:
        parameters.append(("min_price", _money_text(constraints.min_price)))
    if constraints.max_price is not None:
        parameters.append(("max_price", _money_text(constraints.max_price)))
    if constraints.size:
        parameters.append(("size", constraints.size))
    if constraints.color:
        parameters.append(("color", constraints.color))
    if constraints.availability is not None:
        parameters.append(
            (
                "availability",
                "available" if constraints.availability else "unavailable",
            )
        )
    if constraints.sort is not None:
        parameters.append(("sort", constraints.sort))
    query = urlencode(parameters)
    return f"{path}?{query}" if query else path


def _category_from_path(storefront: StorefrontDefinition, path: str) -> str:
    prefix, suffix = storefront.category_route.split("{category}")
    if not path.startswith(prefix) or (suffix and not path.endswith(suffix)):
        raise ValueError("URL does not match the configured category route")
    end = len(path) - len(suffix) if suffix else len(path)
    category = path[len(prefix) : end]
    if not category or "/" in category:
        raise ValueError("URL does not contain one category")
    return category


def _one_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if values is None:
        return None
    if len(values) != 1:
        raise ValueError(f"URL contains duplicate {name} constraints")
    return values[0] or None


def parse_discovery_url(storefront: StorefrontDefinition, url: str) -> DiscoveryConstraints:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or parts.fragment:
        raise ValueError("discovery URL must be a same-origin relative URL")
    query = parse_qs(parts.query, keep_blank_values=True)
    unknown = set(query) - set(storefront.filters)
    if unknown:
        raise ValueError(f"URL contains unsupported filter: {sorted(unknown)[0]}")
    category = _category_from_path(storefront, parts.path)
    availability_text = _one_value(query, "availability")
    if availability_text not in (None, "available", "unavailable"):
        raise ValueError("availability must be available or unavailable")
    min_price_text = _one_value(query, "min_price")
    max_price_text = _one_value(query, "max_price")
    constraints = DiscoveryConstraints(
        category=category,
        query=_one_value(query, "q"),
        product_type=_one_value(query, "type"),
        min_price=(
            normalize_money(min_price_text, currency=storefront.currency)
            if min_price_text is not None
            else None
        ),
        max_price=(
            normalize_money(max_price_text, currency=storefront.currency)
            if max_price_text is not None
            else None
        ),
        size=_one_value(query, "size"),
        color=_one_value(query, "color"),
        availability=(None if availability_text is None else availability_text == "available"),
        sort=_one_value(query, "sort"),
    )
    _validate_constraints(storefront, constraints)
    return constraints
