"""A colour change of a cart line, done the way a shopper does it: add the new, remove the old.

The model only names the operation, the NEW colour and the observed remove button of the line.
Everything else is read by code: the old line from the cart Snapshot, the facts from the
catalogue, and the two steps (an add of the new colour, then the removal of exactly the old
line) from what the pages verify. The words here are Shopper-facing only; nothing in this module
reaches a log record.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from agent.conditions import QUESTION as COULD_NOT_CHECK
from agent.conditions import _fold_size
from agent.schemas import Snapshot
from agent.storefront import StorefrontDefinition, canonical_colour, colour_label

SWAP_REMOVE_FAILED = (
    "ضفت اللون الجديد، بس ما قدرتش أشيل القديم، فالسلة فيها الاتنين دلوقتي. تقدر تطلب مني أشيله.",
    "I added the new colour but couldn't remove the old one, so your cart has both now. "
    "You can ask me to remove it.",
)
COULD_NOT_IDENTIFY = (
    "لم أقدر أحدد منتجًا واحدًا مطابقًا للتعديل. تقصد أنهي منتج ومقاس ولون؟",
    "I couldn't identify one matching item for this change. Which item, size and colour?",
)


@dataclass(frozen=True)
class SwapLine:
    """The cart line to change, read from its group label, link and quantity textbox."""

    product_id: str
    name_ar: str
    name_en: str
    size: str | None
    old_color: str | None
    quantity: int
    old_group: str


@dataclass(frozen=True)
class SwapDecision:
    """What the checks say: go on, or end/ask with this Shopper-language text."""

    kind: str  # "go" | "ask"
    text: str = ""


def _none_if_empty(value: str) -> str | None:
    value = value.strip()
    return None if value in {"", "—"} else value


def read_line(
    snapshot: Snapshot | None, target_id: int | None, size: str | None, product_route: str
) -> SwapLine | None:
    """The one line the remove button names, or None when anything is missing or ambiguous."""
    if snapshot is None or target_id is None:
        return None
    visible = [e for e in snapshot.elements if e.visible and not e.sensitive and not e.disabled]
    buttons = [
        e
        for e in visible
        if e.id == target_id and e.role == "button" and e.form_action == "/cart/remove"
    ]
    if len(buttons) != 1 or not buttons[0].group:
        return None
    group = buttons[0].group
    head, divider, tail = group.rpartition(" — ")
    if not divider:
        return None
    labels = [part.strip() for part in head.split(" / ")]
    options = tail.split(" / ")
    if len(options) != 2 or not labels[0]:
        return None
    line_size, old_color = _none_if_empty(options[0]), _none_if_empty(options[1])
    if size and not re.search(rf"(?<!\w){re.escape(size)}(?!\w)", group, re.I):
        return None
    pattern = re.compile(
        "^" + re.escape(product_route).replace(r"\{product_id\}", "([^/?#]+)") + "$"
    )
    ids = {
        match.group(1)
        for e in visible
        if e.role == "link" and e.group == group and e.href and (match := pattern.match(e.href))
    }
    boxes = [
        e
        for e in visible
        if e.role == "textbox" and e.group == group and e.name.startswith("الكمية")
    ]
    if len(ids) != 1 or len(boxes) != 1:
        return None
    try:
        quantity = int(boxes[0].value or "")
    except ValueError:
        return None
    if not 1 <= quantity <= 99:
        return None
    return SwapLine(
        product_id=next(iter(ids)),
        name_ar=labels[0],
        name_en=labels[-1] if len(labels) > 1 else labels[0],
        size=line_size,
        old_color=old_color,
        quantity=quantity,
        old_group=group,
    )


def _colour_key(value: str | None, storefront: StorefrontDefinition) -> str:
    return ((canonical_colour(value, storefront) or value or "").strip()).casefold()


def decide(
    line: SwapLine,
    new_color: str | None,
    product: Any,
    language: str,
    storefront: StorefrontDefinition,
) -> SwapDecision:
    """Check the catalogue facts before any cart change. ``product`` is None when unreadable."""
    arabic = language == "ar"
    if product is None:
        return SwapDecision("ask", COULD_NOT_CHECK[language])
    old_key = _colour_key(line.old_color, storefront)
    others = [c for c in product.colors if _colour_key(c, storefront) != old_key]
    colours = ", ".join(colour_label(c, language, storefront) for c in others) or "—"
    new_name = colour_label(new_color, language, storefront, definite=True)
    new_plain = colour_label(new_color, language, storefront)
    if new_color and _colour_key(new_color, storefront) == old_key:
        # The line already has this colour: a misread request, never an answer. Ask.
        return SwapDecision(
            "ask",
            f"اللون {new_name} هو اللي في السلة أصلاً. تحب تغيّره للون إيه؟ "
            f"الألوان المتاحة: {colours}."
            if arabic
            else f"{new_plain} is already the colour in your cart. "
            f"Which colour would you like instead? Available colours: {colours}.",
        )
    if not new_color:
        return SwapDecision(
            "ask",
            f"تحب تغيّره للون إيه؟ الألوان المتاحة: {colours}."
            if arabic
            else f"Which colour would you like instead? Available colours: {colours}.",
        )
    sizes = {_fold_size(size) for size in product.sizes}
    offered = (
        _colour_key(new_color, storefront) in {_colour_key(c, storefront) for c in product.colors}
        and (line.size is None or _fold_size(line.size) in sizes)
        and bool(product.available)
    )
    if offered:
        return SwapDecision("go")
    where = f" في المقاس {line.size}" if line.size else ""
    where_en = f" in size {line.size}" if line.size else ""
    return SwapDecision(
        "ask",
        f"اللون {new_name} مش متاح للمنتج ده{where}. الألوان المتاحة: {colours}. "
        "تحب أغيّره لأنهي لون؟"
        if arabic
        else f"{new_plain} isn't available for this product{where_en}. "
        f"Available colours: {colours}. Which colour would you like?",
    )


def scratch(line: SwapLine, new_color: str) -> dict[str, Any]:
    """The task-only record of the swap in progress. Never kept in the Session or a log."""
    return {**asdict(line), "new_color": new_color, "phase": "add"}


def summary(swap: dict[str, Any], language: str, storefront: StorefrontDefinition) -> str:
    """The done text, built by code."""
    arabic = language == "ar"
    name = swap["name_ar"] if arabic else swap["name_en"]
    size = swap["size"]
    new = colour_label(swap["new_color"], language, storefront, definite=True)
    old_color = swap["old_color"]
    old = (
        colour_label(old_color, language, storefront, definite=True)
        if old_color
        else ("القديم" if arabic else "old")
    )
    if arabic:
        where = f" مقاس {size}" if size else ""
        return f"غيّرت اللون: ضفت {name}{where} باللون {new} وشلت اللي باللون {old}."
    where = f" in size {size}" if size else ""
    return f"Changed the colour: added {name}{where} in {new} and removed the {old} one."
