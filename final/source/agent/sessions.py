"""Stable session interface composing storage and Shopping Task modules."""

from collections.abc import Callable, Mapping
from time import monotonic, time
from typing import Any

from agent import (
    plans,
    remembered_sizes,
    session_restore,
    task_commands,
    task_interpretation,
    task_recovery,
    task_results,
)
from agent.catalogue import DiscoveryResult
from agent.event_log import EventLog
from agent.llm.intent import StructuredIntent
from agent.planner import ScriptedPlanner
from agent.plans import PlanSteps
from agent.schemas import ActionResult, Snapshot
from agent.session_registry import SESSION_TTL_SECONDS, SessionRegistry, StateSaveFailed
from agent.session_state import (
    AcceptedResult,
    ActionResultMismatch,
    ActiveTask,
    EventType,
    InterpretationPauseReason,
    LeaseConflict,
    Session,
    SessionEvent,
    SessionExpired,
    SessionNotFound,
    TaskConflict,
    TaskEnd,
    TaskEndKind,
    TaskStatus,
)
from agent.shopper_access import ShopperBinding
from agent.state_store import StateStore
from agent.swap import SwapDecision
from agent.task_runtime import TaskRuntime

__all__ = [
    "SessionStore",
    "SESSION_TTL_SECONDS",
    "StateSaveFailed",
    "EventType",
    "TaskStatus",
    "TaskEnd",
    "TaskEndKind",
    "InterpretationPauseReason",
    "SessionEvent",
    "ActiveTask",
    "AcceptedResult",
    "Session",
    "SessionNotFound",
    "SessionExpired",
    "TaskConflict",
    "ActionResultMismatch",
    "LeaseConflict",
]


