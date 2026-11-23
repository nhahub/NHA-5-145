import re
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from agent.llm.contract import LLMClient, LLMInvalidResponseError, LLMRequest
from agent.storefront import Money

Language = Literal["ar", "en"]
Dialect = Literal["egyptian_arabic", "franco_arabic", "mixed", "english", "unknown"]
IntentName = Literal[
    "advice",
    "find_products",
    "locate",
    "navigate",
    "open_product",
    "mutate",
    "cart_edit",
    "help",
    "off_topic",
    "unsupported",
]
ConstraintField = Literal[
    "category",
    "query",
    "product_type",
    "min_price",
    "max_price",
    "size",
    "color",
    "availability",
    "sort",
    "target",
    "catalogue",
    "price_preference",
    "product_id",
    "cart_quantity",
    "condition",
]
RevisionField = Literal[
    "category",
    "query",
    "product_type",
    "min_price",
    "max_price",
    "size",
    "color",
    "availability",
    "sort",
    "target",
    "catalogue",
    "price_preference",
    "request_mode",
    "owned_items",
    "owned_item",
    "preferred_colors",
    "desired_wear_position",
]


ConditionFact = Literal["price", "in_stock", "size_exists", "colour_exists"]
ConditionComparator = Literal["lt", "lte", "gt", "gte", "eq", "is", "is_not"]
Beneficiary = Literal[
    "me",
    "brother",
    "sister",
    "mother",
    "father",
    "son",
    "daughter",
    "husband",
    "wife",
    "friend",
    "named_person",
]
# The comparators each page-checkable fact allows; anything else is not a condition.
CONDITION_COMPARATORS: dict[str, frozenset[str]] = {
    "price": frozenset({"lt", "lte", "gt", "gte", "eq"}),
    "in_stock": frozenset({"is"}),
    "size_exists": frozenset({"is", "is_not"}),
    "colour_exists": frozenset({"is", "is_not"}),
}
MAX_REMAINING_STEPS = 2
MAX_SKIPPED_STEPS = 6
StepWords = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


def normalise_steps(data: dict) -> dict:
    """Steps beyond the two that can run become skipped words, in spoken order.

    Overflow is words for the report, never work. A null `skipped_steps` is tolerated.
    Anything that is not a list of strings is left for the model validation to reject.
    """
    steps, skipped = data.get("remaining_steps"), data.get("skipped_steps") or []
    if (
        isinstance(steps, list)
        and isinstance(skipped, list)
        and all(isinstance(item, str) for item in (*steps, *skipped))
    ):
        data["remaining_steps"] = steps[:MAX_REMAINING_STEPS]
        data["skipped_steps"] = [*steps[MAX_REMAINING_STEPS:], *skipped][:MAX_SKIPPED_STEPS]
    return data


class IntentModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class IntentMoney(IntentModel):
    amount: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator("amount")
    @classmethod
    def validate_decimal_text(cls, value: str) -> str:
        if re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d{1,2})?", value) is None:
            raise ValueError(
                "Money amount must be a non-negative decimal string with at most two places"
            )
        return value

    def to_money(self) -> Money:
        """Convert validated model text into the Agent's exact Money value."""
        return Money(amount=Decimal(self.amount), currency=self.currency)


class IntentConstraints(IntentModel):
    category: str | None = Field(
        default=None,
        description=(
            "Catalogue category key. Required for a completed find_products decision, "
            "including browsing a section or filtering by product_type. Also supply it "
            "for advice seeking a known product type: it selects the catalogue evidence "
            "the advisor receives. Null is for conversation without a desired category. "
            "Resolve from the request and catalogue categories; if genuinely ambiguous, "
            "set needs_clarification=true and missing_fields=['category']."
        ),
    )
    query: str | None = Field(
        default=None,
        description=(
            "Literal product-name search or residual search terms not represented by "
            "other constraints. Null for a category/type-only request. Do not duplicate "
            "a product_type or translate its label into a product-name query."
        ),
    )
    product_type: str | None = Field(
        default=None,
        description=(
            "Canonical catalogue type for the desired product. A type alone does not "
            "imply any additional feature or suitability requirement."
        ),
    )
    min_price: IntentMoney | None = None
    max_price: IntentMoney | None = None
    size: str | None = None
    color: str | None = None
    availability: Literal["available", "unavailable"] | None = None
    sort: Literal["cheapest", "newest"] | None = None
    target: Literal["cart", "orders", "checkout", "account"] | None = None


