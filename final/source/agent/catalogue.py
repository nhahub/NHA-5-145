from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.llm.intent import StructuredIntent
from agent.storefront import load_storefront_definition

CATALOGUE_URL = "http://127.0.0.1:4000/__catalogue/v1/products"


class CatalogueModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class CatalogueMoney(CatalogueModel):
    amount: str
    currency: Literal["EGP"]

    @field_validator("amount")
    @classmethod
    def exact_decimal(cls, value: str) -> str:
        if re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d{1,2})?", value) is None:
            raise ValueError("Catalogue amount must be a non-negative exact decimal")
        return value


class CatalogueProduct(CatalogueModel):
    id: str
    category: str
    name_ar: str
    name_en: str
    product_type: str
    price: CatalogueMoney
    sizes: list[str]
    colors: list[str]
    available: bool
    added_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    features: list[str]
    suitable_for: list[str]
    wear_position: Literal["upper", "lower"] | None


class CatalogueSnapshot(CatalogueModel):
    v: Literal[1]
    currency: Literal["EGP"]
    products: list[CatalogueProduct] = Field(min_length=1)

    def validated_products(self) -> list[CatalogueProduct]:
        ids = [product.id for product in self.products]
        if len(ids) != len(set(ids)):
            raise ValueError("Catalogue product IDs must be unique")
        for product in self.products:
            Decimal(product.price.amount)
        return self.products


class CatalogueReader(Protocol):
    async def read(self) -> CatalogueSnapshot: ...


class HttpCatalogueReader:
    async def read(self) -> CatalogueSnapshot:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(CATALOGUE_URL)
            response.raise_for_status()
            snapshot = CatalogueSnapshot.model_validate(response.json())
            snapshot.validated_products()
            return snapshot


@dataclass(frozen=True)
class Suggestion:
    id: str
    label: Literal["exact_match", "alternative", "styling_suggestion"]
    name: str
    price: str
    currency: str
    reason: str
    unmet: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "reason": self.reason,
            "unmet": list(self.unmet),
        }


@dataclass(frozen=True)
class DiscoveryResult:
    exact_count: int | None
    suggestions: tuple[Suggestion, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "exact_count": self.exact_count,
            "suggestions": [item.to_wire() for item in self.suggestions],
        }


_NEUTRAL_PALETTE = ("white", "cream", "gray", "beige")
_FACT_AR = {
    "leather": "جلد",
    "lightweight": "خفيف",
    "breathable": "جيد التهوية",
    "comfortable": "مريح",
    "grip": "ثبات",
    "light_color": "ألوان فاتحة",
    "formal_events": "مناسب للمناسبات الرسمية",
    "hot_weather": "مناسب للجو الحار",
    "beach": "مناسب للبحر",
    "daily_workouts": "مناسب للتمرين اليومي",
    "road_running": "مناسب للجري في الشارع",
    "hiking": "مناسب للمشي الجبلي",
    "black": "أسود",
    "brown": "بني",
    "shirts": "قميص",
    "running": "حذاء جري",
    "white": "أبيض",
    "cream": "كريمي",
    "gray": "رمادي",
    "beige": "بيج",
    "blue": "أزرق",
    "green": "أخضر",
    "red": "أحمر",
    "upper": "علوية",
    "lower": "سفلية",
    "footwear": "حذاء",
    "shoes": "أحذية",
    "clothing": "ملابس",
}
# Every Storefront colour is named in Arabic from the one definition, not a second list.
_FACT_AR.update(load_storefront_definition().color_labels_ar)
_FACT_EN = {
    "leather": "leather",
    "lightweight": "lightweight",
    "breathable": "breathable",
    "comfortable": "comfortable",
    "grip": "grip",
    "light_color": "light colours",
    "formal_events": "suitable for formal events",
    "hot_weather": "suited to hot weather",
    "beach": "suited to the beach",
    "daily_workouts": "suitable for daily workouts",
    "road_running": "suitable for street running",
    "hiking": "suitable for hiking",
    "black": "black",
    "brown": "brown",
    "shirts": "shirt",
    "running": "running shoe",
}


def _fact(value: str, arabic: bool) -> str:
    labels = _FACT_AR if arabic else _FACT_EN
    return labels.get(value, value.replace("_", " "))


