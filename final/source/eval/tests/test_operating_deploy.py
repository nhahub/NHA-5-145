"""Pure ownership/date policy and independent schedules, not real permissions."""

import importlib
import importlib.util
import json
from uuid import uuid4

import pytest

from agent.lifecycle.operating import OperatingPolicy


def renderer():
    if importlib.util.find_spec("deploy.operating") is None:
        pytest.fail("Finite cloud operating renderer is not implemented")
    return importlib.import_module("deploy.operating")


def fixture():
    return dict(
        account="123456789012",
        table="existing-authority",
        namespace="accepted",
        invitation_identity=str(uuid4()),
        lifecycle_identity=str(uuid4()),
        policy=OperatingPolicy(
            str(uuid4()), "a" * 64, "i-0123456789abcdef0", 1793750400, 1796421540
        ),
        startup="scpilot-dec-startup",
        controller="scpilot-dec-controller",
        guard="scpilot-dec-guard",
        scheduler="scpilot-dec-scheduler",
        bucket="scpilot-dec-private-assets",
        distribution="E123456789",
        allocation="eipalloc-0123456789abcdef0",
        security_group="sg-0123456789abcdef0",
        baseline_credits="179.30",
        nameservers=[{"name": f"ns{i}.example.net", "ip": f"192.0.2.{i}"} for i in range(1, 5)],
    )


def test_render_has_three_finite_schedules_and_independent_exact_stop():
    m = renderer()
    bindings = m.GuardBindings(**fixture())
    result = m.render_operating(bindings)
    assert len(result["schedules"]) == 3
    deadline = result["schedules"][2]
    assert deadline["Target"]["Arn"] == "arn:aws:scheduler:::aws-sdk:ec2:stopInstances"
    assert json.loads(deadline["Target"]["Input"]) == {"InstanceIds": [bindings.policy.instance]}
    assert deadline["ScheduleExpressionTimezone"] == "UTC"
    assert deadline["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert deadline["Target"]["RetryPolicy"] == {
        "MaximumEventAgeInSeconds": 900,
        "MaximumRetryAttempts": 2,
    }
    assert result["schedules"][1]["EndDate"].endswith("Z")


def test_guard_policy_cannot_start_renew_or_change_provider():
    m = renderer()
    result = m.render_operating(m.GuardBindings(**fixture()))
    policy = result["guard_policy"]
    text = json.dumps(policy)
    assert "ec2:StartInstances" not in text
    assert "scheduler:CreateSchedule" not in text
    assert "bedrock" not in text.lower() and "openrouter" not in text.lower()
    assert "ec2:StopInstances" in text and "ec2:ReleaseAddress" in text
    start = result["start_grant"]
    assert start["Action"] == ["ec2:StartInstances"]
    assert start["Condition"]["DateLessThan"]["aws:CurrentTime"]
    assert start["Condition"]["DateGreaterThanEquals"]["aws:CurrentTime"]
    assert "instance/i-0123456789abcdef0" in start["Resource"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("baseline_credits", "64.99"),
        ("distribution", "*"),
        ("allocation", "eipalloc-other"),
        ("nameservers", []),
    ],
)
def test_renderer_refuses_missing_ownership_or_credit_margin(field, value):
    m = renderer()
    values = fixture()
    values[field] = value
    with pytest.raises(ValueError):
        m.GuardBindings(**values)
