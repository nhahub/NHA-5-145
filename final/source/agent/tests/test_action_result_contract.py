import pytest
from pydantic import ValidationError

from agent.schemas import parse_action_result, to_wire
from agent.tests.contract_fixtures import load_fixture


def test_v1_action_result_round_trips_shared_fixture() -> None:
    payload = load_fixture("valid/action-result.json")

    result = parse_action_result(payload)

    assert to_wire(result) == payload


@pytest.mark.parametrize(
    "fixture",
    [
        "invalid/action-result-wrong-version.json",
        "invalid/action-result-missing-status.json",
        "invalid/action-result-unknown-status.json",
        "invalid/action-result-unknown-field.json",
    ],
)
def test_v1_action_result_rejects_invalid_shared_fixtures(fixture: str) -> None:
    with pytest.raises(ValidationError):
        parse_action_result(load_fixture(fixture))
