"""Remembered sizes: a Session-scoped, in-memory store keyed by person and size kind.

Never written to disk, never in an event record, never on the wire. The size kind comes only
from verified catalogue facts (category and product type), never from the model's category or
a product name. Code reads and writes; the model only supplies the size and the beneficiary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agent.llm.intent import StructuredIntent
    from agent.session_state import Session

SizeKind = Literal["shoe", "waist", "top"]

# The single kind table. Anything else (bags, electronics, unknown types) has no kind.
_TOP_TYPES = frozenset({"tops", "shirts", "outerwear", "sportswear", "dresses"})
_TOP_SIZES = ("XS", "S", "M", "L", "XL", "XXL")
MAX_KNOWN_PRODUCTS = 200

NAMED_PERSON = "named_person"
DEFAULT_PERSON = "me"


def size_kind(category: str | None, product_type: str | None) -> SizeKind | None:
    if category == "shoes":
        return "shoe"
    if category == "clothing":
        if product_type == "trousers":
            return "waist"
        if product_type in _TOP_TYPES:
            return "top"
    return None


def normalise_size(kind: str, raw: object) -> str | None:
    """The canonical value of a size of this kind, or None when it does not fit the format."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if kind in {"shoe", "waist"}:
        low, high = (30, 50) if kind == "shoe" else (24, 46)
        if re.fullmatch(r"\d{1,3}", text) and low <= int(text) <= high:
            return str(int(text))
        return None
    if kind == "top" and text.upper() in _TOP_SIZES:
        return text.upper()
    return None


# Letter sizes as the Shopper may say them: the letters, or a common Arabic/Franco form.
_SAID_LETTERS = {
    "XS": ("xs", "extra small", "اكس سمول", "اكس اس"),
    "S": ("s", "small", "سمول", "سمال"),
    "M": ("m", "medium", "ميديم", "ميديوم"),
    "L": ("l", "large", "لارج"),
    "XL": ("xl", "extra large", "اكس لارج", "اكس ال"),
    "XXL": ("xxl", "2xl", "double xl", "دبل اكس لارج", "دبل اكس ال"),
}
_PHRASES = sorted(
    ((phrase, size) for size, phrases in _SAID_LETTERS.items() for phrase in phrases),
    key=lambda pair: -len(pair[0]),
)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def size_said(size: object, texts: Iterable[object]) -> bool:
    """True only when the Shopper's own words contain this size as a whole token.

    The model may copy a size from the page or an earlier turn; such a size was never said.
    """
    if not isinstance(size, str) or not size.strip():
        return False
    wanted = size.strip().translate(_DIGITS).upper()
    for raw in texts:
        if not isinstance(raw, str):
            continue
        text = raw.translate(_DIGITS).casefold()
        if wanted.isdigit():
            if re.search(rf"(?<![\w.]){wanted}(?!\w|\.\d)", text):
                return True
            continue
        found = set()
        for phrase, canonical in _PHRASES:  # longest first, so "اكس لارج" is not "لارج"
            pattern = rf"(?<![\w'’]){re.escape(phrase)}(?![\w'’])"
            if re.search(pattern, text):
                found.add(canonical)
                text = re.sub(pattern, " ", text)
        if wanted in found:
            return True
    return False


def person_of(beneficiary: str | None) -> str | None:
    """The person a size is kept for; None for a named person, who is never stored."""
    if beneficiary is None:
        return DEFAULT_PERSON
    return None if beneficiary == NAMED_PERSON else beneficiary


def matching_option(kind: str, remembered: str, options: Iterable[str]) -> str | None:
    """The page's own option string that is exactly the remembered size, never a nearby one."""
    matches = [o for o in options if normalise_size(kind, o) == remembered]
    exact = [o for o in matches if o.strip().casefold() == remembered.casefold()]
    return exact[0] if len(exact) == 1 else None


def note_verified(session: Session, facts: Mapping[str, tuple[str, str]] | None) -> None:
    """Keep the size kind of products whose category and type the catalogue just verified."""
    for product_id, (category, product_type) in (facts or {}).items():
        session.product_kinds.pop(product_id, None)
        session.product_kinds[product_id] = size_kind(category, product_type)
    while len(session.product_kinds) > MAX_KNOWN_PRODUCTS:
        session.product_kinds.pop(next(iter(session.product_kinds)))


def remember(session: Session, beneficiary: str | None, kind: str | None, raw: object) -> bool:
    """Store the latest size said for this person and kind; False when nothing was stored."""
    person = person_of(beneficiary)
    size = normalise_size(kind, raw) if kind else None
    if person is None or kind is None or size is None:
        return False
    session.remembered_sizes[(person, kind)] = size
    return True


def recall(session: Session, intent: StructuredIntent) -> tuple[str, str] | None:
    """(kind, size) remembered for this add's person and product, or None."""
    person = person_of(intent.beneficiary)
    kind = session.product_kinds.get(intent.product_id or "")
    if person is None or kind is None:
        return None
    size = session.remembered_sizes.get((person, kind))
    return (kind, size) if size is not None else None


def remember_add(session: Session, intent: StructuredIntent) -> str | None:
    """Store the size said with a cart add under the product's kind; the note for a named person.

    The latest size said wins. A named person's size is used for this request only.
    """
    if not intent.constraints.size or not intent.product_id:
        return None
    if intent.beneficiary == NAMED_PERSON:
        return not_saved_note(intent.language)
    remember(
        session,
        intent.beneficiary,
        session.product_kinds.get(intent.product_id),
        intent.constraints.size,
    )
    return None


def stale_selection(session: Session, intent: StructuredIntent) -> str | None:
    """The size the Copilot selected on this product's form for someone else, if any."""
    chosen = session.copilot_selected_size.get(intent.product_id or "")
    if chosen is None:
        return None
    same = chosen[0] == (intent.beneficiary or DEFAULT_PERSON) and chosen[0] != NAMED_PERSON
    return None if same else chosen[1]


def record_selection(session: Session, intent: StructuredIntent, size: str | None) -> None:
    if size and intent.product_id:
        session.copilot_selected_size[intent.product_id] = (
            intent.beneficiary or DEFAULT_PERSON,
            size,
        )


def shared_kind(session: Session, product_ids: Iterable[str]) -> str | None:
    """The one kind that ALL the shown products share; None when they differ or none shown."""
    kinds = {session.product_kinds.get(product_id) for product_id in product_ids}
    return next(iter(kinds)) if len(kinds) == 1 else None


def not_saved_note(language: str) -> str:
    return (
        "استخدمت المقاس ده للطلب ده بس ومش هحفظه."
        if language == "ar"
        else "I used that size for this request only and didn't save it."
    )


def used_note(language: str, size: str) -> str:
    return (
        f"ضفتها بمقاس {size} زي ما قلت."
        if language == "ar"
        else f"Added it in size {size}, as you said."
    )


def unavailable_line(language: str, size: str) -> str:
    return (
        f"المقاس {size} مش متاح في المنتج ده."
        if language == "ar"
        else f"Size {size} isn't available for this product."
    )


def with_note(summary: str, note: str | None) -> str:
    return summary if not note else f"{summary.rstrip('. ')}. {note}"
