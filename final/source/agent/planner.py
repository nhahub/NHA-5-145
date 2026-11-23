import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urljoin, urlsplit

from agent.discovery import DiscoveryConstraints, build_discovery_url
from agent.llm.intent import StructuredIntent
from agent.llm.intent_pipeline import trusted_clarification
from agent.navigation import (
    DESTINATION_TERMS,
    LOCATE_CUE,
    OPEN_CUE,
    destination_label,
    destination_mentions,
)
from agent.schemas import (
    Action,
    AskShopperAction,
    ClickAction,
    NavigateAction,
    SelectAction,
    Snapshot,
    SnapshotElement,
    SpotlightAction,
    TypeAction,
)
from agent.storefront import StorefrontDefinition, load_storefront_definition, normalize_money

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_LATIN_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_NUMBER = r"[0-9٠-٩۰-۹][0-9٠-٩۰-۹.,٬٫]*"
_SCRIPTED_PROMPT_OVERRIDE = re.compile(
    r"(?:تجاهل\s+(?:كل\s+)?(?:القواعد|التعليمات)|"
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b)",
    re.IGNORECASE,
)
_SCRIPTED_PRODUCT_REQUEST = re.compile(
    r"\b(?:find|search|look\s+for|looking\s+for|shop\s+for|recommend|suggest|buy|get|need|want)\b|"
    r"(?<!\w)(?:عايز|عاوز|عايزة|عاوزة|محتاج|محتاجة|بدور|دورلي|هات|اشتري|رشح)(?!\w)",
    re.IGNORECASE,
)
Language = Literal["ar", "en"]


def detect_language(message: str) -> Language:
    return "ar" if re.search(r"[\u0600-\u06ff]", message) else "en"


class UnsupportedShoppingTask(ValueError):
    pass


@dataclass(frozen=True)
class ActionIdentity:
    task_id: str
    action_id: str
    sequence_number: int


def _first_match(normalized: str, vocabulary: dict[str, tuple[str, ...]]) -> str | None:
    return next(
        (value for value, terms in vocabulary.items() if any(term in normalized for term in terms)),
        None,
    )


def _minimum_price_text(message: str) -> str | None:
    minimum = re.search(
        rf"(?:at\s+least|over|above|more\s+than|أكتر\s+من|اكتر\s+من|أكثر\s+من|اكثر\s+من)\s*({_NUMBER})",
        message,
        re.IGNORECASE,
    )
    return minimum.group(1) if minimum else None


def _budget_text(message: str, *, allow_currency_fallback: bool = True) -> str | None:
    budget = re.search(
        rf"(?:under|below|less\s+than|ta7t|تحت|أقل\s+من|اقل\s+من|حد\s+أقصى)\s*({_NUMBER})",
        message,
        re.IGNORECASE,
    )
    if budget:
        return budget.group(1)
    if not allow_currency_fallback:
        return None
    currency_amount = re.search(
        rf"({_NUMBER})\s*(?:egp|جنيه(?:\s+مصري)?|ج\s*\.\s*م)", message, re.IGNORECASE
    )
    return currency_amount.group(1) if currency_amount else None


def _unquoted_query(message: str, category_vocabulary: dict[str, tuple[str, ...]]) -> str | None:
    category_terms = sorted(
        (term for terms in category_vocabulary.values() for term in terms),
        key=len,
        reverse=True,
    )
    category_pattern = "|".join(re.escape(term) for term in category_terms)
    query_first = re.search(
        rf"(?:find|search(?:\s+for)?)\s+(.+?)\s+(?:in\s+)?(?:{category_pattern})(?:\s|$)",
        message,
        re.IGNORECASE,
    )
    if query_first:
        return query_first.group(1).strip()
    category_first = re.search(
        rf"(?:find|search)\s+(?:{category_pattern})\s+for\s+(.+)$",
        message,
        re.IGNORECASE,
    )
    return category_first.group(1).strip() if category_first else None


