# CAP-06 Lambda Function URL/OAC contract: offline preparation

Checked 22 October 2026 against public primary AWS documentation. Used agent-reach
Exa search and the dedicated web reader; inspected the current repository adapter.
This is a design input, not a deployed template, IAM authorization result, cost
qualification, or cloud acceptance. No authenticated AWS calls, resources, DNS,
certificate requests, model calls, installs, or remote writes occurred. Existing
CAP-05 quota and deployment gates remain open. The original checkout's
`docs/graduation-scope.md` and ignored local spec were read because this worktree
does not contain them.

## Function URL access control

Use an ordinary Lambda **Function URL** with `AuthType: AWS_IAM`; do not confuse
it with the separately documented Lambda Web Function product. Attach an OAC
whose origin type is `lambda`, signing behavior `always`, and protocol `sigv4`.
`always` replaces viewer Authorization with CloudFront's signature. Keep shopper
invitation authority in the existing body/handler, independently of transport IAM.
[OAC configuration properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-originaccesscontrol-originaccesscontrolconfig.html).

AWS states that new Function URLs require both `lambda:InvokeFunctionUrl` and
`lambda:InvokeFunction` starting October 2025. Constrain the former to
`lambda:FunctionUrlAuthType=AWS_IAM`; constrain the latter to
`lambda:InvokedViaFunctionUrl=true`. The latter condition prevents this grant
from authorizing other invocation methods.
[Function URL access control](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html).

The CloudFront guide grants **both** actions to principal
`cloudfront.amazonaws.com`, each restricted to the exact distribution ARN
`arn:aws:cloudfront::<account>:distribution/<id>`. It also explicitly requires
viewer PUT/POST requests to supply the SHA-256 of the request body in
`x-amz-content-sha256`; Lambda does not accept unsigned payloads here. The viewer
does not need AWS credentials when CloudFront performs the origin signing.
[CloudFront Function URL OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-lambda.html).

For an offline CloudFormation permission fragment, use two
`AWS::Lambda::Permission` resources with the same exact function/alias,
CloudFront service principal and exact `SourceArn`. Set `FunctionUrlAuthType:
AWS_IAM` on the URL action and `InvokedViaFunctionUrl: true` on InvokeFunction.
`SourceArn` uses StringLike internally, so reject wildcard input. `SourceAccount`
is a supported property, but its existence does not prove every integration
supplies that context key. Do not mix these resources with
`AWS::Lambda::ResourcePolicy` on the same function.
[Lambda permission properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-permission.html).

The account-bearing exact CloudFront ARN already supplies the account bound:
IAM states that `aws:SourceAccount` is unnecessary when `aws:SourceArn` includes
the account ID. Follow the CloudFront-specific example rather than asserting
that an additional SourceAccount condition has been qualified.
[IAM source context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-sourcearn).

## Origin and behavior configuration

Represent the Function URL hostname without scheme/path as `Origin.DomainName`,
attach its `OriginAccessControlId`, and use `CustomOriginConfig` (not
`S3OriginConfig`). `CustomOriginConfig` is the CloudFormation form for origins
other than regular S3 or VPC origins. Keep OriginPath empty for the adapter's
exact `/`, `/status`, `/wake` routes.
[Distribution Origin](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-distribution-origin.html).

Select `OriginProtocolPolicy: https-only`, HTTPS port 443 and TLSv1.2. Explicitly
bound connection/read timeouts rather than using a long-lived startup request.
CloudFormation documents read timeout default 30 seconds and range 1–120 seconds;
availability of higher limits still requires eventual account qualification.
[CustomOriginConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-distribution-customoriginconfig.html).

POST requires CloudFront's all-seven-method AllowedMethods group:
GET/HEAD/OPTIONS/PUT/PATCH/POST/DELETE. There is no GET/HEAD/POST-only option.
The adapter must continue rejecting every unsupported method/path; HEAD/OPTIONS
need not become successful application operations. Keep CachedMethods GET/HEAD.
[CacheBehavior properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-distribution-cachebehavior.html).

Use managed `CachingDisabled` (`4135ea2d-6df8-44a3-9df3-4b5a84be39ad`) for the
dynamic adapter: all TTLs are zero. A positive minimum TTL can override no-store,
so the current response header alone is insufficient.
[Managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html).
Explicitly set relevant error-caching minimum TTLs to zero; AWS documents a
separate default of ten seconds. Do not remap service failures to successful HTML.
[Error caching](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/custom-error-pages-expiration.html).

