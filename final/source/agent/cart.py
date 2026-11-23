"""Plan reversible edits through current, visible Storefront controls."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

from agent.product_reference import names_product
from agent.remembered_sizes import matching_option, unavailable_line
from agent.schemas import Action, AskShopperAction, ClickAction, SelectAction, Snapshot, TypeAction
from agent.storefront import StorefrontDefinition, colour_label

if TYPE_CHECKING:
    from agent.llm.intent import StructuredIntent

MESSAGES = {
    "add": ("تمت الإضافة إلى السلة", "Added to cart"),
    "quantity": ("تم تحديث الكمية", "Quantity updated"),
    "remove": ("تم حذف المنتج من السلة", "Item removed from cart"),
    "undo": ("تم التراجع عن تعديل السلة", "Cart change undone"),
}


CART_ROUTES = {
    "add": "/cart/items",
    "quantity": "/cart/quantity",
    "remove": "/cart/remove",
    "undo": "/cart/undo",
}

# Add-form option controls, in the order the Shopper is asked about them.
VARIANT_CONTROLS = (("size", "المقاس"), ("color", "اللون"))


def bind_product_add(
    intent: StructuredIntent, snapshot: Snapshot, product_route: str
) -> StructuredIntent:
    """Bind a model-selected product to its sole current add form, never by prose."""
    if intent.cart_operation != "add" or intent.product_id is None:
        return intent
    expected = product_route.replace("{product_id}", intent.product_id)
    if urlsplit(snapshot.url).path != expected:
        raise ValueError("Selected product does not match the current add page")
    buttons = [
        e
        for e in snapshot.elements
        if e.visible
        and not e.sensitive
        and not e.disabled
        and e.role == "button"
        and e.form_action == CART_ROUTES["add"]
    ]
    target = buttons[0].id if len(buttons) == 1 and not snapshot.truncated else None
    if intent.cart_target_id is not None and intent.cart_target_id != target:
        raise ValueError("Proposed add button does not match the selected product form")
    return intent.model_copy(update={"cart_target_id": target})


UNDO_EXPIRED = (
    "التراجع متاح ١٠ ثواني بس بعد تعديل السلة، والمدة خلصت. ما غيّرتش حاجة في السلة.",
    "Undo is only available for 10 seconds after a cart change, and that time has passed. "
    "Nothing in your cart was changed.",
)


def undo_expired(intent: StructuredIntent, snapshot: Snapshot | None) -> bool:
    """An undo with no observed enabled Undo control: the Storefront's window has closed."""
    if (
        intent.intent != "cart_edit"
        or intent.cart_operation != "undo"
        or intent.needs_clarification
    ):
        return False
    return snapshot is None or not any(
        e.visible
        and not e.sensitive
        and not e.disabled
        and e.role == "button"
        and e.form_action == CART_ROUTES["undo"]
        for e in snapshot.elements
    )


def validate_cart_intent(
    message: str, intent: StructuredIntent, snapshot: Snapshot | None = None
) -> StructuredIntent:
    """Check executable capability, never reinterpret Shopper language."""
    del message
    if intent.cart_operation not in CART_ROUTES and intent.cart_operation != "replace":
        raise ValueError("Unsupported cart operation")
    if intent.cart_quantity is not None and (
        not 1 <= intent.cart_quantity <= 99 or int(intent.cart_quantity) != intent.cart_quantity
    ):
        return intent.model_copy(
            update={
                "cart_quantity": None,
                "cart_quantity_mode": None,
                "needs_clarification": True,
                "missing_fields": ["cart_quantity"],
            }
        )
    if intent.cart_quantity is not None:
        intent = intent.model_copy(update={"cart_quantity": int(intent.cart_quantity)})
    if intent.needs_clarification or undo_expired(intent, snapshot):
        # An expired undo has nothing to bind; the task completes with an honest answer.
        return intent
    # A colour change is an add and a removal: its line is named by its remove button.
    route_name = "remove" if intent.cart_operation == "replace" else intent.cart_operation
    if intent.cart_target_id is not None:
        targets = (
            []
            if snapshot is None
            else [
                element
                for element in snapshot.elements
                if element.id == intent.cart_target_id
                and element.visible
                and not element.sensitive
                and not element.disabled
                and element.role == "button"
                and element.form_action == CART_ROUTES[route_name]
            ]
        )
        if len(targets) != 1:
            raise ValueError("Cart target is not an observed executable control")
    return intent


