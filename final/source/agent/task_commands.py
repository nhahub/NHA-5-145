"""Shopper messages, answers, Confirmation consumption and Stop."""

from uuid import uuid4

from agent import plans
from agent.cart import scripted_cart_intent
from agent.confirmation import (
    classify_guarded_mutation,
    scripted_mutation_intent,
)
from agent.planner import (
    ActionIdentity,
    detect_language,
    is_expected_login_redirect,
)
from agent.schemas import (
    AskShopperAction,
    GuardedClickAction,
    NavigateAction,
    Snapshot,
    SpotlightAction,
    to_wire,
)
from agent.session_state import ActionResultMismatch, ActiveTask, TaskConflict
from agent.task_interpretation import (
    _CONTEXT_TEXT_LIMIT,
    begin_interpretation,
    finish_interpretation,
)
from agent.task_runtime import TaskRuntime


def submit_message(
    runtime: TaskRuntime,
    session_id: str,
    text: str,
    snapshot: Snapshot,
    *,
    replace_active: bool = False,
    tab_id: str | None = None,
) -> ActiveTask:
    from agent.navigation import is_deictic_cart_open

    scripted_mutation = scripted_mutation_intent(text) or scripted_cart_intent(text)
    if scripted_mutation is not None:
        task = begin_interpretation(
            runtime,
            session_id,
            text,
            snapshot,
            replace_active=replace_active,
            tab_id=tab_id,
        )
        finish_interpretation(
            runtime, session_id, task.task_id, task.model_call_id or "", scripted_mutation
        )
        return task
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    if session.active_task is not None:
        if not replace_active:
            raise TaskConflict("A Shopping Task is already active")
        runtime.end_task(session, session.active_task, "cancelled")
    previous_target = session.last_followup_target
    followup_target = previous_target if is_deictic_cart_open(text) else None
    session.last_followup_target = None
    task_id = f"task-{uuid4().hex}"
    planner_message = "افتح السلة" if followup_target == "cart" else text
    action, scripted_intent = runtime.planner.plan_with_intent(
        planner_message,
        snapshot,
        ActionIdentity(
            task_id=task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=1,
        ),
    )
    task = ActiveTask(
        task_id=task_id,
        action=action,
        language=detect_language(text),
        message=text,
        resolved_state={
            "_original_message": text[:_CONTEXT_TEXT_LIMIT],
            "_answers": [],
            **({"_previous_target": previous_target} if previous_target else {}),
            **({"target": followup_target} if followup_target else {}),
        },
        target_url=action.url if isinstance(action, NavigateAction) else None,
        intent_kind=scripted_intent.intent if scripted_intent is not None else None,
        target_name=(scripted_intent.constraints.target if scripted_intent is not None else None),
    )
    if scripted_intent is not None:
        task.language = scripted_intent.language
    if isinstance(action, AskShopperAction):
        task.status = "awaiting_answer"
    session.active_task = task
    session.last_task = task
    runtime.record_snapshot(session, snapshot)
    session.conversation.append({"role": "shopper", "text": text})
    session.conversation.append({"role": "copilot", "text": action.narration})
    runtime.sessions.touch(session)
    runtime.append(session, "task_started", {"task_id": task_id})
    runtime.append(
        session,
        "narration",
        {"task_id": task_id, "text": action.narration},
    )
    runtime.append(
        session,
        "action",
        {"task_id": task_id, "action": to_wire(action)},
    )
    return task


def answer(
    runtime: TaskRuntime,
    session_id: str,
    task_id: str,
    question_id: str,
    text: str,
    snapshot: Snapshot,
    tab_id: str | None = None,
) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    task = session.active_task
    if (
        task is None
        or task.task_id != task_id
        or not isinstance(task.action, AskShopperAction)
        or task.action.action_id != question_id
    ):
        raise ActionResultMismatch("Answer does not match the pending Shopper question")
    if task.action.options in (["Stop"], ["إيقاف"]):
        if text != task.action.options[0]:
            raise ActionResultMismatch("Choose Stop to end this Shopping Task")
        runtime.end_task(session, task, "cancelled")
        runtime.sessions.touch(session)
        return task
    if task.action.kind == "confirmation":
        if (
            task.status != "awaiting_answer"
            or task.confirmation is None
            or task.mutation_proposal is None
        ):
            raise ActionResultMismatch("There is no live Confirmation")

        def outcome(value: str) -> None:
            runtime.record(
                session,
                "confirmation",
                task_id=task.task_id,
                outcome=value,
                mutation_kind=task.mutation_kind,
            )

        def unusable(message: str) -> ActiveTask:
            """Inside a plan the step fails and the plan reports it; otherwise as ever."""
            if not plans.fail_unusable_confirmation(runtime, session, task):
                raise ActionResultMismatch(message)
            runtime.sessions.touch(session)
            return task

        if text in {"Stop", "إيقاف"}:
            outcome("stopped")
            task.confirmation.invalidate()
            runtime.end_task(session, task, "cancelled")
            runtime.sessions.touch(session)
            return task
        expected_answer = "تأكيد" if task.language == "ar" else "Confirm"
        candidate = next(
            (
                (element, current)
                for element in snapshot.elements
                if (current := classify_guarded_mutation(snapshot, element.id, task.task_id))
                == task.mutation_proposal
            ),
            None,
        )
        if candidate is None or text != expected_answer:
            outcome("stale")
            if text != expected_answer:
                # Not a Confirm at all: refused as ever, the step keeps waiting for its card.
                raise ActionResultMismatch("Confirmation no longer matches the Storefront state")
            return unusable("Confirmation no longer matches the Storefront state")
        element, current = candidate
        if not task.confirmation.can_confirm(question_id, "Confirm", current):
            outcome("expired")
            return unusable("Confirmation expired or was already used")
        if runtime.confirmation_registrar is None or not runtime.confirmation_registrar(
            session.shopper,
            snapshot.url,
            question_id,
            task.task_id,
            task.mutation_kind or "",
            int(dict(current.arguments)["cart_revision"]),
        ):
            outcome("unregistered")
            return unusable("The Storefront could not register this Confirmation")
        if not task.confirmation.confirm(question_id, "Confirm", current):
            outcome("expired")
            return unusable("Confirmation expired before execution")
        outcome("consumed")
        action = GuardedClickAction(
            v=1,
            type="guarded_click",
            task_id=task.task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=task.action.sequence_number + 1,
            narration=(
                "هأنفذ الإجراء اللي أكدته دلوقتي."
                if task.language == "ar"
                else "I'll perform the exact action you confirmed now."
            ),
            id=element.id,
            confirmation_id=question_id,
            mutation_kind=task.mutation_kind or "clear_cart",
            target_signature=current.target_signature,
            state_signature=current.state_signature,
            cart_revision=int(dict(current.arguments)["cart_revision"]),
            effect=current.effect,
        )
        task.confirmation = None
        task.action = action
        task.step_count += 1
        task.status = "awaiting_action_result"
        runtime.record_snapshot(session, snapshot)
        runtime.append(session, "narration", {"task_id": task.task_id, "text": action.narration})
        runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(action)})
        runtime.sessions.touch(session)
        return task
    if task.auth_handoff:
        if text == "Stop":
            runtime.end_task(session, task, "cancelled")
            runtime.sessions.touch(session)
            return task
        if text != "Continue":
            raise ActionResultMismatch("Choose Continue or Stop to resume order history")
        if (
            task.target_url is not None
            and session.last_snapshot is not None
            and is_expected_login_redirect(snapshot, session.last_snapshot, task.target_url)
        ):
            runtime.sessions.touch(session)
            return task
        if task.step_count >= 8:
            raise TaskConflict("Shopping Task step limit reached")
        action = runtime.planner.plan_orders_resume(
            snapshot,
            ActionIdentity(
                task_id=task.task_id,
                action_id=f"action-{uuid4().hex}",
                sequence_number=task.action.sequence_number + 1,
            ),
            task.language,
            trusted_origin=session.last_snapshot,
        )
        task.action = action
        task.auth_handoff = isinstance(action, AskShopperAction)
        task.awaiting_newest_order_spotlight = isinstance(action, SpotlightAction)
        task.target_url = action.url if isinstance(action, NavigateAction) else None
        task.step_count += 1
        task.status = (
            "awaiting_answer" if isinstance(action, AskShopperAction) else "awaiting_action_result"
        )
        session.conversation.append({"role": "copilot", "text": action.narration})
        runtime.sessions.touch(session)
        runtime.append(session, "narration", {"task_id": task.task_id, "text": action.narration})
        runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(action)})
        return task
    if task.step_count >= 8:
        narration = (
            "وصلت للحد الأقصى للخطوات ووقفت المهمة مؤقتًا."
            if task.language == "ar"
            else "I reached the step limit and paused this task."
        )
        question = (
            "وصلنا لحد الخطوات. تحب نعمل إيه؟"
            if task.language == "ar"
            else "We reached the step limit. What would you like me to do?"
        )
        capped = AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task.task_id,
            action_id=f"question-{uuid4().hex}",
            sequence_number=task.action.sequence_number + 1,
            narration=narration,
            question=question,
            options=["Start over", "Stop"] if task.language == "en" else ["ابدأ من جديد", "إيقاف"],
        )
        task.action = capped
        task.status = "awaiting_answer"
        runtime.append(session, "narration", {"task_id": task.task_id, "text": narration})
        runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(capped)})
        runtime.sessions.touch(session)
        return task
    action = runtime.planner.plan_answer(
        task.message,
        text,
        snapshot,
        ActionIdentity(
            task_id=task.task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=task.action.sequence_number + 1,
        ),
    )
    task.action = action
    if isinstance(action, NavigateAction):
        task.target_url = action.url
    task.step_count += 1
    task.status = (
        "awaiting_answer" if isinstance(action, AskShopperAction) else "awaiting_action_result"
    )
    runtime.record_snapshot(session, snapshot)
    session.conversation.append({"role": "shopper", "text": text})
    session.conversation.append({"role": "copilot", "text": action.narration})
    runtime.sessions.touch(session)
    runtime.append(session, "narration", {"task_id": task.task_id, "text": action.narration})
    runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(action)})
    return task


