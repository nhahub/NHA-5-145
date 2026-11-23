"""Pure, disabled scheduling proposal; no SDK, environment discovery or apply."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class ObservationBindings:
    account: str
    controller: str
    group: str
    schedule: str
    execution_role: str
    start: datetime
    end: datetime

    def __post_init__(self):
        try:
            for name in ("account", "controller", "group", "schedule", "execution_role"):
                value = getattr(self, name)
                pattern = r"[0-9]{12}" if name == "account" else r"[A-Za-z0-9_-]{1,64}"
                if type(value) is not str or re.fullmatch(pattern, value) is None:
                    raise ValueError()
            if self.group == "default":
                raise ValueError()
            for value in (self.start, self.end):
                if (
                    type(value) is not datetime
                    or value.tzinfo is not UTC
                    or value.second
                    or value.microsecond
                ):
                    raise ValueError()
            if not timedelta(minutes=1) <= self.end - self.start <= timedelta(days=60):
                raise ValueError()
        except Exception:
            raise ValueError("Exact finite Stockholm observation bindings required") from None


def render_observation(bindings):
    if type(bindings) is not ObservationBindings:
        raise ValueError("Validated observation bindings required")
    bindings.__post_init__()
    b = bindings
    function = f"arn:aws:lambda:eu-north-1:{b.account}:function:{b.controller}"
    group = f"arn:aws:scheduler:eu-north-1:{b.account}:schedule-group/{b.group}"
    retry = {"MaximumEventAgeInSeconds": 60, "MaximumRetryAttempts": 0}

    def policy(statement):
        return {"Version": "2012-10-17", "Statement": [statement]}

    def alarm(suffix, namespace, metric, dimension, *, missing=False):
        return {
            "AlarmName": f"{b.group}-{b.schedule}-{suffix}",
            "ActionsEnabled": False,
            "Namespace": namespace,
            "MetricName": metric,
            "Dimensions": [dimension],
            "Statistic": "Sum",
            "Period": 60,
            "EvaluationPeriods": 5,
            "DatapointsToAlarm": 5 if missing else 1,
            "Threshold": 1,
            "ComparisonOperator": "LessThanThreshold"
            if missing
            else "GreaterThanOrEqualToThreshold",
            "TreatMissingData": "breaching" if missing else "notBreaching",
        }

    return {
        "schedule_group": {"Name": b.group},
        "execution_role": {
            "RoleName": b.execution_role,
            "AssumeRolePolicyDocument": policy(
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "scheduler.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": b.account,
                            "aws:SourceArn": group,
                        }
                    },
                }
            ),
        },
        "execution_permission": policy(
            {
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": function,
            }
        ),
        "schedule": {
            "Name": b.schedule,
            "GroupName": b.group,
            "State": "DISABLED",
            "ScheduleExpression": "rate(1 minute)",
            "ScheduleExpressionTimezone": "UTC",
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "StartDate": b.start.isoformat().replace("+00:00", "Z"),
            "EndDate": b.end.isoformat().replace("+00:00", "Z"),
            "ActionAfterCompletion": "NONE",
            "Target": {
                "Arn": function,
                "RoleArn": f"arn:aws:iam::{b.account}:role/{b.execution_role}",
                "Input": '{"kind":"tick"}',
                "RetryPolicy": dict(retry),
            },
        },
        "controller_configuration": {"FunctionName": function, "MemorySize": 256, "Timeout": 30},
        "controller_concurrency": {"FunctionName": function, "ReservedConcurrentExecutions": 1},
        "controller_async": {"FunctionName": function, **retry},
        "alarms": [
            alarm(
                "errors", "AWS/Lambda", "Errors", {"Name": "FunctionName", "Value": b.controller}
            ),
            alarm(
                "missing",
                "ShoppingCopilot/Lifecycle",
                "TickCompleted",
                {"Name": "Component", "Value": "Controller"},
                missing=True,
            ),
        ],
    }
