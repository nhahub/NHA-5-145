import pytest
from pydantic import ValidationError

from agent.schemas import parse_action, to_wire
from agent.tests.contract_fixtures import load_fixture


def test_v1_action_round_trips_shared_fixture() -> None:
    payload = load_fixture("valid/action.json")

    action = parse_action(payload)

    assert to_wire(action) == payload


def test_v1_action_union_round_trips_every_shared_variant() -> None:
    payloads = load_fixture("valid/action-variants.json")
    assert isinstance(payloads, list)

    assert [to_wire(parse_action(payload)) for payload in payloads] == payloads


def test_v1_action_accepts_integral_json_numbers() -> None:
    payload = load_fixture("valid/action-integral-numbers.json")

    assert to_wire(parse_action(payload)) == payload


@pytest.mark.parametrize(
    "fixture",
    [
        "invalid/action-wrong-version.json",
        "invalid/action-missing-task-id.json",
        "invalid/action-unknown-type.json",
        "invalid/action-fractional-sequence.json",
        "invalid/action-unsafe-integer.json",
        "invalid/action-unknown-field.json",
    ],
)
def test_v1_action_rejects_invalid_shared_fixtures(fixture: str) -> None:
    with pytest.raises(ValidationError):
        parse_action(load_fixture(fixture))
