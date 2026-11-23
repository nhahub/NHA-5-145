"""Pure, fixed-resource IAM/schedule documents for the approved operating window."""

import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from agent.admission.dynamodb import _identifier
from agent.lifecycle.operating import OperatingPolicy
from deploy.cloud_access import CloudAccessBindings, render_cloud_access


def stamp(epoch):
    return datetime.fromtimestamp(epoch, UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class GuardBindings:
    account: str
    table: str
    namespace: str
    invitation_identity: str
    lifecycle_identity: str
    policy: OperatingPolicy
    startup: str
    controller: str
    guard: str
    scheduler: str
    bucket: str
    distribution: str
    allocation: str
    security_group: str
    baseline_credits: str
    nameservers: tuple

    def __post_init__(self):
        try:
            for name, pattern in (
                ("account", r"[0-9]{12}"),
                ("table", r"[A-Za-z0-9_.-]{3,255}"),
                ("namespace", r"[A-Za-z0-9_-]{1,64}"),
                *(
                    (n, r"[A-Za-z0-9_-]{1,64}")
                    for n in ("startup", "controller", "guard", "scheduler")
                ),
                ("bucket", r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]"),
                ("distribution", r"E[A-Z0-9]{1,31}"),
                ("allocation", r"eipalloc-[0-9a-f]{17}"),
                ("security_group", r"sg-[0-9a-f]{17}"),
            ):
                value = getattr(self, name)
                if type(value) is not str or re.fullmatch(pattern, value) is None:
                    raise ValueError()
            _identifier(self.invitation_identity)
            _identifier(self.lifecycle_identity)
            if type(self.policy) is not OperatingPolicy:
                raise ValueError()
            self.policy.__post_init__()
            credits = Decimal(self.baseline_credits)
            if (
                type(self.baseline_credits) is not str
                or not credits.is_finite()
                or not 65 <= credits <= 1_000_000
            ):
                raise ValueError()
            if len({self.startup, self.controller, self.guard, self.scheduler}) != 4:
                raise ValueError()
            if type(self.nameservers) not in (tuple, list) or len(self.nameservers) != 4:
                raise ValueError()
            servers = []
            for item in self.nameservers:
                if type(item) is dict and set(item) == {"name", "ip"}:
                    name, address = item["name"], item["ip"]
                elif type(item) is tuple and len(item) == 2:
                    name, address = item
                else:
                    raise ValueError()
                if type(name) is not str or re.fullmatch(r"[a-z0-9.-]{1,253}", name) is None:
                    raise ValueError()
                ipaddress.IPv4Address(address)
                servers.append((name, address))
            if len(set(servers)) != 4 or len({row[0] for row in servers}) != 4:
                raise ValueError()
            object.__setattr__(self, "nameservers", tuple(servers))
        except Exception:
            raise ValueError(
                "Exact owned guard bindings and eligible credit margin required"
            ) from None

    def values(self):
        self.__post_init__()
        return {
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name not in {"policy", "nameservers"}
            },
            "policy": self.policy.values(),
            "nameservers": [{"name": name, "ip": address} for name, address in self.nameservers],
        }

    @classmethod
    def parse(cls, value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Exact guard configuration required")
        return cls(**{**value, "policy": OperatingPolicy.parse(value["policy"])})


def render_operating(bindings):
    if type(bindings) is not GuardBindings:
        raise ValueError("Validated guard bindings required")
    bindings.__post_init__()
    b = bindings
    region = f"arn:aws:ec2:eu-north-1:{b.account}:"

    def role(name):
        return f"arn:aws:iam::{b.account}:role/{name}"

    def function(name):
        return f"arn:aws:lambda:eu-north-1:{b.account}:function:{name}"

    table = f"arn:aws:dynamodb:eu-north-1:{b.account}:table/{b.table}"
    start_grant = {
        "Sid": "FiniteInvitedOperationStart",
        "Effect": "Allow",
        "Action": ["ec2:StartInstances"],
        "Resource": region + "instance/" + b.policy.instance,
        "Condition": {
            "StringEquals": {"aws:RequestedRegion": "eu-north-1"},
            "DateGreaterThanEquals": {"aws:CurrentTime": stamp(b.policy.opens)},
            "DateLessThan": {"aws:CurrentTime": stamp(b.policy.closes)},
        },
    }
    access = render_cloud_access(
        CloudAccessBindings(
            b.account,
            b.policy.instance,
            b.table,
            b.namespace,
            b.distribution,
            b.startup,
            b.controller,
            b.bucket,
        )
    )
    stop_only = json.loads(json.dumps(access["runtime"]["controller"]["policy"]))
    for statement in stop_only["Statement"]:
        statement["Action"] = [a for a in statement["Action"] if a != "ec2:StartInstances"]
    controller_policy = {
        "Version": "2012-10-17",
        "Statement": [*stop_only["Statement"], start_grant],
    }

    def allow(actions, resource, condition=None):
        return {
            "Effect": "Allow",
            "Action": actions,
            "Resource": resource,
            **({"Condition": condition} if condition else {}),
        }

    partition = {
        "ForAllValues:StringEquals": {"dynamodb:LeadingKeys": [b.namespace]},
        "Null": {"dynamodb:LeadingKeys": "false"},
    }
    guard_policy = {
        "Version": "2012-10-17",
        "Statement": [
            allow(["dynamodb:GetItem"], table, partition),
            allow(
                ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:ConditionCheckItem"],
                table,
                {
                    **partition,
                    "ForAnyValue:StringEquals": {
                        "dynamodb:EnclosingOperation": ["TransactWriteItems"]
                    },
                },
            ),
            allow(
                ["ec2:DescribeInstances", "ec2:DescribeAddresses", "ec2:DescribeSecurityGroups"],
                "*",
                {"StringEquals": {"aws:RequestedRegion": "eu-north-1"}},
            ),
            allow(["ec2:StopInstances"], region + "instance/" + b.policy.instance),
            allow(
                ["ec2:DisassociateAddress", "ec2:ReleaseAddress"],
                region + "elastic-ip/" + b.allocation,
                {"StringEquals": {"ec2:ResourceTag/OwnerOperation": b.policy.operation}},
            ),
            allow(
                ["ec2:RevokeSecurityGroupIngress"], region + "security-group/" + b.security_group
            ),
            allow(["iam:PutRolePolicy", "iam:GetRolePolicy"], role(b.controller)),
            allow(
                ["lambda:PutFunctionConcurrency", "lambda:GetFunctionConcurrency"],
                function(b.startup),
            ),
            allow(
                [
                    "cloudfront:GetDistributionConfig",
                    "cloudfront:GetDistribution",
                    "cloudfront:UpdateDistribution",
                ],
                f"arn:aws:cloudfront::{b.account}:distribution/{b.distribution}",
            ),
            allow(["s3:GetObject", "s3:PutObject"], f"arn:aws:s3:::{b.bucket}/guard/*"),
            allow(["freetier:GetAccountPlanState"], "*"),
            allow(["cloudwatch:GetMetricData"], "*"),
            allow(
                ["logs:CreateLogStream", "logs:PutLogEvents"],
                f"arn:aws:logs:eu-north-1:{b.account}:log-group:/aws/lambda/{b.guard}:log-stream:*",
            ),
        ],
    }
    scheduler_policy = {
        "Version": "2012-10-17",
        "Statement": [
            allow(["lambda:InvokeFunction"], [function(b.controller), function(b.guard)]),
            allow(["ec2:StopInstances"], region + "instance/" + b.policy.instance),
        ],
    }

    def recurring(name, expression, target, end):
        return {
            "Name": name,
            "GroupName": b.scheduler,
            "State": "DISABLED",
            "ScheduleExpression": expression,
            "ScheduleExpressionTimezone": "UTC",
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "StartDate": stamp(b.policy.opens),
            "EndDate": stamp(end),
            "ActionAfterCompletion": "NONE",
            "Target": {
                "Arn": function(target),
                "RoleArn": role(b.scheduler),
                "Input": json.dumps({"kind": "tick" if target == b.controller else "guard"}),
                "RetryPolicy": {"MaximumEventAgeInSeconds": 60, "MaximumRetryAttempts": 0},
            },
        }

    schedules = [
        recurring("tick", "rate(1 minute)", b.controller, b.policy.closes + 900),
        recurring("guard", "rate(5 minutes)", b.guard, b.policy.closes + 48 * 3600),
        {
            "Name": "deadline-stop",
            "GroupName": b.scheduler,
            "State": "DISABLED",
            "ScheduleExpression": "at(" + stamp(b.policy.closes)[:19] + ")",
            "ScheduleExpressionTimezone": "UTC",
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "ActionAfterCompletion": "NONE",
            "Target": {
                "Arn": "arn:aws:scheduler:::aws-sdk:ec2:stopInstances",
                "RoleArn": role(b.scheduler),
                "Input": json.dumps({"InstanceIds": [b.policy.instance]}),
                "RetryPolicy": {"MaximumEventAgeInSeconds": 900, "MaximumRetryAttempts": 2},
            },
        },
    ]
    return {
        "start_grant": start_grant,
        "controller_policy": controller_policy,
        "stop_policy": stop_only,
        "startup_policy": access["runtime"]["startup"]["policy"],
        "guard_policy": guard_policy,
        "scheduler_policy": scheduler_policy,
        "schedules": schedules,
        "guard_config": b.values(),
    }
