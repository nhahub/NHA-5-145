from dataclasses import dataclass
from typing import Literal

AssertionKind = Literal[
    "url_matches",
    "element_visible",
    "element_spotlighted",
    "store_state",
    "panel_text",
    "panel_contains",
    "panel_count",
]
Language = Literal["ar", "en"]
ExpectedStatus = Literal["complete", "question"]
CaseSetup = Literal["authenticated", "selected_swatch", "disabled_product", "loaded_catalogue"]


@dataclass(frozen=True)
class EvaluationAssertion:
    kind: AssertionKind
    target: str
    expected: str | None = None


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    message: str
    language: Language
    assertions: tuple[EvaluationAssertion, ...]
    timeout_ms: int = 10_000
    expected_status: ExpectedStatus = "complete"
    setup: CaseSetup | None = None
    viewport: tuple[int, int] | None = None


FILTER_ASSERTIONS = (
    EvaluationAssertion(
        kind="url_matches",
        target=r"/c/shoes\?type=running&max_price=2000$",
    ),
    EvaluationAssertion(kind="element_visible", target="#results-heading", expected="3 منتجات"),
    EvaluationAssertion(
        kind="store_state",
        target="filters.type",
        expected="running",
    ),
    EvaluationAssertion(kind="store_state", target="filters.max_price.amount", expected="2000"),
    EvaluationAssertion(kind="store_state", target="filters.max_price.currency", expected="EGP"),
    EvaluationAssertion(kind="store_state", target="product_count", expected="3"),
)

INITIAL_FILTER_CASES = (
    EvaluationCase(
        case_id="filter-ar",
        message="عاوز كوتشي للجري بأقل من ٢٠٠٠",
        language="ar",
        assertions=FILTER_ASSERTIONS,
    ),
    EvaluationCase(
        case_id="filter-en",
        message="Show me running shoes under 2000 EGP",
        language="en",
        assertions=FILTER_ASSERTIONS,
    ),
)

DISCOVERY_CASES = INITIAL_FILTER_CASES + (
    EvaluationCase(
        case_id="filter-franco",
        message="3ayez kootshi running ta7t 2,000 EGP",
        language="en",
        assertions=FILTER_ASSERTIONS,
    ),
    EvaluationCase(
        case_id="filter-mixed",
        message="عاوز black running shoes مقاس 42 تحت 2500 EGP والأرخص",
        language="ar",
        assertions=(
            EvaluationAssertion(
                kind="url_matches",
                target=(
                    r"/c/shoes\?type=running&max_price=2500&size=42&color=black&sort=cheapest$"
                ),
            ),
            EvaluationAssertion(
                kind="element_visible", target="#results-heading", expected="2 منتجات"
            ),
            EvaluationAssertion(kind="store_state", target="filters.size", expected="42"),
            EvaluationAssertion(kind="store_state", target="filters.color", expected="black"),
            EvaluationAssertion(kind="store_state", target="filters.sort", expected="cheapest"),
            EvaluationAssertion(kind="store_state", target="product_count", expected="2"),
        ),
    ),
    EvaluationCase(
        case_id="filter-unavailable",
        message="Show unavailable bags newest first",
        language="en",
        assertions=(
            EvaluationAssertion(
                kind="url_matches",
                target=r"/c/bags\?availability=unavailable&sort=newest$",
            ),
            EvaluationAssertion(
                kind="element_visible", target="#results-heading", expected="3 منتجات"
            ),
            EvaluationAssertion(
                kind="store_state", target="filters.availability", expected="unavailable"
            ),
            EvaluationAssertion(kind="store_state", target="filters.sort", expected="newest"),
            EvaluationAssertion(kind="store_state", target="product_count", expected="3"),
        ),
    ),
    EvaluationCase(
        case_id="filter-empty",
        message="Show black running shoes size 99 under 100 EGP",
        language="en",
        assertions=(
            EvaluationAssertion(
                kind="panel_text",
                target="#conversation li:last-child",
                expected="No products match your request.",
            ),
            EvaluationAssertion(
                kind="element_visible", target="#results-heading", expected="0 منتجات"
            ),
            EvaluationAssertion(
                kind="element_visible",
                target='[role="status"]',
                expected="لا توجد منتجات مطابقة. جرّب إزالة فلتر اللون.",
            ),
            EvaluationAssertion(kind="store_state", target="product_count", expected="0"),
        ),
    ),
    EvaluationCase(
        case_id="ask-ambiguous",
        message="Show me something under 1000 EGP",
        language="en",
        assertions=(
            EvaluationAssertion(
                kind="panel_text",
                target="#pending-question p",
                expected="Which category should I search?",
            ),
        ),
        expected_status="question",
    ),
)


