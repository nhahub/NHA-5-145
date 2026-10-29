"""Shared in-memory Session and Shopping Task records and domain errors."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from agent.catalogue_retrieval import RetrievalBudget

from agent.confirmation import ConfirmationLedger, MutationProposal
from agent.planner import Language
from agent.product_context import ProductContext
from agent.schemas import Action, ActionResult, Snapshot
from agent.shopper_access import ShopperBinding

EventType = Literal[
    "task_started", "narration", "action", "suggestions", "done", "cancelled", "error"
]


TaskStatus = Literal[
    "interpreting", "awaiting_action_result", "awaiting_answer", "completed", "cancelled", "paused"
]


InterpretationPauseReason = Literal[
    "budget",
    "inference_busy",
    "inference_disabled",
    "inference_unavailable",
    "throttled",
    "timeout",
    "network",
    "provider_http",
    "invalid_response",
    "catalogue_unavailable",
    "interrupted",
    "unexpected",
]


@dataclass(frozen=True)
class SessionEvent:
    id: int
    event: EventType
    data: dict[str, Any]


@dataclass
class ActiveTask:
    task_id: str
    action: Action | None
    language: Language
    message: str
    target_url: str | None = None
    step_count: int = 1
    status: TaskStatus = "awaiting_action_result"
    model_call_id: str | None = None
    resolved_state: dict[str, Any] = field(default_factory=dict)
    pending_clarification: str | None = None
    intent_kind: str | None = None
    target_name: str | None = None
    auth_handoff: bool = False
    awaiting_newest_order_spotlight: bool = False
    suggestions: dict[str, object] | None = None
    pause_message: str | None = None
    origin_url: str | None = None
    confirmation: ConfirmationLedger | None = None
    mutation_proposal: MutationProposal | None = None
    mutation_kind: Literal["clear_cart", "submit_checkout"] | None = None
    cart_actions: list[Action] = field(default_factory=list)
    cart_operation: str | None = None
    retrieval_budget: "RetrievalBudget | None" = None


@dataclass(frozen=True)
class AcceptedResult:
    task: ActiveTask
    result: ActionResult


@dataclass
class Session:
    session_id: str
    shopper: ShopperBinding | None = None
    events: list[SessionEvent] = field(default_factory=list)
    active_task: ActiveTask | None = None
    accepted_results: dict[tuple[str, str, int], AcceptedResult] = field(default_factory=dict)
    conversation: list[dict[str, str]] = field(default_factory=list)
    last_task: ActiveTask | None = None
    last_snapshot: Snapshot | None = None
    last_followup_target: str | None = None
    lease_tab_id: str | None = None
    last_activity_at: float = 0.0
    requires_reconciliation: bool = False
    product_context: ProductContext = field(default_factory=ProductContext)
    advice_context: dict[str, Any] = field(default_factory=dict)


class SessionNotFound(KeyError):
    pass


class SessionExpired(SessionNotFound):
    pass


class TaskConflict(ValueError):
    pass


class ActionResultMismatch(ValueError):
    pass


class LeaseConflict(ValueError):
    pass
