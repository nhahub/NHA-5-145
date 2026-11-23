import re

DESTINATION_TERMS: dict[str, tuple[str, ...]] = {
    "cart": ("shopping cart", "cart", "basket", "السلة", "سلة", "عربة التسوق"),
    "checkout": ("checkout", "check out", "payment", "الدفع"),
    "account": ("account", "حسابي", "الحساب", "حساب", "hesab", "7esab"),
    "orders": (
        "order history",
        "orders",
        "my order",
        "سجل الطلبات",
        "الطلبات",
        "طلباتي",
    ),
}

LOCATE_CUE = re.compile(
    r"\bwhere\b|"
    r"(?<!\w)(?:فين|وين|أين|(?:ال)?مكان)(?!\w)|\b(?:feen|fin)\b",
    re.IGNORECASE,
)
OPEN_CUE = re.compile(
    r"\b(?:open|go\s+to|navigate\s+to|take\s+me\s+to)\b|"
    r"(?<!\w)(?:افتح(?:ي|لي)?|افتح(?:ه|ها)(?:لي|لى)|"
    r"تفتح(?:ه|ها)?(?:لي|لى)|ادخل(?:ي)?|روح(?:ي)?|وديني|خدني)(?!\w)|"
    r"\b(?:efta7(?:ly|li)?|ed5ol|ro7)\b",
    re.IGNORECASE,
)
DEICTIC_CART_OPEN = re.compile(r"^\s*افتح(?:ه|ها)(?:لي|لى)\s*[؟?!.،,]*\s*$")


def is_deictic_cart_open(message: str) -> bool:
    return DEICTIC_CART_OPEN.fullmatch(message) is not None


def destination_mentions(message: str, available_routes: set[str]) -> tuple[str, ...]:
    normalized = message.casefold()
    return tuple(
        target
        for target, terms in DESTINATION_TERMS.items()
        if target in available_routes and any(_contains_term(normalized, term) for term in terms)
    )


def _contains_term(message: str, term: str) -> bool:
    prefix = r"(?:و)?(?:ال)?" if re.search(r"[\u0600-\u06ff]", term) else ""
    return bool(re.search(rf"(?<!\w){prefix}{re.escape(term)}(?!\w)", message))


def destination_label(target: str, language: str) -> str:
    if language == "ar":
        return {
            "cart": "السلة",
            "checkout": "الدفع",
            "account": "الحساب",
            "orders": "سجل الطلبات",
        }[target]
    return {
        "cart": "Cart",
        "checkout": "Checkout",
        "account": "Account",
        "orders": "Order history",
    }[target]
