"""Resolve a product the Shopper named (open or add) from the verified catalogue (B5).

The interpreter only marks the request (`request_mode: "open"`) and copies the name from the
Shopper's words into `constraints.query`. Code decides the product: the name must occur in the
Shopper's own words, and the product's Arabic or English catalogue name must equal it after
normalisation (the same normalisation as the ticket 08 name check). Exactly one product opens
(or is added); several give cards and a question; none falls back to the normal search. The
model never supplies the product id on this path, and names stay out of event records.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from agent.catalogue import DiscoveryResult, Suggestion
from agent.llm.intent import StructuredIntent
from agent.product_confirmation import CONFIRMED_KEY, NAMED_KEY, reference_names
from agent.product_reference import names_product, product_name_tokens

MAX_NAME_CHARS = 200
MAX_CARDS = 3
QUESTION = {"ar": "تقصد أنهي منتج؟", "en": "Which product do you mean?"}
CARD_REASON = {
    "ar": "اسمه بيطابق كلامك.",
    "en": "Its name matches what you said.",
}
_VARIANTS = ("size", "color")


@dataclass(frozen=True)
class NamedProduct:
    """One catalogue product, whichever catalogue API it came from."""

    id: str
    name_ar: str
    name_en: str
    price: str
    currency: str
    record: Any = None

    def card(self, language: str) -> Suggestion:
        # Both names: products that share one name differ in the other, and either one the
        # Shopper then says counts as naming the product (ticket 08).
        return Suggestion(
            self.id,
            "exact_match",
            f"{self.name_ar} / {self.name_en}",
            self.price,
            self.currency,
            CARD_REASON["ar" if language == "ar" else "en"],
            (),
        )


@dataclass
class Resolution:
    kind: Literal["one", "several", "none"]
    # "one": the open_product / cart add intent with the product id; "several": unchanged;
    # "none": the request rewritten as the plain search it falls back to.
    intent: StructuredIntent
    products: list[NamedProduct]

    @property
    def choices(self) -> DiscoveryResult:
        language = self.intent.language
        return DiscoveryResult(None, tuple(p.card(language) for p in self.products[:MAX_CARDS]))


def from_candidate(candidate) -> NamedProduct:
    product = candidate.product
    return NamedProduct(
        product.id,
        product.nameAr,
        product.nameEn,
        product.price.amount,
        product.price.currency,
        candidate,
    )


def from_catalogue_product(product) -> NamedProduct:
    return NamedProduct(
        product.id,
        product.name_ar,
        product.name_en,
        product.price.amount,
        product.price.currency,
        product,
    )


def is_open_by_name(intent: StructuredIntent) -> bool:
    return intent.request_mode == "open" and not intent.needs_clarification


def shopper_words(message: object, state: Any) -> list[object]:
    """The Shopper's own words for this task: the message, the original one and the answers."""
    answers = state.get("_answers") or []
    return [message, state.get("_original_message"), *answers]


def _same_name(name: str, candidate: str) -> bool:
    wanted = product_name_tokens(name)
    return bool(wanted) and wanted == product_name_tokens(candidate)


def requested_name(intent: StructuredIntent, words: Sequence[object]) -> str | None:
    """The name to look up: copied by the model, and really in the Shopper's words."""
    name = (intent.constraints.query or "").strip()
    if not name or len(name) > MAX_NAME_CHARS:
        return None
    if not any(isinstance(text, str) and names_product(text, name) for text in words):
        return None
    return name


def _payload(intent: StructuredIntent) -> dict[str, Any]:
    return intent.model_dump(mode="json")


def _variants(intent: StructuredIntent) -> dict[str, Any]:
    constraints = intent.constraints.model_dump(mode="json")
    return {key: constraints[key] for key in _VARIANTS if constraints.get(key) is not None}


def opened(intent: StructuredIntent, product_id: str) -> StructuredIntent:
    """The marked request as the ordinary intent for exactly this code-chosen product."""
    payload = _payload(intent)
    payload.update(product_id=product_id, request_mode="browse")
    if intent.intent == "cart_edit":
        payload["constraints"] = _variants(intent)
    else:
        payload.update(
            intent="open_product",
            constraints={},
            catalogue_requirements=[],
            price_preference=None,
            owned_item=None,
            owned_items=[],
            preferred_colors=[],
            subjective_preferences=[],
            desired_wear_position=None,
            advice_product_ids=[],
            revised_fields=[],
            revision_source=None,
        )
    return StructuredIntent.model_validate(payload)


