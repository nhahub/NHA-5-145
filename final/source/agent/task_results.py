"""ActionResult identity matching and execution progress."""

import re
from urllib.parse import urlsplit
from uuid import uuid4

from agent.cart import MESSAGES, bind_product_add, plan_cart_edit
from agent.llm.intent import StructuredIntent
from agent.planner import (
    ActionIdentity,
    is_expected_login_redirect,
    snapshot_matches_url,
)
from agent.remembered_sizes import (
    recall,
    record_selection,
    stale_selection,
    used_note,
    with_note,
)
from agent.schemas import (
    ActionResult,
    AskShopperAction,
    ClickAction,
    GuardedClickAction,
    NavigateAction,
    Snapshot,
    SpotlightAction,
    to_wire,
)
from agent.session_state import (
    AcceptedResult,
    ActionResultMismatch,
    ActiveTask,
)
from agent.swap import SWAP_REMOVE_FAILED
from agent.swap import summary as swap_summary
from agent.task_runtime import TaskRuntime
from agent.touched_products import note_product_touched


def _visible_product_count(snapshot: Snapshot) -> int | None:
    counts = {
        int(match.group(1))
        for element in snapshot.elements
        if element.visible and element.role == "heading" and element.level == 2
        if (match := re.fullmatch(r"(\d+) منتجات", element.name.strip())) is not None
    }
    return next(iter(counts)) if len(counts) == 1 else None


def _swap_removing(task: ActiveTask) -> bool:
    return task.swap is not None and task.swap["phase"] == "remove"


def _swap_remove_failed(runtime: TaskRuntime, session, task: ActiveTask) -> None:
    """The new colour is in the cart but the old line could not be removed: say so, stop."""
    task.action = None
    task.cart_actions.clear()
    task.swap = None
    runtime.end_task(
        session,
        task,
        "paused",
        "swap_remove_failed",
        SWAP_REMOVE_FAILED[0 if task.language == "ar" else 1],
    )


def _step_to(runtime: TaskRuntime, session, task: ActiveTask, action) -> None:
    task.action = action
    task.step_count += 1
    task.status = "awaiting_action_result"
    runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(action)})


def _swap_click_remove(runtime: TaskRuntime, session, task: ActiveTask, snapshot: Snapshot) -> None:
    """On the verified cart Snapshot click the remove button of exactly the old line."""
    assert task.swap is not None
    buttons = [
        e
        for e in snapshot.elements
        if e.visible
        and not e.sensitive
        and not e.disabled
        and e.role == "button"
        and e.form_action == "/cart/remove"
        and e.group == task.swap["old_group"]
    ]
    if len(buttons) != 1:
        _swap_remove_failed(runtime, session, task)
        return
    _step_to(
        runtime,
        session,
        task,
        ClickAction(
            v=1,
            type="click",
            task_id=task.task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=task.step_count + 1,
            narration="هشيل اللون القديم من السلة."
            if task.language == "ar"
            else "I'll remove the old colour from the cart.",
            id=buttons[0].id,
        ),
    )


def _swap_to_remove_phase(runtime: TaskRuntime, session, task: ActiveTask, intent) -> None:
    """The add is verified: open the cart to remove the old line."""
    assert task.swap is not None
    task.swap["phase"] = "remove"
    task.cart_operation = "remove"
    task.resolved_state["_intent"] = intent.model_copy(
        update={
            "cart_operation": "remove",
            "product_id": None,
            "constraints": intent.constraints.model_copy(update={"size": None, "color": None}),
            "cart_quantity": None,
            "cart_quantity_mode": None,
            "cart_target_id": None,
        }
    ).model_dump(mode="json")
    _step_to(
        runtime,
        session,
        task,
        NavigateAction(
            v=1,
            type="navigate",
            task_id=task.task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=task.step_count + 1,
            narration="هفتح السلة وأشيل اللون القديم."
            if task.language == "ar"
            else "I'll open the cart and remove the old colour.",
            url="/cart",
        ),
    )


