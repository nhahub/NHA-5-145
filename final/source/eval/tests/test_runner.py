import pytest

from eval.runner import authoritative_state_url, remaining_timeout_ms, state_value


def test_state_value_reads_nested_authoritative_state() -> None:
    state = {
        "filters": {
            "type": "running",
            "max_price": {"amount": "2000", "currency": "EGP"},
        },
        "product_count": 3,
    }

    assert state_value(state, "filters.type") == "running"
    assert state_value(state, "filters.max_price.amount") == "2000"
    assert state_value(state, "product_count") == 3


def test_remaining_timeout_rejects_an_expired_case() -> None:
    with pytest.raises(TimeoutError, match="Evaluation Case exceeded"):
        remaining_timeout_ms(0.0)


def test_authoritative_state_url_includes_the_category_and_filters() -> None:
    assert authoritative_state_url(
        "http://localhost:4000/c/bags?availability=unavailable&sort=newest"
    ) == ("http://localhost:4000/__test/state?category=bags&availability=unavailable&sort=newest")
