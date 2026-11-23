"""Pure access-document preparation, deliberately not a deployable stack or CLI."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudAccessBindings:
    account: str
    instance: str
    table: str
    namespace: str
    distribution: str
    startup: str
    controller: str
    bucket: str

    def __post_init__(self):
        patterns = {
            "account": r"[0-9]{12}",
            "instance": r"i-[0-9a-f]{17}",
            "table": r"[A-Za-z0-9_.-]{3,255}",
            "namespace": r"[A-Za-z0-9_-]{1,64}",
            "distribution": r"E[A-Z0-9]{1,31}",
            "startup": r"[A-Za-z0-9_-]{1,64}",
            "controller": r"[A-Za-z0-9_-]{1,64}",
            "bucket": r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]",
        }
        for name, pattern in patterns.items():
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(pattern, value) is None:
                raise ValueError("Exact bounded deployment identifiers required")
        if (
            self.startup == self.controller
            or self.bucket.startswith(("xn--", "sthree-", "amzn-s3-demo-"))
            or self.bucket.endswith(("-s3alias", "--ol-s3", "--x-s3", "--table-s3"))
        ):
            raise ValueError("Distinct functions and plain general-purpose bucket required")


def render_cloud_access(bindings):
    if type(bindings) is not CloudAccessBindings:
        raise ValueError("Validated fixed deployment bindings required")
    bindings.__post_init__()
    b = bindings
    region = "eu-north-1"
    table = f"arn:aws:dynamodb:{region}:{b.account}:table/{b.table}"
    host = f"arn:aws:ec2:{region}:{b.account}:instance/{b.instance}"
    distribution = f"arn:aws:cloudfront::{b.account}:distribution/{b.distribution}"

    def function(name):
        return f"arn:aws:lambda:{region}:{b.account}:function:{name}"

    def statement(sid, actions, resource, extra=None):
        return {
            "Sid": sid,
            "Effect": "Allow",
            "Action": actions,
            "Resource": resource,
            "Condition": {"StringEquals": {"aws:RequestedRegion": region}, **(extra or {})},
        }

    def role(name, *, controller=False):
        partition = {
            "ForAllValues:StringEquals": {"dynamodb:LeadingKeys": [b.namespace]},
            "Null": {"dynamodb:LeadingKeys": "false"},
        }
        statements = [
            statement("AuthorityRead", ["dynamodb:GetItem"], table, partition),
            statement(
                "AuthorityTransactions",
                ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:ConditionCheckItem"],
                table,
                {
                    **partition,
                    "ForAnyValue:StringEquals": {
                        "dynamodb:EnclosingOperation": ["TransactWriteItems"]
                    },
                },
            ),
            statement(
                "OwnLogStreams",
                ["logs:CreateLogStream", "logs:PutLogEvents"],
                f"arn:aws:logs:{region}:{b.account}:log-group:/aws/lambda/{name}:log-stream:*",
            ),
        ]
        if controller:
            statements.extend(
                [
                    statement("DesignatedHost", ["ec2:StartInstances", "ec2:StopInstances"], host),
                    statement("DescribeHost", ["ec2:DescribeInstances"], "*"),
                ]
            )
        else:
            statements.append(
                statement("DispatchController", ["lambda:InvokeFunction"], function(b.controller))
            )
        return {
            "trust": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            "policy": {"Version": "2012-10-17", "Statement": statements},
        }

    def origin_statement(action, resource, extra=None):
        return {
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": action,
            "Resource": resource,
            "Condition": {"ArnEquals": {"AWS:SourceArn": distribution}, **(extra or {})},
        }

    return {
        "schema": 1,
        "region": region,
        "runtime": {"startup": role(b.startup), "controller": role(b.controller, controller=True)},
        "lambda_url": {
            "AuthType": "AWS_IAM",
            "Policy": {
                "Version": "2012-10-17",
                "Statement": [
                    origin_statement(
                        "lambda:InvokeFunctionUrl",
                        function(b.startup),
                        {"StringEquals": {"lambda:FunctionUrlAuthType": "AWS_IAM"}},
                    ),
                    origin_statement(
                        "lambda:InvokeFunction",
                        function(b.startup),
                        {"Bool": {"lambda:InvokedViaFunctionUrl": "true"}},
                    ),
                ],
            },
        },
        "s3_policy": {
            "Version": "2012-10-17",
            "Statement": [origin_statement("s3:GetObject", f"arn:aws:s3:::{b.bucket}/waiting/*")],
        },
        "oac": {
            kind: {
                "Name": f"scpilot-{kind}-{b.distribution.lower()}",
                "OriginAccessControlOriginType": kind,
                "SigningBehavior": "always",
                "SigningProtocol": "sigv4",
            }
            for kind in ("lambda", "s3")
        },
        "control_delivery": {
            "ViewerProtocolPolicy": "https-only",
            "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
            "AllowedMethods": ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
            "CachedMethods": ["GET", "HEAD"],
            "OriginRequestPolicyConfig": {
                "Name": f"scpilot-control-{b.distribution.lower()}",
                "HeadersConfig": {
                    "HeaderBehavior": "whitelist",
                    "Headers": ["origin", "content-type", "x-amz-content-sha256"],
                },
                "CookiesConfig": {"CookieBehavior": "none"},
                "QueryStringsConfig": {"QueryStringBehavior": "none"},
            },
            "CustomErrorResponses": [
                {"ErrorCode": code, "ErrorCachingMinTTL": 0}
                for code in (400, 403, 404, 405, 414, 416, 500, 501, 502, 503, 504)
            ],
        },
        "precreated_log_groups": [
            {"LogGroupName": f"/aws/lambda/{name}", "RetentionInDays": 7}
            for name in (b.startup, b.controller)
        ],
    }