class CatalogueRequirement(IntentModel):
    excluded: bool = False
    kind: Literal["feature", "suitable_for"]
    value: str
    source: str


class PricePreference(IntentModel):
    value: Literal["lower_price"]
    source: str


class OwnedItem(IntentModel):
    category: str
    product_type: str | None = None
    color: str | None = None
    source: str


class IntentCondition(IntentModel):
    # A page-checkable condition: price, stock, size or colour. Never prose.
    # (No docstring: it would be copied into the provider schema as a description.)

    fact: ConditionFact
    comparator: ConditionComparator
    value: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def comparator_and_value_fit_the_fact(self) -> Self:
        if self.comparator not in CONDITION_COMPARATORS[self.fact]:
            raise ValueError("Comparator does not fit this condition fact")
        if self.fact == "price" and (
            re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d{1,2})?", self.value) is None
        ):
            raise ValueError("Price condition needs a non-negative decimal amount")
        if self.fact == "in_stock" and self.value not in {"true", "false"}:
            raise ValueError("Stock condition needs true or false")
        return self


class StructuredIntent(IntentModel):
    v: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    language: Language
    dialect: Dialect
    intent: IntentName
    constraints: IntentConstraints
    missing_fields: list[ConstraintField]
    conflicting_fields: list[ConstraintField] = Field(default_factory=list)
    needs_clarification: bool
    catalogue_requirements: list[CatalogueRequirement] = Field(default_factory=list)
    price_preference: PricePreference | None = None
    owned_item: OwnedItem | None = None
    desired_wear_position: Literal["upper", "lower", "footwear"] | None = None
    # "open": the Shopper named a product to open or add that is not in known products; the name
    # is copied into constraints.query and code resolves the product from the catalogue (v10).
    request_mode: Literal["browse", "recommend", "style", "open"] = "browse"
    owned_items: list[OwnedItem] = Field(default_factory=list, max_length=6)
    preferred_colors: list[str] = Field(default_factory=list, max_length=6)
    subjective_preferences: list[str] = Field(default_factory=list, max_length=6)
    advice_product_ids: list[str] = Field(default_factory=list, max_length=6)
    navigation_source: str | None = None
    product_id: str | None = Field(
        default=None,
        description=(
            "Verified catalogue identity for open_product or cart_edit/add. For add, "
            "supply the chosen known product ID even when its page is not open yet; "
            "runtime navigates there before binding a fresh add button. Never use this "
            "to select an existing cart line for quantity/remove/undo."
        ),
    )
    revised_fields: list[RevisionField] = Field(default_factory=list)
    revision_source: str | None = None
    mutation_kind: Literal["clear_cart", "submit_checkout"] | None = None
    mutation_source: str | None = None
    cart_operation: Literal["add", "quantity", "remove", "undo", "replace"] | None = Field(
        default=None,
        description=(
            "Cart capability: add a product, change quantity of an existing line, remove a "
            "line, undo, or replace (v10 only). "
            "Every increase, decrease, or final quantity change uses operation "
            "quantity; its direction belongs in cart_quantity_mode, not this field."
        ),
    )
    cart_source: str | None = None
    cart_target: str | None = None
    cart_target_id: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Numeric ID of the observed enabled BUTTON for the selected cart operation. "
            "Never a product ID, link ID, or quantity textbox ID."
        ),
    )
    cart_quantity: int | float | None = Field(
        default=None,
        allow_inf_nan=False,
        description=(
            "For increase/decrease: the number of units requested to add/remove, not the "
            "resulting total. Runtime computes current quantity plus/minus this amount. "
            "For set: the requested final quantity. For add: units to put in the product form."
            " Preserve an out-of-range or fractional request rather than changing its value; "
            "runtime will ask for a whole quantity within 1..99."
        ),
    )

    cart_quantity_mode: Literal["set", "increase", "decrease"] | None = Field(
        default=None,
        description=(
            "Use increase/decrease for a requested change relative to the current cart "
            "quantity. Use set only for an explicitly requested final quantity (or add-form "
            "quantity). Interpret intent in the Shopper's language; do not compute a "
            "different amount to compensate for a wrong mode."
        ),
    )

    # No field descriptions: the provider schema is copied into every branch, and the
    # prompt explains these fields. Later steps are the Shopper's words, never intents.
    first_step: StepWords | None = None
    remaining_steps: list[StepWords] = Field(default_factory=list, max_length=MAX_REMAINING_STEPS)
    skipped_steps: list[StepWords] = Field(default_factory=list, max_length=MAX_SKIPPED_STEPS)
    condition: IntentCondition | None = None
    beneficiary: Beneficiary | None = None
    refers_to_this: bool = False

    @model_validator(mode="before")
    @classmethod
    def open_marker_is_normalised(cls, data: object) -> object:
        """`request_mode: "open"` (open/add a product the Shopper named) is a hint code can
        always settle, so a stray combination is repaired here, never refused: it applies only
        to find_products or a cart add with a name in constraints.query. Elsewhere, or with no
        name, it falls back to browse (the name field goes with it unless find_products keeps
        it as a search); with a name the model's own product_id is dropped, because the
        Shopper's words decide the product."""
        if not isinstance(data, dict) or data.get("request_mode") != "open":
            return data
        constraints = data.get("constraints")
        constraints = constraints if isinstance(constraints, dict) else {}
        query = constraints.get("query")
        named = isinstance(query, str) and bool(query.strip())
        applies = data.get("v") == 10 and (
            data.get("intent") == "find_products"
            or (data.get("intent") == "cart_edit" and data.get("cart_operation") == "add")
        )
        if applies and named:
            return {**data, "product_id": None}
        data = {**data, "request_mode": "browse"}
        if data.get("intent") != "find_products" and "query" in constraints:
            data["constraints"] = {k: v for k, v in constraints.items() if k != "query"}
        return data

    @model_validator(mode="before")
    @classmethod
    def replace_carries_no_quantity(cls, data: object) -> object:
        """A colour change names no quantity: stray model values are cleared, not refused."""
        if isinstance(data, dict) and data.get("cart_operation") == "replace":
            data = {**data, "cart_quantity": None, "cart_quantity_mode": None}
        return data

    @model_validator(mode="before")
    @classmethod
    def unsupported_conditions_need_clarification(cls, data: object) -> object:
        """A condition outside the four page-checkable kinds is a question, not a guess."""
        if not isinstance(data, dict) or data.get("v") != 10:
            return data
        unsupported = False

        def checked(raw: object) -> object:
            nonlocal unsupported
            if raw is None:
                return None
            try:
                IntentCondition.model_validate(raw)
            except ValidationError:
                unsupported = True
                return None
            return raw

        data = normalise_steps(dict(data))
        if "condition" in data:
            data["condition"] = checked(data["condition"])
        if unsupported:
            missing = data.get("missing_fields")
            missing = list(missing) if isinstance(missing, list) else []
            data["needs_clarification"] = True
            data["missing_fields"] = (
                [*missing, "condition"] if "condition" not in missing else missing
            )
        return data

    @field_validator("subjective_preferences", mode="before")
    @classmethod
    def optional_preferences_do_not_invalidate_the_request(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return list(
            dict.fromkeys(
                item.strip()
                for item in value
                if isinstance(item, str) and 0 < len(item.strip()) <= 120
            )
        )[:6]

    @property
    def context_items(self) -> list[OwnedItem]:
        items = list(self.owned_items)
        if self.owned_item is not None and self.owned_item not in items:
            items.append(self.owned_item)
        return items

    @property
    def catalogue_discovery(self) -> bool:
        return (
            self.intent == "find_products"
            and not self.needs_clarification
            and bool(
                self.catalogue_requirements
                or self.price_preference is not None
                or self.desired_wear_position is not None
                or self.request_mode in {"recommend", "style"}
                or self.context_items
            )
        )

    @model_validator(mode="after")
    def clarification_state_is_consistent(self) -> Self:
        if self.v < 10 and (
            self.first_step is not None
            or self.remaining_steps
            or self.skipped_steps
            or self.condition is not None
            or self.beneficiary is not None
            or self.refers_to_this
            or self.cart_operation == "replace"
        ):
            raise ValueError("Multi-step fields and replace require schema 10")
        if (self.intent == "advice" or self.advice_product_ids) and (
            self.v < 9 or self.intent != "advice" or self.constraints.target is not None
        ):
            raise ValueError("Advice requires schema 9 and cannot carry action authority")
        if self.intent == "cart_edit":
            if self.v not in {5, 6, 7, 8, 9, 10} or not self.cart_operation:
                raise ValueError("Cart edit needs a supported operation")
            if (
                self.v >= 6
                and self.cart_operation == "quantity"
                and self.cart_quantity_mode is None
                and not self.needs_clarification
            ):
                raise ValueError("Quantity edits require an explicit mode")
            if self.cart_quantity_mode is not None and (
                self.v < 6
                or self.cart_quantity is None
                or not (
                    self.cart_operation == "quantity"
                    or (
                        self.v >= 8
                        and self.cart_operation == "add"
                        and self.cart_quantity_mode == "set"
                    )
                )
            ):
                raise ValueError("Quantity mode must match an explicit quantity operation")
            allowed = {"size", "color", *({"query"} if self.request_mode == "open" else ())}
            if any(
                value is not None
                for key, value in self.constraints.model_dump().items()
                if key not in allowed
            ):
                raise PydanticCustomError(
                    "cart_authority_isolation", "Cart edits cannot carry discovery constraints"
                )
            if (
                (self.product_id and self.cart_operation != "add")
                or self.catalogue_requirements
                or self.context_items
            ):
                raise PydanticCustomError("cart_authority_isolation", "Cart edits must be isolated")
        elif any(
            value is not None
            for value in (
                self.cart_operation,
                self.cart_source,
                self.cart_target,
                self.cart_target_id,
                self.cart_quantity,
                self.cart_quantity_mode,
            )
        ):
            raise ValueError("Only cart edits carry cart parameters")
        if self.intent == "mutate":
            if (
                self.mutation_kind is None
                or self.constraints != IntentConstraints()
                or self.catalogue_requirements
                or self.product_id is not None
            ):
                raise ValueError("Mutation intent must be explicit and isolated")
        elif self.mutation_kind is not None or self.mutation_source is not None:
            raise ValueError("Only a mutation intent may carry mutation authority")
        if self.intent not in {"find_products", "advice"}:
            self.subjective_preferences = []
        discovery_fields = (
            "category",
            "query",
            "product_type",
            "min_price",
            "max_price",
            "size",
            "color",
            "availability",
            "sort",
        )
        has_discovery_constraints = any(
            getattr(self.constraints, field) is not None for field in discovery_fields
        ) or bool(
            self.catalogue_requirements
            or self.price_preference
            or self.context_items
            or self.desired_wear_position
            or self.request_mode != "browse"
            or self.preferred_colors
        )
        if self.intent in {"navigate", "locate", "open_product"} and has_discovery_constraints:
            raise PydanticCustomError(
                "navigation_discovery_isolation",
                "Structured Intent cannot mix navigation and discovery authority",
            )
        if self.intent == "find_products" and self.constraints.target is not None:
            raise PydanticCustomError(
                "discovery_navigation_isolation",
                "Product discovery cannot contain a navigation target",
            )
        if self.intent == "open_product" and self.constraints.target is not None:
            raise ValueError("A product target cannot be a Storefront destination")
        if (
            self.intent != "open_product"
            and not (self.intent == "cart_edit" and self.cart_operation == "add")
            and self.product_id is not None
        ):
            raise ValueError("Product ID is only valid for opening a recommended product")
        minimum = self.constraints.min_price
        maximum = self.constraints.max_price
        prices_conflict = (
            minimum is not None
            and maximum is not None
            and minimum.to_money().amount > maximum.to_money().amount
        )
        if prices_conflict:
            required_fields = {"min_price", "max_price"}
            if not required_fields.issubset(self.conflicting_fields):
                raise ValueError("Conflicting prices must be reported as conflicting fields")
        return self


class StructuredIntentDraftError(ValueError):
    """The provider replied, but its draft cannot enter the trusted intent boundary."""


async def collect_structured_intent(client: LLMClient, request: LLMRequest) -> StructuredIntent:
    text_parts: list[str] = []
    try:
        async for chunk in client.complete(request):
            if chunk.tool_call is not None:
                raise StructuredIntentDraftError("Structured intent cannot contain a tool call")
            if chunk.text is not None:
                text_parts.append(chunk.text)
    except ValidationError as error:
        raise StructuredIntentDraftError(str(error)) from error
    except LLMInvalidResponseError as error:
        raise StructuredIntentDraftError(str(error)) from error
    if not text_parts:
        raise StructuredIntentDraftError("Structured intent response was empty")
    try:
        return StructuredIntent.model_validate_json("".join(text_parts))
    except ValidationError as error:
        raise StructuredIntentDraftError(str(error)) from error