def _element_named(
    snapshot: Snapshot,
    terms: tuple[str, ...],
    *,
    roles: tuple[str, ...] | None = None,
) -> SnapshotElement | None:
    return next(
        (
            element
            for element in snapshot.elements
            if element.visible
            and (roles is None or element.role in roles)
            and any(term in element.name.lower() for term in terms)
        ),
        None,
    )


def observed_results_url(snapshot: Snapshot) -> str | None:
    """Controlled-store adapter: the visible link describes applied, not draft, filters."""
    links = [
        e
        for e in snapshot.elements
        if e.role == "link" and e.name == "النتائج الحالية" and e.visible and not e.sensitive
    ]
    if not links:
        return snapshot.url
    if len(links) != 1 or not links[0].href or links[0].disabled:
        return None
    applied = urlsplit(urljoin(snapshot.url, links[0].href))
    current = urlsplit(snapshot.url)
    if (applied.scheme, applied.netloc, applied.path) != (
        current.scheme,
        current.netloc,
        current.path,
    ):
        return None
    return applied.geturl()


def snapshot_matches_url(
    snapshot: Snapshot, expected_url: str, origin_snapshot: Snapshot | None = None
) -> bool:
    expected = urlsplit(expected_url)
    observed = observed_results_url(snapshot)
    if observed is None:
        return False
    actual = urlsplit(observed)
    return (
        (origin_snapshot is None or _same_origin(snapshot, origin_snapshot))
        and actual.path == expected.path
        and parse_qs(actual.query) == parse_qs(expected.query)
    )


def _same_origin(snapshot: Snapshot, other: Snapshot) -> bool:
    left = urlsplit(snapshot.url)
    right = urlsplit(other.url)
    return left.scheme in {"http", "https"} and (left.scheme, left.netloc) == (
        right.scheme,
        right.netloc,
    )


def is_expected_login_redirect(
    snapshot: Snapshot, origin_snapshot: Snapshot, destination: str
) -> bool:
    actual = urlsplit(snapshot.url)
    query = parse_qs(actual.query)
    return (
        _same_origin(snapshot, origin_snapshot)
        and actual.path == "/login"
        and query == {"next": [destination]}
    )


def _safe_order_link(href: str) -> bool:
    if re.fullmatch(r"#[A-Za-z0-9_-]+", href):
        return True
    parsed = urlsplit(href)
    return (
        href.startswith("/")
        and not href.startswith("//")
        and not parsed.scheme
        and not parsed.netloc
        and not parsed.fragment
    )


def _visible_link_to(snapshot: Snapshot, href: str) -> SnapshotElement | None:
    return next(
        (
            element
            for element in snapshot.elements
            if element.visible and element.role == "link" and element.href == href
        ),
        None,
    )


def _spotlight(
    element: SnapshotElement,
    *,
    identity: ActionIdentity,
    language: Language,
    narration: str | None = None,
    message: str | None = None,
) -> SpotlightAction:
    is_arabic = language == "ar"
    return SpotlightAction(
        v=1,
        type="spotlight",
        task_id=identity.task_id,
        action_id=identity.action_id,
        sequence_number=identity.sequence_number,
        narration=narration
        or ("هوريك مكان الصفحة." if is_arabic else "I'll show you where it is."),
        id=element.id,
        message=message or ("اضغط هنا" if is_arabic else "Open here"),
    )


