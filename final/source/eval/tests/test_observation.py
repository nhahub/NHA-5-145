"""Conditional configuration only: renderer never creates or enables resources."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from deploy.observation import ObservationBindings, render_observation


@pytest.fixture
def bindings():
    return ObservationBindings(
        account="123456789012",
        controller="copilot-controller",
        group="copilot-lifecycle",
        schedule="copilot-minute",
        execution_role="copilot-schedule-role",
        start=datetime(2026, 11, 1, tzinfo=UTC),
        end=datetime(2026, 12, 31, tzinfo=UTC),
    )


def test_bundle_is_fixed_disabled_and_has_finite_utc_window(bindings):
    bundle = render_observation(bindings)
    schedule = bundle["schedule"]
    arn = "arn:aws:lambda:eu-north-1:123456789012:function:copilot-controller"
    assert schedule["State"] == "DISABLED"
    assert schedule["ScheduleExpression"] == "rate(1 minute)"
    assert schedule["ScheduleExpressionTimezone"] == "UTC"
    assert schedule["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert schedule["StartDate"] == "2026-11-01T00:00:00Z"
    assert schedule["EndDate"] == "2026-12-31T00:00:00Z"
    assert schedule["ActionAfterCompletion"] == "NONE"
    assert schedule["Target"] == {
        "Arn": arn,
        "RoleArn": "arn:aws:iam::123456789012:role/copilot-schedule-role",
        "Input": '{"kind":"tick"}',
        "RetryPolicy": {"MaximumEventAgeInSeconds": 60, "MaximumRetryAttempts": 0},
    }
    assert bundle["controller_configuration"] == {
        "FunctionName": arn,
        "MemorySize": 256,
        "Timeout": 30,
    }
    assert bundle["controller_concurrency"] == {
        "FunctionName": arn,
        "ReservedConcurrentExecutions": 1,
    }
    assert bundle["controller_async"] == {
        "FunctionName": arn,
        "MaximumEventAgeInSeconds": 60,
        "MaximumRetryAttempts": 0,
    }


def test_role_trust_uses_exact_group_and_permission_only_invokes_controller(bindings):
    bundle = render_observation(bindings)
    statement = bundle["execution_role"]["AssumeRolePolicyDocument"]["Statement"]
    assert statement == [
        {
            "Effect": "Allow",
            "Principal": {"Service": "scheduler.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": "123456789012",
                    "aws:SourceArn": (
                        "arn:aws:scheduler:eu-north-1:123456789012:schedule-group/copilot-lifecycle"
                    ),
                }
            },
        }
    ]
    permission = bundle["execution_permission"]["Statement"]
    assert permission == [
        {
            "Effect": "Allow",
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:eu-north-1:123456789012:function:copilot-controller",
        }
    ]
    assert bundle["schedule_group"] == {"Name": bindings.group}


def test_alarms_cannot_send_notifications_or_count_browser_calls_as_ticks(bindings):
    errors, missing = render_observation(bindings)["alarms"]
    for alarm in (errors, missing):
        assert alarm["ActionsEnabled"] is False
        assert not any(k.endswith("Actions") for k in alarm)
        assert alarm["Period"] == 60 and alarm["EvaluationPeriods"] == 5
        assert alarm["Statistic"] == "Sum" and alarm["Threshold"] == 1
    assert errors["Namespace"] == "AWS/Lambda" and errors["MetricName"] == "Errors"
    assert errors["Dimensions"] == [{"Name": "FunctionName", "Value": bindings.controller}]
    assert errors["DatapointsToAlarm"] == 1 and errors["TreatMissingData"] == "notBreaching"
    assert missing["Namespace"] == "ShoppingCopilot/Lifecycle"
    assert missing["MetricName"] == "TickCompleted"
    assert missing["Dimensions"] == [{"Name": "Component", "Value": "Controller"}]
    assert missing["DatapointsToAlarm"] == 5 and missing["TreatMissingData"] == "breaching"


@pytest.mark.parametrize(
    "field,value",
    [
        ("account", "123"),
        ("account", 123456789012),
        ("controller", "some:alias"),
        ("group", "*"),
        ("schedule", "../bad"),
        ("execution_role", "role/path"),
        ("start", datetime(2026, 11, 1)),
        ("end", datetime(2027, 1, 1, tzinfo=UTC)),
        ("end", datetime(2026, 11, 1, tzinfo=UTC)),
        ("start", "2026-11-01"),
    ],
)
def test_invalid_or_excessive_scope_refuses(bindings, field, value):
    with pytest.raises(ValueError):
        replace(bindings, **{field: value})


def test_no_non_utc_or_subminute_dates_and_no_rebound_dataclass(bindings):
    from datetime import timezone

    with pytest.raises(ValueError):
        replace(bindings, start=bindings.start.astimezone(timezone(timedelta(hours=2))))
    with pytest.raises(ValueError):
        replace(bindings, start=bindings.start + timedelta(seconds=1))
    object.__setattr__(bindings, "group", "*")
    with pytest.raises(ValueError):
        render_observation(bindings)
    with pytest.raises(ValueError):
        render_observation({})
