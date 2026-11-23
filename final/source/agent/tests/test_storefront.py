from decimal import Decimal

import pytest

from agent.storefront import (
    Money,
    StorefrontDefinitionError,
    UnsupportedCurrencyError,
    load_storefront_definition,
    normalize_money,
    parse_storefront_definition,
)


def valid_definition() -> dict[str, object]:
    return {
        "v": 1,
        "name": "Controlled Storefront",
        "currency": "EGP",
        "routes": {"category": "/c/{category}", "product": "/p/{product_id}"},
        "filters": [
            "q",
            "type",
            "min_price",
            "max_price",
            "size",
            "color",
            "availability",
            "sort",
        ],
        "categories": {
            "shoes": {"ar": "الأحذية", "en": "Shoes"},
            "clothing": {"ar": "الملابس", "en": "Clothing"},
            "bags": {"ar": "الشنط", "en": "Bags"},
            "electronics": {"ar": "الإلكترونيات", "en": "Electronics"},
        },
        "vocabulary": {
            "categories": {
                "shoes": ["shoes", "كوتشي"],
                "clothing": ["clothing", "ملابس"],
                "bags": ["bags", "شنط"],
                "electronics": ["electronics", "إلكترونيات"],
            },
            "types": {"running": ["running", "جري"]},
            "colors": {"black": ["black", "أسود"]},
            "controls": {
                "q": ["بحث", "search"],
                "type": ["النوع", "type"],
                "min_price": ["أقل سعر", "minimum price"],
                "max_price": ["أقصى سعر", "maximum price"],
                "size": ["المقاس", "size"],
                "color": ["اللون", "color"],
                "availability": ["التوفر", "availability"],
                "sort": ["الترتيب", "sort"],
                "submit": ["تطبيق الفلاتر", "apply filters"],
            },
            "availability": {
                "available": ["available", "متاح"],
                "unavailable": ["unavailable", "غير متاح"],
            },
            "sort": {
                "cheapest": ["cheapest", "الأرخص"],
                "newest": ["newest", "الأحدث"],
            },
            "features": {"leather": ["leather", "جلد"]},
            "suitable_for": {"formal_events": ["formal", "فرح"]},
            "soft_preferences": {"lower_price": ["affordable", "مش غالي"]},
        },
        "url_rules": {
            "same_origin_only": True,
            "category_filters_in_query": True,
        },
    }


def test_definition_loads_authoritative_egp_capabilities():
    definition = parse_storefront_definition(valid_definition())

    assert definition.currency == "EGP"
    assert definition.category_route == "/c/{category}"
    assert definition.filters == (
        "q",
        "type",
        "min_price",
        "max_price",
        "size",
        "color",
        "availability",
        "sort",
    )
    assert definition.categories["shoes"].ar == "الأحذية"
    assert definition.vocabulary.categories["shoes"] == ("shoes", "كوتشي")
    assert definition.vocabulary.types["running"] == ("running", "جري")
    assert definition.vocabulary.controls["max_price"] == (
        "أقصى سعر",
        "maximum price",
    )
    assert definition.url_rules.same_origin_only is True
    assert definition.url_rules.category_filters_in_query is True


def test_destination_routes_are_validated_as_same_origin_paths() -> None:
    payload = valid_definition()
    payload["routes"] = {"category": "/c/{category}", "product": "/p/{product_id}", "cart": "/cart"}
    assert parse_storefront_definition(payload).destination_routes["cart"] == "/cart"
    payload["routes"] = {
        "category": "/c/{category}",
        "product": "/p/{product_id}",
        "cart": "https://outside.test/cart",
    }
    with pytest.raises(StorefrontDefinitionError, match="routes.cart"):
        parse_storefront_definition(payload)
    payload["routes"] = {
        "category": "https://outside.test/c/{category}",
        "product": "/p/{product_id}",
    }
    with pytest.raises(StorefrontDefinitionError, match="routes.category"):
        parse_storefront_definition(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.pop("currency"), "currency is required"),
        (lambda value: value.__setitem__("currency", "USD"), "currency must be EGP"),
        (lambda value: value.__setitem__("currency", 123), "currency must be a string"),
        (lambda value: value.__setitem__("filters", ["q", "mystery"]), "unsupported filter"),
        (lambda value: value.__setitem__("categories", {}), "categories must not be empty"),
        (lambda value: value.pop("vocabulary"), "vocabulary is required"),
        (lambda value: value.pop("url_rules"), "url_rules is required"),
    ],
)
def test_definition_rejects_missing_or_malformed_authoritative_configuration(mutation, message):
    payload = valid_definition()
    mutation(payload)

    with pytest.raises(StorefrontDefinitionError, match=message):
        parse_storefront_definition(payload)


def test_default_definition_file_is_valid_json_and_loads():
    definition = load_storefront_definition()

    assert definition.currency == "EGP"
    assert set(definition.categories) == {"shoes", "clothing", "bags", "electronics"}


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("EGP 1,234.50", Decimal("1234.50")),
        ("١٬٢٣٤٫٥٠ جنيه", Decimal("1234.50")),
        ("۱٬۲۳۴٫۵۰ ج.م", Decimal("1234.50")),
        ("1 234,50 LE", Decimal("1234.50")),
        ("2.000 EGP", Decimal("2000")),
        ("٢٠٠٠", Decimal("2000")),
    ],
)
def test_money_normalization_preserves_exact_decimal_amounts(text, amount):
    money = normalize_money(text, currency="EGP")

    assert money == Money(amount=amount, currency="EGP")
    assert isinstance(money.amount, Decimal)


@pytest.mark.parametrize("text", ["$20", "20 USD", "€ 20", "20 SAR"])
def test_money_in_another_currency_is_rejected_without_conversion(text):
    with pytest.raises(UnsupportedCurrencyError, match="provide an EGP amount"):
        normalize_money(text, currency="EGP")


@pytest.mark.parametrize("text", ["", "free", "1,2,3", "-20 EGP", "NaN"])
def test_malformed_money_is_rejected_instead_of_guessed(text):
    with pytest.raises(ValueError):
        normalize_money(text, currency="EGP")
