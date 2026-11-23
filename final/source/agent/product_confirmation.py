"""Confirm a product the Shopper did not name before it is opened or added (B6).

The model picks a product by id; deterministic code checks the pick against evidence: the
product's verified name must occur in the Shopper's own words, or code itself resolved the
product ("this", an exact option answer, the open page, a "yes" to this very question).
Otherwise the Shopper is asked "تقصد X؟" and nothing is done until they say yes. Names come
from verified catalogue/page references, never from model prose.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from agent.llm.intent import StructuredIntent
from agent.product_context import current_product, observed_products
from agent.product_reference import names_product
from agent.schemas import Snapshot
from agent.storefront import StorefrontDefinition

# A completed task that ended because the Shopper declined the product did not do its step.
PRODUCT_DECLINED = "product_declined"
CONFIRMED_KEY = "_confirmed_product"
PENDING_KEY = "_confirm_product"
# Code resolved this product from the Shopper's exact words (open/add by name, ticket 06).
NAMED_KEY = "_named_product"

QUESTION = {"ar": "تقصد {name}؟", "en": "Did you mean {name}?"}
OPTIONS = {"ar": ["أيوه", "لا"], "en": ["Yes", "No"]}
DECLINED = {
    "ar": "تمام، ما عملتش حاجة. قولي تقصد أنهي منتج.",
    "en": "OK, I didn't do anything. Tell me which product you mean.",
}
DECLINED_REASON = {
    "ar": "ما أكدتش المنتج، فما نفّذتش الخطوة دي.",
    "en": "The product wasn't confirmed, so I didn't do this step.",
}
_SEPARATORS = re.compile(r"\s+[|/]\s+")
_ARABIC = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[A-Za-z]")


def reference_names(
    product_id: str,
    state: Mapping[str, Any],
    snapshot: Snapshot | None,
    storefront: StorefrontDefinition,
) -> list[str]:
    """Every verified name part (Arabic, English) known for this product id."""
    references: list[Any] = [
        *state.get("_known_products", []),
        *state.get("_previous_suggestions", []),
        *state.get("_this_candidates", []),
    ]
    if snapshot is not None:
        references.extend(observed_products(snapshot, storefront))
    parts: list[str] = []
    for item in references:
        if not isinstance(item, dict) or item.get("id") != product_id:
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        for part in (name, *_SEPARATORS.split(name), *name.split(" | ")):
            part = part.strip()
            if part and part not in parts:
                parts.append(part)
    return parts


def _display_name(parts: Sequence[str], language: str) -> str:
    """One readable name: the part in the Shopper's script when the references have both."""
    singles = [p for p in parts if not _SEPARATORS.search(p) and " | " not in p] or list(parts)
    wanted = _ARABIC if language == "ar" else _LATIN
    return next((p for p in singles if wanted.search(p)), singles[0] if singles else "")


def unnamed_product(
    intent: StructuredIntent,
    state: Mapping[str, Any],
    shopper_texts: Sequence[object],
    snapshot: Snapshot | None,
    storefront: StorefrontDefinition,
) -> str | None:
    """The name to ask about when a model-chosen product is not backed by evidence, else None."""
    product_id = intent.product_id
    if (
        product_id is None
        or intent.needs_clarification
        or not (
            intent.intent == "open_product"
            or (intent.intent == "cart_edit" and intent.cart_operation == "add")
        )
    ):
        return None
    if product_id in (state.get(CONFIRMED_KEY), state.get(NAMED_KEY)):
        return None  # the Shopper said yes to, or named, exactly this product
    candidates = {
        item.get("id") for item in state.get("_this_candidates", []) if isinstance(item, dict)
    }
    if intent.refers_to_this and product_id in candidates:
        return None  # code resolved "this"; the model only set the marker
    page = current_product(snapshot, storefront) if snapshot is not None else None
    if page is not None and page["id"] == product_id:
        return None  # its page is already open
    parts = reference_names(product_id, state, snapshot, storefront)
    words = [text for text in shopper_texts if isinstance(text, str)]
    if any(names_product(text, part) for part in parts for text in words):
        return None
    return _display_name(parts, intent.language)
