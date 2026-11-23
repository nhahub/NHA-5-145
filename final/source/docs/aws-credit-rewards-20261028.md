# Temporary AWS credit activities — proposed bounded execution

The owner asks to earn the remaining activity credits using disposable resources,
then terminate those resources. This is a separate account task. It does not add
services to Shopping Copilot or authorize project activation/provider changes.
Read-only account inspection found zero existing budgets, Lambda functions,
RDS instances or Scheduler schedules in scope; project EC2 remains stopped.

## Proposed authority

Use the existing active Free-plan account, Stockholm eu-north-1 (global billing
and IAM APIs use their normal global endpoints). **Up to USD1 total in existing
AWS credits, USD0 cash, no account upgrade or advanced-feature activation.**
Expected cost is a few cents. This conservative ceiling includes up to three
hours of RDS instance/storage and worst-case burst CPU charges, small Lambda/
Scheduler/KMS/request/transfer allowances, and contingency. No credit reward is
counted as available until AWS reports it. No use of old CAP-07 grants, reserve,
provider key, ledger, instance, role, security group or DynamoDB namespace.

All new names use one unique `scpilot-reward-<suffix>` prefix and an exact owner
operation tag. Inventory and save their identifiers before writes. Never adopt,
replace, delete or modify an existing resource. No application/customer data.
Run sequentially so each resource can be cleaned before the next activity.
The absolute session ends three hours after the first write; no extension.

| Activity                          | Exact proposed action                                                                                                                                                     | Limit and cleanup                                                                                                                                                                                                                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Budget, USD20 reward              | One monthly COST monitoring budget with USD100 threshold, no automatic actions, reports or external recipients                                                            | Monitoring is free; threshold is not permission to spend USD100. Confirm reward then delete this temporary budget; stop waiting after ten minutes and record pending honestly.                                                                                                                                               |
| Lambda, USD20 reward              | One Python3.12/128MiB/3second function serving fixed harmless HTML, one AWS_IAM-authenticated function URL, one dedicated execution role with no data-service permissions | At most three signed test invocations; no public unauthenticated policy, provisioned concurrency, VPC/NAT, extra layers or project connection. Verify response/credit; delete URL/function/owned log group if created, then role.                                                                                            |
| RDS, USD20 reward                 | One PostgreSQL17.11 db.t4g.micro, Single-AZ, encrypted20GiBgp3, existing defaultVPC/subnets via one dedicated subnet group and one dedicated no-ingress security group    | No public accessibility, no workload, storage autoscaling, backup retention, final snapshot, retained automated backup, enhanced monitoring, PerformanceInsights or ExtendedSupport. Create then observe available/credit; delete, rather than stop. Verify DB/backups/snapshots gone before deleting owned network helpers. |
| Bedrock, conditional USD20 reward | At most one Amazon Nova Micro playground prompt, `Reply with OK.`, at most100input/32output tokens, USD0.01 sublimit inside USD1                                          | Only if read-only availability and applicable invocation quotas are positive. No subscriptions/terms acceptance, capacity provisioning, quota increase, batch job, retries or project qualification. Skip on quota/access/Free restriction.                                                                                  |

Create a dedicated, least-privilege Scheduler execution role and a one-time
RDS DeleteDBInstance cleanup schedule **before** creating the temporary database.
The role can delete only the exact new reward DB ARN with its ownership tag;
the schedule passes SkipFinalSnapshot/DeleteAutomatedBackups. It triggers at
T0+twohours, has a bounded retry policy within the third hour and deletes itself
after completion. Refuse RDS creation if this cleanup guard cannot be verified.
Normal cleanup occurs much sooner, then deletes the schedule and its role. A
local bounded cleanup helper independently handles partial success and teardown.
Do not leave the database running merely to wait for credit to appear. A deletion
failure is reported and cleanup remains the priority; budgets are not billing caps.

## Current findings and costs

AWS FreeTier activity API confirms four remaining USD20 activities. The account
balance observed before execution is USD119.79. The RDS activity's embedded
tutorial mentions Aurora, but the official activity requirements permit either
RDS or Aurora; supported standard RDS is the smaller temporary trial.

Official Pricing API, 28 October: PostgreSQL db.t4g.micro Single-AZ Stockholm
USD0.016/hour and gp3 USD0.12/GB-month. Three hours of instance plus20GiB storage
is approximately USD0.058. Include worst-case two-vCPU burst surcharge at a
conservative USD0.10/vCPU-hour for three hours (USD0.60), rather than assuming
an idle database cannot burst. Budget USD0.02 for other service/request/transfer
usage;20percent contingency gives approximately USD0.814, below USD1. Verify
current official burst pricing is no higher before creating RDS; reduce scope or
refuse if the estimate exceeds the ceiling. Expected idle trial cost is much lower.

Seven pages of applied Bedrock quotas were inspected: Nova Micro cross-region
requests/minute, tokens/minute and daily invocation-token quota are all zero.
Batch quotas are not playground authorization. Therefore **no Nova Micro prompt
is currently permitted by the preflight**, and no USD20 Bedrock reward is promised.
The prior project diagnostics are preserved; no new call is authorized through
their consumed grants. Target the other USD60 first. The Bedrock reward remains
unclaimed rather than upgrading or repeatedly calling a zero-quota endpoint.

## Verification and evidence

Before writes, recheck Free/credit state, ownership/name absence, service pricing,
region and cleanup guards. Verify generated payloads and bounded cleanup locally.
After each activity, query FreeTier activity status and remaining credits with
bounded checks, allowing up to ten minutes for posting. Report earned versus
pending/blocked amounts separately. Save receipts without credentials. Final
inventory must show zero new budget/function/URL/database/backup/snapshot/
network helpers/schedules/roles/log groups. Verify the original project host is
still stopped with no EIP, original custody unchanged, and no provider call.

Sources checked using Agent Reach:

- [AWS activity requirements](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans-activities.html)
- [AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)
- [RDS Free-plan eligibility](https://aws.amazon.com/rds/free/)
- [Lambda function URL authentication](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)

The owner has authorized the goal and disposable create/delete approach. This
exact USD1 ceiling and resource/cleanup scope await approval under the project's operating rules'
AWS exact cost/resource/rollback gate. No activity resource has been created yet.
