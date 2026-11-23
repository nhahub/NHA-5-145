from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_FILTERS = (
    "q",
    "type",
    "min_price",
    "max_price",
    "size",
    "color",
    "availability",
    "sort",
)


class StorefrontDefinitionError(ValueError):
    """The authoritative Storefront Definition cannot be used safely."""


class UnsupportedCurrencyError(ValueError):
    """A Shopper supplied a currency the EGP-only Storefront does not support."""


@dataclass(frozen=True)
class CategoryDefinition:
    ar: str
    en: str


@dataclass(frozen=True)
class VocabularyDefinition:
    categories: dict[str, tuple[str, ...]]
    types: dict[str, tuple[str, ...]]
    colors: dict[str, tuple[str, ...]]
    controls: dict[str, tuple[str, ...]]
    availability: dict[str, tuple[str, ...]]
    sort: dict[str, tuple[str, ...]]
    features: dict[str, tuple[str, ...]]
    suitable_for: dict[str, tuple[str, ...]]
    soft_preferences: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class UrlRules:
    same_origin_only: bool
    category_filters_in_query: bool


@dataclass(frozen=True)
class StorefrontDefinition:
    v: int
    name: str
    currency: str
    category_route: str
    product_route: str
    filters: tuple[str, ...]
    categories: dict[str, CategoryDefinition]
    vocabulary: VocabularyDefinition
    url_rules: UrlRules
    destination_routes: dict[str, str]
    color_labels_ar: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money amount must be a Decimal")
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("Money amount must be a non-negative finite decimal")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("Money currency must be an uppercase ISO currency code")


def _definition_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storefront-definition.json"


def _required_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise StorefrontDefinitionError(f"{key} must be an object")
    return value


