# Remaining RDS reward — renewed execution proposal

Prepared 29 October 2026. Status: awaiting owner approval; no cloud writes.

The owner resumed work after yesterday's pause. Budgets and Lambda earned USD40
and were deleted. The earlier EC2 reward brings additional rewards to USD60/100.
RDS is the next remaining USD20 activity. Yesterday's closed operation, clock and
approval record must remain immutable; use a fresh operation for this renewal.

## Exact renewed scope

Authorize up to **USD1 additional existing AWS credits**, **USD0 cash**, active
Free plan mandatory, for one disposable RDS trial in Stockholm (`eu-north-1`).
This is a ceiling, not expected expenditure. Do not count an unposted reward as
available credit. No upgrade or advanced-feature activation is authorized.

- One PostgreSQL 17.11 `db.t4g.micro`, Single-AZ, encrypted 20-GiB gp3 database.
- Existing default VPC/subnets, one dedicated subnet group and one dedicated
  security group with no ingress and no egress. No public database access.
- One dedicated Scheduler execution role and inline policy permitting deletion
  only of the new database ARN with its operation ownership tag; one verified
  deletion schedule before database creation.
- If RDS automatically creates its standard service-linked role, record its
  prior absence and remove it after the trial only when AWS confirms it is unused.
  Preserve any preexisting role; do not remove unrelated dependencies.
- No workload, connection tests, retained backups or final snapshot; backup
  retention zero. No autoscaling, enhanced monitoring, Performance Insights,
  Extended Support, NAT gateway or additional compute.

No project host start, EIP allocation, application activation, DNS changes,
OpenRouter requests, Bedrock calls, Lambda recreation or budget recreation.

## Timing, cost and teardown

First cloud write must occur on 29 October 2026, Cairo time. The fixed operation
window ends three hours after that write. Refuse database creation after T0+90
minutes. Native deletion is scheduled for T0+two hours, with at most three retries
and maximum event age one hour. A separate local supervisor handles partial
failures and cleanup. Normal deletion occurs immediately after reward confirmation,
or after at most ten minutes of reward waiting once the database is available.
Do not keep a database running just to wait for a reward.

Yesterday's verified price basis: USD0.016/hour instance, USD0.12/GB-month gp3.
Three hours of instance/storage is approximately USD0.058. Conservative burst
allowance: two vCPUs × three hours × USD0.10/vCPU-hour = USD0.60. Other usage
allowance USD0.02 plus 20% contingency gives approximately USD0.814. Fresh official
price, engine availability, account-plan and eligible-credit checks must pass
before writes; refuse if the bound exceeds USD1 or Free-plan access is restricted.
These are estimates, not an enforceable AWS billing cap.

Delete the database with SkipFinalSnapshot and DeleteAutomatedBackups. Verify
the database, associated backups/snapshots, owned network helpers, deletion
schedule and dedicated role/policy are gone. Reconcile the service-linked role as
above. On an uncertain API result, inspect exact names, ownership and receipts
before retrying; never launch a second database. Preserve cleanup guards until
uncertain creation and database deletion are resolved. If teardown fails, retain
the diagnostics/guard and prioritize cleanup; do not claim a clean closure.

Final read-only inventory must also confirm the original project host remains
stopped and no EIP exists. Its retained disk/table and provider custody remain
unchanged. Record reward earned versus pending honestly, then close the operation.

## Preparation and evidence

The existing ten local helper safety tests pass on resumption. The RDS path has
not been cloud-executed. Before any writes, finish local renewal binding and
cleanup orchestration checks, including service-linked-role handling and ensuring
old deletion flags cannot close a new operation prematurely. Do not use the old
initializer to fabricate approval for this renewal. Retain redacted receipts and
delete transient credential-bearing CLI inputs.

Source requirements and previous outcomes are in
[the original proposal](aws-credit-rewards-20261028.md) and
[the closed results](aws-credit-rewards-results-20261028.md). Bedrock remains a
separate blocked activity; this proposal authorizes no model invocation.
