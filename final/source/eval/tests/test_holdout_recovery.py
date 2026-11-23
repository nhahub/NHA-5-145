import pytest

from eval.holdout_recovery import recoverable


@pytest.mark.parametrize("status", ["complete", "inflight", "interrupted"])
def test_prediction_attempts_are_never_startup_recovered(status):
    assert not recoverable({"attempts": {"a": {"status": status}}})


def test_only_startup_failures_before_prediction_are_recoverable():
    assert recoverable({"attempts": {"a": {"status": "startup_failure"}}})
    assert not recoverable({"attempts": {}})