def _verified_reason(product: CatalogueProduct, intent: StructuredIntent, arabic: bool) -> str:
    facts: list[str] = []
    constraints = intent.constraints
    if constraints.product_type == product.product_type:
        facts.append(_fact(product.product_type, arabic))
    if constraints.color in product.colors:
        facts.append(("اللون " if arabic else "colour ") + _fact(constraints.color, arabic))
    if constraints.size in product.sizes:
        facts.append(("مقاس " if arabic else "size ") + str(constraints.size))
    for requirement in intent.catalogue_requirements:
        values = product.features if requirement.kind == "feature" else product.suitable_for
        if not requirement.excluded and requirement.value in values:
            facts.append(_fact(requirement.value, arabic))
    if intent.request_mode == "recommend":
        facts.extend(_fact(value, arabic) for value in product.features[:2])
        price = f"{product.price.amount} {product.price.currency}"
        maximum = constraints.max_price
        within_budget = (
            maximum is not None and Decimal(product.price.amount) <= maximum.to_money().amount
        )
        price_reason = (
            f"سعره {price}، ضمن ميزانيتك {maximum.amount} {maximum.currency}"
            if arabic and within_budget
            else f"At {price}, within your {maximum.amount} {maximum.currency} budget"
            if within_budget
            else f"سعره {price}"
            if arabic
            else f"Priced at {price}"
        )
        details = "، ".join(dict.fromkeys(facts)) if arabic else ", ".join(dict.fromkeys(facts))
        intro = (
            (
                "اختيار يناسب الشروط التي حددتها"
                if arabic
                else "An option that meets your stated requirements"
            )
            if not _unmet(product, intent)
            else (
                "بديل للمقارنة؛ راجع الشروط غير المتحققة أدناه"
                if arabic
                else "An alternative to compare; check the unmet requirements below"
            )
        )
        return f"{intro}. {price_reason}." + (
            (f" موثق في المتجر: {details}." if arabic else f" Listed by the store: {details}.")
            if details
            else ""
        )
    if not facts:
        return "منتج متاح في القسم المطلوب." if arabic else "Available in the requested category."
    return ("موثق: " if arabic else "Verified: ") + ", ".join(dict.fromkeys(facts)) + "."


def _display_unmet(code: str, arabic: bool) -> str:
    field, _, value = code.partition(": ")
    if field == "excluded_unverified":
        return (
            f"غياب {_fact(value, True)} غير موثق؛ تحقق من خامة أو مواصفات المنتج"
            if arabic
            else f"Absence of {_fact(value, False)} is unverified; check the product specifications"
        )
    if field == "color":
        return (
            f"اللون {_fact(value, True)} غير متاح لهذا المنتج"
            if arabic
            else f"{_fact(value, False)} is not an available colour"
        )
    if field == "size":
        return f"مقاس {value} غير متاح" if arabic else f"size {value} is unavailable"
    if field in {"feature", "suitable_for"}:
        return (
            f"{_fact(value, True)} غير موثق لهذا المنتج"
            if arabic
            else f"{_fact(value, False)} is not verified for this product"
        )
    if field == "product_type":
        return f"ليس من نوع {_fact(value, True)}" if arabic else f"not a {_fact(value, False)}"
    if field == "wear_position":
        return (
            f"موضع اللبس المطلوب {_fact(value, True)} غير متحقق"
            if arabic
            else f"requested wear position {value} is unmet"
        )
    return f"الشرط {value} غير متحقق أو غير موثق" if arabic else f"{value} is unmet or unverified"


def _unmet(product: CatalogueProduct, intent: StructuredIntent) -> tuple[str, ...]:
    constraints = intent.constraints
    misses: list[str] = []
    for field, value in (
        ("category", constraints.category),
        ("product_type", constraints.product_type),
        ("size", constraints.size),
        ("color", constraints.color),
    ):
        if value is None:
            continue
        actual = (
            product.category
            if field == "category"
            else product.product_type
            if field == "product_type"
            else product.sizes
            if field == "size"
            else product.colors
        )
        matches = value in actual if isinstance(actual, list) else value == actual
        if not matches:
            misses.append(f"{field}: {value}")
    for requirement in intent.catalogue_requirements:
        actual = product.features if requirement.kind == "feature" else product.suitable_for
        if requirement.excluded:
            # Positive fact lists cannot establish an explicit negative claim.
            misses.append(f"excluded_unverified: {requirement.value}")
        elif requirement.value not in actual:
            misses.append(f"{requirement.kind}: {requirement.value}")
    if constraints.query is not None:
        searchable = " ".join(
            (
                product.name_ar,
                product.name_en,
                product.product_type,
                *product.colors,
                *product.features,
                *product.suitable_for,
            )
        ).casefold()
        if constraints.query.casefold() not in searchable:
            misses.append(f"query: {constraints.query}")
    if (
        constraints.max_price is not None
        and Decimal(product.price.amount) > constraints.max_price.to_money().amount
    ):
        misses.append(f"max_price: {constraints.max_price.amount} EGP")
    if (
        constraints.min_price is not None
        and Decimal(product.price.amount) < constraints.min_price.to_money().amount
    ):
        misses.append(f"min_price: {constraints.min_price.amount} EGP")
    return tuple(misses)