def plan_cart_edit(
    intent: StructuredIntent,
    snapshot: Snapshot,
    task_id: str,
    sequence: int,
    *,
    asked: dict | None = None,
    remembered: tuple[str, str] | None = None,
    used: dict | None = None,
    stale_size: str | None = None,
    selected: dict | None = None,
    storefront: StorefrontDefinition | None = None,
) -> list[Action]:
    """Plan the edit, or one handback. ``asked`` receives the add option a question asks for.

    ``remembered`` is the (size kind, size) kept for this add's person and product. It is read
    only when the add names no size and the page's size control has none; it is used only when
    the page offers exactly that size (``used`` then receives it), never a nearby one.
    ``stale_size`` is a size control value the Copilot itself selected for another person: it
    counts as no value. ``selected`` receives the size this plan selects.
    """
    elements = [e for e in snapshot.elements if e.visible and not e.sensitive and not e.disabled]
    route = {
        "add": "/cart/items",
        "quantity": "/cart/quantity",
        "remove": "/cart/remove",
        "undo": "/cart/undo",
    }[intent.cart_operation]
    buttons = [e for e in elements if e.role == "button" and e.form_action == route]
    if intent.cart_target_id is not None:
        buttons = [e for e in buttons if e.id == intent.cart_target_id]
    elif intent.cart_target:
        if intent.cart_operation == "add":
            headings = [e.name.casefold() for e in elements if e.role == "heading"]
            if not any(names_product(name, intent.cart_target) for name in headings):
                buttons = []
        else:
            buttons = [
                e for e in buttons if names_product(f"{e.name} {e.group or ''}", intent.cart_target)
            ]
    if intent.v >= 8 and intent.cart_target_id is None:
        buttons = []
    actions: list[Action] = []

    def base():
        return dict(
            v=1,
            task_id=task_id,
            action_id=f"action-{uuid4().hex}",
            sequence_number=sequence + len(actions),
            narration="هعدّل السلة مع إمكانية التراجع."
            if intent.language == "ar"
            else "I'll update the cart with an Undo option.",
        )

    def handback(ar: str, en: str, *, allow_answer: bool = False):
        text = ar if intent.language == "ar" else en
        return [
            AskShopperAction(
                **{**base(), "sequence_number": sequence, "narration": text},
                type="ask_shopper",
                question=text,
                options=[] if allow_answer and intent.v >= 8 else ["Stop"],
            )
        ]

    for value in (intent.constraints.size, intent.constraints.color):
        if value and intent.cart_operation in {"quantity", "remove"}:
            buttons = [
                e
                for e in buttons
                if e.group and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", e.group, re.I)
            ]
    unresolved = set(intent.missing_fields) - {"query", "product_id", "target", "size", "color"}
    if len(buttons) != 1 or intent.conflicting_fields or unresolved:
        return handback(
            "لم أقدر أحدد منتجًا واحدًا مطابقًا للتعديل. تقصد أنهي منتج ومقاس ولون؟",
            "I couldn't identify one matching item for this change. Which item, size and colour?",
            allow_answer=True,
        )
    if intent.cart_operation == "add":
        for field, name in VARIANT_CONTROLS:
            desired = getattr(intent.constraints, field)
            controls = [e for e in elements if e.role == "combobox" and e.name == name]
            if len(controls) != 1:
                return handback(
                    "تعذر التحقق من اختيارات المنتج في الصفحة. أوقف المهمة وحدّث صفحة المنتج.",
                    "I couldn't verify the option controls. Stop and refresh the product page.",
                )
            control = controls[0]
            prefix = ""
            current = control.value
            if field == "size" and not desired and stale_size and current == stale_size:
                current = ""
            if field == "size" and not (desired or current) and remembered is not None:
                offered = matching_option(*remembered, control.options or [])
                if offered is not None:
                    desired = offered
                    if used is not None:
                        used["size"] = remembered[1]
                else:
                    prefix = unavailable_line(intent.language, remembered[1]) + " "
            if not (desired or current) or (desired and desired not in (control.options or [])):
                options = ", ".join(control.options or [])
                shown = options
                if field == "color" and storefront is not None and intent.language == "ar":
                    shown = ", ".join(
                        colour_label(option, "ar", storefront) for option in control.options or []
                    )
                if options and asked is not None:
                    asked.update(field=field, options=list(control.options or []))
                if not options:
                    return handback(
                        "لا توجد اختيارات متاحة لهذا المنتج في الصفحة. أوقف المهمة وراجع المنتج.",
                        "No product options are available on the page. Stop and check the product.",
                    )
                return handback(
                    f"{prefix}محتاج اختيارًا متاحًا لحقل {control.name}. المتاح: {shown}. تختار إيه؟",
                    f"{prefix}Choose an available option for {control.name}: {options}. Which one?",
                    allow_answer=True,
                )
            if desired and desired != current:
                actions.append(SelectAction(**base(), type="select", id=control.id, option=desired))
                if field == "size" and selected is not None:
                    selected["size"] = desired
    if intent.cart_operation in {"add", "quantity"} and intent.cart_quantity is not None:
        name = (
            "الكمية"
            if intent.cart_operation == "add"
            else buttons[0].name.replace("تحديث الكمية", "الكمية", 1)
        )
        controls = [
            e
            for e in elements
            if e.name == name
            and e.role == "textbox"
            and (not buttons[0].group or e.group == buttons[0].group)
        ]
        if len(controls) != 1:
            return handback(
                "تعذر تحديد حقل الكمية للمنتج. أوقف المهمة وحدّث الصفحة قبل المحاولة مجددًا.",
                "I couldn't identify this item's quantity control. Stop and refresh the page.",
            )
        quantity = intent.cart_quantity
        if intent.cart_quantity_mode in {"increase", "decrease"}:
            try:
                current = int(controls[0].value or "")
            except ValueError:
                return handback(
                    "تعذر قراءة الكمية الحالية. أوقف المهمة وحدّث السلة قبل المحاولة مجددًا.",
                    "I couldn't read the current quantity. Stop and refresh the cart.",
                )
            quantity = (
                current + quantity
                if intent.cart_quantity_mode == "increase"
                else current - quantity
            )
        if not 1 <= quantity <= 99:
            return handback(
                "التعديل سيجعل الكمية خارج المدى من 1 إلى 99. تحب تكون الكمية النهائية كام؟",
                "The resulting quantity would be outside 1 to 99. What final quantity do you want?",
                allow_answer=True,
            )
        actions.append(
            TypeAction(
                **base(),
                type="type",
                id=controls[0].id,
                text=str(quantity),
                submit=False,
            )
        )
    elif intent.cart_operation == "quantity":
        return handback(
            "تحب تكون الكمية النهائية كام؟ اختار عددًا صحيحًا من 1 إلى 99.",
            "What final quantity would you like? Choose a whole number from 1 to 99.",
            allow_answer=True,
        )
    actions.append(ClickAction(**base(), type="click", id=buttons[0].id))
    return actions