def _vocabulary_group(
    vocabulary: dict[str, Any],
    key: str,
    *,
    expected_keys: set[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    raw_group = _required_mapping(vocabulary, key)
    if not raw_group:
        raise StorefrontDefinitionError(f"vocabulary.{key} must not be empty")
    if expected_keys is not None and set(raw_group) != expected_keys:
        raise StorefrontDefinitionError(
            f"vocabulary.{key} keys must be {', '.join(sorted(expected_keys))}"
        )
    group: dict[str, tuple[str, ...]] = {}
    for canonical, raw_terms in raw_group.items():
        if (
            not isinstance(canonical, str)
            or not isinstance(raw_terms, list)
            or not raw_terms
            or not all(isinstance(term, str) and term.strip() for term in raw_terms)
        ):
            raise StorefrontDefinitionError(
                f"vocabulary.{key}.{canonical} must be a non-empty list of strings"
            )
        normalized_terms = tuple(term.strip().lower() for term in raw_terms)
        if len(set(normalized_terms)) != len(normalized_terms):
            raise StorefrontDefinitionError(
                f"vocabulary.{key}.{canonical} must not contain duplicates"
            )
        group[canonical] = normalized_terms
    return group


def load_storefront_definition(
    path: str | Path | None = None,
) -> StorefrontDefinition:
    definition_path = Path(path) if path is not None else _definition_path()
    try:
        payload = json.loads(definition_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise StorefrontDefinitionError(
            f"Storefront Definition not found: {definition_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise StorefrontDefinitionError(
            f"Storefront Definition is not valid JSON: {error.msg}"
        ) from error

    return parse_storefront_definition(payload)


def parse_storefront_definition(payload: object) -> StorefrontDefinition:
    """Validate decoded Storefront Definition data without guessing defaults."""

    if not isinstance(payload, dict):
        raise StorefrontDefinitionError("Storefront Definition must be an object")
    if payload.get("v") != 1:
        raise StorefrontDefinitionError("v must be 1")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise StorefrontDefinitionError("name must be a non-empty string")
    if "currency" not in payload:
        raise StorefrontDefinitionError("currency is required")
    currency = payload["currency"]
    if not isinstance(currency, str):
        raise StorefrontDefinitionError("currency must be a string")
    if currency != "EGP":
        raise StorefrontDefinitionError("currency must be EGP for the local MVP")

    routes = _required_mapping(payload, "routes")
    category_route = routes.get("category")
    if not isinstance(category_route, str) or category_route.count("{category}") != 1:
        raise StorefrontDefinitionError("routes.category must contain one {category} placeholder")
    category_parts = urlsplit(category_route)
    if (
        not category_route.startswith("/")
        or category_route.startswith("//")
        or category_parts.scheme
        or category_parts.netloc
        or category_parts.query
        or category_parts.fragment
    ):
        raise StorefrontDefinitionError("routes.category must be a same-origin path")
    product_route = routes.get("product")
    if product_route != "/p/{product_id}":
        raise StorefrontDefinitionError("routes.product must be /p/{product_id} for the local MVP")
    destination_routes: dict[str, str] = {}
    for route_name, route_path in routes.items():
        if route_name in {"category", "product"}:
            continue
        if not isinstance(route_path, str):
            raise StorefrontDefinitionError(f"routes.{route_name} must be a same-origin path")
        parsed_route = urlsplit(route_path)
        if (
            not route_path.startswith("/")
            or route_path.startswith("//")
            or parsed_route.scheme
            or parsed_route.netloc
            or parsed_route.query
            or parsed_route.fragment
        ):
            raise StorefrontDefinitionError(f"routes.{route_name} must be a same-origin path")
        destination_routes[route_name] = route_path

    raw_filters = payload.get("filters")
    if not isinstance(raw_filters, list) or not all(isinstance(item, str) for item in raw_filters):
        raise StorefrontDefinitionError("filters must be a list of strings")
    unknown_filters = [item for item in raw_filters if item not in SUPPORTED_FILTERS]
    if unknown_filters:
        raise StorefrontDefinitionError(
            f"unsupported filter in Storefront Definition: {unknown_filters[0]}"
        )
    if len(set(raw_filters)) != len(raw_filters):
        raise StorefrontDefinitionError("filters must not contain duplicates")

    raw_categories = _required_mapping(payload, "categories")
    if not raw_categories:
        raise StorefrontDefinitionError("categories must not be empty")
    categories: dict[str, CategoryDefinition] = {}
    for slug, raw_category in raw_categories.items():
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", slug):
            raise StorefrontDefinitionError("category slugs must be URL-safe strings")
        if not isinstance(raw_category, dict):
            raise StorefrontDefinitionError(f"category {slug} must be an object")
        ar = raw_category.get("ar")
        en = raw_category.get("en")
        if not isinstance(ar, str) or not ar.strip() or not isinstance(en, str) or not en.strip():
            raise StorefrontDefinitionError(f"category {slug} must have non-empty ar and en names")
        categories[slug] = CategoryDefinition(ar=ar, en=en)

    if "vocabulary" not in payload:
        raise StorefrontDefinitionError("vocabulary is required")
    raw_vocabulary = _required_mapping(payload, "vocabulary")
    vocabulary = VocabularyDefinition(
        categories=_vocabulary_group(raw_vocabulary, "categories", expected_keys=set(categories)),
        types=_vocabulary_group(raw_vocabulary, "types"),
        colors=_vocabulary_group(raw_vocabulary, "colors"),
        controls=_vocabulary_group(
            raw_vocabulary,
            "controls",
            expected_keys={*raw_filters, "submit"},
        ),
        availability=_vocabulary_group(
            raw_vocabulary,
            "availability",
            expected_keys={"available", "unavailable"},
        ),
        sort=_vocabulary_group(
            raw_vocabulary,
            "sort",
            expected_keys={"cheapest", "newest"},
        ),
        features=_vocabulary_group(raw_vocabulary, "features"),
        suitable_for=_vocabulary_group(raw_vocabulary, "suitable_for"),
        soft_preferences=_vocabulary_group(raw_vocabulary, "soft_preferences"),
    )
    if "url_rules" not in payload:
        raise StorefrontDefinitionError("url_rules is required")
    raw_url_rules = _required_mapping(payload, "url_rules")
    if raw_url_rules.get("same_origin_only") is not True:
        raise StorefrontDefinitionError("url_rules.same_origin_only must be true")
    if raw_url_rules.get("category_filters_in_query") is not True:
        raise StorefrontDefinitionError("url_rules.category_filters_in_query must be true")
    url_rules = UrlRules(
        same_origin_only=True,
        category_filters_in_query=True,
    )

    return StorefrontDefinition(
        v=1,
        name=name,
        currency=currency,
        category_route=category_route,
        product_route=product_route,
        filters=tuple(raw_filters),
        categories=categories,
        vocabulary=vocabulary,
        url_rules=url_rules,
        destination_routes=destination_routes,
        color_labels_ar=_colour_labels(payload, vocabulary.colors),
    )


def _colour_labels(payload: dict[str, Any], colors: dict[str, tuple[str, ...]]) -> dict[str, str]:
    raw = payload.get("color_labels", {})
    raw_ar = raw.get("ar", {}) if isinstance(raw, dict) else {}
    if not isinstance(raw_ar, dict):
        raise StorefrontDefinitionError("color_labels.ar must be an object")
    labels: dict[str, str] = {}
    for key, label in raw_ar.items():
        if key not in colors or not isinstance(label, str) or not label.strip():
            raise StorefrontDefinitionError(f"color_labels.ar.{key} must name a Storefront colour")
        labels[key] = label.strip()
    return labels


def canonical_colour(text: object, storefront: StorefrontDefinition) -> str | None:
    """The Storefront colour a word names (the key itself or any alias), else None."""
    if not isinstance(text, str):
        return None
    word = text.strip().casefold()
    for canonical, aliases in storefront.vocabulary.colors.items():
        if word == canonical.casefold() or word in {alias.casefold() for alias in aliases}:
            return canonical
    return None


def colour_label(
    value: object, language: str, storefront: StorefrontDefinition, *, definite: bool = False
) -> str:
    """A colour in the Shopper's language. Arabic uses the definition's label ("الأصفر" when
    ``definite``, for use after "اللون"); English keeps the key. A value the Storefront does
    not know, such as a page option, is returned as it is."""
    text = str(value if value is not None else "").strip()
    canonical = canonical_colour(text, storefront)
    if canonical is None:
        return text
    if language == "ar":
        label = storefront.color_labels_ar.get(canonical)
        if label is None:
            return text
        return f"ال{label}" if definite else label
    return canonical if text.casefold() != canonical else text


_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_EGP_MARKERS = re.compile(
    r"(?:\bEGP\b|\bL\.?\s*E\.?\b|ج\s*\.\s*م|جنيه(?:\s+مصري)?)",
    re.IGNORECASE,
)
_OTHER_CURRENCIES = re.compile(
    r"(?:\$|€|£|\bUSD\b|\bEUR\b|\bGBP\b|\bSAR\b|ر\s*\.\s*س|ريال(?:\s+سعودي)?)",
    re.IGNORECASE,
)


def _normalize_decimal_text(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if not compact or not re.fullmatch(r"[0-9.,]+", compact):
        raise ValueError("money amount is malformed")

    if "," in compact and "." in compact:
        decimal_separator = "," if compact.rfind(",") > compact.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        whole, fraction = compact.rsplit(decimal_separator, 1)
        groups = whole.split(thousands_separator)
        if (
            not (1 <= len(fraction) <= 2)
            or not fraction.isdigit()
            or len(groups) < 2
            or not groups[0].isdigit()
            or not all(len(group) == 3 and group.isdigit() for group in groups[1:])
        ):
            raise ValueError("money amount has malformed separators")
        return f"{''.join(groups)}.{fraction}"

    if "," in compact:
        groups = compact.split(",")
        if (
            len(groups) == 2
            and 1 <= len(groups[1]) <= 2
            and all(group.isdigit() for group in groups)
        ):
            return f"{groups[0]}.{groups[1]}"
        if groups[0].isdigit() and all(len(group) == 3 and group.isdigit() for group in groups[1:]):
            return "".join(groups)
        raise ValueError("money amount has malformed separators")

    if compact.count(".") > 1:
        groups = compact.split(".")
        if groups[0].isdigit() and all(len(group) == 3 and group.isdigit() for group in groups[1:]):
            return "".join(groups)
        raise ValueError("money amount has malformed separators")
    if "." in compact:
        whole, fraction = compact.split(".")
        if whole.isdigit() and len(fraction) == 3 and fraction.isdigit():
            return f"{whole}{fraction}"
        if not whole.isdigit() or not fraction.isdigit() or not (1 <= len(fraction) <= 2):
            raise ValueError("money amount has malformed separators")
    return compact


def normalize_money(text: str, *, currency: str) -> Money:
    if currency != "EGP":
        raise StorefrontDefinitionError("configured currency must be EGP")
    if not isinstance(text, str):
        raise TypeError("money text must be a string")
    normalized = text.translate(_DIGIT_TRANSLATION).replace("٬", ",").replace("٫", ".")
    if _OTHER_CURRENCIES.search(normalized):
        raise UnsupportedCurrencyError("Currency conversion is unavailable; provide an EGP amount")
    normalized = _EGP_MARKERS.sub("", normalized).strip()
    if normalized.startswith("-"):
        raise ValueError("money amount must not be negative")
    decimal_text = _normalize_decimal_text(normalized)
    try:
        amount = Decimal(decimal_text)
    except InvalidOperation as error:
        raise ValueError("money amount is malformed") from error
    return Money(amount=amount, currency=currency)
