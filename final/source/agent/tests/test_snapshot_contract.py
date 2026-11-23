import pytest
from pydantic import ValidationError

from agent.schemas import parse_snapshot, to_wire
from agent.tests.contract_fixtures import load_fixture


def test_v1_snapshot_round_trips_shared_fixture_without_sensitive_value() -> None:
    payload = load_fixture("valid/snapshot.json")

    snapshot = parse_snapshot(payload)

    assert to_wire(snapshot) == payload
    sensitive_element = to_wire(snapshot)["elements"][1]
    assert sensitive_element["sensitive"] is True
    assert "value" not in sensitive_element


def test_v1_snapshot_accepts_integral_json_numbers() -> None:
    payload = load_fixture("valid/snapshot-integral-numbers.json")

    assert to_wire(parse_snapshot(payload)) == payload


@pytest.mark.parametrize(
    "fixture",
    [
        "invalid/snapshot-wrong-version.json",
        "invalid/snapshot-missing-url.json",
        "invalid/snapshot-sensitive-value.json",
        "invalid/snapshot-sensitive-options.json",
        "invalid/snapshot-sensitive-false.json",
        "invalid/snapshot-null-optional.json",
        "invalid/snapshot-unknown-field.json",
        "invalid/snapshot-python-field-alias.json",
    ],
)
def test_v1_snapshot_rejects_invalid_shared_fixtures(fixture: str) -> None:
    with pytest.raises(ValidationError):
        parse_snapshot(load_fixture(fixture))
