# CAP-06 inventory and gross-cost reconciliation — 23 October 2026

Public-source research and local-document review only. No account, credential,
model, DNS, provisioning or resource API was called; nothing was installed,
activated, upgraded or applied. Public AWS pricing catalogs were read without
credentials. This document changes no selected service, spending authorization,
roadmap gate or runtime configuration.

**Finding:** `55.50 + 23 = 78.50` correctly adds two rounded planning allocations.
It is not a reconciled bill of materials or evidence that USD80 suffices. Shared
control storage/log allowances overlap, the historical Lambda row does not split
the now-prepared two functions, and its edge requests do not distinguish static
and control traffic. A fully stated illustrative scenario below is **USD68.36
infrastructure**, **USD79.36 with the historical USD11 future-model allocation**,
or **USD79.39 with the separate USD0.03 diagnostic hold retained as well**. Its
unmeasured assumptions leave the financial gate open.

## Inventory boundary

The [selected handoff](../cap04-deployment-handoff.md),
[Stockholm amendment](../specs/2026-10-19-cap04-stockholm-ingress-amendment.md)
and [prepared access bundle](../cap06-cloud-access.md) establish this scope:

| Existing selected/prepared component | Quantity and cost boundary                                                                                                                                                                                                                                                                               |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux EC2                            | One Stockholm candidate `t3.small`, shared tenancy, Standard CPU credits, one Agent worker. Size remains conditional on actual capacity.                                                                                                                                                                 |
| EBS                                  | 20 GB total encrypted gp3 retained for 60 days, including root/releases/catalogue/log headroom; baseline IOPS/throughput only. Extra disks/snapshots are not assumed.                                                                                                                                    |
| Public address/network               | One retained EIP, existing public-subnet/IGW path, two registrar A records. EIP remains billable while stopped. Existing VPC inventory is not permission to modify shared resources.                                                                                                                     |
| Caddy and DNS                        | Direct HTTPS on `app.scpilot.tech` and `store.scpilot.tech`; retained protected ACME state. Registrar DNS is assumed included in the already purchased domain; USD0 incremental is conditional, not a new DNS/domain purchase.                                                                           |
| S3                                   | Private waiting/release/backup object scope; current renderer binds one bucket. Exact eventual bucket/object inventory remains to be approved. No public website bucket or extra backup service.                                                                                                         |
| CloudFront                           | One pay-as-you-go generated waiting/control hostname, private S3 and IAM Function URL origins, corresponding OAC/policies. Shopping traffic stays direct. No custom viewer ACM/Virginia dependency, flat-rate subscription or additional shopping distribution.                                          |
| Lambda                               | **Two** existing prepared regional functions: startup HTTP and internal controller, outside VPC; startup alone exposes the IAM Function URL through OAC. Both runtime roles, invoke permissions and separate seven-day log groups belong in the concrete apply inventory. No third observation function. |
| DynamoDB                             | One bound Standard on-demand control table/namespace for invitation/lifecycle authority; no streams, indexes, replicas, PITR or paid prewarming assumed. Initialization/admin authority is separate.                                                                                                     |
| IAM/host authority                   | Separate startup/controller execution roles and host instance role/profile; deployment/initializer permissions separately approved. Exact role/policy counts, names and bindings remain an apply-package task.                                                                                           |
| Diagnostics/model                    | Bounded redacted logs; basic AWS metrics. Bedrock remains disabled/unqualified. Its future model/token allocation and prior diagnostic hold are separate from infrastructure.                                                                                                                            |

The [inactive observation bundle](../cap06-observation-delivery.md) and
[proposal](../specs/2026-10-22-cap06-observation-delivery-design.md)
are **conditional additions**, not adopted infrastructure: one dedicated Scheduler
schedule group, one finite one-minute schedule, one invoke-only execution role,
one fixed-dimension EMF completion metric and two standard one-metric CloudWatch
alarms. The controller is reused. Proposed controller settings are 256 MiB,
30-second timeout, reserved concurrency 1, async function-error retries 0 and
age 60 seconds. Schedule is DISABLED; alarm actions are disabled with no action
ARNs. No SNS, SQS/DLQ, extra event bus, Step Functions, third Lambda or paid
notification channel is selected. No NAT, ALB, RDS, Redis, interface endpoint,
customer-managed KMS key, Secrets Manager, ECR, WAF or paid support is added here.

## Current public rates

Checked 23 October against the exact public catalogs linked below. Prices are
USD before tax, credits and free allowances. Stockholm controls regional prices;
CloudFront uses serving-edge geography. No account-shared free request, storage,
transfer, metric, alarm or Scheduler allowance is subtracted.

