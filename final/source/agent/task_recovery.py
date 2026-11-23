"""Refresh state views and reconciliation without action replay."""

from typing import Any
from uuid import uuid4

from agent import plans
from agent.schemas import (
    AskShopperAction,
    ClickAction,
    GuardedClickAction,
    Snapshot,
    to_wire,
)
from agent.task_runtime import TaskRuntime


def state(runtime: TaskRuntime, session_id: str, tab_id: str) -> dict[str, Any]:
    session = runtime.sessions.get(session_id)
    owned = session.lease_tab_id in {None, tab_id}
    if owned and session.active_task is not None and session.active_task.confirmation is not None:
        task = session.active_task
        runtime.record(
            session,
            "confirmation",
            task_id=task.task_id,
            outcome="invalidated",
            mutation_kind=task.mutation_kind,
        )
        task.confirmation.invalidate()
        task.confirmation = None
        task.mutation_proposal = None
        task.action = None
        runtime.end_task(
            session,
            task,
            "paused",
            "refresh",
            "انتهى التأكيد بعد تحديث الصفحة. حاول تاني لتأكيد الحالة الحالية."
            if task.language == "ar"
            else "Confirmation expired on refresh. Retry from the current Storefront state.",
        )
    if owned and session.active_task is not None and session.active_task.status == "interpreting":
        task = session.active_task
        task.model_call_id = None
        runtime.end_task(
            session,
            task,
            "paused",
            "refresh",
            "اتحدثت الصفحة أثناء فهم الطلب. حاول تاني أو أوقف المهمة."
            if task.language == "ar"
            else "The page refreshed while I was interpreting. Retry or stop this task.",
        )
    if (
        owned
        and session.active_task is not None
        and session.active_task.status == "awaiting_action_result"
    ):
        session.requires_reconciliation = True
    task = session.active_task or session.last_task
    pending_question = None
    if task is not None and isinstance(task.action, AskShopperAction):
        pending_question = to_wire(task.action)
    runtime.sessions.touch(session)
    return {
        "session_id": session.session_id,
        "lease": "owned" if owned else "takeover_required",
        "event_cursor": session.last_event_id,
        "conversation": session.conversation,
        "requires_reconciliation": session.requires_reconciliation,
        "plan": plans.view(session),
        "task": (
            {
                "task_id": task.task_id,
                "status": task.status,
                "pending_question": pending_question,
                "suggestions": task.suggestions,
                "pause_message": task.pause_message,
            }
            if task is not None
            else None
        ),
    }


def reconcile(
    runtime: TaskRuntime, session_id: str, tab_id: str, snapshot: Snapshot
) -> dict[str, Any]:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    task = session.active_task
    if (
        session.requires_reconciliation
        and task is not None
        and task.action is not None
        and not isinstance(task.action, AskShopperAction)
    ):
        action = task.action
        if isinstance(action, GuardedClickAction) or (
            task.cart_operation and isinstance(action, ClickAction)
        ):
            runtime.ask_to_stop_uncertain_mutation(session, task, action)
        elif task.cart_operation or task.mutation_kind:
            task.action = None
            task.cart_actions.clear()
            runtime.end_task(
                session,
                task,
                "paused",
                "refresh",
                "اتحدثت الصفحة قبل تعديل السلة أو الطلب. حاول تاني من الحالة الحالية."
                if task.language == "ar"
                else "The page refreshed before the cart or order change. "
                "Retry from the current Storefront state.",
            )
        else:
            narration = (
                "بعد التحديث مش متأكد إذا الإجراء السابق اكتمل. مش هكرره تلقائيًا."
                if task.language == "ar"
                else (
                    "After refresh, I can't prove the previous action completed, "
                    "so I won't replay it."
                )
            )
            question = (
                "نكمل من الصفحة الحالية ولا نوقف المهمة؟"
                if task.language == "ar"
                else "Continue from the current page or stop this task?"
            )
            uncertain = AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=task.task_id,
                action_id=f"question-{uuid4().hex}",
                sequence_number=action.sequence_number + 1,
                narration=narration,
                question=question,
                options=["Continue", "Stop"] if task.language == "en" else ["كمّل", "إيقاف"],
            )
            task.action = uncertain
            task.status = "awaiting_answer"
            task.step_count += 1
            runtime.append(session, "narration", {"task_id": task.task_id, "text": narration})
            runtime.append(
                session, "action", {"task_id": task.task_id, "action": to_wire(uncertain)}
            )
            session.conversation.append({"role": "copilot", "text": narration})
    runtime.record_snapshot(session, snapshot)
    session.requires_reconciliation = False
    plans.settle(runtime, session)
    runtime.sessions.touch(session)
    view = state(runtime, session_id, tab_id)
    session.requires_reconciliation = False
    view["requires_reconciliation"] = False
    return view
