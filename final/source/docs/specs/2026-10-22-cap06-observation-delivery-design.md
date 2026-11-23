# CAP-06 browser-independent lifecycle observation proposal

**22 October 2026 — conditional local preparation; resource adoption pending owner decision.** No schedule,
alarm, role, policy, resource, runtime change or AWS API request is made by this
document. Existing selected resources stay as they are. The owner's continuation
authorizes reversible inactive implementation and package verification; it does
not adopt or provision the new service. This is not deployed monitoring.

## Problem and intended result

Accepted wake currently notifies the controller asynchronously, and an open
waiting page requests observations. Once that browser closes, nothing reliably
requests the next readiness, startup-deadline, drain or stopped-state observation.
Host heartbeats cannot solve observation when the host is impaired or stopped.

Add one independent periodic producer, reusing the existing Stockholm controller
and DynamoDB authority. It must help a previously accepted wake progress, discover
readiness loss and advance the existing safe stop protocol after 60 minutes of
genuine inactivity. It never creates a wake, treats polling as meaningful activity,
revives an expired lease, or replays a claimed/uncertain command or shopping Action.

The owner already selected automatic wake through the generated startup link.
The proposed scheduling service below is an implementation choice for review,
not a previously approved service or permission to provision it.

## Proposed resource addition

Use **EventBridge Scheduler**, a dedicated schedule group, one execution role,
and one fixed schedule targeting the existing unqualified controller Lambda ARN.
It remains outside the VPC, in `eu-north-1`. Keep the current two functions; no
third Lambda, SQS, SNS, Step Functions or standing monitor is selected.

The schedule uses `rate(1 minute)`, UTC, flexible window OFF, an explicit future
start and finite end within the separately approved demonstration window.
Keep completion deletion off so its configuration can be inspected at teardown.
Use no catch-up loop, self-invocation, sleep, runtime-managed schedule creation or
generation encoded at provisioning. The target input is exactly `{"kind":"tick"}`.

The execution role trusts only `scheduler.amazonaws.com`, with exact SourceAccount
and the dedicated schedule-group SourceArn. Scheduler uses the group for this
confused-deputy condition; do not substitute the individual schedule ARN. Its sole
runtime permission is `lambda:InvokeFunction` on the fixed controller ARN. Runtime
startup/controller roles cannot create/update schedules or pass that role. No
public URL or anonymous Lambda permission is added. Deployment credentials need
separate reviewed create/configure/PassRole permissions.

Configure Scheduler maximum event age 60 seconds and maximum retry attempts 0.
Keep the controller's Lambda asynchronous maximum event age 60 seconds and
function-error retry attempts 0. Lambda can still duplicate delivery and retry
throttling/system errors within its age limit; these settings are not exactly-once
delivery. Controller reserved concurrency 1 and a proposed 256 MiB/30 second
configuration require actual account eligibility and Linux measurement. No DLQ is
selected: a fresh tick recomputes current state, while unknown commands stay locked.

## Trusted tick behavior for inactive preparation

1. Accept only the exact tick shape on the controller's internal invoke path.
   HTTP startup requests cannot supply it or choose a host, endpoint or generation.
   Startup runtime continues accepting only the existing HTTP-v2 contract.
2. Read the bound durable lifecycle. If stopped, return its safe status without
   an EC2 call or lifecycle write. Otherwise require a valid positive generation.
3. Observe the designated host and signed readiness against the current generation
   and revision, using the existing `ControlObserver`. Reconcile startup deadlines,
   health, work leases, activity, drain and stop state through existing transactions.
4. Attempt at most one already-pending command using that same generation and
   `EC2CommandExecutor`. A START can only come from a prior invitation-validated
   accepted wake or explicit owner prewarm intent, with the existing fresh
   invitation/window/deadline checks at claim and before the EC2 call. This rescues
   a lost notification; a timer alone never grants start authority.
5. Return the safe status. Readiness after a just-acknowledged START and observed
   stopped after a STOP are confirmed by later observations, never by API acceptance.

Keep existing `dispatch|observe` events with their bound generations unchanged.
An older tick has no generation-specific authority: it requests a fresh current
observation. Changes after its read are fenced by the existing revision/generation
checks; fail this invocation and let a later tick start afresh, without retrying a
claimed command. Duplicate invocations cannot claim a command twice. A stale or
uncertain EC2 result still requires owner investigation; scheduled invocation is
not an automatic unlock/recovery policy.

## Timing, failures and monitoring

