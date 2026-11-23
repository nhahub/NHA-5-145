"""The stored form of a Session: what survives a restart, bounded, as a JSON document.

Kept: the owner binding and tab lease, the conversation (newest turns), the event stream and
its cursor (newest events), remembered sizes, the Copilot-selected size, "this" candidates and
product context, the plan and its last report, and a thin record of the active and last task.
Not kept: page Snapshots, accepted results, Confirmations and any other single-use authority.
"""

from typing import Any

from agent.product_context import ProductContext
from agent.session_state import (
    ActivePlan,
    ActiveTask,
    PlanStep,
    Session,
    SessionEvent,
)
from agent.shopper_access import ShopperBinding

FORMAT = 1
MAX_CONVERSATION_TURNS = 60
MAX_TURN_CHARACTERS = 4000
MAX_EVENTS = 200
# The stream is also cut by size so a few large events cannot crowd out the rest of the record.
MAX_EVENT_BYTES = 96 * 1024


def _event_size(event: SessionEvent) -> int:
    return len(repr(event.data)) + 64


def _bounded_events(events: list[SessionEvent]) -> list[SessionEvent]:
    kept: list[SessionEvent] = []
    total = 0
    for event in reversed(events[-MAX_EVENTS:]):
        total += _event_size(event)
        if total > MAX_EVENT_BYTES and kept:
            break
        kept.append(event)
    kept.reverse()
    return kept


def _plan_to_json(plan: ActivePlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "plan_id": plan.plan_id,
        "language": plan.language,
        "steps": [
            {"position": s.position, "text": s.text, "status": s.status, "task_id": s.task_id}
            for s in plan.steps
        ],
        "cursor": plan.cursor,
        "skipped_steps": list(plan.skipped_steps),
        "reasons": {str(position): text for position, text in plan.reasons.items()},
        "cancel_reason": plan.cancel_reason,
        "paused": plan.paused,
        "paused_action_id": plan.paused_action_id,
    }


def _plan_from_json(data: dict[str, Any] | None) -> ActivePlan | None:
    if data is None:
        return None
    return ActivePlan(
        plan_id=data["plan_id"],
        language=data["language"],
        steps=[
            PlanStep(
                position=s["position"], text=s["text"], status=s["status"], task_id=s["task_id"]
            )
            for s in data["steps"]
        ],
        cursor=data["cursor"],
        skipped_steps=list(data["skipped_steps"]),
        reasons={int(position): text for position, text in data["reasons"].items()},
        cancel_reason=data["cancel_reason"],
        paused=data["paused"],
        paused_action_id=data["paused_action_id"],
    )


def _task_to_json(task: ActiveTask | None) -> dict[str, Any] | None:
    """A thin record: enough to end an interrupted task and show the last one, nothing to rerun."""
    if task is None:
        return None
    return {
        "task_id": task.task_id,
        "language": task.language,
        "message": task.message,
        "status": task.status,
        "target_url": task.target_url,
        "origin_url": task.origin_url,
        "step_count": task.step_count,
        "intent_kind": task.intent_kind,
        "target_name": task.target_name,
        "pause_message": task.pause_message,
        "plan_position": task.plan_position,
        "mutation_kind": task.mutation_kind,
        "suggestions": task.suggestions,
    }


def _task_from_json(data: dict[str, Any] | None) -> ActiveTask | None:
    if data is None:
        return None
    return ActiveTask(
        task_id=data["task_id"],
        action=None,
        language=data["language"],
        message=data["message"],
        target_url=data["target_url"],
        step_count=data["step_count"],
        status=data["status"],
        intent_kind=data["intent_kind"],
        target_name=data["target_name"],
        pause_message=data["pause_message"],
        origin_url=data["origin_url"],
        plan_position=data["plan_position"],
        mutation_kind=data["mutation_kind"],
        suggestions=data["suggestions"],
    )


def session_to_json(session: Session) -> dict[str, Any]:
    conversation = [
        {"role": turn["role"], "text": turn["text"][:MAX_TURN_CHARACTERS]}
        for turn in session.conversation[-MAX_CONVERSATION_TURNS:]
    ]
    context = session.product_context
    return {
        "format": FORMAT,
        "session_id": session.session_id,
        "shopper": (
            {"shopper_id": session.shopper.shopper_id, "generation": session.shopper.generation}
            if session.shopper is not None
            else None
        ),
        "invitation_id": session.invitation_id,
        "lease_tab_id": session.lease_tab_id,
        "conversation": conversation,
        "conversation_dropped": len(session.conversation) - len(conversation),
        "events": [
            {"id": e.id, "event": e.event, "data": e.data} for e in _bounded_events(session.events)
        ],
        "last_event_id": session.last_event_id,
        "active_task": _task_to_json(session.active_task),
        "last_task": _task_to_json(session.last_task),
        "plan": _plan_to_json(session.plan),
        # The running plan is also the last one: stored once, restored as one object.
        "last_plan": (
            None
            if session.last_plan is None or session.last_plan is session.plan
            else _plan_to_json(session.last_plan)
        ),
        "last_plan_is_plan": session.plan is not None and session.last_plan is session.plan,
        "remembered_sizes": [
            [person, kind, size] for (person, kind), size in session.remembered_sizes.items()
        ],
        "copilot_selected_size": {
            key: [person, size] for key, (person, size) in session.copilot_selected_size.items()
        },
        "product_kinds": dict(session.product_kinds),
        "last_touched": [dict(item) for item in session.last_touched],
        "product_context": {
            "origin": list(context.origin) if context.origin is not None else None,
            "products": context.products,
            "suggestions": context.suggestions,
            "conversation_start": context.conversation_start,
        },
        "requires_reconciliation": session.requires_reconciliation,
    }


def session_from_json(data: dict[str, Any], *, now: float) -> Session:
    """The Session as it was saved; `now` is this process's clock for its activity time."""
    shopper = data["shopper"]
    dropped = data["conversation_dropped"]
    context = data["product_context"]
    plan = _plan_from_json(data["plan"])
    session = Session(
        session_id=data["session_id"],
        shopper=ShopperBinding(shopper["shopper_id"], shopper["generation"]) if shopper else None,
        invitation_id=data["invitation_id"],
        lease_tab_id=data["lease_tab_id"],
        events=[SessionEvent(e["id"], e["event"], e["data"]) for e in data["events"]],
        last_event_id=data["last_event_id"],
        restored=True,
        active_task=_task_from_json(data["active_task"]),
        last_task=_task_from_json(data["last_task"]),
        conversation=[dict(turn) for turn in data["conversation"]],
        last_activity_at=now,
        requires_reconciliation=data["requires_reconciliation"],
        plan=plan,
        last_plan=plan if data["last_plan_is_plan"] else _plan_from_json(data["last_plan"]),
        remembered_sizes={(person, kind): size for person, kind, size in data["remembered_sizes"]},
        copilot_selected_size={
            key: (person, size) for key, (person, size) in data["copilot_selected_size"].items()
        },
        product_kinds=dict(data["product_kinds"]),
        last_touched=[dict(item) for item in data["last_touched"]],
        product_context=ProductContext(
            origin=tuple(context["origin"]) if context["origin"] is not None else None,
            products={key: dict(value) for key, value in context["products"].items()},
            suggestions=[dict(item) for item in context["suggestions"]],
            # Turns dropped from the front of the stored conversation shift every index.
            conversation_start=max(0, context["conversation_start"] - dropped),
        ),
    )
    return session