def as_search(intent: StructuredIntent, *, category_missing: bool = False) -> StructuredIntent:
    """No product has this name: the request becomes the plain search for those words."""
    payload = _payload(intent)
    payload.update(
        intent="find_products",
        request_mode="browse",
        product_id=None,
        cart_operation=None,
        cart_source=None,
        cart_target=None,
        cart_target_id=None,
        cart_quantity=None,
        cart_quantity_mode=None,
        refers_to_this=False,
        condition=None,
    )
    if category_missing:
        # Without the retrieval loop a search needs a category: ask for it, as always.
        payload.update(needs_clarification=True, missing_fields=["category"])
    return StructuredIntent.model_validate(payload)


async def resolve_named_product(
    intent: StructuredIntent,
    words: Sequence[object],
    lookup: Callable[[str], Awaitable[Sequence[NamedProduct]]],
    *,
    category_missing: bool = False,
) -> Resolution:
    """Decide a request marked request_mode=open; `lookup` reads the verified catalogue."""
    name = requested_name(intent, words)
    found: list[NamedProduct] = []
    if name is not None:
        seen: set[str] = set()
        for product in await lookup(name):
            if product.id not in seen and (
                _same_name(name, product.name_ar) or _same_name(name, product.name_en)
            ):
                seen.add(product.id)
                found.append(product)
    if len(found) == 1:
        return Resolution("one", opened(intent, found[0].id), found)
    if found:
        return Resolution("several", intent, found)
    return Resolution("none", as_search(intent, category_missing=category_missing), [])


def needs_name_check(intent: StructuredIntent, state: Any) -> bool:
    """A model-chosen product (open, or a cart add) the Shopper's words must not contradict."""
    product_id = intent.product_id
    if (
        product_id is None
        or intent.needs_clarification
        or intent.request_mode == "open"
        or not (
            intent.intent == "open_product"
            or (intent.intent == "cart_edit" and intent.cart_operation == "add")
        )
    ):
        return False
    if product_id in (state.get(CONFIRMED_KEY), state.get(NAMED_KEY)):
        return False  # the Shopper said yes to it, or code resolved it from their name
    draft = state.get("_intent")
    if isinstance(draft, dict) and draft.get("product_id") == product_id:
        return False  # answering a question about this very product: it was settled earlier
    candidates = {i.get("id") for i in state.get("_this_candidates", []) if isinstance(i, dict)}
    return not (intent.refers_to_this and product_id in candidates)  # code resolved "this"


async def check_chosen_product(
    intent: StructuredIntent,
    words: Sequence[object],
    state: Any,
    snapshot: Any,
    storefront: Any,
    lookup: Callable[[str], Awaitable[Sequence[NamedProduct]]],
) -> Resolution | None:
    """Does the Shopper's own wording name a DIFFERENT catalogue product than the model chose?

    The model may pick the open page's product for "add Quick Step" (ticket 08 exempts the
    open page). Names come from the verified catalogue, matched like tickets 06/08. Exactly one
    other product named: switch to it ("one"). Several: ask which ("several"). The chosen
    product's own name present, or no other product named: None (behave as before).
    """
    texts = [t for t in words if isinstance(t, str) and t.strip()]
    chosen = intent.product_id
    if not texts or chosen is None:
        return None
    if any(
        names_product(text, part)
        for part in reference_names(chosen, state, snapshot, storefront)
        for text in texts
    ):
        return None
    named: dict[str, NamedProduct] = {}
    for product in await lookup(texts[0][:1024]):
        if any(
            names_product(text, name)
            for text in texts
            for name in (product.name_ar, product.name_en)
        ):
            named.setdefault(product.id, product)
    if chosen in named:
        return None
    others = list(named.values())
    if len(others) == 1:
        return Resolution("one", opened(intent, others[0].id), others)
    if others:
        return Resolution("several", intent, others)
    return None


def choice_intent(language: str) -> StructuredIntent:
    """The read-only intent a "which product?" answer is published under."""
    return StructuredIntent.model_validate(
        {
            "v": 9,
            "language": language,
            "dialect": "unknown",
            "intent": "advice",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )
