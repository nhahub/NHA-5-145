"""Multi-part messages: a thin plan beside the Session's one active Shopping Task.

The plan holds only the Shopper's words for each step. It never carries an intent, a product
ID, an element ID or a target: each step is interpreted by the normal path at its own turn,
against the latest observed Snapshot, as its own Shopping Task with its own task id.
Progression is driven by the shared task end (`TaskRuntime.end_task`).

A plan never runs on after something goes wrong: a step that fails (or is stopped, or whose
request is replaced by a new one) skips everything after it, ends the plan, and the Shopper
gets one report of what was done, what failed and what was skipped. Nothing is rolled back.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from agent.conditions import CONDITION_FALSE
from agent.llm.intent import StructuredIntent
from agent.planner import Language
from agent.product_confirmation import DECLINED_REASON, PRODUCT_DECLINED
from agent.schemas import AskShopperAction
from agent.session_state import (
    ActivePlan,
    ActiveTask,
    PlanStep,
    Session,
    TaskEnd,
)
from agent.task_runtime import TaskRuntime

# A completed task that ended in the catalogue's exhausted fallback did not do its step.
RETRIEVAL_EXHAUSTED = "retrieval_exhausted"
_GENERIC_FIRST_STEP: dict[str, str] = {"ar": "الطلب الأول", "en": "First request"}
# The only choices a question may offer and still be a failure rather than a real question.
_FAILURE_OPTIONS = frozenset(
    {"Stop", "إيقاف", "Try again", "حاول تاني", "Start over", "ابدأ من جديد"}
)
# Intents of one family continue a step's question; another family is a new request.
_FAMILIES = {
    "cart_edit": "cart_edit",
    "mutate": "mutate",
    "navigate": "go",
    "locate": "go",
    "open_product": "go",
    "find_products": "search",
    "advice": "search",
    "help": "talk",
    "off_topic": "talk",
    "unsupported": "talk",
}
_REASON_EXHAUSTED = {"ar": "ما قدرتش أكمّل البحث.", "en": "I couldn't finish the search."}
_REASON_NOT_STARTED = {"ar": "ما قدرتش أبدأ الخطوة دي.", "en": "I couldn't start this step."}
_REASON_CONFIRMATION = {
    "ar": "انتهى التأكيد أو اتغيّرت السلة، فما نفّذتش الخطوة دي. تقدر تطلبها تاني.",
    "en": "The Confirmation expired or the cart changed, so I didn't do this step. "
    "You can ask again.",
}
_HEADINGS: dict[str, dict[str, str]] = {
    "ar": {
        "done": "خلصت طلبك:",
        "failed": "وقفت عند خطوة ماتمّتش:",
        "stop": "وقفت الطلب زي ما طلبت:",
        "new_request": "لغيت باقي الخطوات وبدأت طلبك الجديد:",
        "takeover": "لغيت باقي الخطوات لأن المحادثة اتفتحت في صفحة تانية:",
    },
    "en": {
        "done": "Your request is finished:",
        "failed": "I stopped at a step that didn't work:",
        "stop": "I stopped your request as you asked:",
        "new_request": "I cancelled the remaining steps and started your new request:",
        "takeover": "I cancelled the remaining steps because the chat moved to another tab:",
    },
}
_SKIPPED_SUFFIX = {
    "cancelled": {"ar": " (اتلغت)", "en": " (cancelled)"},
    "failed": {"ar": " (اتخطّت)", "en": " (skipped)"},
}


@dataclass(frozen=True)
class PlanSteps:
    """What the first interpretation of a message said about the parts after the first."""

    first_step: str | None = None
    remaining_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    dialect: str = "unknown"

    @classmethod
    def from_intent(cls, intent: StructuredIntent) -> "PlanSteps":
        return cls(
            intent.first_step,
            list(intent.remaining_steps),
            list(intent.skipped_steps),
            intent.dialect,
        )


def open_plan(
    runtime: TaskRuntime,
    session: Session,
    task: ActiveTask,
    steps: PlanSteps,
    language: Language,
) -> None:
    """Create the plan when the first interpretation yields later steps; otherwise nothing.

    A step's own interpretation never nests a plan, and a plan already running is never
    replaced (an answer to step 1's question is interpreted again and may repeat the steps).
    Called just before the first task's own actions are published.
    """
    if task.plan_position is not None or session.plan is not None or not steps.remaining_steps:
        return
    words = [
        steps.first_step or _GENERIC_FIRST_STEP[language],
        *steps.remaining_steps,
    ]
    plan = ActivePlan(
        plan_id=f"plan-{uuid4().hex}",
        language=language,
        steps=[PlanStep(position=i, text=text) for i, text in enumerate(words, start=1)],
        skipped_steps=list(steps.skipped_steps),
        message=str(task.resolved_state.get("_original_message") or task.message),
    )
    session.plan = plan
    session.last_plan = plan
    runtime.append(
        session,
        "plan_created",
        {
            "plan_id": plan.plan_id,
            "language": language,
            "steps": [{"position": s.position, "text": s.text} for s in plan.steps],
            "skipped": list(plan.skipped_steps),
        },
    )
    runtime.record(
        session,
        "plan_created",
        plan_id=plan.plan_id,
        step_count=len(plan.steps),
        skipped_count=len(plan.skipped_steps),
        language=language,
        dialect=steps.dialect,
    )
    _mark_running(runtime, session, plan, 0, task)


def _mark_running(
    runtime: TaskRuntime, session: Session, plan: ActivePlan, index: int, task: ActiveTask
) -> None:
    step = plan.steps[index]
    step.status = "running"
    step.task_id = task.task_id
    plan.cursor = index
    task.plan_position = step.position
    runtime.append(
        session,
        "plan_step_started",
        {"plan_id": plan.plan_id, "position": step.position, "task_id": task.task_id},
    )


def _resume(runtime: TaskRuntime, session: Session, plan: ActivePlan, step: PlanStep) -> None:
    plan.paused = plan.paused_action_id = None
    runtime.append(session, "plan_resumed", {"plan_id": plan.plan_id, "position": step.position})


def _finish_step(
    runtime: TaskRuntime,
    session: Session,
    plan: ActivePlan,
    step: PlanStep,
    outcome: str,
    task: ActiveTask | None,
) -> None:
    if plan.paused is not None and step.status == "running":
        # The step moved on from the Shopper's question before it ended: resumed comes first.
        # A Stop or a skip just ends the wait with the plan.
        if outcome in {"done", "failed"}:
            _resume(runtime, session, plan, step)
        else:
            plan.paused = plan.paused_action_id = None
    step.status = outcome  # type: ignore[assignment]
    runtime.append(
        session,
        "plan_step_finished",
        {"plan_id": plan.plan_id, "position": step.position, "outcome": outcome},
    )
    runtime.record(
        session,
        "plan_step",
        plan_id=plan.plan_id,
        position=step.position,
        outcome=outcome,
        intent_type=task.intent_kind if task is not None else None,
        guarded=bool(task is not None and task.mutation_kind is not None),
    )


def _report(plan: ActivePlan, outcome: str) -> str:
    """The one message about a finished plan, built from the Shopper's own step words."""
    lang = plan.language
    if outcome == "cancelled":
        heading = _HEADINGS[lang][plan.cancel_reason or "stop"]
        skipped = _SKIPPED_SUFFIX["cancelled"][lang]
    else:
        heading = _HEADINGS[lang][outcome]
        skipped = _SKIPPED_SUFFIX["failed"][lang]
    lines = [heading]
    for step in plan.steps:
        if step.status == "done":
            lines.append(f"✓ {step.text}")
        elif step.status == "failed":
            reason = plan.reasons.get(step.position)
            lines.append(f"✕ {step.text} — {reason}" if reason else f"✕ {step.text}")
        elif step.status == "skipped" and plan.reasons.get(step.position):
            # Skipped by its own condition: the reason replaces the "(skipped)" suffix.
            lines.append(f"– {step.text} — {plan.reasons[step.position]}")
        else:
            lines.append(f"– {step.text}{skipped}")
    if plan.skipped_steps:
        if lang == "ar":
            lines.append(
                "مش هعمل دول دلوقتي لأن الحد ٣ طلبات في الرسالة: " + "، ".join(plan.skipped_steps)
            )
        else:
            lines.append(
                "Not done, because one message can hold at most 3 requests: "
                + ", ".join(plan.skipped_steps)
            )
    return "\n".join(lines)


def _finish_plan(runtime: TaskRuntime, session: Session, plan: ActivePlan, outcome: str) -> None:
    done = sum(s.status == "done" for s in plan.steps)
    failed = sum(s.status == "failed" for s in plan.steps)
    skipped = sum(s.status == "skipped" for s in plan.steps)
    report = _report(plan, outcome)
    runtime.append(
        session,
        "plan_finished",
        {"plan_id": plan.plan_id, "outcome": outcome, "report": report},
    )
    session.conversation.append({"role": "copilot", "text": report})
    runtime.record(
        session,
        "plan_finished",
        plan_id=plan.plan_id,
        outcome=outcome,
        done_count=done,
        failed_count=failed,
        skipped_count=skipped,
    )
    if outcome == "cancelled":
        runtime.record(
            session,
            "plan_cancelled",
            plan_id=plan.plan_id,
            reason=plan.cancel_reason or "stop",
        )
    plan.paused = plan.paused_action_id = None
    session.plan = None


def _stop_plan(
    runtime: TaskRuntime, session: Session, plan: ActivePlan, outcome: str, from_index: int
) -> None:
    """Every step from `from_index` on was not reached: skipped, and the plan is over."""
    for step in plan.steps[from_index:]:
        _finish_step(runtime, session, plan, step, "skipped", None)
    _finish_plan(runtime, session, plan, outcome)


def _fail_step(
    runtime: TaskRuntime,
    session: Session,
    plan: ActivePlan,
    step: PlanStep,
    task: ActiveTask | None,
    reason: str,
    *,
    cancel_task: bool,
) -> None:
    """The step failed: nothing later runs, its task is ended so the Session is free at once.

    Nothing is rolled back; the Shopper's earlier cart changes and their Undo stay.
    """
    if reason:
        plan.reasons[step.position] = reason
    _finish_step(runtime, session, plan, step, "failed", task)
    for later in plan.steps[plan.cursor + 1 :]:
        _finish_step(runtime, session, plan, later, "skipped", None)
    if cancel_task and task is not None and session.active_task is task:
        # The step's own end is already handled: the plan only listens while the step runs.
        runtime.end_task(session, task, "cancelled")
    _finish_plan(
        runtime, session, plan, "cancelled" if plan.cancel_reason == "takeover" else "failed"
    )


def family(intent_kind: str | None) -> str | None:
    return _FAMILIES.get(intent_kind or "")


def is_failure_question(action: object) -> bool:
    """A question that only offers to stop or try again: the step did not work."""
    return (
        isinstance(action, AskShopperAction)
        and action.kind != "confirmation"
        and bool(action.options)
        and all(option in _FAILURE_OPTIONS for option in action.options)
    )


def _running_step(session: Session, task: ActiveTask | None) -> tuple[ActivePlan, PlanStep] | None:
    plan = session.plan
    if plan is None or task is None or task.plan_position is None:
        return None
    step = plan.steps[plan.cursor]
    if step.status != "running" or step.task_id != task.task_id:
        return None
    return plan, step


def settle(runtime: TaskRuntime, session: Session) -> None:
    """Fail the current step on a failure question; show it paused on any other question."""
    task = session.active_task
    found = _running_step(session, task)
    if found is None or task is None:
        return
    plan, step = found
    asked = task.action if task.status == "awaiting_answer" else None
    action = asked if isinstance(asked, AskShopperAction) else None
    if plan.paused is not None and (action is None or action.action_id != plan.paused_action_id):
        _resume(runtime, session, plan, step)
    if action is None:
        return
    if is_failure_question(action):
        _fail_step(runtime, session, plan, step, task, action.narration, cancel_task=True)
    elif plan.paused is None:
        plan.paused = "confirmation" if action.kind == "confirmation" else "question"
        plan.paused_action_id = action.action_id
        runtime.append(
            session,
            "plan_paused",
            {"plan_id": plan.plan_id, "position": step.position, "reason": plan.paused},
        )


def fail_unusable_confirmation(runtime: TaskRuntime, session: Session, task: ActiveTask) -> bool:
    """A step's Confirmation expired, went stale or could not be registered.

    Returns False when the task is not a running plan step (the caller then refuses as it
    always did). Otherwise the Confirmation is dead, the step fails and the Shopper can ask again.
    """
    found = _running_step(session, task)
    if found is None:
        return False
    plan, step = found
    if task.confirmation is not None:
        task.confirmation.invalidate()
    task.confirmation = None
    task.mutation_proposal = None
    task.action = None
    _fail_step(
        runtime, session, plan, step, task, _REASON_CONFIRMATION[plan.language], cancel_task=True
    )
    return True


def reroute_new_request(
    runtime: TaskRuntime, session: Session, task: ActiveTask, intent: StructuredIntent
) -> bool:
    """An answer that is really a new request ends the plan and starts a fresh task.

    Only for a plan step's answer whose intent is of another family than the question's.
    Returns True when the answer was taken over (the caller stops interpreting it).
    """
    from agent.task_interpretation import begin_interpretation

    found = _running_step(session, task)
    if (
        found is None
        or task.answering_family is None
        or family(intent.intent) in {None, task.answering_family}
        or session.last_snapshot is None
    ):
        return False
    plan, _ = found
    text, snapshot = task.message, session.last_snapshot
    task.model_call_id = None
    plan.cancel_reason = "new_request"
    # The answer was already written to the conversation; the fresh task writes it again.
    if session.conversation and session.conversation[-1] == {"role": "shopper", "text": text}:
        session.conversation.pop()
    runtime.end_task(session, task, "cancelled")

    def started(fresh: ActiveTask) -> None:
        session.start_pending = fresh.task_id

    begin_interpretation(
        runtime,
        session.session_id,
        text,
        snapshot,
        tab_id=session.lease_tab_id,
        on_started=started,
    )
    return True


def cancel_after_current(runtime: TaskRuntime, session: Session, reason: str) -> None:
    """The plan ends cancelled once its current step ends; nothing after it ever starts."""
    plan = session.plan
    if plan is None:
        return
    plan.cancel_reason = reason
    if _running_step(session, session.active_task) is None:
        _stop_plan(runtime, session, plan, "cancelled", plan.cursor)


def on_task_end(runtime: TaskRuntime, end: TaskEnd) -> None:
    """The one place a plan moves: when the current step's task ends.

    It acts only while the cursor step is running, so the second end of the same task (the
    automatic cancel of a failed step) is ignored.
    """
    session, task = end.session, end.task
    found = _running_step(session, task)
    if found is None:
        return
    plan, step = found
    if end.kind == "cancelled":
        # A Stop (or a replaced request): this step was stopped, not failed.
        if plan.cancel_reason != "new_request":
            plan.cancel_reason = "stop"
        _stop_plan(runtime, session, plan, "cancelled", plan.cursor)
        return
    if end.kind == "paused":
        _fail_step(runtime, session, plan, step, task, task.pause_message or "", cancel_task=True)
        return
    if end.reason == RETRIEVAL_EXHAUSTED:
        _fail_step(
            runtime, session, plan, step, task, _REASON_EXHAUSTED[plan.language], cancel_task=False
        )
        return
    if end.reason == PRODUCT_DECLINED:
        # The Shopper did not confirm the product: the step was not done, nothing runs after.
        _fail_step(
            runtime, session, plan, step, task, DECLINED_REASON[plan.language], cancel_task=False
        )
        return
    if end.reason == CONDITION_FALSE:
        # The step's own condition was not met: skipped, not failed; the plan carries on.
        if task.skip_reason:
            plan.reasons[step.position] = task.skip_reason
        _finish_step(runtime, session, plan, step, "skipped", task)
    else:
        _finish_step(runtime, session, plan, step, "done", task)
    following = plan.cursor + 1
    if plan.cancel_reason == "takeover":
        _stop_plan(runtime, session, plan, "cancelled", following)
    elif following >= len(plan.steps):
        _finish_plan(runtime, session, plan, "done")
    else:
        _start_step(runtime, session, plan, following)


def _is_whole_message(turn: object, message: str) -> bool:
    """A Shopper turn holding the plan's whole message (history keeps a bounded prefix)."""
    if not isinstance(turn, dict) or turn.get("role") != "shopper":
        return False
    text = turn.get("text")
    return isinstance(text, str) and bool(text) and message.startswith(text)


def _start_step(runtime: TaskRuntime, session: Session, plan: ActivePlan, index: int) -> None:
    from agent.task_interpretation import begin_interpretation

    step = plan.steps[index]
    snapshot = session.last_snapshot
    try:
        if snapshot is None:
            raise ValueError("A current Storefront Snapshot is required")

        def started(task: ActiveTask) -> None:
            # The interpreter must know earlier parts of the Shopper's message are finished.
            task.resolved_state["_plan_step"] = {
                "position": step.position,
                "of": len(plan.steps),
                "earlier_steps_done": True,
            }
            # The step answers its own words: the whole message and the last step's
            # destination would pull a model back to a part that is already done.
            task.resolved_state.pop("_previous_target", None)
            conversation = task.resolved_state.get("_recent_conversation")
            if isinstance(conversation, list):
                task.resolved_state["_recent_conversation"] = [
                    turn for turn in conversation if not _is_whole_message(turn, plan.message)
                ]
            _mark_running(runtime, session, plan, index, task)
            session.start_pending = task.task_id

        begin_interpretation(
            runtime,
            session.session_id,
            step.text,
            snapshot,
            tab_id=session.lease_tab_id,
            on_started=started,
        )
    except Exception:
        # The next step could not even begin: it failed, and nothing after it runs.
        # Never raised into the request that ended the previous task: that task did end.
        if step.status == "pending":
            plan.cursor = index
            _fail_step(
                runtime,
                session,
                plan,
                step,
                None,
                _REASON_NOT_STARTED[plan.language],
                cancel_task=False,
            )


def view(session: Session) -> dict[str, object] | None:
    """The plan as the Session knows it, for a Panel that reloaded mid-plan or after one."""
    plan = session.plan or session.last_plan
    if plan is None:
        return None
    return {
        "plan_id": plan.plan_id,
        "language": plan.language,
        "active": session.plan is plan,
        "steps": [{"position": s.position, "text": s.text, "status": s.status} for s in plan.steps],
        "skipped": list(plan.skipped_steps),
        "paused": plan.paused if session.plan is plan else None,
    }
