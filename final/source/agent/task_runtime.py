"""Shared dependencies and cross-cutting task policy used by task transitions."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from agent.confirmation import (
    ConfirmationLedger,
    classify_guarded_mutation,
)
from agent.event_log import EventLog, shopper_tag
from agent.planner import (
    ScriptedPlanner,
)
from agent.schemas import (
    Action,
    AskShopperAction,
    Snapshot,
    to_wire,
)
from agent.session_registry import SessionRegistry
from agent.session_state import (
    ActiveTask,
    EventType,
    Session,
    SessionEvent,
    TaskConflict,
    TaskEnd,
    TaskEndKind,
)
from agent.shopper_access import ShopperBinding


@dataclass
class TaskRuntime:
    sessions: SessionRegistry
    planner: ScriptedPlanner
    clock: Callable[[], float]
    confirmation_registrar: Callable[[ShopperBinding | None, str, str, str, str, int], bool] | None
    events: EventLog | None = None
    task_end_listeners: list[Callable[[TaskEnd], None]] = field(default_factory=list)

    def end_task(
        self,
        session: Session,
        task: ActiveTask,
        kind: TaskEndKind,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        """The one place a Shopping Task ends: completed, cancelled, or paused with a reason.

        A completed or cancelled task leaves the Session's active task; a paused one stays
        there awaiting Retry. Cancelling appends its `cancelled` event and pausing writes its
        `task_paused` record here; a completed task's `done` event is written by the caller
        first, because its summary differs. A pause's `message` is the Shopper-facing text: it
        is stored and published as the `error` event before any listener hears the end.
        """
        task.status = kind
        if kind == "paused":
            self.record(session, "task_paused", task_id=task.task_id, reason=reason)
            if message is not None:
                task.pause_message = message
                self.append(session, "error", {"task_id": task.task_id, "message": message})
        else:
            session.active_task = None
            session.last_task = task
            if kind == "cancelled":
                self.append(session, "cancelled", {"task_id": task.task_id})
        end = TaskEnd(session=session, task=task, kind=kind, reason=reason)
        for listener in self.task_end_listeners:
            listener(end)

    def record_debug(self, session: Session, kind: str, text: str, task_id: str) -> None:
        """Free text for the owner's debug switch; written only while it is on."""
        if self.events is None:
            return
        try:
            self.events.emit_debug(
                kind,
                text,
                session_id=session.session_id,
                task_id=task_id,
                shopper=shopper_tag(session.shopper),
                invitation_id=session.invitation_id,
            )
        except Exception:
            self.events.failures += 1

    def record(self, session: Session, event: str, **fields: Any) -> None:
        """Emit one event-log record for this session; never fails the task."""
        if self.events is None:
            return
        try:
            self.events.emit(
                event,
                session_id=session.session_id,
                shopper=shopper_tag(session.shopper),
                invitation_id=session.invitation_id,
                **fields,
            )
        except Exception:
            self.events.failures += 1

    def record_snapshot(self, session: Session, snapshot: Snapshot) -> None:
        location = urlsplit(snapshot.url)
        if session.product_context.origin != (location.scheme, location.netloc):
            session.advice_context.clear()
        session.last_snapshot = snapshot
        session.product_context.observe(
            snapshot, self.planner.storefront, len(session.conversation)
        )

    def require_task_origin(self, task: ActiveTask, snapshot: Snapshot) -> None:
        if task.origin_url is not None:
            original, current = urlsplit(task.origin_url), urlsplit(snapshot.url)
            if (original.scheme, original.netloc) != (current.scheme, current.netloc):
                raise TaskConflict("Continuing a task requires its original Storefront origin")

    def ask_to_stop_uncertain_mutation(
        self, session: Session, task: ActiveTask, action: Action
    ) -> None:
        if task.mutation_kind == "submit_checkout":
            narration = (
                "مش متأكد إذا الطلب الخيالي اتسجل. راجع سجل الطلبات؛ مش هقدمه تاني تلقائيًا."
                if task.language == "ar"
                else "I can't verify whether the fictional order was submitted. "
                "Check order history; I won't submit it again automatically."
            )
        else:
            narration = (
                "مش متأكد إذا تعديل السلة اكتمل. راجع السلة الحالية؛ مش هكرره تلقائيًا."
                if task.language == "ar"
                else "I can't verify whether the cart changed. Review the current cart; "
                "I won't repeat the change automatically."
            )
        question = (
            "أوقف المهمة دي، واطلب التعديل من جديد لو لسه محتاجه."
            if task.language == "ar"
            else "Stop this task, then make a new request only if the change is still needed."
        )
        stop = AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task.task_id,
            action_id=f"question-{uuid4().hex}",
            sequence_number=action.sequence_number + 1,
            narration=narration,
            question=question,
            options=["إيقاف"] if task.language == "ar" else ["Stop"],
        )
        task.action = stop
        task.step_count += 1
        task.status = "awaiting_answer"
        task.pause_message = None
        task.cart_actions.clear()
        task.mutation_proposal = None
        self.append(session, "narration", {"task_id": task.task_id, "text": narration})
        self.append(session, "action", {"task_id": task.task_id, "action": to_wire(stop)})
        session.conversation.append({"role": "copilot", "text": narration})

    def offer_mutation(
        self, task: ActiveTask, snapshot: Snapshot, sequence: int
    ) -> AskShopperAction:
        proposal = next(
            (
                candidate
                for element in snapshot.elements
                if (candidate := classify_guarded_mutation(snapshot, element.id, task.task_id))
                is not None
                and (
                    (
                        task.mutation_kind == "clear_cart"
                        and "/cart/clear" in candidate.target_signature
                    )
                    or (
                        task.mutation_kind == "submit_checkout"
                        and "/checkout/submit" in candidate.target_signature
                    )
                )
            ),
            None,
        )
        if proposal is None:
            raise ValueError("No current Guarded Mutation target is available")
        ledger = ConfirmationLedger(clock=self.clock)
        question_id = ledger.offer(proposal)
        task.confirmation = ledger
        task.mutation_proposal = proposal
        is_arabic = task.language == "ar"
        effect = (
            (
                "إزالة كل المنتجات من السلة الحالية"
                if task.mutation_kind == "clear_cart"
                else "تسجيل طلب خيالي واحد بمحتويات السلة الحالية، دون دفع حقيقي"
            )
            if is_arabic
            else proposal.effect
        )
        question = (
            f"تأكيد الإجراء: {effect}. هل تريد المتابعة؟"
            if is_arabic
            else f"Confirm this action: {effect}. Continue?"
        )
        return AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task.task_id,
            action_id=question_id,
            sequence_number=sequence,
            narration=question,
            question=question,
            options=["تأكيد", "إيقاف"] if is_arabic else ["Confirm", "Stop"],
            kind="confirmation",
        )

    def append(self, session: Session, event: EventType, data: dict[str, Any]) -> None:
        payload = {"session_id": session.session_id, **data}
        session.last_event_id += 1
        session.events.append(SessionEvent(id=session.last_event_id, event=event, data=payload))
        action = data.get("action") or {}
        if event.startswith("plan_"):
            return  # plans have their own records (plan_created, plan_step, plan_finished)
        self.record(
            session,
            "task",
            kind=event,
            task_id=data.get("task_id"),
            action_type=action.get("type"),
            sequence=action.get("sequence_number"),
            question_kind=(action.get("kind") or "question")
            if action.get("type") == "ask_shopper"
            else None,
            language=data.get("language"),
        )