class ScriptedPlanner:
    def __init__(self, storefront: StorefrontDefinition | None = None) -> None:
        self._storefront = storefront or load_storefront_definition()

    @property
    def storefront(self) -> StorefrontDefinition:
        return self._storefront

    def plan_intent(
        self, intent: StructuredIntent, snapshot: Snapshot, identity: ActionIdentity
    ) -> Action:
        is_arabic = intent.language == "ar"
        if intent.needs_clarification or (
            intent.intent == "find_products" and intent.constraints.category is None
        ):
            if not intent.needs_clarification:
                intent = intent.model_copy(
                    update={"missing_fields": ["category"], "needs_clarification": True}
                )
            question, options = trusted_clarification(intent, self._storefront)
            return AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=question,
                question=question,
                options=options,
            )
        if intent.intent == "find_products":
            values = intent.constraints
            constraints = DiscoveryConstraints(
                category=values.category or "",
                query=values.query,
                product_type=values.product_type,
                min_price=values.min_price.to_money() if values.min_price else None,
                max_price=values.max_price.to_money() if values.max_price else None,
                size=values.size,
                color=values.color,
                availability=(
                    None if values.availability is None else values.availability == "available"
                ),
                sort=values.sort,
            )
            url = build_discovery_url(self._storefront, constraints)
            narration = (
                "هعرض لك المنتجات المطابقة." if is_arabic else "I'll show matching products."
            )
            return NavigateAction(
                v=1,
                type="navigate",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=narration,
                url=url,
            )
        if intent.intent == "open_product":
            product_id = intent.product_id
            if product_id is None or re.fullmatch(r"[a-z0-9][a-z0-9-]*", product_id) is None:
                raise UnsupportedShoppingTask("The recommended product ID is invalid")
            return NavigateAction(
                v=1,
                type="navigate",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration="هفتح صفحة المنتج نفسه."
                if is_arabic
                else "I'll open that product's page.",
                url=self._storefront.product_route.replace("{product_id}", product_id),
            )
        if intent.intent in {"navigate", "locate"}:
            target = intent.constraints.target
            if target is None or target not in self._storefront.destination_routes:
                raise UnsupportedShoppingTask("This Storefront destination is unavailable")
            url = self._storefront.destination_routes[target]
            if intent.intent == "navigate":
                return NavigateAction(
                    v=1,
                    type="navigate",
                    task_id=identity.task_id,
                    action_id=identity.action_id,
                    sequence_number=identity.sequence_number,
                    narration="هفتح الصفحة المطلوبة." if is_arabic else "I'll open that page.",
                    url=url,
                )
            element = _visible_link_to(snapshot, url)
            narration = None
            if element is None:
                gateway = {"orders": "account", "checkout": "cart"}.get(target)
                gateway_url = self._storefront.destination_routes.get(gateway or "")
                if gateway is not None and gateway_url is not None:
                    element = _visible_link_to(snapshot, gateway_url)
                    if element is not None:
                        if target == "orders":
                            narration = (
                                "Order history is inside your account. "
                                "I'll point to the account link."
                                if not is_arabic
                                else "سجل الطلبات داخل الحساب. هوريك رابط الحساب."
                            )
                        else:
                            narration = (
                                "Checkout is reached from the cart. I'll point to the cart link."
                                if not is_arabic
                                else "الدفع يبدأ من السلة. هوريك رابط السلة."
                            )
            if element is None:
                raise UnsupportedShoppingTask("The requested destination is not visible")
            return _spotlight(
                element,
                identity=identity,
                language=intent.language,
                narration=narration,
            )
        raise UnsupportedShoppingTask("This Shopping Task needs a different request")

    def plan_orders_resume(
        self,
        snapshot: Snapshot,
        identity: ActionIdentity,
        language: Language,
        trusted_origin: Snapshot | None = None,
    ) -> Action:
        orders_route = self._storefront.destination_routes.get("orders")
        if orders_route is None:
            raise UnsupportedShoppingTask("This Storefront has no order-history destination")
        current = urlsplit(snapshot.url)
        orders = urlsplit(orders_route)
        trusted = trusted_origin is None or _same_origin(snapshot, trusted_origin)
        if not trusted:
            return AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=(
                    "الصفحة الحالية خارج المتجر الموثوق، لذلك أوقفت المتابعة."
                    if language == "ar"
                    else "This page is outside the trusted Storefront, so I stopped here."
                ),
                question=(
                    "هل تريد إيقاف المهمة؟"
                    if language == "ar"
                    else "Would you like to stop this task?"
                ),
                options=["Stop"],
            )
        if trusted and current.path == orders.path and not current.query and not current.fragment:
            newest = next(
                (
                    element
                    for element in snapshot.elements
                    if element.visible
                    and element.role == "link"
                    and element.name in {"أحدث طلب", "Newest order"}
                    and element.href is not None
                    and _safe_order_link(element.href)
                ),
                None,
            )
            if newest is None:
                return AskShopperAction(
                    v=1,
                    type="ask_shopper",
                    task_id=identity.task_id,
                    action_id=identity.action_id,
                    sequence_number=identity.sequence_number,
                    narration=(
                        "لا أقدر أتحقق من رابط أحدث طلب الظاهر، لذلك لم أحدده."
                        if language == "ar"
                        else (
                            "I can't verify a visible newest-order link, "
                            "so I won't identify an order."
                        )
                    ),
                    question=(
                        "هل تريد إيقاف المهمة؟"
                        if language == "ar"
                        else "Would you like to stop this task?"
                    ),
                    options=["Stop"],
                )
            return _spotlight(
                newest,
                identity=identity,
                language=language,
                narration=(
                    "هوريك أحدث طلب." if language == "ar" else "I'll show you the newest order."
                ),
                message=("أحدث طلب" if language == "ar" else "Newest order"),
            )
        if (
            trusted
            and trusted_origin is not None
            and is_expected_login_redirect(snapshot, trusted_origin, orders_route)
        ):
            return AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=(
                    "سجل الدخول بنفسك، ثم اختَر متابعة. لن أقرأ بيانات الدخول."
                    if language == "ar"
                    else "Sign in yourself, then choose Continue. I won't read your credentials."
                ),
                question=(
                    "بعد تسجيل الدخول، هل أتابع إلى أحدث طلب؟"
                    if language == "ar"
                    else "After signing in, should I continue to the newest order?"
                ),
                options=["Continue", "Stop"],
            )
        return NavigateAction(
            v=1,
            type="navigate",
            task_id=identity.task_id,
            action_id=identity.action_id,
            sequence_number=identity.sequence_number,
            narration=(
                "هفتح سجل الطلبات بعد تحديث حالة الصفحة."
                if language == "ar"
                else "I'll reopen order history from the current page."
            ),
            url=orders_route,
        )

    def _ask_for_category(self, *, is_arabic: bool, identity: ActionIdentity) -> AskShopperAction:
        categories = list(self._storefront.categories.values())
        return AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=identity.task_id,
            action_id=identity.action_id,
            sequence_number=identity.sequence_number,
            narration=(
                "محتاج أعرف القسم المناسب قبل ما أفلتر المنتجات."
                if is_arabic
                else "I need the product category before I can filter the catalogue."
            ),
            question="بتدور في قسم إيه؟" if is_arabic else "Which category should I search?",
            options=[category.ar if is_arabic else category.en for category in categories],
        )

    def plan(self, message: str, snapshot: Snapshot, identity: ActionIdentity) -> Action:
        return self.plan_with_intent(message, snapshot, identity)[0]

    def plan_with_intent(
        self, message: str, snapshot: Snapshot, identity: ActionIdentity
    ) -> tuple[Action, StructuredIntent | None]:
        normalized = message.translate(_ARABIC_DIGITS).lower()
        is_arabic = detect_language(message) == "ar"
        destinations = self._scripted_destinations(normalized)
        locate_cue = LOCATE_CUE.search(normalized) is not None
        open_cue = OPEN_CUE.search(normalized) is not None
        if _SCRIPTED_PROMPT_OVERRIDE.search(normalized):
            raise UnsupportedShoppingTask("Prompt override cannot authorize an Action")
        vocabularies = (self._storefront.vocabulary.categories, self._storefront.vocabulary.types)
        product_terms = any(
            term in normalized
            for vocabulary in vocabularies
            for terms in vocabulary.values()
            for term in terms
        )
        if (
            destinations
            and (locate_cue or open_cue)
            and _SCRIPTED_PRODUCT_REQUEST.search(normalized)
            and product_terms
        ):
            scripted_intent = StructuredIntent.model_validate(
                {
                    "v": 1,
                    "language": "ar" if is_arabic else "en",
                    "dialect": self._scripted_dialect(message),
                    "intent": "find_products",
                    "constraints": {},
                    "missing_fields": ["target"],
                    "conflicting_fields": ["category", "target"],
                    "needs_clarification": True,
                }
            )
            return self.plan_intent(scripted_intent, snapshot, identity), scripted_intent
        if destinations and (locate_cue or open_cue):
            destination = destinations[0] if len(destinations) == 1 else None
            clarification = len(destinations) != 1 or locate_cue and open_cue
            scripted_intent = StructuredIntent.model_validate(
                {
                    "v": 1,
                    "language": "ar" if is_arabic else "en",
                    "dialect": self._scripted_dialect(message),
                    "intent": "locate" if locate_cue else "navigate",
                    "constraints": {"target": destination},
                    "missing_fields": ["target"] if clarification else [],
                    "conflicting_fields": ["target"]
                    if destination is not None and locate_cue and open_cue
                    else [],
                    "needs_clarification": clarification,
                }
            )
            return self.plan_intent(scripted_intent, snapshot, identity), scripted_intent
        if re.search(r"\b(?:usd|eur|gbp|sar|aed)\b|[$€£]", normalized):
            question = (
                "ميزانيتك كام بالجنيه المصري؟" if is_arabic else "What is your budget in EGP?"
            )
            narration = (
                "محتاج الميزانية بالجنيه المصري من غير تحويل عملة."
                if is_arabic
                else "I need an EGP budget and won't convert currencies."
            )
            return AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=identity.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=narration,
                question=question,
                options=[],
            ), None

        vocabulary = self._storefront.vocabulary
        category = _first_match(normalized, vocabulary.categories)
        if category is None:
            return self._ask_for_category(is_arabic=is_arabic, identity=identity), None

        product_type = _first_match(normalized, vocabulary.types)
        color = _first_match(normalized, vocabulary.colors)
        query_match = re.search(r'["“]([^"”]+)["”]', message)
        size_match = re.search(r"(?:size|مقاس)\s*([0-9a-z]+)", normalized, re.IGNORECASE)
        minimum_text = _minimum_price_text(normalized)
        budget_text = _budget_text(normalized, allow_currency_fallback=minimum_text is None)
        minimum = (
            normalize_money(minimum_text, currency=self._storefront.currency)
            if minimum_text is not None
            else None
        )
        maximum = (
            normalize_money(budget_text, currency=self._storefront.currency)
            if budget_text is not None
            else None
        )
        if any(term in normalized for term in vocabulary.availability["unavailable"]):
            availability = False
        elif any(term in normalized for term in vocabulary.availability["available"]):
            availability = True
        else:
            availability = None
        sort = None
        if any(term in normalized for term in vocabulary.sort["cheapest"]):
            sort = "cheapest"
        elif any(term in normalized for term in vocabulary.sort["newest"]):
            sort = "newest"

        constraints = DiscoveryConstraints(
            category=category,
            query=(
                query_match.group(1)
                if query_match
                else _unquoted_query(message, vocabulary.categories)
            ),
            product_type=product_type,
            min_price=minimum,
            max_price=maximum,
            size=size_match.group(1) if size_match else None,
            color=color,
            availability=availability,
            sort=sort,
        )
        url = build_discovery_url(self._storefront, constraints)

        if category == "shoes" and product_type == "running" and maximum is not None:
            maximum_text = format(maximum.amount, "f")
            narration = (
                f"هفلتر لك أحذية الجري بحد أقصى {maximum_text.translate(_LATIN_DIGITS)} جنيه."
                if is_arabic
                else f"I'll filter running shoes to a maximum of EGP {maximum_text}."
            )
        else:
            category_name = self._storefront.categories[category]
            narration = (
                f"هعرض لك نتائج {category_name.ar} المطابقة."
                if is_arabic
                else f"I'll show matching {category_name.en.lower()}."
            )
        return NavigateAction(
            v=1,
            type="navigate",
            task_id=identity.task_id,
            action_id=identity.action_id,
            sequence_number=identity.sequence_number,
            narration=narration,
            url=url,
        ), None

    def _scripted_destinations(self, normalized_message: str) -> tuple[str, ...]:
        return destination_mentions(normalized_message, set(self._storefront.destination_routes))

    @staticmethod
    def _scripted_dialect(message: str) -> str:
        if re.search(r"[\u0600-\u06ff]", message):
            return "egyptian_arabic"
        if re.search(r"\b(?:feen|fin|efta7|ed5ol|ro7)\b", message, re.IGNORECASE):
            return "franco_arabic"
        return "english"

    def plan_answer(
        self,
        original_message: str,
        answer: str,
        snapshot: Snapshot,
        identity: ActionIdentity,
    ) -> Action:
        if _SCRIPTED_PROMPT_OVERRIDE.search(original_message) or _SCRIPTED_PROMPT_OVERRIDE.search(
            answer
        ):
            raise UnsupportedShoppingTask("Prompt override cannot authorize an Action")
        available_routes = set(self._storefront.destination_routes)
        answer_targets = destination_mentions(answer, available_routes)
        original_targets = destination_mentions(original_message, available_routes)
        targets = answer_targets or original_targets
        navigation_context = bool(
            original_targets
            or answer_targets
            or LOCATE_CUE.search(original_message)
            or OPEN_CUE.search(original_message)
        )
        if navigation_context and answer.strip().casefold() in {
            "search products",
            "find products",
            "أبحث عن منتجات",
            "ابحث عن منتجات",
        }:
            return self._ask_for_category(
                is_arabic=detect_language(original_message) == "ar",
                identity=identity,
            )
        if navigation_context:
            target = targets[0] if len(targets) == 1 else None
            answer_locate = LOCATE_CUE.search(answer) is not None or answer.strip().casefold() in {
                "show me where it is",
                "وريني مكانها",
            }
            answer_open = OPEN_CUE.search(answer) is not None or answer.strip().casefold() in {
                "open it",
                "افتحها",
            }
            original_locate = LOCATE_CUE.search(original_message) is not None
            original_open = OPEN_CUE.search(original_message) is not None
            wants_locate = answer_locate or (original_locate and not original_open)
            wants_open = answer_open or (original_open and not original_locate)
            if target is None or (wants_locate == wants_open):
                is_arabic = detect_language(original_message) == "ar"
                if target is None:
                    options = [
                        destination_label(name, "ar" if is_arabic else "en")
                        for name in DESTINATION_TERMS
                        if name in available_routes
                    ]
                    question = "تقصد أنهي صفحة؟" if is_arabic else "Which page do you mean?"
                else:
                    options = (
                        ["وريني مكانها", "افتحها"]
                        if is_arabic
                        else [
                            "Show me where it is",
                            "Open it",
                        ]
                    )
                    question = (
                        "تحب أوريك مكان الصفحة ولا أفتحها؟"
                        if is_arabic
                        else "Would you like me to show where the page is or open it?"
                    )
                return AskShopperAction(
                    v=1,
                    type="ask_shopper",
                    task_id=identity.task_id,
                    action_id=identity.action_id,
                    sequence_number=identity.sequence_number,
                    narration=question,
                    question=question,
                    options=options,
                )
            intent = StructuredIntent.model_validate(
                {
                    "v": 1,
                    "language": "ar" if detect_language(original_message) == "ar" else "en",
                    "dialect": self._scripted_dialect(original_message),
                    "intent": "locate" if wants_locate else "navigate",
                    "constraints": {"target": target},
                    "missing_fields": [],
                    "conflicting_fields": [],
                    "needs_clarification": False,
                }
            )
            return self.plan_intent(intent, snapshot, identity)

        category_by_answer = {
            category.en.lower(): slug for slug, category in self._storefront.categories.items()
        } | {category.ar: slug for slug, category in self._storefront.categories.items()}
        selected_category = category_by_answer.get(answer.strip().lower())
        if selected_category is not None:
            category_name = self._storefront.categories[selected_category]
            selected_name = (
                category_name.ar if detect_language(original_message) == "ar" else category_name.en
            )
            return self.plan(
                f"{original_message} {selected_name}",
                snapshot,
                identity,
            )

        amount_match = re.search(_NUMBER, answer)
        if amount_match is None or not re.search(r"\begp\b|جنيه|ج\s*\.\s*م", answer, re.IGNORECASE):
            raise UnsupportedShoppingTask("A budget answer must contain an EGP amount")
        amount = amount_match.group()
        original_normalized = original_message.lower()
        category = (
            _first_match(original_normalized, self._storefront.vocabulary.categories) or "shoes"
        )
        category_name = self._storefront.categories[category]
        product_type = _first_match(original_normalized, self._storefront.vocabulary.types)
        task = f"{category_name.en} under {amount} EGP"
        if product_type:
            task = f"{product_type} {task}"
        return self.plan(task, snapshot, identity)

    def plan_visible_control_fallback(
        self,
        expected_url: str,
        snapshot: Snapshot,
        identity: ActionIdentity,
        language: Language,
    ) -> Action:
        expected = urlsplit(expected_url)
        actual = urlsplit(observed_results_url(snapshot) or snapshot.url)
        target = parse_qs(expected.query)
        current = parse_qs(actual.query)
        narration = (
            "هستخدم الفلاتر الظاهرة عشان أكمل الطلب."
            if language == "ar"
            else "I'll use the visible filters to finish the request."
        )
        staged_control = False
        for name, values in target.items():
            if current.get(name) == values:
                continue
            value = values[0]
            if name == "type":
                type_terms = self._storefront.vocabulary.types.get(value, (value,))
                element = _element_named(snapshot, type_terms, roles=("radio",))
                if element is not None and element.checked:
                    staged_control = True
                    continue
                if element is not None:
                    return ClickAction(
                        v=1,
                        type="click",
                        task_id=identity.task_id,
                        action_id=identity.action_id,
                        sequence_number=identity.sequence_number,
                        narration=narration,
                        id=element.id,
                    )
            elif name in ("availability", "sort"):
                element = _element_named(
                    snapshot,
                    self._storefront.vocabulary.controls[name],
                    roles=("combobox",),
                )
                if element is not None and element.value == value:
                    staged_control = True
                    continue
                if element is not None:
                    return SelectAction(
                        v=1,
                        type="select",
                        task_id=identity.task_id,
                        action_id=identity.action_id,
                        sequence_number=identity.sequence_number,
                        narration=narration,
                        id=element.id,
                        option=value,
                    )
            else:
                terms = self._storefront.vocabulary.controls.get(name)
                element = (
                    _element_named(snapshot, terms, roles=("textbox", "searchbox"))
                    if terms is not None
                    else None
                )
                if element is not None and element.value == value:
                    staged_control = True
                    continue
                if element is not None:
                    return TypeAction(
                        v=1,
                        type="type",
                        task_id=identity.task_id,
                        action_id=identity.action_id,
                        sequence_number=identity.sequence_number,
                        narration=narration,
                        id=element.id,
                        text=value,
                        submit=True,
                    )

        if staged_control:
            submit = _element_named(
                snapshot,
                self._storefront.vocabulary.controls["submit"],
                roles=("button",),
            )
            if submit is not None:
                return ClickAction(
                    v=1,
                    type="click",
                    task_id=identity.task_id,
                    action_id=identity.action_id,
                    sequence_number=identity.sequence_number,
                    narration=narration,
                    id=submit.id,
                )

        return AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=identity.task_id,
            action_id=identity.action_id,
            sequence_number=identity.sequence_number,
            narration=narration,
            question=(
                "الفلاتر المتوقعة مش ظاهرة. تحب نوقف ولا تحاول بنفسك؟"
                if language == "ar"
                else (
                    "The expected filters are not visible. "
                    "Would you like to stop or continue manually?"
                )
            ),
            options=["إيقاف", "هكمل بنفسي"] if language == "ar" else ["Stop", "Continue manually"],
        )
