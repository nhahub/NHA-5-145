"""Offline access documents; no credentials, SDK clients or AWS policy simulator."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from deploy.cloud_access import CloudAccessBindings, render_cloud_access


@pytest.fixture
def bindings():
    return CloudAccessBindings(
        account="123456789012",
        instance="i-0123456789abcdef0",
        table="copilot-control",
        namespace="demo",
        distribution="E123EXAMPLE",
        startup="copilot-startup",
        controller="copilot-controller",
        bucket="copilot-example-bucket",
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("account", "*"),
        ("account", 123456789012),
        ("account", "123456789012:evil"),
        ("instance", "i-0123456789abcdef0*"),
        ("table", "table/index/*"),
        ("namespace", "demo*"),
        ("distribution", "E123*"),
        ("distribution", "e123"),
        ("startup", "function:evil"),
        ("controller", "copilot-startup"),
        ("bucket", "Bucket"),
        ("bucket", "bucket/path"),
        ("bucket", "a..bucket"),
        ("bucket", "192.168.1.1"),
        ("bucket", "a.-bucket"),
        ("bucket", "a-.bucket"),
        ("bucket", "a" * 64),
        ("namespace", []),
    ],
)
def test_cloud_bindings_refuse_injection_or_ambiguous_targets(bindings, field, bad):
    with pytest.raises(ValueError):
        replace(bindings, **{field: bad})


def test_cloud_bundle_is_deterministic_and_bindings_are_frozen(bindings):
    assert json.dumps(render_cloud_access(bindings), sort_keys=True) == json.dumps(
        render_cloud_access(bindings), sort_keys=True
    )
    with pytest.raises(FrozenInstanceError):
        bindings.instance = "i-11111111111111111"


def test_runtime_iam_has_exact_scope_and_transaction_actions(bindings):
    bundle = render_cloud_access(bindings)
    table = "arn:aws:dynamodb:eu-north-1:123456789012:table/copilot-control"
    instance = "arn:aws:ec2:eu-north-1:123456789012:instance/i-0123456789abcdef0"
    controller = "arn:aws:lambda:eu-north-1:123456789012:function:copilot-controller"
    for name, role in bundle["runtime"].items():
        assert role["trust"] == {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        statements = {item["Sid"]: item for item in role["policy"]["Statement"]}
        read, write = statements["AuthorityRead"], statements["AuthorityTransactions"]
        assert read["Action"] == ["dynamodb:GetItem"]
        assert write["Action"] == [
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:ConditionCheckItem",
        ]
        for statement in (read, write):
            assert statement["Resource"] == table
            assert statement["Condition"]["ForAllValues:StringEquals"] == {
                "dynamodb:LeadingKeys": ["demo"]
            }
            assert statement["Condition"]["Null"] == {"dynamodb:LeadingKeys": "false"}
        assert write["Condition"]["ForAnyValue:StringEquals"] == {
            "dynamodb:EnclosingOperation": ["TransactWriteItems"]
        }
        logs = statements["OwnLogStreams"]
        assert logs["Action"] == ["logs:CreateLogStream", "logs:PutLogEvents"]
        function = bindings.startup if name == "startup" else bindings.controller
        assert (
            logs["Resource"]
            == f"arn:aws:logs:eu-north-1:123456789012:log-group:/aws/lambda/{function}:log-stream:*"
        )
        if name == "startup":
            assert statements["DispatchController"]["Resource"] == controller
            assert statements["DispatchController"]["Action"] == ["lambda:InvokeFunction"]
            assert not any(
                action.startswith("ec2:")
                for item in statements.values()
                for action in item["Action"]
            )
        else:
            assert statements["DesignatedHost"]["Resource"] == instance
            assert statements["DesignatedHost"]["Action"] == [
                "ec2:StartInstances",
                "ec2:StopInstances",
            ]
            assert statements["DescribeHost"]["Resource"] == "*"
        for item in statements.values():
            assert item["Condition"]["StringEquals"]["aws:RequestedRegion"] == "eu-north-1"
            assert all("*" not in action for action in item["Action"])
            assert "dynamodb:TransactWriteItems" not in item["Action"]
    assert bundle["precreated_log_groups"] == [
        {"LogGroupName": "/aws/lambda/copilot-startup", "RetentionInDays": 7},
        {"LogGroupName": "/aws/lambda/copilot-controller", "RetentionInDays": 7},
    ]


def test_cloudfront_url_policy_requires_both_permissions_and_exact_distribution(bindings):
    url = render_cloud_access(bindings)["lambda_url"]
    assert url["AuthType"] == "AWS_IAM"
    statements = url["Policy"]["Statement"]
    assert [s["Action"] for s in statements] == [
        "lambda:InvokeFunctionUrl",
        "lambda:InvokeFunction",
    ]
    for statement in statements:
        assert statement["Principal"] == {"Service": "cloudfront.amazonaws.com"}
        assert (
            statement["Resource"]
            == "arn:aws:lambda:eu-north-1:123456789012:function:copilot-startup"
        )
        assert statement["Condition"]["ArnEquals"] == {
            "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/E123EXAMPLE"
        }
    assert statements[0]["Condition"]["StringEquals"] == {"lambda:FunctionUrlAuthType": "AWS_IAM"}
    assert statements[1]["Condition"]["Bool"] == {"lambda:InvokedViaFunctionUrl": "true"}


def test_s3_oac_cannot_read_release_or_backup_objects(bindings):
    statement = render_cloud_access(bindings)["s3_policy"]["Statement"][0]
    assert statement["Principal"] == {"Service": "cloudfront.amazonaws.com"}
    assert statement["Action"] == "s3:GetObject"
    assert statement["Resource"] == "arn:aws:s3:::copilot-example-bucket/waiting/*"
    assert statement["Condition"]["ArnEquals"]["AWS:SourceArn"].endswith("/E123EXAMPLE")


def test_control_forwarding_and_cache_settings_preserve_private_post_contract(bindings):
    bundle = render_cloud_access(bindings)
    for kind in ("lambda", "s3"):
        assert bundle["oac"][kind]["OriginAccessControlOriginType"] == kind
        assert bundle["oac"][kind]["SigningBehavior"] == "always"
        assert bundle["oac"][kind]["SigningProtocol"] == "sigv4"
    delivery = bundle["control_delivery"]
    assert delivery["CachePolicyId"] == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    assert delivery["AllowedMethods"] == [
        "GET",
        "HEAD",
        "OPTIONS",
        "PUT",
        "PATCH",
        "POST",
        "DELETE",
    ]
    assert delivery["CachedMethods"] == ["GET", "HEAD"]
    assert delivery["ViewerProtocolPolicy"] == "https-only"
    policy = delivery["OriginRequestPolicyConfig"]
    assert policy["HeadersConfig"] == {
        "HeaderBehavior": "whitelist",
        "Headers": ["origin", "content-type", "x-amz-content-sha256"],
    }
    assert policy["CookiesConfig"] == {"CookieBehavior": "none"}
    assert policy["QueryStringsConfig"] == {"QueryStringBehavior": "none"}
    assert {entry["ErrorCode"] for entry in delivery["CustomErrorResponses"]} == {
        400,
        403,
        404,
        405,
        414,
        416,
        500,
        501,
        502,
        503,
        504,
    }
    assert all(entry["ErrorCachingMinTTL"] == 0 for entry in delivery["CustomErrorResponses"])
