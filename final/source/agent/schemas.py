from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, model_validator

MAX_SAFE_INTEGER = 2**53 - 1


def normalize_json_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("JSON integers must not be booleans")
    if isinstance(value, int) and abs(value) <= MAX_SAFE_INTEGER:
        return value
    if isinstance(value, float) and value.is_integer() and abs(value) <= MAX_SAFE_INTEGER:
        return int(value)
    raise ValueError("Value must be a safe integral JSON number")


JsonInteger = Annotated[int, BeforeValidator(normalize_json_integer)]


class WireModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, payload: Any) -> Any:
        if isinstance(payload, dict) and any(value is None for value in payload.values()):
            raise ValueError("Wire fields must be omitted instead of set to null")
        return payload


class Viewport(WireModel):
    w: JsonInteger
    h: JsonInteger
    scroll_y: JsonInteger = Field(alias="scrollY")


class SnapshotElement(WireModel):
    id: JsonInteger
    role: str
    name: str
    visible: bool
    href: str | None = None
    form_action: str | None = None
    mutation_state: str | None = None
    value: str | None = None
    options: list[str] | None = None
    checked: bool | None = None
    group: str | None = None
    region: str | None = None
    disabled: bool | None = None
    level: JsonInteger | None = None
    sensitive: Literal[True] | None = None

    @model_validator(mode="after")
    def exclude_sensitive_value(self) -> Self:
        sensitive_state = (
            self.href,
            self.form_action,
            self.mutation_state,
            self.value,
            self.options,
            self.checked,
            self.group,
            self.region,
            self.disabled,
            self.level,
        )
        if self.sensitive and any(value is not None for value in sensitive_state):
            raise ValueError("Sensitive Fields may contain only minimal metadata")
        return self


class Snapshot(WireModel):
    v: Literal[1]
    url: str
    title: str
    lang: str
    viewport: Viewport
    truncated: bool
    elements: list[SnapshotElement]


class ActionBase(WireModel):
    v: Literal[1]
    task_id: str
    action_id: str
    sequence_number: JsonInteger
    narration: str


class NavigateAction(ActionBase):
    type: Literal["navigate"]
    url: str


class ClickAction(ActionBase):
    type: Literal["click"]
    id: JsonInteger


class GuardedClickAction(ActionBase):
    type: Literal["guarded_click"]
    id: JsonInteger
    confirmation_id: str = Field(pattern=r"^confirmation-[0-9a-f]{32}$")
    mutation_kind: Literal["clear_cart", "submit_checkout"]
    target_signature: str = Field(min_length=1)
    state_signature: str = Field(pattern=r"^cart:\d+$")
    cart_revision: JsonInteger = Field(ge=0)
    effect: str = Field(min_length=1)


class TypeAction(ActionBase):
    type: Literal["type"]
    id: JsonInteger
    text: str
    submit: bool


class SelectAction(ActionBase):
    type: Literal["select"]
    id: JsonInteger
    option: str


class ScrollToAction(ActionBase):
    type: Literal["scroll_to"]
    id: JsonInteger


class SpotlightAction(ActionBase):
    type: Literal["spotlight"]
    id: JsonInteger
    message: str


class AskShopperAction(ActionBase):
    type: Literal["ask_shopper"]
    question: str
    options: list[str]
    kind: Literal["confirmation"] | None = None


class DoneAction(ActionBase):
    type: Literal["done"]
    summary: str


Action = Annotated[
    NavigateAction
    | ClickAction
    | GuardedClickAction
    | TypeAction
    | SelectAction
    | ScrollToAction
    | SpotlightAction
    | AskShopperAction
    | DoneAction,
    Field(discriminator="type"),
]

_ACTION_ADAPTER = TypeAdapter(Action)


class ActionResult(WireModel):
    v: Literal[1]
    task_id: str
    action_id: str
    sequence_number: JsonInteger
    status: Literal["ok", "not_found", "blocked", "navigated", "timeout", "cancelled", "stale"]
    snapshot: Snapshot


def parse_snapshot(payload: object) -> Snapshot:
    return Snapshot.model_validate(payload)


def parse_action(payload: object) -> Action:
    return _ACTION_ADAPTER.validate_python(payload)


def parse_action_result(payload: object) -> ActionResult:
    return ActionResult.model_validate(payload)


def to_wire(message: WireModel) -> dict[str, Any]:
    return message.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
