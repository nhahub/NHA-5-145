# CAP-05 account access preflight — 20 October 2026

**Current frontier:** two separately approved diagnostics failed; the second
returned ThrottlingException / HTTP429. Read-only applied GPT-OSS20B RPM/TPM and
Nova Lite on-demand shortlist quotas are zero. Both diagnostic ledgers are
disabled, USD0.03 held across USD0.04 cumulative authorization, actual billing
unknown. No additional call is authorized. See the applied-zero-quota section and
[durable evidence](../../eval/evidence/cap05-diagnostic-20261020/README.md).

The initial research below predates authenticated access and the diagnostic calls;
its no-call/no-login statements describe that earlier stage. The subsequent
account observations and quota section supersede that initial state. Constraints
remain Free plan, Stockholm and USD0 cash; no upgrade or application deployment.

## Historical first access action — completed

In the existing **Stockholm project console**, open the ordinary **CloudShell**
panel. When its Bash prompt is ready, run only:

```bash
AWS_MAX_ATTEMPTS=1 aws bedrock get-foundation-model-availability --model-id openai.gpt-oss-20b-1:0 --region eu-north-1 --output json --no-cli-pager
```

This is a signed Bedrock control-plane **GET**, with no request body; it does not
invoke the model or create a model agreement. Share the resulting availability
JSON or the short error, excluding account identifiers if present. Do not share
credentials, browser tokens, configuration/cache files or debug logs.
[API contract](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetFoundationModelAvailability.html),
[CLI command](https://docs.aws.amazon.com/cli/latest/reference/bedrock/get-foundation-model-availability.html).

CloudShell is explicitly included in the **new project-based experience's Free
Tier**, alongside Bedrock and AWS SDKs & Tools. The new-project monitoring guide
explicitly recommends CloudShell when the local CLI is not configured and says
the project user automatically has the correct IAM permissions to access it.
Therefore an upgrade/advanced-features requirement must not be assumed from the
account's Region restrictions. Actual account launch/result remains unverified;
the visible link alone is not that evidence.
[New-experience supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html),
[project-specific CloudShell/CLI instructions](https://docs.aws.amazon.com/accounts/latest/reference/monitor-your-project.html).

CloudShell uses console credentials automatically and has AWS CLI v2 installed.
It runs an AWS-managed compute environment and persistent home storage when
launched; it is not literally zero service state. Its ordinary service has no
additional charge, although resources/traffic used through it can be charged.
Use the ordinary panel, not creation of a VPC environment or other resources.
Stockholm has a documented CloudShell endpoint. If an upgrade, access-denied or
advanced-features screen appears, stop and record it; do not work around it by
switching Regions or changing IAM/account settings.
[CloudShell operation/pricing](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html),
[Stockholm endpoint](https://docs.aws.amazon.com/general/latest/gr/cloudshell.html).

## Exact response and interpretation

| Field                                | Documented values                                |
| ------------------------------------ | ------------------------------------------------ |
| `modelId`                            | Requested foundation model ID                    |
| `agreementAvailability.status`       | `AVAILABLE`, `PENDING`, `NOT_AVAILABLE`, `ERROR` |
| `agreementAvailability.errorMessage` | Optional agreement error string                  |
| `authorizationStatus`                | `AUTHORIZED`, `NOT_AUTHORIZED`                   |
| `entitlementAvailability`            | `AVAILABLE`, `NOT_AVAILABLE`                     |
| `regionAvailability`                 | `AVAILABLE`, `NOT_AVAILABLE`                     |

Record all fields, not only Region availability. A positive response would be
account/model eligibility evidence, not proof of a successful Converse call,
quota, final billed price, credit coverage or live-call authorization. HTTP403
indicates missing permissions for this request, not a measured inference failure.
[Availability API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetFoundationModelAvailability.html),
[agreement structure](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_AgreementAvailability.html).

## Local authentication fallback

The new-project guide explicitly documents `aws login --region project-region`;
this applies to the new project/Builder ID experience rather than assuming a
traditional root user or requesting access keys. Generic CLI login requires CLI
v2.32.0 or later, opens the browser, and writes a temporary login cache locally.
If CloudShell works, there is no reason to install it for this preflight. If a
local path is chosen later, use the owner's browser-based login to the Stockholm
project; do not create an IAM user, attach a policy or collect/paste credentials.
Successful login does not itself prove Bedrock permission.
[Project-specific login command](https://docs.aws.amazon.com/accounts/latest/reference/monitor-your-project.html),
[CLI login requirements/cache](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

## Dated cost evidence and first diagnostic limits

The unauthenticated AWS regional price catalogue retrieved on 20 October has
publication timestamp **2026-10-16T21:08:06Z**, version **20261016210806**. Its
ordinary `On-demand Inference` entries for `gpt-oss-20b`, `eu-north-1` are:

- Input SKU `RJX3DWJDGTUF4WG5`: USD0.0000700000 per 1K tokens = **USD0.07/M**.
- Output SKU `V29P6GYCBB47MJQV`: USD0.0003000000 per 1K tokens = **USD0.30/M**.

These are regional list prices, not account entitlement or a USD receipt. Avoid
silently substituting Mantle, batch, Priority or Flex products.
[AWS Stockholm Bedrock price catalogue](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/eu-north-1/index.json).

Converse `usage` documents `inputTokens`, `outputTokens`, `totalTokens` and optional
`cacheReadInputTokens`, `cacheWriteInputTokens`, `cacheDetails`; it has no generic
`reasoningTokens` member. With caching enabled, total input is uncached
`inputTokens + cacheReadInputTokens + cacheWriteInputTokens`; different cache
rates can apply. Reasoning content is separate from final answer text, and
visible text length is not a substitute for generated-token usage.
[TokenUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html),
[cache accounting](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html),
[OpenAI request/response guidance](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-openai.html).

**Recommendation, not authorization:** after availability succeeds, prepare a
separately approved single serial Converse diagnostic using fixed fictional text,
explicit output limit, no cache checkpoints, no tools/guardrails, standard
regional inference and zero automatic retries. Set a conservative reservation
before sending it, preserve the reservation on timeout or uncertain/missing
usage, and reconcile the result before a second call. Treat calculated token cost
as an estimate until reasoning/cache and billing semantics are verified. The GET
above supplies no token-accounting or paid qualification evidence and authorizes
no inference cohort. The model card's 128K context and native Converse support
help bound that proposed experiment, but do not independently guarantee its
invoice cost.
[Candidate model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html).

## Owner result and local SDK follow-up — 20 October

The owner subsequently ran the CloudShell availability check and reported
`authorizationStatus=AUTHORIZED`, `agreementAvailability.status=AVAILABLE`,
`entitlementAvailability=AVAILABLE`, and `regionAvailability=AVAILABLE` for the
Stockholm candidate. This supersedes the earlier unverified account-launch and
eligibility state. It does not establish local Windows authentication or authorize
inference.

The next local prerequisites are **AWS CLI v2 and CRT in the project Python
environment**, followed by the owner's browser login. Official Boto3 guidance
requires CLI>=2.32.0 and Boto3>=1.41.0 **with CRT**. Its login provider consumes the
CLI-created login profile/cache and automatically refreshes short-lived
credentials. Select the same named profile in the application process; do not
export or paste cached credentials.
[Boto3 console login](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html#login-credentials),
[SDK login-provider support](https://docs.aws.amazon.com/sdkref/latest/guide/feature-login-credentials.html).

Safe local source/metadata inspection of `D:\agent depi\.venv` found Boto3 and
botocore **1.43.115**, with `awscrt` absent. No session or credential files were
read. The installed `LoginProvider` explicitly rejects login profiles without
CRT and requests `botocore[crt]`; its package metadata requires `awscrt==0.36.0`
for that extra. The documented installation form is `boto3[crt]`; preserving the
existing SDK pin would mean `boto3[crt]==1.43.115` in that environment. This note
does not install it or authorize a dependency-file change.
[Official CRT installation guidance](https://docs.aws.amazon.com/boto3/latest/guide/quickstart.html#using-the-aws-common-runtime-crt).

Current first-party Windows documentation now provides an official **current-user
MSI**, requiring no administrator rights:
[AWSCLIV2-User.msi](https://awscli.amazonaws.com/AWSCLIV2-User.msi).
The all-users [AWSCLIV2.msi](https://awscli.amazonaws.com/AWSCLIV2.msi) requires
administrator rights. AWS's recommended
[install.ps1](https://awscli.amazonaws.com/v2/install.ps1) installs for the current
user by default under `%LOCALAPPDATA%\Programs\Amazon\AWSCLIV2`. A custom portable
MSI extraction is therefore unnecessary and is not the documented Windows
installation path. No installer was downloaded to disk or executed here.
[AWS Windows installation instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

The official installer script's source verifies the MSI with
`Get-AuthenticodeSignature`: status must be `Valid`, signer organization must
exactly match `Amazon.com Services LLC`, `Amazon Web Services, Inc.`, or
`Amazon.com, Inc.`, and the issuer organization must match DigiCert. It deliberately
avoids pinning a renewing certificate thumbprint. Preserve signature verification;
do not use its skip-verification switch. A SHA256 recorded locally is useful for
artifact identity but is not authenticity proof without a separately trusted
expected hash. No MSI signature was measured in this research-only pass.
[First-party installer verification source](https://awscli.amazonaws.com/v2/install.ps1).

The official [version endpoint](https://awscli.amazonaws.com/v2/version.txt) and
[CLI v2 changelog](https://raw.githubusercontent.com/aws/aws-cli/v2/CHANGELOG.rst)
both reported **2.38.2** during this check. After separately authorized
installation and dependency preparation, the intended owner interaction is:

```powershell
aws login --profile cap05-stockholm --region eu-north-1
```

Select the existing Stockholm project in the browser. The new-project guide
explicitly documents this `aws login` route; its project-specific instruction is
more relevant than assuming the generic IAM Identity Center setup applies.
`AWS_PROFILE=cap05-stockholm` selects that profile in the later SDK process.
Re-run the same noninvoking availability GET through the local SDK before any
model call. Do not print or inspect login cache contents. A profile name/credential
provider method and redacted availability result are sufficient diagnostics.
[New-project login route](https://docs.aws.amazon.com/accounts/latest/reference/monitor-your-project.html).

## Reasoning-inclusive output bounds

AWS explicitly maps OpenAI `max_completion_tokens` to Converse
`inferenceConfig.maxTokens`. OpenAI defines that former limit as including visible
output and reasoning tokens. AWS's model-reasoning guide also describes reasoning
as adding output tokens. Together these support a **reasoning-inclusive output
limit as the documented interpretation**, rather than budgeting only the final
JSON text. This is a cross-source interpretation that still needs the first
diagnostic's usage/stop-reason evidence for this exact Bedrock model version.
[AWS parameter mapping](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-openai.html),
[OpenAI completion-limit contract](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/),
[AWS reasoning overhead](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-reasoning.html).

The AWS 20B card lists **128K context, 16K maximum output**, with reasoning on by
default. Even generously interpreting K as 1024 and reserving the full context
as input _plus_ the full model output separately gives ordinary regional token
list cost of `131072 * 0.07/M + 16384 * 0.30/M = USD0.01409024` per request.
This deliberately over-reserves relative to a small diagnostic payload and an
explicit lower output limit. For example, USD0.015 per attempted request holds
23 attempts within USD0.35; retain each failed/uncertain reservation. This is a
conditional planning envelope, not an AWS-enforced cash cap or invoice proof.
It assumes exactly one standard regional model attempt each, no automatic
retries, no cache writes, and no additional priced features. Enforce a finite
attempt count and an independent cumulative budget; stop on unexpected usage,
price/tier/route, or unknown provider outcome. Credits and zero cash liability
remain separate account facts.
[AWS 20B limits](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html),
[Stockholm token rates](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/eu-north-1/index.json).

## Failed single diagnostic: read-only trace path — 20 October

The separately authorized **one USD0.02-credit diagnostic** subsequently made one
attempt and returned `BedrockProviderError`, category `provider_http`, in 1313ms,
with no retained usage/output. Provider request ID:
`<failed-request-id retained privately>`. USD0.015 remains reserved; USD0.005 is
unreserved. **No retry is authorized.** This supersedes the earlier illustrative
USD0.35 planning envelope as an execution permission: that example granted none.
The category/request ID alone does not establish an HTTP status, AWS error code,
root cause, zero billing, or inference completion.

Current AWS documentation explicitly logs `Converse`, `ConverseStream`,
`InvokeModel` and `InvokeModelWithResponseStream` as **management events**. Do not
assume ordinary Converse needs paid data-event logging. CloudTrail Event history
provides the past 90 days of regional management events with no CloudTrail charge
for viewing. Therefore the smallest trace action is an existing-history lookup
in **eu-north-1**, without creating a trail, data store, CloudWatch log group,
invocation-logging configuration or any other resource.
[Bedrock CloudTrail classifications](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html),
[free regional Event history](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html).

Use `LookupEvents` with the single lookup attribute **EventName=Converse** and a
narrow UTC window around the attempt. Parse each returned `CloudTrailEvent` JSON
string locally and match its exact **`requestID`** to the provider request ID
above; check `eventType=AwsApiCall`. `EventId` identifies the CloudTrail event and
is not the Bedrock request ID. Lookup supports one attribute plus a time range,
up to 50 records/page and `NextToken` pagination, with a two-requests/second
account/Region limit. No match is inconclusive; it does not justify replaying the
invocation or asserting that it never reached AWS.
[LookupEvents API](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html),
[Bedrock requestID example](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html).

From only the exact matching event, inspect `eventTime`, `eventSource`,
`eventName`, `awsRegion`, `requestID`, `errorCode`, `errorMessage`, and the requested
`modelId`. Keep identity/access-key fields, IP addresses and raw events out of
shared output. AWS documents error code/message as optional; some services place
error information in `responseElements`. An absent error or missing event does
not establish success or cost. If lookup is denied, record the denial without
changing IAM, enabling logging or invoking again. Event history can alternatively
be read in the existing Stockholm console, filtering Event name `Converse` and
comparing the event record's request ID.
[CloudTrail error-field contract](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html).

The current AWS model card still documents the direct
`openai.gpt-oss-20b-1:0` ID with a `bedrock-runtime` Converse example and **In-Region
Stockholm** support. Its regional table marks Geo/Global cross-Region options
unsupported for Stockholm. These sources do not establish a requirement to
replace this call with an inference profile. AWS's OpenAI parameter guide
explicitly maps `temperature` to Converse `inferenceConfig.temperature` and
`max_completion_tokens` to `maxTokens`; the existing parameter names alone are
not evidence of an unsupported-temperature error. No cause should be selected
from an online error example in place of the exact failed request's evidence.
[20B direct-ID and regional contract](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html),
[OpenAI parameter mapping](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-openai.html).

This follow-up performed public-source research and local source inspection
only; no CloudTrail/API lookup, logging change or repeated model call was made.

## Applied zero quotas: activation boundary — 20 October

Later evidence supplied by the coordinating session: a second, separately
authorized **one USD0.02-credit attempt** failed in 703ms with HTTP429
`ThrottlingException`, without usage. Subsequent read-only `GetServiceQuota`
reported gpt-oss-20b RPM `L-AF7F0545=0.0`, `Adjustable=false`, and TPM
`L-036E14D8=0.0`. A complete seven-page quota listing also found Nova Lite
on-demand RPM `L-E386A278=0`, `Adjustable=false`, TPM `L-70423BF8=0`, and zero
daily/cross-Region Nova Micro/Lite values. Availability remained positive and
the candidate models active/on-demand. Both diagnostic ledgers are disabled;
each holds USD0.015, **USD0.03 held against USD0.04 cumulative authorization**.
Neither authorization permits another invocation. This paragraph records supplied
results; this research follow-up made no authenticated calls.

**What the sources establish:** Bedrock applied quotas may be lower than published
defaults because of regional factors, account age, usage/payment history,
fraudulent usage or increase approval. AWS does not promise automatic increases.
Runtime quotas are shared by Converse, InvokeModel and Chat Completions, so
changing only the API cannot restore capacity. A positive availability result
does not override the applied zero capacity.
[AWS account-specific quota policy](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html),
[shared runtime API quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-runtime.html).

AWS's official troubleshooting article identifies zero runtime quotas despite
nonzero defaults as a possible indicator of an **account-level restriction** and
says such restrictions cannot be resolved through IAM/model-access settings.
It directs account-specific resolution to AWS Support. This is a documented
possibility, **not a diagnosis** of this account from its 429 response. Account
age, a safety review, verification/payment state, and regional allocation remain
unconfirmed causes; no activation date or 24/48-hour fix is established.
[AWS official account-restriction guidance](https://repost.aws/knowledge-center/bedrock-invokemodel-api-error),
[AWS official zero/new-account quota guidance](https://repost.aws/knowledge-center/bedrock-throttling-error).

**No blanket Paid-plan requirement was established.** The new project experience
explicitly lists Bedrock among Free Tier services. Also, AWS expressly says
gpt-oss-20b/120b open-weight models require no AWS Marketplace subscription.
Therefore the documented Marketplace subscription setup delay/payment-method
steps for other third-party models cannot be presented as this GPT-OSS fix.
No IAM expansion, subscription, payment change or account upgrade is justified
by this evidence alone.
[Free-project service list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html),
[GPT-OSS subscription exception](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

**Viable next options within the present constraints:** retain the zero-quota
evidence and keep live qualification closed. Inspect only existing AWS account
notices for an explicit incomplete verification action; do not invent an
activation/payment task. A later read-only quota check can establish whether AWS
has changed the allocation, but passage of time is not a documented remedy. AWS's
documented account-specific resolution route is Support; its current
unavailability is a real external dependency, not a reason to keep requesting the
same owner response. No guaranteed self-service, cost-free activation route was
found in the bounded primary-source check.

One limited read-only discovery option exists if useful: AWS documents
`bedrock-mantle` as a **separate quota allocation**, viewable in Service Quotas.
Existing evidence about runtime zeros alone cannot prove Mantle values. This is
not permission to send a Mantle request, create capacity, or silently switch the
qualified API: the existing CAP-05 adapter uses Converse and Mantle would require
an explicit contract/design and qualification decision. If the complete quota
listing already includes the relevant Mantle zeros, no further discovery is
useful. Neither a different provider nor an endpoint change closes the current
strict Bedrock gate without the required evidence.
[Separate Mantle quota allocation](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-mantle.html).

## Completed account access after the research

The owner opened ordinary CloudShell and supplied the filtered response:
authorization AUTHORIZED, agreement AVAILABLE, entitlement AVAILABLE and region
AVAILABLE. The agent then downloaded the official current-user MSI, verified a
Valid Authenticode signature with Amazon Web Services, Inc. organization and
DigiCert issuer, and installed AWS CLI2.38.2 (exit0). The initial text-matching
check rejected the quoted organization formatting; no installer executed until
exact organization extraction and trust checks passed.

The optional boto3[crt]==1.43.115 setup installed awscrt==0.36.0. The owner completed
browser login for profile cap05-stockholm. A local Boto3 GetFoundationModelAvailability
call in eu-north-1 independently returned the same four positive statuses. These
are actual subsequent account observations, superseding the earlier research-only
absence of CRT/local login and unexecuted installation; the earlier source checks
were unauthenticated. No access keys were requested or shared, model invocation
performed, agreement accepted, application infrastructure deployed or plan upgraded.
This was the pre-inference access stage. The diagnostic protocol now records both
separately approved failed attempts and the subsequent applied-zero-quota evidence.

### Actual read-only trace outcome

GetFoundationModel returned ACTIVE, ON_DEMAND, text input/output and streaming
support after the failed diagnostic. A first local formatting attempt could not
serialize its lifecycle datetime; a corrected read-only request produced the
sanitized model-details record. This was not another inference call.

The existing Event history returned no Converse record in initial filtered checks.
At about307seconds, a narrow unfiltered lookup saw surrounding GetFoundationModel
and OAuth event names, with no matching inference requestID and no pagination.
This is inconclusive: cause and exact service error remain unknown. No logging
configuration or retry was performed. Future adapter metadata now includes only
allowlisted error codes and strict HTTP status, never raw provider messages.