Do not forward viewer Host: Function URLs expect the origin hostname.
`AllViewerExceptHostHeader` is intended for this service, but also forwards all
other viewer headers, cookies and query strings. That is broader than this
adapter requires.
[Managed origin request policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html#managed-origin-request-policy-allviewerexcepthostheader).
Prefer a custom origin request policy with header allowlist `Origin`,
`Content-Type`, `X-Amz-Content-Sha256`, no cookies and no query strings. AWS still
automatically includes protocol headers such as Host, User-Agent and X-Amz-Cf-Id;
the allowlist is not the entire delivered event header set.
[OriginRequestPolicyConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-originrequestpolicy-originrequestpolicyconfig.html),
[HeadersConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-cloudfront-originrequestpolicy-headersconfig.html).

CloudFront does not cache POST responses. It does not retry a POST after the
origin response read timeout, but that does not make an uncertain mutation safe
to replay. Retain the durable single-command claim protocol. `CachingDisabled`
also prevents request collapsing; preserve no automatic client retry.
[Custom origin behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html).

## Existing adapter audit and required follow-up

Observed in `agent/lifecycle/waiting.html`: `/wake` serializes `{code}` and sends
Content-Type application/json, with a five-second browser abort, but no payload
hash. Before enabling OAC, serialize once, UTF-8 encode that exact string, compute
SHA-256, send lowercase hexadecimal in x-amz-content-sha256, and use the same body
bytes/string for fetch. Cover Arabic, non-ASCII, escaped characters and an empty
code in a browser-level regression. Compute failure must send no wake request.
The digest is transport integrity, not invitation authorization. Preserve input
clearing, explicit retry, no logging and same-origin fetch.

Observed in `agent/lifecycle/startup.py`: HTTP-v2 only; no query/cookies; lower-case
ASCII headers; at most 32 headers/4 KiB; at most 1 KiB decoded body; same exact
generated CloudFront Origin and exact Content-Type for POST. It does not inspect
the IAM authorizer or authenticate OAC itself: deployed policy is the outer
boundary. Keep these checks and test a realistic event with OAC-added headers.
Do not substitute the origin Host for the viewer Origin check. Future generated
domain injection must match the exact distribution used by the permission.

Function URLs translate requests into the API Gateway payload-format 2.0 schema;
body/base64 flags, lower-case headers and combined duplicate headers must be
tested against the actual forwarded event. An offline synthetic fixture cannot
prove deployed transport compatibility.
[Function URL invocation schema](https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html).

Do not wait for EC2 readiness inside the HTTP request: retain 202 plus status
polling and a separately scheduled trusted executor/observer. Ordinary Lambda
invocations have a 900-second maximum, 6 MB synchronous request/response limit,
4 KiB environment aggregate, and finite concurrency; new accounts may have lower
quotas. These are service limits, not recommended application budgets.
[Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).
Python 3.12 remains a listed managed runtime; package dependencies for its Linux
runtime and separately verify the future deployed artifact/handler.
[Supported runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html).

## Exact DynamoDB runtime permission shape

Transactions authorize constituent Put/Update/Get/Delete through PutItem,
UpdateItem, GetItem, DeleteItem, and checks through ConditionCheckItem. Do not
invent a `dynamodb:TransactWriteItems` IAM action. AWS provides the
`dynamodb:EnclosingOperation` condition for restricting writes to transactions.
[Transaction IAM](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html).

For the inspected injected authority runtime, allow GetItem plus conditioned
PutItem/UpdateItem/ConditionCheckItem on one exact eu-north-1 table ARN. Add Query
only to a role that calls invitation listing/inspection; startup/lifecycle reads
use GetItem. No runtime Scan/DeleteItem/table-management action is present.
Separate the explicit initializer's standalone PutItem from runtime transaction
write grants. Apply exact namespace `ForAllValues:StringEquals` on
`dynamodb:LeadingKeys`; LeadingKeys is supported by these actions.
[DynamoDB authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_dynamodb.html).
LeadingKeys is the partition key, and AWS requires the ForAllValues modifier.
It does not bind the sort key or distinguish invitation/admin/lifecycle methods
sharing this namespace; code checks and role separation remain necessary.
[Fine-grained conditions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/specifying-conditions.html).

## Optional private S3 release origin

For a separate release/static-artifact origin, use the S3 REST endpoint, bucket
owner enforced ownership and Block Public Access. S3 website endpoints cannot
use OAC. Use a separate `s3` OAC with `always` signing, and a bucket statement
granting only s3:GetObject on the intended object prefix to
cloudfront.amazonaws.com, conditioned on the exact account-bearing distribution
SourceArn. Do not grant viewer writes/ListBucket. SSE-KMS would need a separately
scoped key policy; do not assume bucket permission alone is sufficient.
[S3 OAC prerequisites and read policy](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).

## Acceptance still required

An offline policy/fragment can be reviewed and tested for exact identities,
actions and conditions, but does not prove IAM evaluation. Future authorized
cloud qualification must show direct unsigned Function URL denial, correct
distribution success, another distribution denial, POST digest success/failure,
safe status/error freshness, actual HTTP-v2 header bounds, runtime role namespace
denial outside its partition, no credential leakage, and unchanged uncertain
command behavior. Factory selection, scheduling, EC2 observation/readiness,
artifact publication, resource creation and deployment remain separate work.
