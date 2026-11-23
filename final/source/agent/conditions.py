"""Page-checkable conditions: "if it is under 1000", "if it comes in black", "if in stock".

Code decides. The model only says which fact, which comparator and which value; the outcome
comes from the verified catalogue record of the one product the add names, never from the
product's name, the page's prose or a guess. Anything code cannot read is `None`, and the
Copilot asks instead of judging.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from agent.llm.intent import IntentCondition
from agent.remembered_sizes import _DIGITS
from agent.storefront import StorefrontDefinition, canonical_colour, colour_label

CONDITION_FALSE = "condition_false"

QUESTION = {
    "ar": "ما قدرتش أتأكد من الشرط ده من بيانات المنتج. تحب أعمل إيه؟",
    "en": "I couldn't check that condition from the product's data. What would you like me to do?",
}


_canonical_colour = canonical_colour


def _fold_size(text: str) -> str:
    return text.strip().translate(_DIGITS).casefold()


def evaluate(
    condition: IntentCondition, product: Any, storefront: StorefrontDefinition
) -> bool | None:
    """True or False when the product's verified record answers the condition, else None."""
    if product is None:
        return None
    fact, comparator, value = condition.fact, condition.comparator, condition.value
    try:
        if fact == "price":
            if product.price.currency != storefront.currency:
                return None
            price, wanted = Decimal(product.price.amount), Decimal(value)
            return {
                "lt": price < wanted,
                "lte": price <= wanted,
                "gt": price > wanted,
                "gte": price >= wanted,
                "eq": price == wanted,
            }[comparator]
        if fact == "in_stock":
            return bool(product.available) == (value == "true")
        if fact == "size_exists":
            exists = _fold_size(value) in {_fold_size(size) for size in product.sizes}
            return exists if comparator == "is" else not exists
        if fact == "colour_exists":
            wanted_colour = _canonical_colour(value, storefront)
            if wanted_colour is None:
                return None
            have = {
                _canonical_colour(colour, storefront) or str(colour).strip().casefold()
                for colour in product.colors
            }
            exists = wanted_colour.casefold() in have
            return exists if comparator == "is" else not exists
    except (InvalidOperation, AttributeError, TypeError, KeyError):
        return None
    return None


def not_met_text(
    condition: IntentCondition, product: Any, language: str, storefront: StorefrontDefinition
) -> str:
    """Why the add was not done, built by code in the Shopper's language."""
    arabic = language == "ar"
    value = condition.value
    positive = condition.comparator != "is_not"
    if condition.fact == "price":
        amount = product.price.amount
        return (
            f"ما ضفتهاش: سعرها {amount} جنيه، والشرط مش متحقق."
            if arabic
            else f"I didn't add it: it costs {amount} {storefront.currency}, "
            "so the condition isn't met."
        )
    if condition.fact == "in_stock":
        if value == "true":
            return (
                "ما ضفتهاش: المنتج مش متاح دلوقتي."
                if arabic
                else "I didn't add it: it's not available right now."
            )
        return (
            "ما ضفتهاش: المنتج متاح، والشرط كان إنه مش متاح."
            if arabic
            else "I didn't add it: it is available, and the condition was that it isn't."
        )
    if condition.fact == "size_exists":
        if arabic:
            verb = "مش موجود" if positive else "موجود"
            return f"ما ضفتهاش: المقاس {value} {verb} في المنتج ده."
        verb = "isn't available" if positive else "is available"
        return f"I didn't add it: size {value} {verb} for this product."
    if arabic:
        verb = "مش موجود" if positive else "موجود"
        return f"ما ضفتهاش: اللون {colour_label(value, language, storefront)} {verb} في المنتج ده."
    verb = "isn't available" if positive else "is available"
    return (
        f"I didn't add it: colour {colour_label(value, language, storefront)} {verb} "
        "for this product."
    )
