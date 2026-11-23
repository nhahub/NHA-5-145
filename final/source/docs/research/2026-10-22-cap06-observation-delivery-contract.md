# CAP-06 external observation delivery contract

Checked **22 October 2026** against public AWS documentation and regional price
catalogs. Research only: no account API, credentials, resources, model calls,
installation, activation or topology selection. This supports the next reviewable
design; it does not close the Free-plan, credit, deployment or CAP-05 gates.

## Free-project eligibility

**The current published Free-project policy does not categorically block
EventBridge Scheduler.** Its `AllowFreeTierServices` statement is `Effect: Deny`
with a `NotAction` list containing **both `events:*` and `scheduler:*`**. Those
actions are exceptions to that particular deny, not grants of permission. The
Free service matrix lists Amazon EventBridge. Both documents warn that the new
experience is a limited rollout. The separate spend-limit policy includes a deny
on `scheduler:CreateSchedule`; effective project/IAM policies, spend-limit state,
quotas and actual feature entitlement remain account-specific.
[Managed project policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html),
[service matrix](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).

Scheduler has a documented Stockholm endpoint,
`scheduler.eu-north-1.amazonaws.com`. Keep the schedule, Lambda and DynamoDB in
the project's assigned `eu-north-1`; regional service availability does not prove
this project's permission. Do not upgrade or enable advanced features to resolve
a denial. Existing owner evidence lists Lambda, DynamoDB and CloudWatch credit
applicability; it does **not** establish EventBridge/Scheduler credit applicability.
An advertised free allowance and a credit balance are different evidence.
[Scheduler endpoints](https://docs.aws.amazon.com/general/latest/gr/eventbridgescheduler.html),
[project Region rules](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html),
[local account evidence](../cap04-account-feasibility.md).

## Delivery comparison

| Contract              | Scheduled rule → Lambda                                                                                                                                                                                       | Scheduler → Lambda templated target                                                                                                                                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Status and placement  | Legacy feature; scheduled rules use the default event bus. AWS recommends Scheduler for new scheduling.                                                                                                       | Independent schedule; an event bus is unnecessary.                                                                                                                                                                                                                                                          |
| Cadence and precision | `rate(1 minute)`; cron cannot run faster than one minute. UTC; no second precision, with distributed delivery delays.                                                                                         | `rate(1 minute)`; rate value is a positive integer in minutes/hours/days. Every schedule type has 60-second precision; with flexible window OFF, an intended 01:00 target API invocation occurs within 01:00:00–01:00:59 under the documented timing model. Queue/throttle/outage delay remains additional. |
| Invocation            | EventBridge invokes Lambda asynchronously. Delivery success is acceptance by Lambda, not completion of controller code.                                                                                       | Lambda integration explicitly invokes asynchronously. A successful API response does not establish a completed observation, EC2 command or readiness.                                                                                                                                                       |
| Delivery retries      | Default up to 185 retries over 24 hours, exponential backoff and jitter. Configurable attempts 0–185, age 60–86400 seconds. Exhausted events are dropped unless a DLQ is configured.                          | At-least-once delivery; configurable attempts 0–185, age 60–86400 seconds; exponential backoff. A configured SQS standard DLQ receives exhausted target-invocation failures.                                                                                                                                |
| Payload               | Entire scheduled event by default; constant JSON target input can replace it.                                                                                                                                 | Explicit well-formed JSON input for a Lambda target; maximum 256 KB. Use an explicit tiny payload rather than depend on the default notification.                                                                                                                                                           |
| IAM                   | A function resource policy can grant `lambda:InvokeFunction` to `events.amazonaws.com`, restricted by exact rule `AWS:SourceArn`. Current docs also allow a target execution role with the invoke permission. | Required execution role permits only `lambda:InvokeFunction` on the exact target. Its trust principal is `scheduler.amazonaws.com`; constrain `aws:SourceAccount` and **schedule-group ARN** in `aws:SourceArn`. AWS explicitly says not to use an individual schedule ARN for that trust condition.        |

Sources: [scheduled rules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html),
[rule expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html),
[Scheduler expressions](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html),
[CreateSchedule syntax](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_CreateSchedule.html),
[EventBridge Lambda delivery](https://docs.aws.amazon.com/lambda/latest/dg/services-ec2.html),
[Scheduler Lambda delivery](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html),
[rule retries](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-retry-policy.html),
[rule retry API](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_RetryPolicy.html),
[Scheduler retry API](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_RetryPolicy.html),
[Scheduler at-least-once contract](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html),
[target input](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_Target.html),
[rule IAM](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html),
[Scheduler trust](https://docs.aws.amazon.com/scheduler/latest/UserGuide/cross-service-confused-deputy-prevention.html),
[Scheduler DLQ](https://docs.aws.amazon.com/scheduler/latest/UserGuide/configuring-schedule-dlq.html).

**Both paths have a second, independent retry/age boundary inside Lambda.**
Lambda defaults to two further function-error attempts and up to six hours of
queue retention. `MaximumRetryAttempts=0` suppresses function-error retries;
`MaximumEventAgeInSeconds` accepts 60–21600. Neither setting prevents duplicates
or throttling/system-error requeueing. Configure the exact function/version/alias
being invoked. Concurrency 1 limits simultaneous function executions; it is not
a lock over durable state, an overlap policy that skips future schedule ticks,
or exactly-once delivery. Successive duplicate ticks can still execute. Retain
durable claims, fresh generation/revision/deadline validation, and single-attempt
EC2 dispatch.
[Lambda async configuration](https://docs.aws.amazon.com/lambda/latest/api/API_PutFunctionEventInvokeConfig.html),
[Lambda async errors](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html),
[reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html).

## Conditional integration recommendation

If the owner approves an external scheduling resource and its complete gross
cost/eligibility/rollback checks pass, prefer the documented Scheduler Lambda
templated target, one fixed `rate(1 minute)` schedule, explicit UTC time zone,
flexible window OFF, and explicit UTC start/end dates covering the approved
window. Its resource proposal comprises a schedule group, schedule and narrowly
scoped execution role; optional monitoring adds two CloudWatch alarms. The
creator also needs [permission to pass that exact execution role](https://docs.aws.amazon.com/scheduler/latest/UserGuide/security_iam_troubleshoot.html). A legacy
scheduled rule is a separately reviewable
alternative, not an automatic workaround for an account denial. Do not install
either as part of this research. No SQS/DLQ, SNS, customer-managed KMS key,
sleeping Lambda or self-invocation chain is selected here.

Proposed trusted input is exactly `{"kind":"tick"}` with **no generation**,
invitation, instance ID or requested start operation. The configured IAM target
binding supplies invocation authority; a payload field claiming a schedule ARN
would not authenticate the caller. The trusted handler derives the current
generation from durable state at execution, captures fresh observation first,
then attempts at most one still-valid pending command. An accepted start may
proceed only after fresh invitation/deadline checks; a tick never creates wake
intent, refreshes meaningful activity, starts an unrequested host, or replays a
consumed/uncertain claim. Generation/revision changes during observation must
refuse stale results. Unknown dispatch remains locked for owner investigation.
These are proposed project requirements, not guarantees AWS provides and not
claims that the current strict dispatch/observe entry accepts `tick`.
[Current runtime boundary](../cap06-controller-runtime.md),
[existing async/claim analysis](2026-10-22-cap06-controller-runtime-contract.md).

Use short explicit delivery retry/age settings, reviewed independently at both
layers; a reasonable candidate for periodic observations is delivery retries 0,
delivery age 60 seconds, and Lambda function-error retries 0/age 60 seconds.
Fresh recurring ticks recover observation progress without replaying a retained
old command. These settings deliberately trade individual-tick retention for
freshness; they do not bound service outage recovery. The handler needs a
bounded per-pass deadline and no wait-for-ready loop. Proposed 256 MiB/30-second
Lambda configuration is a costing input pending actual packaged Linux tests,
not evidence of sufficient memory, duration or readiness.

This external source continues invoking while browsers are closed and the host
is stopped/impaired, unlike browser polling or a heartbeat running on that same
host. Healthy delivery plus the next pass to drain a newly due stop suggests an
approximately **60–63-minute** outcome for a 60-minute idle policy; that is a
planning estimate, not a maximum. AWS queue delay, throttling, control-plane
outages, unknown claims and failed probes can extend it without a proven bound.

Optional monitoring proposal: one custom standard-resolution `TickCompleted`
metric emitted through a bounded JSON EMF log only after a successful trusted
tick, with a constant namespace and dimension combination. No event contents,
generation, invitation, instance ID, key or per-request identifier enters the
metric/log. Two standard alarm metrics monitor builtin function `Errors` and
missing `TickCompleted` over an explicitly reviewed five-minute window, treating
missing completion data as breaching. No SNS or alarm actions are selected.
Other calls to a shared controller can mask missing `Invocations`, so that
builtin count is insufficient for this schedule-specific check.

EMF requires `logs:PutLogEvents` but does **not** require an additional
`cloudwatch:PutMetricData` grant. It incurs both log and custom-metric charges;
each unique dimension combination creates another metric. Extraction is
asynchronous and can duplicate metric values: the completion metric is an
availability signal, not an exactly-once tick ledger or command authority.
Log publishing/processing delay can produce missing/partial alarm data; review
M-out-of-N evaluation against deployed behavior. Alarms provide AWS alarm state,
not an independent notification channel, bounded outage detection or proof of
host readiness. Review Scheduler delivery metrics and durable observation
freshness during acceptance. Test closed-browser idle stop, host outage,
lost/duplicate tick, async backlog, stale generation and uncertain command
behavior before claiming deployed reliability.
[Lambda metric meanings](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html),
[EMF permissions, cost and cardinality](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html),
[EMF format](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html),
[EMF alarm timing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Alarms.html).

## Gross 60-day cost scenarios

Use **86,400 nominal ticks = 60 × 24 × 60**, x86 Lambda at 256 MiB, and two
normalized 30-day months. These are explicit scenarios, not measured workload
or spending caps. Do not subtract unproven or account-shared free allowances.
Duplicated executions, other trigger traffic, billing INIT/extension duration,
retries and larger items can increase consumption.

| Stockholm public rate checked 22 October                                                                                                                              | Source and effective/publication dates                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Scheduler first 14M scheduled invocations $0; above that **$1.09/M**, SKU `J23QGNYZKAWP2FMK`                                                                          | [AWSEvents regional catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSEvents/current/eu-north-1/index.json), effective 1 September / published 24 September 2026. Generic pricing-page $1/M example is not this regional rate. |
| Lambda **$0.20/M requests + $0.0000166667/GB-second**, first x86 tier                                                                                                 | [Lambda regional catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-north-1/index.json), effective 1 October / published 16 October 2026.                                                                     |
| DynamoDB Standard on-demand **$0.1345/M RRU; $0.67/M WRU; $0.269/GB-month** paid storage rate                                                                         | [DynamoDB regional catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/eu-north-1/index.json), effective 1 August / published 11 September 2026.                                                             |
| CloudWatch Standard logs **$0.54/GB ingested + $0.028/GB-month stored**; standard alarm **$0.10/alarm-metric-month**; custom metric first tier **$0.30/metric-month** | [CloudWatch regional catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/eu-north-1/index.json), effective 1 October / published 7 October 2026.                                                           |

Scheduler's advertised **14M/month allowance is for Scheduler invocations**;
it does not make Lambda, DynamoDB or logs free. Its advertised allowance is
aggregated across Regions and unused usage does not roll over. Model the full
86,400 at the Stockholm paid rate here: **$0.094176**. A same-account legacy rule
with a direct Lambda target has no separately published scheduled-rule charge;
the comparison assumes $0 for rule scheduling itself based on the published
charge categories, without adding custom `PutEvents`, API destinations, cross-
account routing, discovery or replay. That is a pricing interpretation, not an
account billing audit. It does not waive target-service charges.
[EventBridge prices and allowance scope](https://aws.amazon.com/eventbridge/pricing/),
[AWS charge categories](https://repost.aws/knowledge-center/eventbridge-reduce-charges).

DynamoDB rounds strong reads by 4 KiB and writes by 1 KiB; transactions perform
two underlying reads/writes. `PutItem` replacement is charged using the larger
old/new item; small changed attributes do not make a whole lifecycle replacement
a 1-KiB write. Failed conditions/transactions can consume capacity. The 16-KiB
item size below is an **assumption to enforce/measure**, not an observed row size.
Count condition checks explicitly; public transaction text describes reads or
writes without a sufficiently precise per-ConditionCheck billing example to
establish this application's total. Do not assert that condition checks are
free or that cancellation avoids charges.
[Read/write metering](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html),
[transaction capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-capacity-handling),
[binary units](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html).

Illustrative assumptions supplied for the proposed pass: stopped fast path,
three strong gets of rows ≤16 KiB = **12 RRU/tick**, no writes; active allowance,
up to 36 strong gets of rows ≤16 KiB plus read headroom = **160 RRU/tick**, and
four transactional lifecycle puts of ≤16 KiB = **128 WRU/tick**. For conservatism
also allocate **16 extra WRU/tick** for condition/metadata overhead (for example,
eight additional ≤1-KiB transactional items at two WRU each), rather than call
the unmeasured 128-WRU count a complete bound. If actual condition/item counts or
sizes exceed that allowance, recompute before deployment. No indexes, streams,
PITR, DAX, cross-Region replica, paid throughput prewarm or extra service is
assumed. The 144-WRU total below is deliberately conservative billing allocation,
not a claim about exactly how an individual ConditionCheck is metered.

| Added 60-day category                                      | Stopped fast path, 2 s billed/tick | Active allocation, 2 s billed/tick | Active timeout stress, 30 s billed/tick |
| ---------------------------------------------------------- | ---------------------------------: | ---------------------------------: | --------------------------------------: |
| Scheduler, without allowance subtraction                   |                          $0.094176 |                          $0.094176 |                               $0.094176 |
| Lambda requests                                            |                          $0.017280 |                          $0.017280 |                               $0.017280 |
| Lambda compute                                             |                          $0.720001 |                          $0.720001 |                              $10.800022 |
| DynamoDB RRU                                               |                          $0.139450 |                          $1.859328 |                               $1.859328 |
| DynamoDB WRU                                               |                                 $0 |                          $8.335872 |                               $8.335872 |
| Additional 0.01 GB control storage × 2 months at paid rate |                          $0.005380 |                          $0.005380 |                               $0.005380 |
| Logs: 0.1 GB ingested + 0.2 GB-month stored                |                          $0.059600 |                          $0.059600 |                               $0.059600 |
| Optional two standard alarm metrics × 2 months             |                          $0.400000 |                          $0.400000 |                               $0.400000 |
| Optional one custom completion metric × 2 months           |                          $0.600000 |                          $0.600000 |                               $0.600000 |
| **Incremental scenario total, rounded up**                 |                          **$2.04** |                         **$12.10** |                              **$22.18** |

Active timeout stress runs every nominal tick for its entire 30-second billed
allocation and applies all active read/write allowances; it is not a forecast.
INIT can be billable in addition to handler time, so a 30-second function timeout
does not itself establish a 30-second billed-duration cap. Additional invocations
must be costed separately. The log/storage rows are allowances, not enforced
limits. A scheduled rule would subtract only the $0.094176 Scheduler row under
the stated pricing interpretation.
[Lambda pricing duration rules](https://aws.amazon.com/lambda/pricing/),
[INIT billing across ZIP/runtime configurations](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/).

Rounding the stress increment to a proposed **$23 planning allocation** and
adding it to the older approximately $55.50 continuous-host reference gives
**approximately $78.50**, leaving $1.50 of a proposed $80 envelope and the
previous separate $20 unallocated. The old $0.43 wake/control estimate is itself a
scenario, not a bound on public polling/startup/controller traffic. Reconcile
all of those workloads and avoid counting the same storage/log allocation twice
before asserting an $80 planning envelope fits. Regional price arithmetic does
not establish cash-free eligibility: EventBridge credit applicability, all
effective permissions, available balance/expiry, other spend and teardown remain
required evidence. No topology, resources, upgrade or extra spend is authorized
by this report.