def _matches_wear_position(product: CatalogueProduct, position: str | None) -> bool:
    if position is None:
        return True
    if position == "footwear":
        return product.category == "shoes"
    return product.wear_position == position


def _style_unmet(product: CatalogueProduct, intent: StructuredIntent) -> tuple[str, ...]:
    misses = list(_unmet(product, intent))
    if not _matches_wear_position(product, intent.desired_wear_position):
        misses.append(f"wear_position: {intent.desired_wear_position}")
    return tuple(misses)


def _style_colour(product: CatalogueProduct, intent: StructuredIntent) -> tuple[int, str | None]:
    palette = tuple(intent.preferred_colors) or _NEUTRAL_PALETTE
    for index, colour in enumerate(palette):
        if colour in product.colors:
            return index, colour
    return len(palette), product.colors[0] if product.colors else None


def _style_sort_key(product: CatalogueProduct, intent: StructuredIntent) -> tuple[object, ...]:
    colour_rank, _ = _style_colour(product, intent)
    if intent.constraints.sort == "newest":
        return (product.added_at, colour_rank, product.id)
    if intent.constraints.sort == "cheapest" or intent.price_preference is not None:
        return (Decimal(product.price.amount), colour_rank, product.id)
    return (colour_rank, product.id)


def _style_reason(product: CatalogueProduct, intent: StructuredIntent, arabic: bool) -> str:
    _, colour = _style_colour(product, intent)
    owned_colours = {item.color for item in intent.context_items if item.color is not None}
    position = intent.desired_wear_position or product.wear_position or product.category
    position_label = _fact(position, arabic)
    arabic_subject = "حذاء" if position == "footwear" else f"قطعة {position_label}"
    arabic_available = "متاح" if position == "footwear" else "متاحة"
    if colour is None:
        return (
            f"{arabic_subject} {arabic_available}؛ لونه غير موثق في بيانات المتجر."
            if arabic
            else f"Available {position_label} item; colour is unverified in the catalogue."
        )
    colour_label = _fact(colour, arabic)
    if colour in owned_colours:
        return (
            f"{arabic_subject} {arabic_available} باللون {colour_label}، "
            "وهو لون مذكور في القطع التي تملكها."
            if arabic
            else (f"Available {position_label} item in {colour_label}, a colour you said you own.")
        )
    if colour in _NEUTRAL_PALETTE:
        return (
            f"{arabic_subject} {arabic_available} باللون {colour_label}؛ اختيار محايد للتنسيق."
            if arabic
            else (
                f"Available {position_label} item in {colour_label}; "
                "it offers neutral colour balance."
            )
        )
    return (
        f"{arabic_subject} {arabic_available} باللون {colour_label}؛ اقتراح لون اختياري."
        if arabic
        else (
            f"Available {position_label} item in {colour_label}; "
            "this is an optional colour suggestion."
        )
    )


def _diverse_style_candidates(
    candidates: list[tuple[CatalogueProduct, tuple[str, ...]]], intent: StructuredIntent
) -> list[tuple[CatalogueProduct, tuple[str, ...]]]:
    if intent.constraints.sort == "cheapest" or intent.price_preference is not None:
        return candidates[:3]
    selected: list[tuple[CatalogueProduct, tuple[str, ...]]] = []
    used_colours: set[str | None] = set()
    for candidate in candidates:
        _, colour = _style_colour(candidate[0], intent)
        if colour in used_colours:
            continue
        selected.append(candidate)
        used_colours.add(colour)
        if len(selected) == 3:
            return selected
    for candidate in candidates:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) == 3:
            break
    return selected


