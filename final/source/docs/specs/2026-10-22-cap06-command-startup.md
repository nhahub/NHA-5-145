# CAP-06 command executor and startup HTTP preparation

The owner asked to continue the approved Stockholm automatic-wake design. This
slice makes its command and waiting interfaces testable offline. It does not
activate a backend, deploy a Lambda, create resources, run a model or spend credit.
The Free plan, zero cash constraint, pending deployment approval and Bedrock quota
blocker remain unchanged.

## Decisions

Builder calls: use injected synchronous Python components, existing DynamoDB
authority and the existing waiting HTML. A separate trusted worker will eventually
schedule observations and command execution. Do not introduce another AWS service
or make a public request run an EC2 operation. This slice does not establish a
working deployed automatic-wake system.

`EC2CommandExecutor(lifecycle, client, instance_id).execute_once()` claims at most
one durable command and invokes at most one StartInstances or StopInstances call
for the configured instance. Only Stockholm's standard EC2 endpoint, SDK retries
disabled (total attempts 1), connect timeout at most 5 seconds and read timeout at
most 15 seconds are accepted. Check client configuration before claiming and again
before SDK entry. No client/credential creation, retries, waiters, instance discovery
or automatic claim takeover. Validate instance IDs as fixed configuration.

Add `DynamoLifecycle.check_command(receipt)` to refresh exact claimed receipt,
generation, deadline and startup invitation validity immediately before dispatch.
A rejected check keeps the durable claim locked. This check is not atomic with EC2;
do not claim EC2 generation fencing or instantaneous revocation across network I/O.
The executor never accepts a caller-supplied receipt. Durable exclusive claiming,
not an in-memory lock, prevents competing executors dispatching the same intent.

Validate successful SDK responses: HTTP 200, exactly one matching instance and
coherent named/numeric previous/current EC2 states. Start accepts stopped/pending/
running to pending/running; stop accepts pending/running/stopping/stopped to
stopping/stopped. A malformed response, service error or transport exception is
uncertain, even if the operation may have committed. Attempt settlement once as
uncertain, expose no SDK error details and never retry the EC2 call. A lost
settlement stays claimed. A certain acknowledgement still needs a later trusted
observation; it never independently admits shopping work.

`DynamoStartupRates(invitations, clock=...).rate(lane)` implements fixed global,
wake and poll per-minute limits 240/10/120 using three durable rows. Strong reads,
metadata identity checks and conditional transactions prevent reopening/reset and
lost increments. No retries, TTL or dynamically named lanes. Reject corrupt rows,
clock rollback, uncertain writes and exhausted limits. These protect application
work; edge-level request/invocation cost containment remains a deployment gate.

`create_startup_handler(lifecycle, rates, origin=...)` returns an injected Lambda
Function URL HTTP-v2 handler. Origin is an exact generated CloudFront HTTPS origin
(`https://[a-z0-9]{1,63}.cloudfront.net`), configured by the owner/deployment. No
listener or SDK construction. Deployment must use AWS_IAM plus CloudFront OAC;
the handler alone is not proof that public access is protected.

Serve GET /, GET /status, POST /wake only. No query strings; strict method/path,
event version/header/body validation; no cookies, redirects or CORS workaround.
POST requires exact configured Origin and application/json with exactly one code.
Decode base64 strictly, cap encoded and decoded bodies at bounded sizes (1024
decoded bytes), reject duplicate JSON keys and invalid UTF-8. Do not reflect
request data. Return 202 after durable wake acceptance only; no EC2 dispatch in
the request. Status reads do not wake or extend meaningful activity.

Reuse waiting.html with nonce CSP and replace its fixed local destination with
https://app.scpilot.tech/. All responses are no-store, no-referrer and nosniff.
Expose only the existing safe lifecycle view. Invalid invitation/origin/input is
403; malformed transport is 400; unknown routes 404; rate/authority uncertainty
503 (rate bounds also fail closed). No logs of events, codes, SDK responses,
receipts, credentials or account identifiers. UI still clears codes and never
puts them in URLs/storage; re-entry at the shopping app remains required.

## Verification and remaining work

Use Moto DynamoDB with dummy credentials and botocore Stubber EC2 responses only.
Test competing executors, committed-but-lost responses, failed settlement,
post-claim revocation/deadline, configuration mutation, malformed SDK replies,
rate persistence/concurrency/corruption/clock rollback and HTTP request attacks.
Run existing invitation/lifecycle/admission/allowance regressions and fresh release
build, repository lint/format checks and independent review.

Remaining: actual Lambda/OAC/IAM and fixed instance wiring; trusted readiness and
observation scheduling; async Agent/host work integration; durable host services;
DNS/TLS and cost approval; cloud acceptance. No automatic retry/unlock or provider
substitution is authorized by this preparation.