| Input                                                                    | Rate used and current catalog publication                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EC2 Linux `t3.small`, SKU `RZ2CPJT3JCVWXCQM`; gp3 SKU `H33YTQG3Y9XKNSF3` | **0.0216/running hour; 0.0836/GB-month**, effective 1 October, published 22 October. [EC2 Stockholm CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/eu-north-1/index.csv).                                                                                                                                                                                                                  |
| Public IPv4 in use or idle                                               | **0.005/address-hour**, published 16 October. [VPC Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/eu-north-1/index.json).                                                                                                                                                                                                                                                    |
| Lambda x86 first tier                                                    | **0.20/M requests + 0.0000166667/GB-second**, published 22 October. [Lambda Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-north-1/index.json). Function URLs have [no extra endpoint fee](https://docs.aws.amazon.com/lambda/latest/dg/furls-http-invoke-decision.html).                                                                                                 |
| DynamoDB Standard on-demand                                              | **0.1345/M RRU; 0.67/M WRU; 0.269/GB-month** paid storage tier, published 11 September. [Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/eu-north-1/index.json). Paid storage rate is deliberately applied to the whole scenario.                                                                                                                                        |
| S3 Standard                                                              | **0.023/GB-month; 0.005/1,000 PUT/COPY/POST/LIST; 0.0004/1,000 GET**, published 15 October. [Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/eu-north-1/index.json).                                                                                                                                                                                                           |
| CloudWatch                                                               | Standard logs **0.54/GB ingestion + 0.028/GB-month stored**; custom metric **0.30/metric-month** first tier; standard alarm **0.10/alarm-metric-month**, published 7 October. [Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/eu-north-1/index.json), [metric/alarm billing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_billing.html). |
| Direct internet egress                                                   | **0.09/GB** first paid tier, published 16 September. [Stockholm DataTransfer catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/eu-north-1/index.json).                                                                                                                                                                                                                              |
| CloudFront                                                               | Middle East scenario: **0.012/10,000 HTTPS requests; 0.110/GB** first paid outbound tier. Europe outbound is 0.085/GB; HTTPS request rate is the same. Published 19 October. [Global catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudFront/current/index.json), [transfer rules](https://aws.amazon.com/cloudfront/pricing/).                                                                  |
| Scheduler                                                                | Stockholm paid tier **1.09/M scheduled invocations**, SKU `J23QGNYZKAWP2FMK`, published 24 September. [AWSEvents Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSEvents/current/eu-north-1/index.json). Its advertised 14M/month allowance is [aggregated across Regions](https://aws.amazon.com/eventbridge/pricing/); no unused allowance is presumed here.                                |

AWS bills Lambda INIT as well as handler duration; a 30-second handler timeout
is not a complete billed-duration ceiling. Reserved concurrency has no additional
fee but is neither provisioned concurrency nor a spending cap. Account eligibility
for reserving even one unit must be checked: AWS normally leaves 100 units
unreserved. [INIT billing](https://aws.amazon.com/blogs/compute/aws-lambda-standardizes-billing-for-init-phase/),
[concurrency rules](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html).

## What overlaps in the old sum

The [19 October scenario](2026-10-19-cap04-network-cost-refresh.md) contains a
Stockholm continuous direct subtotal of **55.071**, including **11** for future
inference/qualification. Its wake increment recomputes to **0.42758875**, including
an optional **0.01** viewer Function row; rounding gives approximately **55.50**.
A viewer Function is not established as part of the current prepared access
inventory, so it is not adopted or charged in the reconciled scenario.

The [22 October observation stress](2026-10-22-cap06-observation-delivery-contract.md)
recomputes to **22.1716576**, rounded upward to **22.18**, then allocated **23**.
It includes **0.00538** for another average 0.01 GB of table storage and **0.0596**
for 0.1 GB logs/0.2 GB-month retention. The prior wake row already has 0.01 GB
control storage, and the prior base explicitly says its logging allowance covers
wake logs. There is no additional table or proven storage increase merely from
adding Scheduler. These rows are overlapping allowances unless explicitly treated
as _additional measured capacity_. They are not evidence of two AWS charges for
the same bytes. Below, total table storage is counted once, and total logs are
counted once. If actual growth exceeds those totals, increase them openly.

Tick Lambda invocations and per-tick DynamoDB units are additional to browser
startup/controller work and must remain charged separately. The new metric and
alarms were not priced in the old base and are additional. No second EC2/EIP/EBS,
waiting distribution, startup function or table is introduced by observation.

The historical 100,000 S3 GET + 100,000 Lambda invocation rows also need an edge
request reconciliation: if they represent disjoint static and HTTP control
requests, they cannot all fit inside only 100,000 total CloudFront requests.
Internal async controller/tick invocations do not pass through CloudFront. Origin
cache hits/misses and direct release downloads must be counted at their actual
seams; the example below makes disjoint traffic explicit.

## Single-counted illustrative 60-day scenario

Use 1,440 elapsed hours and two normalized 30-day storage months. No credit or
free allowance is deducted. This is a workload example, **not measured capacity,
a worst-case bound, a recommendation to raise allowances or an apply approval**.

Non-tick assumptions: 100,000 static and 100,000 control HTTPS edge requests,
1 GB total startup/control viewer egress, 100,000 waiting-object S3 GET; 100,000
startup executions and 100,000 additional internal controller executions. Both
functions are priced at an assumed 256 MiB and 2 seconds **total billed duration**
per execution; startup's eventual size is not selected by this calculation.
Retain the historical 100,000 RRU/100,000 WRU non-tick workload as a clearly
unmeasured allocation, not a claim that each call consumes only one of each.

Conditional tick stress: 86,400 nominal executions at 256 MiB/30 seconds billed,
160 RRU and 144 WRU each, including the earlier conservative condition/metadata
allocation. No duplicates beyond the nominal count are assumed. One custom
metric and two one-metric alarms exist for the two normalized months. Shared
logs total 1 GB ingestion/1 GB-month stored, including the former 0.1 GB/0.2
GB-month observation allocation; shared table storage averages 0.01 GB total.
Seven-day retention does not enforce ingestion limits. These are costing inputs,
not tested universal maxima. DynamoDB [item rounding and transactions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html)
and [transaction capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-capacity-handling)
must be measured for all actual startup, controller and Agent operations.

| Category                                                                  | Gross 60-day USD |
| ------------------------------------------------------------------------- | ---------------: |
| EC2 continuous: 1,440 × 0.0216                                            |        31.104000 |
| Retained gp3: 20 × 2 × 0.0836                                             |         3.344000 |
| Retained EIP: 1,440 × 0.005                                               |         7.200000 |
| S3: average 1.002 GB × 2 months; 1,000 PUT/LIST; 110,000 GET total        |         0.095092 |
| Shared CloudWatch logs: 1 GB ingestion + 1 GB-month stored                |         0.568000 |
| Direct shopping/admin/maintenance internet egress: 20 GB × 0.09           |         1.800000 |
| Startup/control CloudFront: 200,000 HTTPS + 1 GB Middle East outbound     |         0.350000 |
| Shared DynamoDB storage: 0.01 GB × 2 × 0.269                              |         0.005380 |
| Non-tick Lambda: 200,000 requests + 200,000 × 0.25 GB × 2 seconds         |         1.706670 |
| Non-tick DynamoDB: 100,000 RRU + 100,000 WRU                              |         0.080450 |
| Conditional Scheduler: 86,400 × 1.09/M                                    |         0.094176 |
| Conditional tick Lambda: requests + 86,400 × 0.25 GB × 30 seconds         |        10.817302 |
| Conditional tick DynamoDB: 13.824M RRU + 12.4416M WRU                     |        10.195200 |
| Conditional monitoring: one custom metric + two alarm metrics, two months |         1.000000 |
| **Infrastructure scenario; full precision summed before rounding**        |    **68.360270** |
| Historical future demo/qualification allocation, unapproved for use       |    **11.000000** |
| **Scenario plus future-model planning allocation**                        |    **79.360270** |
| Existing diagnostic amount still held, separately retained here           |     **0.030000** |
| **Conservative combined planning amount**                                 |    **79.390270** |

The USD11 row is a **planning allocation**, not gross measured Bedrock usage.
The [20 October account ledger](../cap04-account-feasibility.md) records
**USD0.03 held across USD0.04 cumulative diagnostic authorization**, actual cost
unknown, and both diagnostic ledgers disabled. Do not release the hold, treat it
as confirmed consumption, infer a current balance, or transfer it into a new
inference authorization. This table reserves it separately; a later approved
ledger may reconcile its relationship to qualification without counting the same
actual charge twice. It does not add another USD0.04 charge.

With the same other inputs, **120 running hours** reduces EC2 by 28.512, giving
**39.848270 infrastructure / 50.878270 including 11 and the separate 0.03 hold**.
Continuous gross infrastructure without the conditional observation/monitoring
workload is **46.253592** under the revised non-tick inputs. At the proposed
USD80 envelope the stressed continuous combined planning figure leaves only
**0.609730**; the older separately unallocated USD20 is not a confirmed current
reserve or permission to use it.

A duration sensitivity exposes the missing bound: if the same 200,000 non-tick
executions average 30 billed seconds instead of 2, their Lambda row becomes
**25.040050**. Keeping every other assumption unchanged gives **91.693650
infrastructure / 102.723650 including 11 and the separate hold**. Higher table
units, Agent lease operations, duplicates, bot traffic, INIT or log volume add
further cost. This does not predict that workload; it shows why neither 78.50 nor
79.39 proves the envelope fits.

Stopping is not teardown. For all 60 days stopped, EBS/EIP alone remain **10.544**;
S3, table storage, independent startup/controller traffic, scheduled observations,
logs and existing alarms can continue. The tick-only stopped fast-path example
is **1.970907** excluding shared storage/logs, using 12 RRU, no writes and 2 billed
seconds/tick, plus the metric/two alarms. It must replace the active tick profile,
not be added to it. [EC2 stop/start retention and charges](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html).

## Missing evidence and remaining decision gates

1. **Budget and credits:** refreshed owner evidence for plan, remaining eligible
   balance, other spend/unbilled holds, project spend-limit state and chosen finite
   window; no live account check occurred here. Public IPv4/VPC applicability
   remains unresolved, and EventBridge/Scheduler applicability has not been shown.
   The earlier screenshots list EC2, Lambda, DynamoDB, S3, CloudFront, CloudWatch
   and Bedrock; they do not prove every feature/charge is covered. Retain full
   gross costs and verify tax/credit exclusions. Credit expiry 7 October 2027
   does not extend the earlier evidenced Free-plan end of 7 April 2027.
   [Credit application](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/useconsolidatedbilling-credits.html),
   [plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
2. **Effective creation/runtime authority:** exact chosen EC2/EBS/EIP/S3/table,
   distribution/OAC/Function URL and both Lambda configurations, log groups,
   IAM roles/policies/PassRole, finite schedule/group and alarms; exact resource
   identifiers, ownership, quotas and regional feature eligibility. Published
   Free-project policy includes `scheduler:*` as an exception to one Deny, while
   the separate spend-limit policy can deny `scheduler:CreateSchedule`; neither
   is a grant of permission. Scheduler is not adopted by this research. Preserve
   Stockholm/Free/no-upgrade and do not probe by creating resources.
   [Published managed policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html),
   [project Regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html).
3. **Actual workload totals:** per-function memory and billed durations including
   INIT, each invocation source (startup, async notification, browser observation,
   periodic tick), duplicate/retry/throttle behavior; exact DynamoDB item sizes,
   condition/transaction unit accounting, Agent lease/activity traffic and growth;
   static/control edge counts, viewer geography/bytes, cache misses and S3
   release/backup/deployment retention. Bound rejected/abuse traffic as well as
   accepted invitations. Concurrency and invitations do not cap infrastructure
   spend before rejection. The older 100k-RRU/WRU allowance is not verified by
   tick fixtures. Extra snapshots, versions, exports, detailed metrics, paid
   queries/API usage or administrative transfer need explicit quantities before
   adoption; none is silently included as a new service.
4. **Monitoring/operation:** qualify log ingestion/retention and EMF extraction,
   stable metric cardinality, both alarms and owner review without SNS actions;
   budget-alert settings/recipient and any requested query/API usage. Budget data
   is delayed and alarms can charge while they exist even with actions disabled.
   No paid dashboard, metric stream, query alarm, notification service or Budget
   Action is selected. [CloudWatch billing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_billing.html),
   [Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
5. **Bedrock gate:** newer local evidence already confirms gpt-oss-20b read-only
   availability/authorization on 20 October; do not erase that result by calling
   it wholly unknown. Applied GPT-OSS20B RPM/TPM and Nova Lite shortlist quotas
   were zero, and diagnostics failed, second with HTTP429. Actual inference,
   model qualification, charged usage and current usable quota remain unresolved.
   No further paid call or quota-increase request is authorized by this report.
6. **Cloud acceptance and teardown:** full protected Linux host/resource binding,
   measured memory/CPU and readiness; DNS delegation/conflicts, public Caddy TLS,
   OAC/IAM signing, external observation and closed-browser idle stop/backlog/
   uncertain-command behavior. Preserve ownership, Sensitive Field exclusion,
   bound Confirmation, stale/duplicate Action rejection, no off-origin navigation
   and refresh recovery without uncertain Action replay. Exact activation dates,
   drain/manual-stop/rollback and deletion order must preserve authority/spending
   state. Disable schedule before teardown, delete alarms and task-specific
   retained state per the accepted retention plan, release EIP and verify EBS,
   S3, tables/logs and subsequent residual billing. Do not delete the shared VPC.

Local Ticket 02, final handoff acceptance/parent CAP-04, CAP-05 qualification,
CAP-06 apply and CAP-07 deployed acceptance remain open. Continued offline
preparation is authorized; actual inventory/cost/rollback acceptance and AWS/DNS
writes remain separate. USD80 is still a proposed planning envelope, USD11 is
still a model allocation rather than call authorization, and public arithmetic
cannot establish zero-cash eligibility.
