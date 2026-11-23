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
    "task_started",
    "narration",
    "action",
    "suggestions",
    "done",
    "cancelled",
    "error",
    "plan_created",
    "plan_step_started",
    "plan_step_finished",
    "plan_paused",
    "plan_resumed",
    "plan_finished",
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


TaskEndKind = Literal["completed", "cancelled", "paused"]


PlanStepStatus = Literal["pending", "running", "done", "failed", "skipped"]


@dataclass
class PlanStep:
    """One thing the Shopper asked for, as their own words; never an intent or a target."""

    position: int  # 1-based, in the order spoken
    text: str
    status: PlanStepStatus = "pending"
    task_id: str | None = None


@dataclass
class ActivePlan:
    """Thin record beside the active task: the steps of one multi-part message.

    The Session still has at most one active task; the plan only remembers what is left and
    starts the next step as its own Shopping Task when the current one completes.
    """

    plan_id: str
    language: Language
    steps: list[PlanStep]
    cursor: int = 0  # index into `steps` of the step whose task is current
    skipped_steps: list[str] = field(default_factory=list)  # words for the report, not work
    # The whole multi-step message, so a later step's interpreter history can leave it out.
    message: str = ""
    # Why each failed step failed (its position -> the Shopper-language reason), for the report.
    reasons: dict[int, str] = field(default_factory=dict)
    # Set when the plan is to end cancelled: "stop", "new_request" or "takeover".
    cancel_reason: str | None = None
    # Why the running step waits on the Shopper: "question" or "confirmation"; None otherwise.
    paused: str | None = None
    # The id of the question that paused the plan, so a new question is told from the same one.
    paused_action_id: str | None = None


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
    # Add option the open question asks for: {"field": "size"|"color", "options": [...]}.
    pending_variant: dict[str, Any] | None = None
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
    # Intent family of the question the Shopper's latest answer replies to (plan steps only).
    answering_family: str | None = None
    # 1-based position when this task is a step of the Session's plan; such a task never
    # creates a plan of its own.
    plan_position: int | None = None
    # One short Shopper-language note for the done summary (a remembered size was used, or a
    # named person's size was not saved). Shopper-facing text only; never recorded in a log.
    size_note: str | None = field(default=None, repr=False)
    # Why a conditional add was not done (a plan step then counts as skipped, not failed).
    # Shopper-facing text only; never recorded in a log.
    skip_reason: str | None = field(default=None, repr=False)
    # A colour change in progress (an add of the new colour, then the removal of the old line):
    # the line read from the cart and the phase. Task-only scratch: never in the Session, an
    # event or a log record.
    swap: dict[str, Any] | None = field(default=None, repr=False)


@dataclass(frozen=True)
class TaskEnd:
    """How one Shopping Task ended; `reason` is the pause reason when it paused."""

    session: "Session"
    task: ActiveTask
    kind: TaskEndKind
    reason: str | None = None


@dataclass(frozen=True)
class AcceptedResult:
    task: ActiveTask
    result: ActionResult


@dataclass
class Session:
    session_id: str
    shopper: ShopperBinding | None = None
    events: list[SessionEvent] = field(default_factory=list)
    # Id of the newest event ever appended: the stream cursor. Stored events are bounded, so
    # the next id never comes from the list's length.
    last_event_id: int = 0
    # True when this process loaded the Session from the State Store (after a restart).
    restored: bool = False
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
    invitation_id: str | None = None
    plan: ActivePlan | None = None
    # The most recent plan, running or finished, until the next one is created (reload view).
    last_plan: ActivePlan | None = None
    # Task id of a task begun by code that nobody has interpreted yet (see `app.drive_plan`).
    start_pending: str | None = None
    # Remembered sizes, keyed by (person, size kind). Saved only with the Session in the State
    # Store (so they survive a restart); never in the state endpoint, any event or log record.
    remembered_sizes: dict[tuple[str, str], str] = field(default_factory=dict, repr=False)
    # Size the Copilot itself selected on a product's add form, and for whom (memory only).
    copilot_selected_size: dict[str, tuple[str, str]] = field(default_factory=dict, repr=False)
    # Size kind of products whose category and type the catalogue verified (id -> kind or None).
    product_kinds: dict[str, str | None] = field(default_factory=dict, repr=False)
    # Products the latest completed task touched (cards shown, an add, an open): what "this"
    # means when no product page is open. Verified {"id","name"} references only, at most 3.
    last_touched: list[dict[str, str]] = field(default_factory=list, repr=False)


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
