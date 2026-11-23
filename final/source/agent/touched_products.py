"""Which product "this" means, decided by code from verified identities (never by the model).

Level 1: the product whose page is open. Level 2: the products the Copilot last suggested,
added or opened. Otherwise nobody: the Shopper is asked. Only `{"id", "name"}` references the
catalogue or the page verified are kept, never model prose; memory only, gone with the Session.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from agent.product_context import current_product
from agent.schemas import Snapshot
from agent.session_state import Session
from agent.storefront import StorefrontDefinition

MAX_TOUCHED = 3


def this_candidates(
    session: Session, snapshot: Snapshot, storefront: StorefrontDefinition
) -> list[dict[str, str]]:
    """The products "this" may mean right now, computed when a task starts."""
    page = current_product(snapshot, storefront)
    if page is not None:
        return [page]
    return [item.copy() for item in session.last_touched]


def note_touched(session: Session, references: Sequence[Mapping[str, Any]]) -> None:
    """Replace (never merge) what "this" falls back to with the latest touched products."""
    kept = [
        {"id": item["id"], "name": item["name"][:200]}
        for item in references
        if isinstance(item.get("id"), str) and isinstance(item.get("name"), str)
    ][:MAX_TOUCHED]
    if kept:
        session.last_touched = kept


def note_product_touched(
    session: Session,
    product_id: str | None,
    snapshot: Snapshot,
    storefront: StorefrontDefinition,
) -> None:
    """An add or an open of one product finished: its verified name comes from the page it
    ended on, else from the identities the Session already remembers."""
    if product_id is None:
        page = current_product(snapshot, storefront)
        if page is not None:
            note_touched(session, [page])
        return
    page = current_product(snapshot, storefront)
    if page is not None and page["id"] == product_id:
        note_touched(session, [page])
    elif product_id in session.product_context.products:
        note_touched(session, [session.product_context.products[product_id]])