def is_auth_handoff(runtime: TaskRuntime, session_id: str, task_id: str, question_id: str) -> bool:
    task = runtime.sessions.get(session_id).active_task
    return bool(
        task is not None
        and task.task_id == task_id
        and task.auth_handoff
        and isinstance(task.action, AskShopperAction)
        and task.action.action_id == question_id
    )


def is_guarded_confirmation(
    runtime: TaskRuntime, session_id: str, task_id: str, question_id: str
) -> bool:
    task = runtime.sessions.get(session_id).active_task
    return bool(
        task is not None
        and task.task_id == task_id
        and task.status == "awaiting_answer"
        and isinstance(task.action, AskShopperAction)
        and task.action.kind == "confirmation"
        and task.action.action_id == question_id
    )


def is_stop_only_question(
    runtime: TaskRuntime, session_id: str, task_id: str, question_id: str
) -> bool:
    task = runtime.sessions.get(session_id).active_task
    return bool(
        task is not None
        and task.task_id == task_id
        and isinstance(task.action, AskShopperAction)
        and task.action.action_id == question_id
        and task.action.options in (["Stop"], ["إيقاف"])
    )


def stop(runtime: TaskRuntime, session_id: str, tab_id: str | None = None) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    task = session.active_task
    if task is None:
        raise TaskConflict("There is no active Shopping Task")
    if task.confirmation is not None:
        task.confirmation.invalidate()
    runtime.end_task(session, task, "cancelled")
    runtime.sessions.touch(session)
    return task