TICKET_08_CASES = (
    EvaluationCase(
        case_id="ticket08-locate-cart",
        message="Where is my cart?",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"http://localhost:4000/$"),
            EvaluationAssertion("element_spotlighted", 'a[href="/cart"]'),
        ),
    ),
    EvaluationCase(
        case_id="ticket08-navigate-cart",
        message="Open my cart",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"http://localhost:4000/cart$"),
            EvaluationAssertion("element_visible", "h1", "السلة"),
            EvaluationAssertion("element_visible", 'a[href="/checkout"]'),
        ),
    ),
    EvaluationCase(
        case_id="ticket08-locate-orders",
        message="Where is my order history?",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"http://localhost:4000/$"),
            EvaluationAssertion("element_spotlighted", 'a[href="/account"]'),
        ),
    ),
    EvaluationCase(
        case_id="ticket08-orders-logged-out",
        message="Open order history",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"/login\?next=%2Faccount%2Forders$"),
            EvaluationAssertion("element_visible", "h1", "تسجيل الدخول"),
            EvaluationAssertion(
                "panel_text",
                "#pending-question p",
                "After signing in, should I continue to the newest order?",
            ),
        ),
        expected_status="question",
    ),
    EvaluationCase(
        case_id="ticket08-orders-authenticated",
        message="Open order history",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"/account/orders$"),
            EvaluationAssertion("element_visible", "h1", "الطلبات"),
            EvaluationAssertion("element_visible", 'a[href="#order-1003"]', "أحدث طلب"),
            EvaluationAssertion("element_spotlighted", 'a[href="#order-1003"]'),
        ),
        setup="authenticated",
    ),
    EvaluationCase(
        case_id="ticket08-navigate-account",
        message="Open my account",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"/account$"),
            EvaluationAssertion("element_visible", "h1", "الحساب"),
        ),
    ),
    EvaluationCase(
        case_id="ticket08-navigate-checkout",
        message="Open checkout",
        language="en",
        assertions=(
            EvaluationAssertion("url_matches", r"/checkout$"),
            EvaluationAssertion("element_visible", "h1", "إتمام الشراء"),
        ),
    ),
)


OWNER_07E_CASES = (
    EvaluationCase(
        case_id="owner-summer-shirt",
        message=(
            "نا مسافر أصيّف في شرم الشيخ الأسبوع الجاي ومحتاج قميص صيفي خفيف "
            "وبحر كده يكون مريح وألوانه فاتحة"
        ),
        language="ar",
        timeout_ms=90_000,
        assertions=(
            EvaluationAssertion("panel_count", ".suggestion-exact_match", "1"),
            EvaluationAssertion("panel_contains", '[data-product-id="clothing-04"]', "EGP"),
        ),
    ),
    EvaluationCase(
        case_id="owner-wedding-shoes",
        message=(
            "3andy wedding kaman kam yom w me7tag formal shoes lono black "
            "bas maykoonsh ghaly awi w ykoon leather"
        ),
        language="ar",
        timeout_ms=90_000,
        assertions=(
            EvaluationAssertion("panel_count", ".suggestion-exact_match", "0"),
            EvaluationAssertion("panel_count", ".suggestion-alternative", "2"),
            EvaluationAssertion(
                "panel_contains", "#suggestions", "مناسب للمناسبات الرسمية غير موثق"
            ),
            EvaluationAssertion("panel_contains", "#suggestions", "اللون أسود غير متاح"),
        ),
    ),
    EvaluationCase(
        case_id="owner-running-workouts",
        message="عايز running shoes تنفع للـ daily workouts وتستحمل الجري في الشارع ومقاسي 43",
        language="ar",
        timeout_ms=90_000,
        assertions=(
            EvaluationAssertion("panel_count", ".suggestion-exact_match", "2"),
            EvaluationAssertion("panel_contains", '[data-product-id="shoe-02"]', "EGP"),
            EvaluationAssertion("panel_contains", '[data-product-id="shoe-04"]', "EGP"),
        ),
    ),
)

STYLING_07E_CASE = EvaluationCase(
    case_id="styling-black-trousers",
    message="عندي بنطلون اسود وعايز حاجة من فوق بس مش عارف اجيب ايه؟",
    language="ar",
    timeout_ms=90_000,
    assertions=(
        EvaluationAssertion("panel_count", ".suggestion-styling_suggestion", "3"),
        EvaluationAssertion("panel_contains", "#suggestions", "تنسيق / Styling Suggestion"),
    ),
)

TICKET_13_CASES = (
    EvaluationCase(
        case_id="ticket13-mobile-filter",
        message="عاوز كوتشي للجري بأقل من ٢٠٠٠",
        language="ar",
        viewport=(390, 844),
        assertions=FILTER_ASSERTIONS,
    ),
    EvaluationCase(
        case_id="ticket13-mobile-cart-destination",
        message="Open my cart",
        language="en",
        viewport=(390, 844),
        assertions=(
            EvaluationAssertion("url_matches", r"/cart$"),
            EvaluationAssertion("element_visible", "h1", "السلة"),
        ),
    ),
    EvaluationCase(
        case_id="ticket13-mobile-swatch-add",
        message="Add this to my cart",
        language="en",
        viewport=(390, 844),
        setup="selected_swatch",
        assertions=(
            EvaluationAssertion("element_visible", "#mini-cart-count", "1"),
            EvaluationAssertion("element_visible", "#cart-feedback", "تمت الإضافة إلى السلة"),
        ),
    ),
    EvaluationCase(
        case_id="ticket13-disabled-add-handback",
        message="Add this to my cart",
        language="en",
        viewport=(390, 844),
        setup="disabled_product",
        expected_status="question",
        assertions=(
            EvaluationAssertion(
                "panel_contains", '#pending-question [data-question-option="Stop"]', "Stop"
            ),
            EvaluationAssertion("element_visible", "#mini-cart-count", "0"),
        ),
    ),
    EvaluationCase(
        case_id="ticket13-desktop-loaded-catalogue",
        message="Where is my cart?",
        language="en",
        viewport=(1280, 800),
        setup="loaded_catalogue",
        assertions=(
            EvaluationAssertion("url_matches", r"/c/shoes$"),
            EvaluationAssertion("element_spotlighted", 'header a[href="/cart"]'),
            EvaluationAssertion("element_visible", "#results-heading", "15 منتجات"),
        ),
    ),
)
