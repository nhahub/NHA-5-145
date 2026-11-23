from eval.gemini_cart import acceptable_intent


def test_evaluation_rejects_unnecessary_clarification_even_with_correct_operation():
    expected = {"intent": "cart_edit", "cart_operation": "add"}
    assert acceptable_intent(
        {**expected, "needs_clarification": False, "missing_fields": [], "conflicting_fields": []},
        expected,
    )
    assert not acceptable_intent(
        {**expected, "needs_clarification": True, "missing_fields": ["query"]}, expected
    )
    assert not acceptable_intent(
        {**expected, "needs_clarification": False, "conflicting_fields": ["color"]}, expected
    )