def _violates_exclusion(product: CatalogueProduct, intent: StructuredIntent) -> bool:
    return any(
        requirement.excluded
        and requirement.value
        in (product.features if requirement.kind == "feature" else product.suitable_for)
        for requirement in intent.catalogue_requirements
    )


def evaluate_catalogue(catalogue: CatalogueSnapshot, intent: StructuredIntent) -> DiscoveryResult:
    if intent.intent != "find_products" or intent.needs_clarification:
        raise ValueError("Catalogue evaluation requires a complete discovery intent")
    if intent.constraints.availability == "unavailable":
        return DiscoveryResult(exact_count=0, suggestions=())
    products = [
        product
        for product in catalogue.validated_products()
        if not _violates_exclusion(product, intent)
    ]
    arabic = intent.language == "ar"
    category = intent.constraints.category
    if category is None:
        raise ValueError("Discovery category is unresolved")
    is_style_request = intent.request_mode == "style" or (
        intent.desired_wear_position is not None and bool(intent.context_items)
    )
    if is_style_request:
        eligible = [
            product for product in products if product.available and product.category == category
        ]
        scored = [(product, _style_unmet(product, intent)) for product in eligible]
        exact = [(product, misses) for product, misses in scored if not misses]
        if intent.constraints.sort == "newest":
            exact.sort(key=lambda pair: _style_sort_key(pair[0], intent), reverse=True)
        else:
            exact.sort(key=lambda pair: _style_sort_key(pair[0], intent))
        selected = _diverse_style_candidates(exact, intent)
        if not selected:
            alternatives = [
                pair
                for pair in scored
                if pair[1]
                and len(pair[1]) <= 2
                and len(pair[1]) < max(2, len(intent.catalogue_requirements) + 2)
            ]
            alternatives.sort(key=lambda pair: (len(pair[1]), *_style_sort_key(pair[0], intent)))
            if alternatives:
                fewest_misses = len(alternatives[0][1])
                selected = _diverse_style_candidates(
                    [pair for pair in alternatives if len(pair[1]) == fewest_misses], intent
                )
        return DiscoveryResult(
            # Styling Suggestions remain distinct from Exact Matches in the shopper-facing
            # result contract, even when every requested product fact is verified.
            exact_count=0,
            suggestions=tuple(
                Suggestion(
                    id=product.id,
                    label="styling_suggestion" if not misses else "alternative",
                    name=product.name_ar if arabic else product.name_en,
                    price=product.price.amount,
                    currency=product.price.currency,
                    reason=(
                        _style_reason(product, intent, arabic)
                        if not misses
                        else _verified_reason(product, intent, arabic)
                    ),
                    unmet=tuple(_display_unmet(code, arabic) for code in misses),
                )
                for product, misses in selected
            ),
        )

    eligible = [
        product for product in products if product.available and product.category == category
    ]
    scored = [(product, _unmet(product, intent)) for product in eligible]
    exact = [(product, misses) for product, misses in scored if not misses]
    sort_price = intent.price_preference is not None or intent.constraints.sort == "cheapest"
    if sort_price:
        exact.sort(key=lambda pair: (Decimal(pair[0].price.amount), pair[0].id))
    elif intent.constraints.sort == "newest":
        exact.sort(key=lambda pair: (pair[0].added_at, pair[0].id), reverse=True)
    else:
        exact.sort(key=lambda pair: pair[0].id)
    selected = exact[:3]
    if not selected:
        alternatives = [
            pair
            for pair in scored
            if pair[1]
            and len(pair[1]) <= 2
            and len(pair[1]) < max(2, len(intent.catalogue_requirements) + 2)
        ]
        alternatives.sort(
            key=lambda pair: (
                len(pair[1]),
                Decimal(pair[0].price.amount),
                pair[0].id,
            )
        )
        if alternatives:
            fewest_misses = len(alternatives[0][1])
            selected.extend(pair for pair in alternatives if len(pair[1]) == fewest_misses)
            selected = selected[:3]
    suggestions = tuple(
        Suggestion(
            id=product.id,
            label="exact_match" if not misses else "alternative",
            name=product.name_ar if arabic else product.name_en,
            price=product.price.amount,
            currency=product.price.currency,
            reason=_verified_reason(product, intent, arabic),
            unmet=tuple(_display_unmet(code, arabic) for code in misses),
        )
        for product, misses in selected
    )
    return DiscoveryResult(exact_count=len(exact), suggestions=suggestions)
