"""Bounded, observed product identities shared by interpretation and execution."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

from agent.schemas import Snapshot
from agent.storefront import StorefrontDefinition

MAX_PRODUCTS = 24
MAX_CONVERSATION_ENTRIES = 12


def current_product(snapshot: Snapshot, storefront: StorefrontDefinition) -> dict[str, str] | None:
    """The product whose page the Snapshot shows (its route and heading), else None."""
    pattern = re.escape(storefront.product_route).replace(
        re.escape("{product_id}"), r"(?P<id>[a-z0-9][a-z0-9-]*)"
    )
    current = re.fullmatch(pattern, urlsplit(snapshot.url).path)
    if not current:
        return None
    heading = next(
        (
            e.name
            for e in snapshot.elements
            if e.visible and not e.sensitive and e.role == "heading" and e.level == 1
        ),
        snapshot.title,
    )
    return {"id": current["id"], "name": heading[:200]}


def observed_products(snapshot: Snapshot, storefront: StorefrontDefinition) -> list[dict[str, str]]:
    origin = urlsplit(snapshot.url)
    pattern = re.escape(storefront.product_route).replace(
        re.escape("{product_id}"), r"(?P<id>[a-z0-9][a-z0-9-]*)"
    )
    references = []
    for element in snapshot.elements:
        if (
            element.role != "link"
            or not element.visible
            or element.disabled
            or element.sensitive
            or not element.href
        ):
            continue
        target = urlsplit(urljoin(snapshot.url, element.href))
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
            continue
        match = re.fullmatch(pattern, target.path)
        if match:
            references.append({"id": match["id"], "name": (element.group or element.name)[:200]})
    current = current_product(snapshot, storefront)
    if current:
        references.append(current)
    labels: dict[str, list[str]] = {}
    for reference in references:
        names = labels.setdefault(reference["id"], [])
        if reference["name"] not in names:
            names.append(reference["name"])
    return [{"id": product_id, "name": " | ".join(names)} for product_id, names in labels.items()]


def require_known_product(
    product_id: str | None,
    state: Mapping[str, Any],
    snapshot: Snapshot | None,
    storefront: StorefrontDefinition,
) -> None:
    references = [
        *state.get("_known_products", []),
        *state.get("_previous_suggestions", []),
        *state.get("_this_candidates", []),
    ]
    if snapshot is not None:
        references.extend(observed_products(snapshot, storefront))
    if product_id is None or product_id not in {
        item.get("id") for item in references if isinstance(item, dict)
    }:
        raise ValueError("Product ID has no observed Storefront reference")


@dataclass
class ProductContext:
    """Remember identities, not stale DOM controls or permission to mutate."""

    origin: tuple[str, str] | None = None
    products: dict[str, dict[str, str]] = field(default_factory=dict)
    suggestions: list[dict[str, str]] = field(default_factory=list)
    conversation_start: int = 0

    def _remember(self, references: Sequence[Mapping[str, Any]]) -> None:
        for item in references:
            product_id, name = item.get("id"), item.get("name")
            if not isinstance(product_id, str) or not isinstance(name, str):
                continue
            self.products.pop(product_id, None)
            self.products[product_id] = {"id": product_id, "name": name[:200]}
        while len(self.products) > MAX_PRODUCTS:
            self.products.pop(next(iter(self.products)))

    def remember_catalogue(self, references: Sequence[Mapping[str, Any]]) -> None:
        """Retain refreshed identities from comparisons as well as visible cards."""
        self._remember(references)

    def remember_suggestions(self, references: Sequence[Mapping[str, Any]]) -> None:
        self._remember(references)
        self.suggestions = [
            self.products[item["id"]].copy()
            for item in references
            if item.get("id") in self.products
        ][:3]

    def observe(
        self, snapshot: Snapshot, storefront: StorefrontDefinition, conversation_size: int
    ) -> None:
        location = urlsplit(snapshot.url)
        origin = (location.scheme, location.netloc)
        if origin != self.origin:
            self.products.clear()
            self.suggestions.clear()
            self.origin = origin
            self.conversation_start = conversation_size
        self._remember(observed_products(snapshot, storefront))

    def prepare(
        self,
        snapshot: Snapshot,
        storefront: StorefrontDefinition,
        conversation: list[dict[str, str]],
    ) -> dict[str, Any]:
        self.observe(snapshot, storefront, len(conversation))
        start = max(self.conversation_start, len(conversation) - MAX_CONVERSATION_ENTRIES)
        latest_reply = next(
            (
                i
                for i in range(len(conversation) - 1, start - 1, -1)
                if conversation[i]["role"] == "copilot"
            ),
            None,
        )
        return {
            "_known_products": list(self.products.values()),
            "_previous_suggestions": list(self.suggestions),
            "_recent_conversation": [
                {"role": entry["role"], "text": entry["text"][: 2400 if i == latest_reply else 500]}
                for i, entry in enumerate(conversation[start:], start=start)
            ],
        }
