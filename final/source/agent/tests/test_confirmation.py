import pytest

from agent.confirmation import (
    ConfirmationLedger,
    MutationProposal,
    classify_guarded_mutation,
)
from agent.schemas import GuardedClickAction, Snapshot


def proposal(
    *,
    task_id: str = "task-1",
    action_type: str = "click",
    target_signature: str = "button|إفراغ السلة|POST /cart/clear",
    arguments: tuple[tuple[str, str], ...] = (("cart_revision", "3"),),
    effect: str = "Remove all 2 cart lines",
    state_signature: str = "cart:3",
) -> MutationProposal:
    return MutationProposal(
        task_id=task_id,
        action_type=action_type,
        target_signature=target_signature,
        arguments=arguments,
        effect=effect,
        state_signature=state_signature,
    )


def test_confirmation_is_exact_single_use_and_uses_stable_target_not_snapshot_id() -> None:
    clock = [100.0]
    ledger = ConfirmationLedger(clock=lambda: clock[0])
    expected = proposal()
    question_id = ledger.offer(expected)

    assert not ledger.confirm(question_id, "yes", expected)
    assert not ledger.confirm("confirmation-unrelated", "Confirm", expected)
    assert not ledger.confirm(question_id, "Confirm", proposal(task_id="task-2"))
    assert not ledger.confirm(question_id, "Confirm", proposal(action_type="navigate"))
    assert not ledger.confirm(
        question_id,
        "Confirm",
        proposal(target_signature="button|إتمام الطلب|POST /checkout/submit"),
    )
    assert not ledger.confirm(
        question_id,
        "Confirm",
        proposal(arguments=(("cart_revision", "4"),)),
    )
    assert not ledger.confirm(
        question_id,
        "Confirm",
        proposal(effect="Remove one cart line"),
    )
    assert ledger.confirm(question_id, "Confirm", expected)
    assert not ledger.confirm(question_id, "Confirm", expected)


def test_confirmation_expires_at_sixty_seconds_or_relevant_state_change() -> None:
    clock = [100.0]
    ledger = ConfirmationLedger(clock=lambda: clock[0])
    question_id = ledger.offer(proposal())

    assert not ledger.confirm(question_id, "Confirm", proposal(state_signature="cart:4"))
    clock[0] = 160.0
    assert not ledger.confirm(question_id, "Confirm", proposal())


def test_confirmation_cannot_be_reused_after_invalidation() -> None:
    ledger = ConfirmationLedger(clock=lambda: 100.0)
    question_id = ledger.offer(proposal())

    ledger.invalidate()

    assert not ledger.confirm(question_id, "Confirm", proposal())


def test_proposal_rejects_unstable_or_empty_authority() -> None:
    with pytest.raises(ValueError):
        proposal(target_signature="")
    with pytest.raises(ValueError):
        proposal(effect="")


def test_guarded_action_wire_rejects_malformed_authority() -> None:
    fields = {
        "v": 1,
        "type": "guarded_click",
        "task_id": "task-1",
        "action_id": "action-1",
        "sequence_number": 2,
        "narration": "Clear the cart",
        "id": 7,
        "confirmation_id": "confirmation-1234567890abcdef1234567890abcdef",
        "mutation_kind": "clear_cart",
        "target_signature": "button|Empty cart|POST /cart/clear",
        "state_signature": "cart:3",
        "cart_revision": 3,
        "effect": "Remove every item from the current cart",
    }
    for change in (
        {"confirmation_id": "yes"},
        {"target_signature": ""},
        {"cart_revision": -1},
    ):
        with pytest.raises(ValueError):
            GuardedClickAction.model_validate({**fields, **change})


def test_only_explicit_bulk_clear_and_checkout_submit_are_guarded() -> None:
    snapshot = Snapshot.model_validate(
        {
            "v": 1,
            "url": "http://localhost:4000/cart",
            "title": "Cart",
            "lang": "en",
            "viewport": {"w": 800, "h": 600, "scrollY": 0},
            "truncated": False,
            "elements": [
                {
                    "id": 1,
                    "role": "link",
                    "name": "Checkout",
                    "visible": True,
                    "href": "/checkout",
                },
                {
                    "id": 2,
                    "role": "button",
                    "name": "Empty cart",
                    "visible": True,
                    "form_action": "/cart/clear",
                    "mutation_state": "cart:3",
                },
                {
                    "id": 3,
                    "role": "button",
                    "name": "Remove shoe",
                    "visible": True,
                    "form_action": "/cart/items/shoe-01/remove",
                },
            ],
        }
    )

    assert classify_guarded_mutation(snapshot, 1, "task-1") is None
    assert classify_guarded_mutation(snapshot, 3, "task-1") is None
    clear = classify_guarded_mutation(snapshot, 2, "task-1")
    assert clear is not None
    assert clear.action_type == "guarded_click"
    assert clear.target_signature == "button|Empty cart|POST /cart/clear"
    assert clear.arguments == (("cart_revision", "3"),)
    assert clear.state_signature == "cart:3"
