"""Model interpretation lifecycle and bounded conversation context."""

from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from agent.cart import (
    UNDO_EXPIRED,
    bind_product_add,
    plan_cart_edit,
    undo_expired,
    validate_cart_intent,
)
from agent.catalogue import DiscoveryResult
from agent.conditions import CONDITION_FALSE
from agent.conditions import QUESTION as CONDITION_QUESTION
from agent.confirmation import (
    validate_mutation_interpretation,
)
from agent.llm.intent import StructuredIntent
from agent.planner import (
    ActionIdentity,
    detect_language,
)
from agent.plans import PlanSteps, family, open_plan, reroute_new_request
from agent.product_confirmation import (
    CONFIRMED_KEY,
    DECLINED,
    OPTIONS,
    PENDING_KEY,
    PRODUCT_DECLINED,
    QUESTION,
    unnamed_product,
)
from agent.product_context import require_known_product
from agent.remembered_sizes import (
    NAMED_PERSON,
    not_saved_note,
    note_verified,
    recall,
    record_selection,
    remember,
    remember_add,
    shared_kind,
    size_said,
    stale_selection,
    used_note,
    with_note,
)
from agent.schemas import (
    AskShopperAction,
    NavigateAction,
    Snapshot,
    to_wire,
)
from agent.session_state import (
    ActionResultMismatch,
    ActiveTask,
    InterpretationPauseReason,
    TaskConflict,
)
from agent.swap import COULD_NOT_CHECK, COULD_NOT_IDENTIFY, SwapDecision, read_line
from agent.swap import scratch as swap_scratch
from agent.task_runtime import TaskRuntime
from agent.touched_products import note_touched, this_candidates

_CONTEXT_TEXT_LIMIT = 2000
_CONTEXT_ANSWER_LIMIT = 8


def _bounded_answers(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item[:_CONTEXT_TEXT_LIMIT] for item in value if isinstance(item, str)][
        -_CONTEXT_ANSWER_LIMIT:
    ]


def _shopper_texts(task: "ActiveTask") -> list[object]:
    """The Shopper's own words for this task: the message, the original one and the answers."""
    return [
        task.message,
        task.resolved_state.get("_original_message"),
        *_bounded_answers(task.resolved_state.get("_answers")),
    ]


def _intent_context(task: "ActiveTask", intent: StructuredIntent) -> dict[str, Any]:
    constraints = intent.constraints.model_dump(mode="json", exclude_none=True)
    original = task.resolved_state.get("_original_message", task.message)
    return {
        **constraints,
        "_intent": intent.model_dump(mode="json"),
        "_original_message": original[:_CONTEXT_TEXT_LIMIT]
        if isinstance(original, str)
        else task.message[:_CONTEXT_TEXT_LIMIT],
        "_answers": _bounded_answers(task.resolved_state.get("_answers")),
        **(
            {"_previous_suggestions": task.resolved_state["_previous_suggestions"]}
            if "_previous_suggestions" in task.resolved_state
            else {}
        ),
        **{
            key: task.resolved_state[key]
            for key in (
                "_known_products",
                "_recent_conversation",
                "_plan_step",
                "_this_candidates",
            )
            if key in task.resolved_state
        },
    }


def begin_interpretation(
    runtime: TaskRuntime,
    session_id: str,
    text: str,
    snapshot: Snapshot,
    *,
    replace_active: bool = False,
    tab_id: str | None = None,
    on_started: Callable[[ActiveTask], None] | None = None,
) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    if session.active_task is not None:
        if not replace_active:
            raise TaskConflict("A Shopping Task is already active")
        runtime.end_task(session, session.active_task, "cancelled")
    previous_target = session.last_followup_target
    followup_target = None
    session.last_followup_target = None
    resolved_state: dict[str, Any] = {
        "_original_message": text[:_CONTEXT_TEXT_LIMIT],
        "_answers": [],
    }
    location = urlsplit(snapshot.url)
    if session.product_context.origin != (location.scheme, location.netloc):
        session.advice_context.clear()
        session.last_touched.clear()
    if previous_target is not None:
        resolved_state["_previous_target"] = previous_target
    resolved_state.update(
        session.product_context.prepare(snapshot, runtime.planner.storefront, session.conversation)
    )
    resolved_state["_this_candidates"] = this_candidates(
        session, snapshot, runtime.planner.storefront
    )
    if session.advice_context:
        resolved_state["_advice_context"] = session.advice_context.copy()
    if followup_target is not None:
        resolved_state["target"] = followup_target
    task = ActiveTask(
        task_id=f"task-{uuid4().hex}",
        action=None,
        language=detect_language(text),
        message=text,
        step_count=0,
        status="interpreting",
        origin_url=snapshot.url,
        model_call_id=f"call-{uuid4().hex}",
        resolved_state=resolved_state,
        pending_clarification="target" if followup_target else None,
    )
    session.active_task = task
    session.last_task = task
    runtime.record_snapshot(session, snapshot)
    session.conversation.append({"role": "shopper", "text": text})
    runtime.append(session, "task_started", {"task_id": task.task_id})
    if on_started is not None:
        on_started(task)
    runtime.record_debug(session, "shopper_message", text, task.task_id)
    runtime.append(
        session,
        "narration",
        {
            "task_id": task.task_id,
            "text": "بفهم طلبك الآن…" if task.language == "ar" else "Understanding your request…",
        },
    )
    runtime.sessions.touch(session)
    return task