def accept_result(
    runtime: TaskRuntime, session_id: str, action_result: ActionResult, tab_id: str | None = None
) -> ActiveTask:
    session = runtime.sessions.get(session_id)
    runtime.sessions.assert_lease(session, tab_id)
    result_identity = (
        action_result.task_id,
        action_result.action_id,
        action_result.sequence_number,
    )
    accepted = session.accepted_results.get(result_identity)
    if accepted is not None:
        if accepted.result != action_result:
            raise ActionResultMismatch("Action Result conflicts with the accepted result")
        return accepted.task
    task = session.active_task
    if task is None:
        raise ActionResultMismatch("There is no pending Action")
    action = task.action
    if action is None or task.status != "awaiting_action_result":
        raise ActionResultMismatch("There is no pending Action")
    identity_matches = (
        action_result.task_id == task.task_id
        and action_result.action_id == action.action_id
        and action_result.sequence_number == action.sequence_number
    )
    if not identity_matches:
        raise ActionResultMismatch("Action Result does not match the pending Action")
    runtime.record(
        session,
        "action_result",
        task_id=task.task_id,
        action_type=action.type,
        sequence=action.sequence_number,
        status=action_result.status,
    )
    if task.cart_operation:
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        same_origin = (
            session.last_snapshot is not None
            and urlsplit(session.last_snapshot.url).netloc
            == urlsplit(action_result.snapshot.url).netloc
            and urlsplit(session.last_snapshot.url).scheme
            == urlsplit(action_result.snapshot.url).scheme
        )
        runtime.record_snapshot(session, action_result.snapshot)
        if isinstance(action, NavigateAction):
            intent = StructuredIntent.model_validate(task.resolved_state["_intent"])
            product_add = intent.cart_operation == "add" and intent.product_id is not None
            expected = (
                runtime.planner.storefront.product_route.replace("{product_id}", intent.product_id)
                if product_add
                else "/cart"
            )
            if (
                same_origin
                and action_result.status in {"ok", "navigated"}
                and urlsplit(action_result.snapshot.url).path == expected
            ):
                if _swap_removing(task):
                    _swap_click_remove(runtime, session, task, action_result.snapshot)
                    runtime.sessions.touch(session)
                    return task
                if intent.v >= 8 and not product_add:
                    # Navigation supplied the previously unavailable cart context.
                    # Resolve a DOM target from this fresh snapshot before any edit.
                    task.action = None
                    task.cart_actions.clear()
                    task.cart_operation = None
                    task.status = "interpreting"
                    task.model_call_id = f"call-{uuid4().hex}"
                    runtime.sessions.touch(session)
                    return task
                if product_add:
                    intent = bind_product_add(
                        intent, action_result.snapshot, runtime.planner.storefront.product_route
                    )
                    task.resolved_state["_intent"] = intent.model_dump(mode="json")
                asked: dict = {}
                used: dict = {}
                chosen: dict = {}
                task.cart_actions = plan_cart_edit(
                    intent,
                    action_result.snapshot,
                    task.task_id,
                    task.step_count + 1,
                    asked=asked,
                    remembered=recall(session, intent) if product_add and not task.swap else None,
                    used=used,
                    stale_size=(
                        stale_selection(session, intent) if product_add and not task.swap else None
                    ),
                    selected=chosen,
                    storefront=runtime.planner.storefront,
                )
                if product_add and not task.swap:
                    record_selection(session, intent, chosen.get("size"))
                if "size" in used:
                    task.size_note = used_note(intent.language, used["size"])
                task.action = task.cart_actions.pop(0)
                if isinstance(task.action, AskShopperAction):
                    task.swap = None  # nothing is removed by a swap whose add had to ask
                task.step_count += 1
                task.status = (
                    "awaiting_answer"
                    if isinstance(task.action, AskShopperAction)
                    else "awaiting_action_result"
                )
                task.pending_variant = None
                if isinstance(task.action, AskShopperAction) and not task.action.options:
                    task.pending_clarification = task.action.question
                    task.pending_variant = asked or None
                    # The next interpretation reads history: record the question it answers.
                    session.conversation.append({"role": "copilot", "text": task.action.question})
                runtime.append(
                    session, "action", {"task_id": task.task_id, "action": to_wire(task.action)}
                )
            elif _swap_removing(task):
                _swap_remove_failed(runtime, session, task)
            else:
                task.action = None
                task.cart_actions.clear()
                runtime.end_task(
                    session,
                    task,
                    "paused",
                    "cart_navigation_failed",
                    "تعذر فتح الصفحة المطلوبة. حاول تاني."
                    if task.language == "ar"
                    else "Could not open the requested page. Retry.",
                )
            runtime.sessions.touch(session)
            return task
        success = action_result.status == "ok" and same_origin
        intent = StructuredIntent.model_validate(task.resolved_state["_intent"])
        if intent.cart_operation == "add" and intent.product_id is not None:
            expected = runtime.planner.storefront.product_route.replace(
                "{product_id}", intent.product_id
            )
            success = success and urlsplit(action_result.snapshot.url).path == expected
        if success and task.cart_actions:
            task.action = task.cart_actions.pop(0)
            task.step_count += 1
            runtime.append(
                session, "action", {"task_id": task.task_id, "action": to_wire(task.action)}
            )
        elif (
            success
            and task.swap is not None
            and task.swap["phase"] == "add"
            and any(
                e.visible and e.role == "status" and e.name in MESSAGES["add"]
                for e in action_result.snapshot.elements
            )
        ):
            _swap_to_remove_phase(runtime, session, task, intent)
        elif success and any(
            e.visible and e.role == "status" and e.name in MESSAGES[task.cart_operation]
            for e in action_result.snapshot.elements
        ):
            summary = with_note(
                swap_summary(task.swap, task.language, runtime.planner.storefront)
                if _swap_removing(task)
                else MESSAGES[task.cart_operation][0 if task.language == "ar" else 1],
                task.size_note,
            )
            session.conversation.append({"role": "copilot", "text": summary})
            runtime.append(
                session,
                "done",
                {"task_id": task.task_id, "summary": summary, "language": task.language},
            )
            if task.cart_operation == "add":
                # "This" may now mean the product just added (before a later plan step starts).
                note_product_touched(
                    session, intent.product_id, action_result.snapshot, runtime.planner.storefront
                )
            runtime.end_task(session, task, "completed")
        elif _swap_removing(task) and isinstance(action, ClickAction) and not success:
            # The click itself failed: the old line is still there next to the new one.
            _swap_remove_failed(runtime, session, task)
        else:
            if isinstance(action, ClickAction):
                runtime.ask_to_stop_uncertain_mutation(session, task, action)
            else:
                task.action = None
                task.cart_actions.clear()
                runtime.end_task(
                    session,
                    task,
                    "paused",
                    "cart_edit_unavailable",
                    "تعذر تجهيز تعديل السلة. حاول تاني من الحالة الحالية."
                    if task.language == "ar"
                    else "Could not prepare the cart change. Retry from the current state.",
                )
        runtime.sessions.touch(session)
        return task
    if isinstance(action, GuardedClickAction):
        destination_url = urlsplit(action_result.snapshot.url)
        origin_url = urlsplit(session.last_snapshot.url) if session.last_snapshot else None
        same_origin = bool(
            origin_url is not None
            and origin_url.scheme in {"http", "https"}
            and (destination_url.scheme, destination_url.netloc)
            == (origin_url.scheme, origin_url.netloc)
        )
        path = destination_url.path
        verified = (
            action_result.status in {"ok", "navigated"}
            and same_origin
            and (
                (
                    action.mutation_kind == "clear_cart"
                    and path == "/cart"
                    and any(
                        element.visible
                        and element.role == "status"
                        and element.name == "السلة فارغة"
                        for element in action_result.snapshot.elements
                    )
                )
                or (
                    action.mutation_kind == "submit_checkout"
                    and path.startswith("/order/complete/")
                    and any(
                        element.visible
                        and element.role == "heading"
                        and element.name == "تم تسجيل طلب خيالي"
                        for element in action_result.snapshot.elements
                    )
                )
            )
        )
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        runtime.record_snapshot(session, action_result.snapshot)
        if not verified:
            runtime.ask_to_stop_uncertain_mutation(session, task, action)
        else:
            summary = (
                "تم إفراغ السلة."
                if task.mutation_kind == "clear_cart" and task.language == "ar"
                else "Cart emptied."
                if task.mutation_kind == "clear_cart"
                else "تم تسجيل الطلب الخيالي دون دفع حقيقي."
                if task.language == "ar"
                else "Fictional order submitted without a real payment."
            )
            runtime.append(
                session,
                "done",
                {"task_id": task.task_id, "summary": summary, "language": task.language},
            )
            session.conversation.append({"role": "copilot", "text": summary})
            runtime.end_task(session, task, "completed")
        runtime.sessions.touch(session)
        return task
    if action_result.status not in {"ok", "navigated"}:
        question = (
            "تعذر الإجراء. ماذا تريد أن أفعل الآن؟"
            if task.language == "ar"
            else "The action did not work. What would you like me to do?"
        )
        narration = (
            "تعذر تنفيذ الإجراء بأمان."
            if task.language == "ar"
            else "The action could not be completed safely."
        )
        next_action = AskShopperAction(
            v=1,
            type="ask_shopper",
            task_id=task.task_id,
            action_id=f"question-{uuid4().hex}",
            sequence_number=action.sequence_number + 1,
            narration=narration,
            question=question,
            options=["Try again", "Stop"] if task.language == "en" else ["حاول تاني", "إيقاف"],
        )
        runtime.append(
            session,
            "narration",
            {"task_id": task.task_id, "text": narration},
        )
        runtime.append(
            session,
            "action",
            {"task_id": task.task_id, "action": to_wire(next_action)},
        )
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        task.action = next_action
        task.step_count += 1
        task.status = "awaiting_answer"
        runtime.record_snapshot(session, action_result.snapshot)
        session.conversation.append({"role": "copilot", "text": narration})
        runtime.sessions.touch(session)
        return task
    if (
        task.intent_kind == "navigate"
        and task.target_name == "orders"
        and task.target_url is not None
        and session.last_snapshot is not None
        and is_expected_login_redirect(
            action_result.snapshot, session.last_snapshot, task.target_url
        )
    ):
        handoff = runtime.planner.plan_orders_resume(
            action_result.snapshot,
            ActionIdentity(
                task_id=task.task_id,
                action_id=f"question-{uuid4().hex}",
                sequence_number=action.sequence_number + 1,
            ),
            task.language,
            trusted_origin=session.last_snapshot,
        )
        if task.step_count >= 8:
            handoff = AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=task.task_id,
                action_id=f"question-{uuid4().hex}",
                sequence_number=action.sequence_number + 1,
                narration=(
                    "وصلنا لحد الخطوات. أوقف المهمة هنا."
                    if task.language == "ar"
                    else "The step limit is reached. Stop this task here."
                ),
                question=(
                    "هل تريد إيقاف المهمة؟"
                    if task.language == "ar"
                    else "Would you like to stop this task?"
                ),
                options=["Stop"],
            )
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        task.action = handoff
        task.auth_handoff = True
        task.status = "awaiting_answer"
        task.step_count += 1
        runtime.record_snapshot(session, action_result.snapshot)
        runtime.append(session, "narration", {"task_id": task.task_id, "text": handoff.narration})
        runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(handoff)})
        session.conversation.append({"role": "copilot", "text": handoff.narration})
        runtime.sessions.touch(session)
        return task
    if task.target_url is not None and not snapshot_matches_url(
        action_result.snapshot, task.target_url, session.last_snapshot
    ):
        identity = ActionIdentity(
            task_id=task.task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=action.sequence_number + 1,
        )
        if task.intent_kind in {"navigate", "locate", "open_product"}:
            next_action = AskShopperAction(
                v=1,
                type="ask_shopper",
                task_id=task.task_id,
                action_id=identity.action_id,
                sequence_number=identity.sequence_number,
                narration=(
                    "لم أتمكن من التحقق من الصفحة المطلوبة، لذلك توقفت."
                    if task.language == "ar"
                    else "I couldn't verify the requested page, so I stopped here."
                ),
                question=(
                    "هل تريد إيقاف المهمة؟"
                    if task.language == "ar"
                    else "Would you like to stop this task?"
                ),
                options=["Stop"],
            )
        else:
            next_action = runtime.planner.plan_visible_control_fallback(
                task.target_url,
                action_result.snapshot,
                identity,
                task.language,
            )
        runtime.append(
            session,
            "narration",
            {"task_id": task.task_id, "text": next_action.narration},
        )
        runtime.append(
            session,
            "action",
            {"task_id": task.task_id, "action": to_wire(next_action)},
        )
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        task.action = next_action
        task.step_count += 1
        task.status = (
            "awaiting_answer"
            if isinstance(next_action, AskShopperAction)
            else "awaiting_action_result"
        )
        runtime.record_snapshot(session, action_result.snapshot)
        session.conversation.append({"role": "copilot", "text": next_action.narration})
        runtime.sessions.touch(session)
        return task
    if task.intent_kind == "mutate" and isinstance(action, NavigateAction):
        try:
            next_action = runtime.offer_mutation(
                task, action_result.snapshot, action.sequence_number + 1
            )
        except ValueError:
            task.action = None
            runtime.end_task(
                session,
                task,
                "paused",
                "guarded_control_missing",
                "الإجراء المطلوب غير متاح في حالة السلة الحالية."
                if task.language == "ar"
                else "That action is unavailable in the current cart state.",
            )
        else:
            task.action = next_action
            task.status = "awaiting_answer"
            task.step_count += 1
            runtime.append(
                session, "narration", {"task_id": task.task_id, "text": next_action.narration}
            )
            runtime.append(
                session, "action", {"task_id": task.task_id, "action": to_wire(next_action)}
            )
            session.conversation.append({"role": "copilot", "text": next_action.narration})
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        runtime.record_snapshot(session, action_result.snapshot)
        runtime.sessions.touch(session)
        return task
    if (
        task.intent_kind == "navigate"
        and task.target_name == "orders"
        and not task.awaiting_newest_order_spotlight
        and snapshot_matches_url(action_result.snapshot, "/account/orders", session.last_snapshot)
    ):
        followup = runtime.planner.plan_orders_resume(
            action_result.snapshot,
            ActionIdentity(
                task_id=task.task_id,
                action_id=f"action-{uuid4().hex}",
                sequence_number=action.sequence_number + 1,
            ),
            task.language,
            trusted_origin=session.last_snapshot,
        )
        session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
        task.action = followup
        task.auth_handoff = False
        task.awaiting_newest_order_spotlight = isinstance(followup, SpotlightAction)
        task.step_count += 1
        task.status = (
            "awaiting_answer"
            if isinstance(followup, AskShopperAction)
            else "awaiting_action_result"
        )
        runtime.record_snapshot(session, action_result.snapshot)
        runtime.append(session, "narration", {"task_id": task.task_id, "text": followup.narration})
        runtime.append(session, "action", {"task_id": task.task_id, "action": to_wire(followup)})
        session.conversation.append({"role": "copilot", "text": followup.narration})
        runtime.sessions.touch(session)
        return task
    if task.intent_kind in {"navigate", "locate", "open_product"}:
        destinations = {
            "cart": ("السلة", "cart"),
            "orders": ("سجل الطلبات", "order history"),
            "checkout": ("الدفع", "checkout"),
            "account": ("الحساب", "account"),
        }
        ar_destination, en_destination = destinations.get(
            task.target_name or "", ("الصفحة", "page")
        )
        if task.intent_kind == "open_product":
            note_product_touched(
                session,
                task.resolved_state.get("_intent", {}).get("product_id"),
                action_result.snapshot,
                runtime.planner.storefront,
            )
            summary = (
                "تم فتح صفحة المنتج المقترح."
                if task.language == "ar"
                else "Opened the recommended product's page."
            )
            narration = summary
        elif task.intent_kind == "navigate" and task.target_name == "orders":
            summary = (
                "تم فتح سجل الطلبات وتحديد أحدث طلب."
                if task.language == "ar"
                else "Opened order history and highlighted the newest order."
            )
            narration = summary
        elif task.intent_kind == "locate":
            if (
                task.target_name == "orders"
                and isinstance(action, SpotlightAction)
                and "account link" in action.narration.lower()
            ):
                summary = (
                    "أشرت إلى رابط الحساب؛ سجل الطلبات موجود بداخله."
                    if task.language == "ar"
                    else "Pointed to the account link; order history is inside your account."
                )
            elif (
                task.target_name == "checkout"
                and isinstance(action, SpotlightAction)
                and "cart link" in action.narration.lower()
            ):
                summary = (
                    "أشرت إلى رابط السلة، ومنها يبدأ الدفع."
                    if task.language == "ar"
                    else "Pointed to the cart link, where checkout starts."
                )
            else:
                summary = (
                    f"تم تحديد {ar_destination}."
                    if task.language == "ar"
                    else f"Located the {en_destination}."
                )
        else:
            summary = (
                f"تم فتح {ar_destination}."
                if task.language == "ar"
                else f"Opened the {en_destination}."
            )
        narration = summary
    else:
        count = _visible_product_count(action_result.snapshot)
        if count is None:
            narration = summary = (
                "تعذر التحقق من نتائج البحث."
                if task.language == "ar"
                else "Couldn't verify the search results."
            )
        elif count == 0:
            narration = summary = (
                "لا توجد منتجات مطابقة لطلبك."
                if task.language == "ar"
                else "No products match your request."
            )
        else:
            narration = (
                "تم تطبيق الفلاتر بنجاح."
                if task.language == "ar"
                else "The filters were applied successfully."
            )
            summary = (
                "تم عرض المنتجات المطابقة."
                if task.language == "ar"
                else "Matching products are now shown."
            )
    if narration != summary:
        # The Panel shows done.summary as its own message; a twin narration would repeat it.
        runtime.append(
            session,
            "narration",
            {"task_id": task.task_id, "text": narration},
        )
    runtime.append(
        session,
        "done",
        {"task_id": task.task_id, "summary": summary, "language": task.language},
    )
    session.accepted_results[result_identity] = AcceptedResult(task=task, result=action_result)
    runtime.record_snapshot(session, action_result.snapshot)
    session.last_followup_target = (
        task.target_name
        if task.intent_kind in {"locate", "navigate"}
        and task.target_name in {"cart", "orders", "checkout", "account"}
        else None
    )
    session.conversation.append({"role": "copilot", "text": summary})
    runtime.end_task(session, task, "completed")
    runtime.sessions.touch(session)
    return task