class SessionStore:
    def __init__(
        self,
        planner: ScriptedPlanner | None = None,
        *,
        clock: Any = monotonic,
        capacity: int = 800,
        confirmation_registrar: Callable[[ShopperBinding | None, str, str, str, str, int], bool]
        | None = None,
        store: StateStore | None = None,
        wall_clock: Callable[[], float] = time,
    ) -> None:
        self._registry = SessionRegistry(
            clock=clock,
            capacity=capacity,
            store=store,
            wall_clock=wall_clock,
            on_restore=lambda session: session_restore.restore_interrupted(self._runtime, session),
        )
        self._runtime = TaskRuntime(
            self._registry, planner or ScriptedPlanner(), clock, confirmation_registrar
        )
        # First to hear every task end: the plan starts the next step before any other listener.
        self._runtime.task_end_listeners.append(lambda end: plans.on_task_end(self._runtime, end))

    def attach_event_log(self, events: EventLog) -> None:
        self._runtime.events = events

    def on_task_end(self, listener: Callable[[TaskEnd], None]) -> None:
        """Hear every Shopping Task end (none are registered by default)."""
        self._runtime.task_end_listeners.append(listener)

    def create(self, tab_id: str | None = None) -> Session:
        return self._registry.create(tab_id)

    def flush(self, *, checkpoint: bool = False) -> None:
        """Save every changed Session to the State Store (no-op without one)."""
        self._registry.flush(checkpoint=checkpoint)

    def adopt(self, session_id: str, binding: ShopperBinding | None) -> bool:
        """Whether a Session this process restored belongs to this Shopper binding.

        After a restart the browser has a new authority; the stored owner binding is the proof
        that lets the same Shopper keep their Session.
        """
        if binding is None:
            return False
        try:
            session = self._registry.get(session_id)
        except SessionNotFound:
            return False
        return session.restored and session.shopper == binding

    def has_capacity(self) -> bool:
        return self._registry.has_capacity()

    def has_pending_work(self) -> bool:
        return self._registry.has_pending_work()

    def get(self, session_id: str) -> Session:
        return self._registry.get(session_id)

    def assert_lease(self, session: Session, tab_id: str | None) -> None:
        return self._registry.assert_lease(session, tab_id)

    def takeover(self, session_id: str, tab_id: str) -> Session:
        session = self._registry.takeover(session_id, tab_id)
        # Nothing after the plan's current step may start in the tab that is being left.
        plans.cancel_after_current(self._runtime, session, "takeover")
        return session

    def settle_plan(self, session_id: str) -> None:
        """Fail the plan's current step when its task waits on a failure question."""
        plans.settle(self._runtime, self.get(session_id))

    def owns_lease(self, session_id: str, tab_id: str | None) -> bool:
        return self._registry.owns_lease(session_id, tab_id)

    def begin_interpretation(
        self,
        session_id: str,
        text: str,
        snapshot: Snapshot,
        *,
        replace_active: bool = False,
        tab_id: str | None = None,
    ) -> ActiveTask:
        return task_interpretation.begin_interpretation(
            self._runtime, session_id, text, snapshot, replace_active=replace_active, tab_id=tab_id
        )

    def finish_interpretation(
        self,
        session_id: str,
        task_id: str,
        call_id: str,
        intent: StructuredIntent,
        *,
        plan_steps: PlanSteps | None = None,
        condition_result: bool | None = None,
        condition_reason: str | None = None,
        swap_check: SwapDecision | None = None,
    ) -> ActiveTask | None:
        return task_interpretation.finish_interpretation(
            self._runtime,
            session_id,
            task_id,
            call_id,
            intent,
            plan_steps=plan_steps,
            condition_result=condition_result,
            condition_reason=condition_reason,
            swap_check=swap_check,
        )

    def finish_catalogue_interpretation(
        self,
        session_id: str,
        task_id: str,
        call_id: str,
        intent: StructuredIntent,
        result: DiscoveryResult,
        *,
        advice_text: str | None = None,
        plan_steps: PlanSteps | None = None,
        end_reason: str | None = None,
        facts: Mapping[str, tuple[str, str]] | None = None,
        beneficiary: str | None = None,
        size_hint: str | None = None,
        clarify: bool = False,
        options: list[str] | None = None,
    ) -> ActiveTask | None:
        return task_interpretation.finish_catalogue_interpretation(
            self._runtime,
            session_id,
            task_id,
            call_id,
            intent,
            result,
            advice_text=advice_text,
            plan_steps=plan_steps,
            end_reason=end_reason,
            facts=facts,
            beneficiary=beneficiary,
            size_hint=size_hint,
            clarify=clarify,
            options=options,
        )

    def note_product_facts(
        self, session_id: str, facts: Mapping[str, tuple[str, str]] | None
    ) -> None:
        """Keep the size kind of products the catalogue just verified (never the facts)."""
        remembered_sizes.note_verified(self.get(session_id), facts)

    def begin_answer_interpretation(
        self,
        session_id: str,
        task_id: str,
        question_id: str,
        text: str,
        snapshot: Snapshot,
        tab_id: str | None,
    ) -> ActiveTask:
        return task_interpretation.begin_answer_interpretation(
            self._runtime, session_id, task_id, question_id, text, snapshot, tab_id
        )

    def fail_interpretation(
        self,
        session_id: str,
        task_id: str,
        call_id: str,
        reason: InterpretationPauseReason,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        return task_interpretation.fail_interpretation(
            self._runtime,
            session_id,
            task_id,
            call_id,
            reason,
            retry_after_seconds=retry_after_seconds,
        )

    def retry_interpretation(
        self, session_id: str, task_id: str, tab_id: str | None, snapshot: Snapshot
    ) -> ActiveTask:
        return task_interpretation.retry_interpretation(
            self._runtime, session_id, task_id, tab_id, snapshot
        )

    def submit_message(
        self,
        session_id: str,
        text: str,
        snapshot: Snapshot,
        *,
        replace_active: bool = False,
        tab_id: str | None = None,
    ) -> ActiveTask:
        return task_commands.submit_message(
            self._runtime, session_id, text, snapshot, replace_active=replace_active, tab_id=tab_id
        )

    def answer(
        self,
        session_id: str,
        task_id: str,
        question_id: str,
        text: str,
        snapshot: Snapshot,
        tab_id: str | None = None,
    ) -> ActiveTask:
        return task_commands.answer(
            self._runtime, session_id, task_id, question_id, text, snapshot, tab_id
        )

    def is_auth_handoff(self, session_id: str, task_id: str, question_id: str) -> bool:
        return task_commands.is_auth_handoff(self._runtime, session_id, task_id, question_id)

    def is_guarded_confirmation(self, session_id: str, task_id: str, question_id: str) -> bool:
        return task_commands.is_guarded_confirmation(
            self._runtime, session_id, task_id, question_id
        )

    def is_stop_only_question(self, session_id: str, task_id: str, question_id: str) -> bool:
        return task_commands.is_stop_only_question(self._runtime, session_id, task_id, question_id)

    def accept_result(
        self, session_id: str, action_result: ActionResult, tab_id: str | None = None
    ) -> ActiveTask:
        return task_results.accept_result(self._runtime, session_id, action_result, tab_id)

    def stop(self, session_id: str, tab_id: str | None = None) -> ActiveTask:
        return task_commands.stop(self._runtime, session_id, tab_id)

    def state(self, session_id: str, tab_id: str) -> dict[str, Any]:
        return task_recovery.state(self._runtime, session_id, tab_id)

    def reconcile(self, session_id: str, tab_id: str, snapshot: Snapshot) -> dict[str, Any]:
        return task_recovery.reconcile(self._runtime, session_id, tab_id, snapshot)

    def events_after(self, session_id: str, event_id: int) -> list[SessionEvent]:
        return [event for event in self.get(session_id).events if event.id > event_id]