One-minute scheduling has service precision/delivery delay, not an exact deadline
guarantee. With healthy delivery, an idle host normally enters draining on the
first observation after 60 minutes and commits stop on a later observation at
least 5 seconds afterward. Plan roughly 60–63 minutes to stop commitment, then
EC2 stop time; qualify the actual distribution. Continued work/meaningful activity
cancels uncommitted drain. Leases and bound Confirmation/Action safety stay intact.

Scheduler, the Lambda async queue and public startup notifications share delivery
and controller capacity. Load/throttling/outages can delay or drop observations.
No availability or shutdown-time guarantee follows from setting rate(1 minute).
Test simultaneous browser traffic and missing/late ticks before acceptance.

For trusted tick failures, expose a generic failed invocation to Lambda's built-in
Errors metric, including invalid configuration/initialization failure. Do not log
event contents, invitations, keys, request/response bodies or exception details.
Emit one `TickCompleted` count only after a successful trusted tick, via bounded
CloudWatch Embedded Metric Format logs. Use a fixed namespace and one fixed
controller component dimension, never a generation, request, invitation or other
unbounded dimension. This avoids new PutMetricData permissions and keeps one
custom metric. Ordinary browser-triggered controller work must not emit it.
Add two standard CloudWatch alarms: controller Errors >=1 over 5 minutes, and
missing TickCompleted across 5 minutes (missing data treated as breaching for
the latter). Thus browser traffic cannot mask absent scheduled observations.
Owner checks these alarms, Scheduler target metrics and the durable observation
time before a testing session; this is not proof of every individual delivery or
an unattended notification service. No alarm actions or emails are configured.
If unattended paging is later required, design and price
it separately rather than silently adding SNS or outbound messaging.

Control-store failure denies new work and may prevent automated stop. A killed
worker may leave a claimed command unresolved, which is deliberately not replayed.
Keep the owner stop/investigation runbook; do not advertise a hard AWS spending cap.
Before the finite schedule ends, close admission/wake, drain and confirm the host
stopped while observations still run. Disable the schedule before dismantling its
target/role/table, preserving state and accounting until reconciliation completes.

## Conditional 60-day cost allocation

Use the separately cited [current AWS contract and rates](../research/2026-10-22-cap06-observation-delivery-contract.md).
There are 86,400 planned one-minute invocations over 60 days. Do not subtract
unverified account free allowances, rewards or credit applicability.

Reserve **USD23 additional AWS credit** as a conservative planning allocation,
not inference authorization or an AWS-enforced cap. The stress scenario assumes
256 MiB, every invocation at the proposed 30 second timeout, 160 DynamoDB RRU and
144 WRU per tick (including conservative transaction-condition headroom), bounded
logs, one custom metric and two alarm metrics. These are explicit assumptions, not measurements or
proven operation/size maxima. Actual implementation must measure them and refuse
deployment if the revised total exceeds the reviewed allocation. Longer runtime,
larger rows, extra traffic and retries can exceed this scenario.

Adding USD23 to the prior rounded USD55.50 continuous two-month topology gives
**USD78.50**, leaving USD1.50 under the proposed USD80 envelope and a separate
USD20 of the last evidenced USD100 unallocated. Most prior contingency is consumed;
this is a planning tradeoff requiring owner review, not a claim of current balance
or billing safety. Public IPv4 credit coverage and all other existing feasibility
gates remain unresolved. The old waiting/control traffic estimate is also a
scenario, not an abuse cap; reprice the complete measured deployment before apply.

## Alternatives and acceptance boundary

Legacy EventBridge scheduled rules can target Lambda and avoid the Scheduler
invocation charge, but AWS recommends Scheduler for new scheduled work. The
current Stockholm Scheduler post-allowance charge is a small part of the overall
path; choosing legacy scheduling does not remove Lambda/DynamoDB/log costs or
account qualification. Prefer Scheduler conditionally; do not maintain both.

If scheduling/account permissions or total costs cannot be established without
upgrade, retain the manual owner start/stop/prewarm fallback and keep automatic
cloud lifecycle acceptance open. Do not imply the browser-only design has solved
unattended idle shutdown. A future host-side stop alone cannot observe outages or
establish the same remote authority guarantees.

Prepare inactive pure configuration/policies and tick behavior locally under the
owner's continuation, with offline duplicate/stale/revoked/expired/unknown-command/deadline/drain/
activity/lease/store-outage tests and actual measured DDB operation/byte counts.
Rebuild both ZIPs and repeat isolation/regressions/review. Actual provisioning
still needs the complete approved resource/cost/rollback inventory, runtime keys,
effective IAM/OAC/event/account eligibility, Linux execution and CAP-07 evidence.
Bedrock zero quotas/qualification, Free plan, Stockholm, zero cash and all shopping
safety boundaries are unchanged. No new model request is authorized by this choice.
