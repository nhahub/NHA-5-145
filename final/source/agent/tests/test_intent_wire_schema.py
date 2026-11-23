"""The provider grammar must not invite fields the chosen operation rejects."""

import pytest

from agent.llm.intent_wire import wire_intent_adapter


def test_cart_wire_rejects_discovery_fields_but_preserves_the_complete_add_goal():
    payload = dict(
        v=10,
        language="ar",
        dialect="egyptian_arabic",
        intent="cart_edit",
        constraints={"size": "43", "color": "blue"},
        missing_fields=[],
        needs_clarification=False,
        cart_operation="add",
        product_id="shoe-12",
        cart_quantity=1,
        cart_quantity_mode="set",
    )
    assert wire_intent_adapter.validate_python(payload).product_id == "shoe-12"
    payload["constraints"]["category"] = "shoes"
    with pytest.raises(ValueError):
        wire_intent_adapter.validate_python(payload)


@pytest.mark.parametrize("operation", ["advice", "find_products"])
def test_discovery_wire_retains_negation_and_price_constraints(operation):
    payload = dict(
        v=10,
        language="en",
        dialect="english",
        intent=operation,
        constraints={"category": "shoes", "max_price": {"amount": "2000", "currency": "EGP"}},
        missing_fields=[],
        needs_clarification=False,
        catalogue_requirements=[
            dict(kind="feature", value="leather", source="not leather", excluded=True)
        ],
    )
    result = wire_intent_adapter.validate_python(payload)
    assert result.catalogue_requirements[0].excluded
    assert result.constraints.max_price.amount == "2000"
    with pytest.raises(ValueError):
        wire_intent_adapter.validate_python({**payload, "cart_operation": "add"})