def scripted_cart_intent(message: str) -> StructuredIntent | None:
    from agent.llm.intent import StructuredIntent

    patterns = [
        ("add", r"(?:add (?:this|it) to (?:my |the )?cart|ضيف ده للسلة|أضف إلى السلة)"),
        ("remove", r"(?:remove (?:this|the) item|شيل المنتج ده)"),
        ("undo", r"(?:undo|تراجع)"),
        ("quantity", r"(?:set quantity to|خلي الكمية) (\d+)"),
    ]
    relative = re.fullmatch(r"Increase quantity by (\d+) for (.+)", message.strip(), re.I)
    if relative:
        return StructuredIntent.model_validate(
            dict(
                v=6,
                language="en",
                dialect="english",
                intent="cart_edit",
                cart_operation="quantity",
                cart_source=message,
                cart_target=relative[2],
                cart_quantity=int(relative[1]),
                cart_quantity_mode="increase",
                constraints={},
                missing_fields=[],
                needs_clarification=False,
            )
        )
    for kind, pattern in patterns:
        match = re.fullmatch(pattern, message.strip(), re.I)
        if match:
            ar = bool(re.search(r"[\u0600-\u06ff]", message))
            return StructuredIntent.model_validate(
                dict(
                    v=5,
                    language="ar" if ar else "en",
                    dialect="egyptian_arabic" if ar else "english",
                    intent="cart_edit",
                    cart_operation=kind,
                    cart_source=message,
                    cart_quantity=int(match[1]) if kind == "quantity" else None,
                    constraints={},
                    missing_fields=[],
                    needs_clarification=False,
                )
            )
    return None
