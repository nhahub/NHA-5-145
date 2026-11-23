"""Bounded read-only catalogue wire contract; no language interpretation."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
ProductId = Annotated[str, Field(min_length=1, max_length=100)]
Revision = Annotated[int, Field(ge=1)]


class WireModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def version_is_integer(cls, data):
        if isinstance(data, dict) and "v" in data and type(data["v"]) is not int:
            raise ValueError("Version must be an integer")
        return data


def _storage_amount(value: str) -> str:
    if Decimal(value) * 100 > 9223372036854775807:
        raise ValueError("Money exceeds catalogue storage bound")
    return value


MoneyAmount = Annotated[
    str,
    Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d{1,2})?$", max_length=24),
    AfterValidator(_storage_amount),
]


class MoneyPredicate(WireModel):
    field: Literal["price"]
    op: Literal["gte", "lte"]
    amount: MoneyAmount
    currency: Literal["EGP"]


class AttributePredicate(WireModel):
    field: Literal["category", "product_type", "color", "size", "feature", "use"]
    op: Literal["eq", "exclude"]
    value: Text


class AvailabilityPredicate(WireModel):
    field: Literal["available"]
    op: Literal["eq"]
    value: bool


Predicate = Annotated[
    MoneyPredicate | AttributePredicate | AvailabilityPredicate,
    Field(discriminator="field"),
]
Predicates = Annotated[list[Predicate], Field(max_length=20)]
Unknowns = Annotated[list[Text], Field(max_length=20)]


class SearchQuery(WireModel):
    v: Literal[1] = 1
    query: str = Field(max_length=1024)
    predicates: Predicates = Field(default_factory=list)
    requirements: Predicates = Field(default_factory=list)
    unverified_requirements: Unknowns = Field(
        default_factory=list,
        description=(
            "Explicit factual must-haves that the typed predicates cannot represent. "
            "Subjective taste/style wishes belong in the decision's "
            "subjective_preferences, not here."
        ),
    )
    sort: Literal["relevance", "cheapest", "newest"] = "relevance"
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="after")
    def predicate_budget(self):
        if len({p.model_dump_json() for p in [*self.predicates, *self.requirements]}) > 20:
            raise ValueError("Too many distinct predicates")
        return self


class DetailsQuery(WireModel):
    v: Literal[1] = 1
    ids: list[ProductId] = Field(
        min_length=1,
        max_length=9,
        description="At least one product ID; never an empty list.",
    )
    requirements: Predicates = Field(default_factory=list)
    unverified_requirements: Unknowns = Field(
        default_factory=list,
        description=(
            "Explicit factual must-haves that the typed predicates cannot represent. "
            "Subjective taste/style wishes belong in the decision's "
            "subjective_preferences, not here."
        ),
    )

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("Duplicate product IDs")
        return self


class ProductMoney(WireModel):
    amount: MoneyAmount
    currency: Literal["EGP"]


class ProductEvidence(WireModel):
    id: ProductId
    category: Text
    nameAr: Text
    nameEn: Text
    type: Text
    price: ProductMoney
    sizes: list[Text] = Field(max_length=100)
    colors: list[Text] = Field(max_length=100)
    available: bool
    addedAt: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    features: list[Text] = Field(max_length=100)
    suitableFor: list[Text] = Field(max_length=100)
    wearPosition: Literal["upper", "lower"] | None
    absent_features: list[Text] = Field(max_length=100)
    absent_uses: list[Text] = Field(max_length=100)


class RequirementResult(WireModel):
    index: int = Field(ge=0, le=19)
    status: Literal["satisfied", "violated", "unknown"]


class Candidate(WireModel):
    product: ProductEvidence
    product_revision: Revision
    requirements: list[RequirementResult] = Field(max_length=20)


class SearchResult(WireModel):
    v: Literal[1]
    catalogue_revision: Revision
    candidates: list[Candidate] = Field(max_length=10)
    ranking: Literal["lexical", "hybrid"]
    exact_count: int | None = Field(ge=0)
    next_cursor: str | None = Field(min_length=1, max_length=2048)
    truncated: bool
    unverified_requirements: Unknowns


class DetailsResult(WireModel):
    v: Literal[1]
    catalogue_revision: Revision
    products: list[Candidate] = Field(max_length=9)
    missing_ids: list[ProductId] = Field(max_length=9)
    unverified_requirements: Unknowns


class CatalogueProtocol(WireModel):
    """Schema export container, not a request sent over the network."""

    search: SearchQuery
    details: DetailsQuery
    search_result: SearchResult
    details_result: DetailsResult