def finish_interpretation(
    runtime: TaskRuntime,
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
    session = runtime.sessions.get(session_id)
    task = session.active_task
    if task is None or task.task_id != task_id or task.model_call_id != call_id:
        return None
    if task.status != "interpreting" or session.requires_reconciliation:
        return None
    steps = plan_steps if plan_steps is not None else PlanSteps.from_intent(intent)
    if session.last_snapshot is not None:
        runtime.require_task_origin(task, session.last_snapshot)
    if reroute_new_request(runtime, session, task, intent):
        return None
    runtime.record(
        session,
        "intent",
        task_id=task_id,
        intent=intent.intent,
        language=intent.language,
        dialect=intent.dialect,
        needs_clarification=intent.needs_clarification,
    )
    if (
        task.resolved_state
        and "_intent" not in task.resolved_state
        and intent.intent == "find_products"
    ):
        supplied = intent.constraints.model_dump(mode="json", exclude_none=True)
        unresolved = set(intent.missing_fields) | set(intent.conflicting_fields)
        preserved = {
            key: value
            for key, value in task.resolved_state.items()
            if key in type(intent.constraints).model_fields and key not in unresolved
        }
        intent = StructuredIntent.model_validate(
            {
                **intent.model_dump(mode="json"),
                "constraints": {**preserved, **supplied},
            }
        )
    if intent.intent in {"off_topic", "unsupported", "help"}:
        if intent.intent == "unsupported":
            # Read as unsupported even after one repair: say so, not the generic shopping line.
            summary = (
                "ما قدرتش أفهم الطلب ده كعملية في المتجر. تقدر تقولها بطريقة تانية؟"
                if intent.language == "ar"
                else "I couldn't match that to something I can do in the shop. "
                "Could you say it another way?"
            )
        else:
            summary = (
                "أقدر أساعدك في التسوق داخل المتجر."
                if intent.language == "ar"
                else ("I can help with shopping in this Storefront.")
            )
        runtime.append(
            session,
            "done",
            {
                "task_id": task_id,
                "summary": summary,
                "language": intent.language,
            },
        )
        task.model_call_id = None
        session.conversation.append({"role": "copilot", "text": summary})
        runtime.end_task(session, task, "completed")
        runtime.sessions.touch(session)
        return task
    if intent.product_id is not None and not intent.needs_clarification:
        require_known_product(
            intent.product_id,
            task.resolved_state,
            session.last_snapshot,
            runtime.planner.storefront,
        )
    # The model chose this product by id: code asks unless the Shopper's words back the choice.
    unnamed = (
        None
        if intent.needs_clarification
        else unnamed_product(
            intent,
            task.resolved_state,
            _shopper_texts(task),
            session.last_snapshot,
            runtime.planner.storefront,
        )
    )
    # A condition code can check applies to an add of a known product, nothing else. It was
    # evaluated by the caller from the verified catalogue record at this step's own turn.
    conditional = intent.condition is not None and not intent.needs_clarification
    asks_condition = conditional and not (
        intent.intent == "cart_edit" and intent.cart_operation == "add" and intent.product_id
    )
    if intent.intent == "cart_edit" and not asks_condition:
        intent = validate_cart_intent(task.message, intent, session.last_snapshot)
        if undo_expired(intent, session.last_snapshot):
            summary = UNDO_EXPIRED[0] if intent.language == "ar" else UNDO_EXPIRED[1]
            open_plan(runtime, session, task, steps, intent.language)
            runtime.append(
                session,
                "done",
                {"task_id": task_id, "summary": summary, "language": intent.language},
            )
            task.model_call_id = None
            session.conversation.append({"role": "copilot", "text": summary})
            runtime.end_task(session, task, "completed")
            runtime.sessions.touch(session)
            return task
    # A colour change of a cart line, read from the cart Snapshot by code. Anywhere else the
    # cart opens first (below) and the line is chosen on the fresh cart Snapshot.
    swapping = (
        intent.intent == "cart_edit"
        and intent.cart_operation == "replace"
        and not intent.needs_clarification
        and not asks_condition
        and session.last_snapshot is not None
        and urlsplit(session.last_snapshot.url).path == "/cart"
    )
    swap_line = (
        read_line(
            session.last_snapshot,
            intent.cart_target_id,
            intent.constraints.size,
            runtime.planner.storefront.product_route,
        )
        if swapping
        else None
    )
    swap_decision = swap_check if swap_line is not None else None
    verdict = condition_result if conditional and not asks_condition else None
    if conditional and verdict is False and condition_reason:
        # Not met: nothing is clicked; the step is skipped with its reason, the plan goes on.
        task.language = intent.language
        task.intent_kind = intent.intent
        task.skip_reason = condition_reason
        open_plan(runtime, session, task, steps, intent.language)
        runtime.append(
            session,
            "done",
            {"task_id": task_id, "summary": condition_reason, "language": intent.language},
        )
        task.model_call_id = None
        session.conversation.append({"role": "copilot", "text": condition_reason})
        runtime.end_task(session, task, "completed", CONDITION_FALSE)
        runtime.sessions.touch(session)
        return task
    asked: dict = {}
    if unnamed is not None:
        question = QUESTION[intent.language].format(name=unnamed)
        action = AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task_id,
            action_id=f"question-{uuid4().hex}",
            sequence_number=task.step_count + 1,
            narration=question,
            question=question,
            options=list(OPTIONS[intent.language]),
        )
    elif conditional and verdict is not True:
        # The fact cannot be read (or the condition is not on an add): ask, never judge.
        question = CONDITION_QUESTION[intent.language]
        task.cart_operation = intent.cart_operation
        action = AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task_id,
            action_id=f"question-{uuid4().hex}",
            sequence_number=task.step_count + 1,
            narration=question,
            question=question,
            options=[],
        )
    elif swapping:
        if swap_line is not None and swap_decision is not None and swap_decision.kind == "go":
            # Add the new colour first; the old line goes only after that add is verified.
            task.swap = swap_scratch(swap_line, intent.constraints.color or "")
            task.cart_operation = "add"
            intent = StructuredIntent.model_validate(
                {
                    "v": 10,
                    "language": intent.language,
                    "dialect": intent.dialect,
                    "intent": "cart_edit",
                    "cart_operation": "add",
                    "cart_source": intent.cart_source,
                    "product_id": swap_line.product_id,
                    "constraints": {"size": swap_line.size, "color": intent.constraints.color},
                    "cart_quantity": swap_line.quantity,
                    "cart_quantity_mode": "set",
                    "missing_fields": [],
                    "conflicting_fields": [],
                    "needs_clarification": False,
                }
            )
            action = NavigateAction(
                v=1,
                type="navigate",
                task_id=task_id,
                action_id=f"action-{uuid4().hex}",
                sequence_number=task.step_count + 1,
                narration="هفتح المنتج وأضيف اللون الجديد، وبعدها أشيل القديم."
                if intent.language == "ar"
                else "I'll open the product, add the new colour, then remove the old one.",
                url=runtime.planner.storefront.product_route.replace(
                    "{product_id}", swap_line.product_id
                ),
            )
        else:
            # Nothing is changed: say which item, or what the check found, and wait.
            task.cart_operation = intent.cart_operation
            if swap_decision is not None:
                text = swap_decision.text
            elif swap_line is None:
                text = COULD_NOT_IDENTIFY[0 if intent.language == "ar" else 1]
            else:
                text = COULD_NOT_CHECK[intent.language]
            action = AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=task_id,
                action_id=f"question-{uuid4().hex}",
                sequence_number=task.step_count + 1,
                narration=text,
                question=text,
                options=[],
            )
    elif intent.intent == "cart_edit" and not intent.needs_clarification:
        task.cart_operation = intent.cart_operation
        if (
            intent.cart_operation == "add"
            and intent.constraints.size
            and not size_said(intent.constraints.size, _shopper_texts(task))
        ):
            # The model copied this size from the page or an earlier turn; the Shopper never
            # said it. Drop it (not the intent) so the remembered size or the question applies.
            intent = intent.model_copy(
                update={"constraints": intent.constraints.model_copy(update={"size": None})}
            )
        task.size_note = remember_add(session, intent) if intent.cart_operation == "add" else None
        product_url = (
            runtime.planner.storefront.product_route.replace("{product_id}", intent.product_id)
            if intent.cart_operation == "add" and intent.product_id
            else None
        )
        if product_url and urlsplit(session.last_snapshot.url).path != product_url:
            # DOM IDs belong to the old page; bind only after verified navigation.
            intent = intent.model_copy(update={"cart_target_id": None})
            task.cart_actions = [
                NavigateAction(
                    v=1,
                    type="navigate",
                    task_id=task_id,
                    action_id=f"action-{uuid4().hex}",
                    sequence_number=task.step_count + 1,
                    narration="هفتح المنتج وأختار المواصفات المطلوبة عشان أضيفه للسلة."
                    if intent.language == "ar"
                    else "I'll open that product and add the requested variant.",
                    url=product_url,
                )
            ]
        elif (
            intent.cart_operation in {"quantity", "remove", "replace"}
            and session.last_snapshot is not None
            and urlsplit(session.last_snapshot.url).path != "/cart"
        ):
            task.cart_actions = [
                NavigateAction(
                    v=1,
                    type="navigate",
                    task_id=task_id,
                    action_id=f"action-{uuid4().hex}",
                    sequence_number=task.step_count + 1,
                    narration="هفتح السلة عشان أعدّل المنتج المطلوب."
                    if intent.language == "ar"
                    else "I'll open the cart to find the requested item.",
                    url="/cart",
                )
            ]
        else:
            intent = bind_product_add(
                intent, session.last_snapshot, runtime.planner.storefront.product_route
            )
            used: dict = {}
            chosen: dict = {}
            task.cart_actions = plan_cart_edit(
                intent,
                session.last_snapshot,
                task_id,
                task.step_count + 1,
                asked=asked,
                remembered=recall(session, intent) if intent.cart_operation == "add" else None,
                used=used,
                stale_size=stale_selection(session, intent),
                selected=chosen,
                storefront=runtime.planner.storefront,
            )
            record_selection(session, intent, chosen.get("size"))
            if "size" in used:
                task.size_note = used_note(intent.language, used["size"])
        action = task.cart_actions.pop(0)
    elif intent.intent == "mutate":
        validate_mutation_interpretation(task.message, intent)
        task.mutation_kind = intent.mutation_kind
        destination = "/cart" if intent.mutation_kind == "clear_cart" else "/checkout"
        if session.last_snapshot is None:
            raise ValueError("A current Storefront Snapshot is required")
        if urlsplit(session.last_snapshot.url).path == destination:
            action = runtime.offer_mutation(task, session.last_snapshot, task.step_count + 1)
        else:
            action = NavigateAction(
                v=1,
                type="navigate",
                task_id=task_id,
                action_id=f"action-{uuid4().hex}",
                sequence_number=task.step_count + 1,
                narration=(
                    "هفتح الصفحة عشان أراجع الإجراء قبل تأكيدك."
                    if intent.language == "ar"
                    else "I'll open the page before asking you to confirm."
                ),
                url=destination,
            )
    else:
        action = runtime.planner.plan_intent(
            intent,
            session.last_snapshot,
            ActionIdentity(
                task_id=task_id,
                action_id=f"action-{uuid4().hex}",
                sequence_number=task.step_count + 1,
            ),
        )
    task.action = action
    task.model_call_id = None
    task.language = intent.language
    task.intent_kind = intent.intent
    task.target_name = intent.constraints.target
    task.step_count += 1
    task.target_url = action.url if isinstance(action, NavigateAction) else None
    task.status = (
        "awaiting_answer" if isinstance(action, AskShopperAction) else "awaiting_action_result"
    )
    task.resolved_state = _intent_context(task, intent)
    task.pending_clarification = (
        (intent.missing_fields or intent.conflicting_fields)[0]
        if intent.needs_clarification and (intent.missing_fields or intent.conflicting_fields)
        else None
    )
    task.pending_variant = None
    if task.cart_operation and isinstance(action, AskShopperAction) and not action.options:
        # The next model call needs the runtime question as well as the draft intent.
        task.pending_clarification = action.question
        task.pending_variant = asked or None
    if (
        intent.refers_to_this
        and task.pending_clarification == "product_id"
        and isinstance(action, AskShopperAction)
        and intent.intent in {"open_product", "cart_edit"}
    ):
        # "Which product?": the choices are the candidates code allowed, never more.
        candidates = [
            item["name"]
            for item in task.resolved_state.get("_this_candidates", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        action.options = candidates if 2 <= len(candidates) <= 3 else []
    elif (
        intent.intent == "open_product"
        and task.pending_clarification == "product_id"
        and isinstance(action, AskShopperAction)
    ):
        action.options = [
            item["name"]
            for item in task.resolved_state.get("_previous_suggestions", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ][:3]
    if unnamed is not None and isinstance(action, AskShopperAction):
        # The draft stays in `_intent`; a yes continues with exactly this product.
        task.pending_clarification = action.question
        task.resolved_state[PENDING_KEY] = {"id": intent.product_id}
    # Later steps exist only as the Shopper's words; the plan is announced before any action.
    open_plan(runtime, session, task, steps, intent.language)
    runtime.append(session, "narration", {"task_id": task_id, "text": action.narration})
    runtime.append(session, "action", {"task_id": task_id, "action": to_wire(action)})
    session.conversation.append({"role": "copilot", "text": action.narration})
    runtime.sessions.touch(session)
    return task


def _remember_search_size(
    session,
    intent: StructuredIntent,
    result: DiscoveryResult,
    *,
    facts: Mapping[str, tuple[str, str]] | None,
    beneficiary: str | None,
    size_hint: str | None,
    exhausted: bool,
    texts: list[object],
) -> str | None:
    """Store a size said with a search/advice turn under the kind ALL shown products share.

    A named person's size is used for this request only; the returned note says so.
    """
    note_verified(session, facts)
    size = intent.constraints.size or size_hint
    if not size or exhausted or not size_said(size, texts):
        return None
    who = beneficiary or intent.beneficiary
    if who == NAMED_PERSON:
        return not_saved_note(intent.language)
    remember(session, who, shared_kind(session, [item.id for item in result.suggestions]), size)
    return None


def _ask_clarification(
    runtime: TaskRuntime,
    session,
    task: ActiveTask,
    intent: StructuredIntent,
    steps: PlanSteps,
    question: str,
    options: list[str] | None = None,
) -> ActiveTask:
    """Publish the catalogue's clarifying question as a free-text question the task waits on."""
    task.language = intent.language
    task.model_call_id = None
    open_plan(runtime, session, task, steps, intent.language)
    asking = AskShopperAction(
        v=1,
        type="ask_shopper",
        task_id=task.task_id,
        action_id=f"question-{uuid4().hex}",
        sequence_number=task.step_count + 1,
        narration=question,
        question=question,
        options=list(options or []),
    )
    task.action = asking
    task.step_count += 1
    task.status = "awaiting_answer"
    task.intent_kind = "find_products"
    task.pending_clarification = question
    task.pending_variant = None
    runtime.append(session, "narration", {"task_id": task.task_id, "text": question})
    runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(asking)})
    session.conversation.append({"role": "copilot", "text": question})
    runtime.sessions.touch(session)
    return task


def finish_catalogue_interpretation(
    runtime: TaskRuntime,
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
    session = runtime.sessions.get(session_id)
    task = session.active_task
    if (
        task is None
        or task.task_id != task_id
        or task.model_call_id != call_id
        or task.status != "interpreting"
        or session.requires_reconciliation
    ):
        return None
    if intent.needs_clarification and intent.intent != "advice":
        raise ValueError("Incomplete intent cannot publish catalogue suggestions")
    if session.last_snapshot is not None:
        runtime.require_task_origin(task, session.last_snapshot)
    if reroute_new_request(runtime, session, task, intent):
        return None
    steps = plan_steps if plan_steps is not None else PlanSteps.from_intent(intent)
    if (
        clarify
        and advice_text is not None
        and (task.plan_position is not None or (session.plan is None and steps.remaining_steps))
    ):
        # A plan never takes a question for an answer: the step waits for the Shopper.
        return _ask_clarification(runtime, session, task, intent, steps, advice_text, options)
    payload = result.to_wire()
    session.product_context.remember_suggestions(payload["suggestions"])
    task.suggestions = payload
    task.resolved_state = _intent_context(task, intent)
    if advice_text is not None:
        session.advice_context = intent.model_dump(
            mode="json",
            include={
                "constraints",
                "catalogue_requirements",
                "price_preference",
                "owned_item",
                "owned_items",
                "desired_wear_position",
                "preferred_colors",
                "subjective_preferences",
                "request_mode",
            },
        )
    task.language = intent.language
    task.intent_kind = intent.intent
    task.model_call_id = None
    if any(item.label == "styling_suggestion" for item in result.suggestions):
        summary = (
            "دي اقتراحات تنسيق من منتجات المتجر المتاحة."
            if intent.language == "ar"
            else "These are styling suggestions from available Storefront products."
        )
    elif result.exact_count is None:
        summary = (
            "دي منتجات من نتائج البحث؛ راجع التفاصيل اللي لسه مش مؤكدة."
            if intent.language == "ar"
            else "These are retrieved products; review any unverified requirements."
        )
    elif result.exact_count:
        summary = (
            f"وجدت {result.exact_count} منتج مطابق ومتحقق منه."
            if intent.language == "ar"
            else f"Found {result.exact_count} verified exact matches."
        )
    elif result.suggestions:
        if intent.price_preference is not None:
            summary = (
                "لا يوجد منتج يحقق كل الشروط. رتبت البدائل من الأقل سعراً مع توضيح ما ينقصها."
                if intent.language == "ar"
                else (
                    "No product meets every requirement. Alternatives are sorted by price "
                    "with gaps shown."
                )
            )
        else:
            summary = (
                "لا توجد منتجات تطابق كل الشروط. هذه بدائل موضّح ما ينقصها."
                if intent.language == "ar"
                else "No product meets every requirement. These are labelled alternatives."
            )
    else:
        summary = (
            "لا أقدر أؤكد وجود منتج مناسب من بيانات المتجر الحالية."
            if intent.language == "ar"
            else "I cannot verify a suitable product in the current catalogue."
        )
    if advice_text is not None:
        summary = advice_text
    summary = with_note(
        summary,
        _remember_search_size(
            session,
            intent,
            result,
            facts=facts,
            beneficiary=beneficiary,
            size_hint=size_hint,
            exhausted=end_reason is not None,
            texts=_shopper_texts(task),
        ),
    )
    if end_reason is None and payload["suggestions"]:
        note_touched(session, payload["suggestions"])
    open_plan(runtime, session, task, steps, intent.language)
    runtime.append(session, "suggestions", {"task_id": task_id, **payload})
    runtime.append(
        session,
        "done",
        {"task_id": task_id, "summary": summary, "language": intent.language},
    )
    session.conversation.append({"role": "copilot", "text": summary})
    runtime.end_task(session, task, "completed", end_reason)
    runtime.sessions.touch(session)
    return task


def begin_answer_interpretation(
    runtime: TaskRuntime,
    session_id: str,
    task_id: str,
    question_id: str,
    text: str,
    snapshot: Snapshot,
    tab_id: str | None,
) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    task = session.active_task
    if (
        task is None
        or task.task_id != task_id
        or not isinstance(task.action, AskShopperAction)
        or task.action.action_id != question_id
        or task.status != "awaiting_answer"
    ):
        raise ActionResultMismatch("Answer does not match the pending Shopper question")
    if task.step_count >= 8:
        raise TaskConflict("Shopping Task step limit reached")
    runtime.require_task_origin(task, snapshot)
    selected = None
    if task.intent_kind == "open_product" and task.pending_clarification == "product_id":
        candidates = {
            item["id"]: item
            for item in (
                *task.resolved_state.get("_previous_suggestions", []),
                *task.resolved_state.get("_this_candidates", []),
            )
            if isinstance(item, dict) and item.get("name") == text
        }
        if len(candidates) == 1 and text in task.action.options:
            selected = next(iter(candidates.values()))
    pending = task.resolved_state.get(PENDING_KEY)
    reply = text.strip().casefold()
    options = [o.casefold() for o in task.action.options]
    confirmed = (
        isinstance(pending, dict)
        and len(options) == 2
        and reply == options[0]
        and isinstance(task.resolved_state.get("_intent"), dict)
    )
    declined = isinstance(pending, dict) and len(options) == 2 and reply == options[1]
    variant, task.pending_variant = task.pending_variant, None
    chosen = None
    if selected is None and variant is not None:
        # Only an exact reply naming one value the page offered for the asked option.
        matches = [o for o in variant["options"] if o.casefold() == text.strip().casefold()]
        chosen = matches[0] if len(matches) == 1 else None
    task.message = text
    task.answering_family = family(task.intent_kind)
    runtime.record_debug(session, "shopper_message", text, task.task_id)
    task.retrieval_budget = None
    answers = _bounded_answers(task.resolved_state.get("_answers"))
    task.resolved_state["_answers"] = [*answers, text[:_CONTEXT_TEXT_LIMIT]][
        -_CONTEXT_ANSWER_LIMIT:
    ]
    if confirmed or declined:
        task.resolved_state.pop(PENDING_KEY, None)
    task.action = None
    task.status = "interpreting"
    task.model_call_id = f"call-{uuid4().hex}"
    runtime.record_snapshot(session, snapshot)
    # The task's history was captured before its own request and question existed.
    task.resolved_state["_recent_conversation"] = session.product_context.prepare(
        snapshot, runtime.planner.storefront, session.conversation
    )["_recent_conversation"]
    task.resolved_state["_this_candidates"] = this_candidates(
        session, snapshot, runtime.planner.storefront
    )
    session.conversation.append({"role": "shopper", "text": text})
    runtime.append(
        session,
        "narration",
        {
            "task_id": task_id,
            "text": "بفهم إجابتك…" if task.language == "ar" else "Understanding your answer…",
        },
    )
    runtime.sessions.touch(session)
    if declined:
        summary = DECLINED[task.language]
        runtime.append(
            session,
            "done",
            {"task_id": task_id, "summary": summary, "language": task.language},
        )
        task.model_call_id = None
        session.conversation.append({"role": "copilot", "text": summary})
        runtime.end_task(session, task, "completed", PRODUCT_DECLINED)
        runtime.sessions.touch(session)
    elif confirmed:
        pending_id = pending["id"]
        task.resolved_state[CONFIRMED_KEY] = pending_id
        intent = StructuredIntent.model_validate(task.resolved_state["_intent"])
        if intent.product_id != pending_id:
            raise ActionResultMismatch("The confirmed product no longer matches the request")
        finish_interpretation(runtime, session_id, task_id, task.model_call_id, intent)
    elif selected is not None:
        task.resolved_state[CONFIRMED_KEY] = selected["id"]
        # The answer is bound to this question's verified choices. No model
        # is needed to reinterpret an exact product button selection.
        intent = StructuredIntent.model_validate(
            {
                "v": 7,
                "language": task.language,
                "dialect": "unknown",
                "intent": "open_product",
                "constraints": {},
                "product_id": selected["id"],
                "navigation_source": text,
                "missing_fields": [],
                "needs_clarification": False,
            }
        )
        finish_interpretation(runtime, session_id, task_id, task.model_call_id, intent)
    elif chosen is not None:
        # Continue the same product and cart operation with the chosen option; the add
        # button is rebound from the current page and every option is revalidated.
        draft = task.resolved_state["_intent"]
        intent = StructuredIntent.model_validate(
            {
                **draft,
                "constraints": {**draft["constraints"], variant["field"]: chosen},
                "cart_target_id": None,
            }
        )
        # If the page no longer supports the bound edit, the model interprets the answer.
        with suppress(ValueError):
            finish_interpretation(runtime, session_id, task_id, task.model_call_id, intent)
    return task


def fail_interpretation(
    runtime: TaskRuntime,
    session_id: str,
    task_id: str,
    call_id: str,
    reason: InterpretationPauseReason,
    *,
    retry_after_seconds: int | None = None,
) -> None:
    session = runtime.sessions.get(session_id)
    task = session.active_task
    if task is None or task.task_id != task_id or task.model_call_id != call_id:
        return
    if task.status != "interpreting":
        return
    task.model_call_id = None
    messages = {
        "inference_busy": (
            "المساعد مشغول الآن. لم يُرسل طلبك للنموذج؛ جرّب بعد قليل.",
            "The assistant is busy. Your request was not sent to the model; retry shortly.",
        ),
        "inference_disabled": (
            "طلبات المساعد متوقفة مؤقتًا. لم يتم تنفيذ أي إجراء تسوّق.",
            "Inference is temporarily disabled. No shopping action was taken.",
        ),
        "inference_unavailable": (
            "تعذر التحقق من ميزانية المساعد بأمان، فتوقفت المهمة قبل أي إجراء.",
            "The inference allowance could not be verified safely; no action was taken.",
        ),
        "budget": (
            "توقفنا قبل إرسال الطلب للحفاظ على ميزانية التجربة. راجع حد الإنفاق المتاح.",
            "Stopped before sending the request to protect the trial budget. "
            "Check the available spending allowance.",
        ),
        "throttled": (
            "وصلنا لحد الطلبات المؤقت لخدمة النموذج. جرّب تاني بعد شوية أو أوقف المهمة.",
            "The model service reached a temporary request limit. Retry later or stop the task.",
        ),
        "timeout": (
            "انتهت مهلة انتظار خدمة النموذج. جرّب تاني أو أوقف المهمة.",
            "The model service timed out. Retry or stop the task.",
        ),
        "network": (
            "تعذر الاتصال بخدمة النموذج. جرّب تاني أو أوقف المهمة.",
            "The model service could not be reached. Retry or stop the task.",
        ),
        "provider_http": (
            "خدمة النموذج رفضت الطلب أو واجهت خطأ. جرّب تاني أو أوقف المهمة.",
            "The model service rejected the request or failed. Retry or stop the task.",
        ),
        "invalid_response": (
            "استجابة النموذج غير صالحة للتحقق، فتوقفت قبل أي إجراء. جرّب تاني أو أوقف المهمة.",
            "The model response could not be validated, so no action was taken. Retry or stop.",
        ),
        "catalogue_unavailable": (
            "تعذر التحقق من بيانات المنتجات الآن، فتوقفت قبل أي إجراء. جرّب تاني أو أوقف المهمة.",
            "Product facts could not be verified, so no action was taken. Retry or stop.",
        ),
        "interrupted": (
            "اتقطع طلب الفهم قبل ما يكتمل. جرّب تاني أو أوقف المهمة.",
            "Interpretation was interrupted before completion. Retry or stop the task.",
        ),
        "unexpected": (
            "توقفت المهمة بسبب خطأ غير متوقع؛ السبب الدقيق غير معروف. جرّب تاني أو أوقف المهمة.",
            "An unexpected error paused the task; the exact cause is unknown. Retry or stop.",
        ),
    }
    if reason == "throttled" and retry_after_seconds is not None:
        messages["throttled"] = (
            f"وصلنا لحد استخدام النموذج. انتظر {retry_after_seconds} ثانية قبل إعادة المحاولة. "
            "لم يتم تعديل السلة.",
            f"Model limit reached. Wait {retry_after_seconds} seconds before retrying. "
            "The cart was not changed.",
        )

    message = messages[reason][0 if task.language == "ar" else 1]
    runtime.end_task(session, task, "paused", reason, message)
    runtime.sessions.touch(session)


def retry_interpretation(
    runtime: TaskRuntime, session_id: str, task_id: str, tab_id: str | None, snapshot: Snapshot
) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    task = session.active_task
    if task is None or task.task_id != task_id or task.status != "paused":
        raise TaskConflict("This Shopping Task is not awaiting Retry")
    runtime.require_task_origin(task, snapshot)
    previous = urlsplit(session.last_snapshot.url) if session.last_snapshot else None
    current = urlsplit(snapshot.url)
    if previous is None or (previous.scheme, previous.netloc) != (
        current.scheme,
        current.netloc,
    ):
        raise TaskConflict("Retry requires the current Storefront origin")
    runtime.record_snapshot(session, snapshot)
    task.status = "interpreting"
    task.model_call_id = f"call-{uuid4().hex}"
    task.pause_message = None
    runtime.append(
        session,
        "narration",
        {
            "task_id": task_id,
            "text": "بحاول أفهم طلبك تاني…" if task.language == "ar" else "Trying again…",
        },
    )
    runtime.sessions.touch(session)
    return task
