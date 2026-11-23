"""Single-use authority for one precisely described Guarded Mutation."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

from agent.schemas import Snapshot

if TYPE_CHECKING:
    from agent.llm.intent import StructuredIntent

CONFIRMATION_TTL_SECONDS = 60


@dataclass(frozen=True)
class MutationProposal:
    task_id: str
    action_type: str
    target_signature: str
    arguments: tuple[tuple[str, str], ...]
    effect: str
    state_signature: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.task_id,
                self.action_type,
                self.target_signature,
                self.effect,
                self.state_signature,
            )
        ):
            raise ValueError("A Guarded Mutation needs complete, stable authority")
        if len({key for key, _ in self.arguments}) != len(self.arguments):
            raise ValueError("Mutation arguments must have unique names")


@dataclass(frozen=True)
class _Offer:
    question_id: str
    proposal: MutationProposal
    created_at: float


class ConfirmationLedger:
    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._offer: _Offer | None = None

    def offer(self, proposal: MutationProposal) -> str:
        question_id = f"confirmation-{uuid4().hex}"
        self._offer = _Offer(question_id, proposal, self._clock())
        return question_id

    def can_confirm(
        self, question_id: str, answer: str, current_proposal: MutationProposal
    ) -> bool:
        offer = self._offer
        if offer is None:
            return False
        if self._clock() - offer.created_at >= CONFIRMATION_TTL_SECONDS:
            self._offer = None
            return False
        return (
            question_id == offer.question_id
            and answer == "Confirm"
            and current_proposal == offer.proposal
        )

    def confirm(self, question_id: str, answer: str, current_proposal: MutationProposal) -> bool:
        if not self.can_confirm(question_id, answer, current_proposal):
            return False
        self._offer = None
        return True

    def invalidate(self) -> None:
        self._offer = None


def classify_guarded_mutation(
    snapshot: Snapshot, element_id: int, task_id: str
) -> MutationProposal | None:
    """Classify controlled mutation endpoints; labels alone confer no authority."""
    page = urlsplit(snapshot.url)
    if page.scheme not in {"http", "https"}:
        return None
    expected = {"/cart": "/cart/clear", "/checkout": "/checkout/submit"}.get(page.path)
    if expected is None:
        return None
    element = next((item for item in snapshot.elements if item.id == element_id), None)
    if (
        element is None
        or not element.visible
        or element.disabled
        or element.role != "button"
        or element.form_action != expected
        or element.mutation_state is None
        or not element.mutation_state.startswith("cart:")
        or not element.mutation_state[5:].isdigit()
    ):
        return None
    revision = element.mutation_state[5:]
    effect = (
        "Remove every item from the current cart"
        if expected == "/cart/clear"
        else "Submit one fictional order for the current cart"
    )
    return MutationProposal(
        task_id=task_id,
        action_type="guarded_click",
        target_signature=f"button|{element.name}|POST {expected}",
        arguments=(("cart_revision", revision),),
        effect=effect,
        state_signature=element.mutation_state,
    )


def validate_mutation_interpretation(message: str, intent: StructuredIntent) -> None:
    """Validate the proposed capability; only the bound Confirmation authorizes execution."""
    del message
    if intent.mutation_kind not in {"clear_cart", "submit_checkout"}:
        raise ValueError("Unsupported Guarded Mutation")


def scripted_mutation_intent(message: str) -> StructuredIntent | None:
    """Bounded no-network fixture for browser safety tests; live language uses the model."""
    from agent.llm.intent import StructuredIntent

    patterns = (
        ("clear_cart", r"(?:please\s+)?(?:empty|clear)\s+(?:my|the)\s+cart[.!?]*"),
        ("clear_cart", r"(?:فضي|افرغ|إفرغ|امسح)\s+(?:لي\s+)?(?:السلة|سلتي)[.!؟]*"),
        (
            "submit_checkout",
            r"(?:please\s+)?(?:place|submit)\s+(?:my|the)\s+(?:fictional\s+)?order[.!?]*",
        ),
        ("submit_checkout", r"(?:أكد|اكد|اتمم)\s+(?:الطلب|طلبي)(?:\s+الخيالي)?[.!؟]*"),
    )
    for kind, pattern in patterns:
        match = re.fullmatch(pattern, message.strip(), re.I)
        if match is None:
            continue
        is_arabic = bool(re.search(r"[\u0600-\u06ff]", message))
        return StructuredIntent.model_validate(
            {
                "v": 4,
                "language": "ar" if is_arabic else "en",
                "dialect": "egyptian_arabic" if is_arabic else "english",
                "intent": "mutate",
                "mutation_kind": kind,
                "mutation_source": message.strip(),
                "constraints": {},
                "missing_fields": [],
                "needs_clarification": False,
            }
        )
    return None
