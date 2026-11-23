# RDS activity reward completed — 29 October 2026

The owner approved the [renewed RDS-only proposal](aws-rds-reward-renewal-20261029.md)
with a USD1 additional existing-credit ceiling, active Free plan and USD0 cash.
One private encrypted PostgreSQL 17.11 db.t4g.micro/20-GiB gp3 trial earned the
USD20 reward. AWS now reports four completed activities: EC2, Budgets, Lambda
and RDS, totaling **USD80 of the additional USD100**. Bedrock remains NOT_STARTED;
no model request was made in this session.

Fresh final account observation: **USD179.74 remaining**, Free plan active. This
is the observed credit balance, not final billing or a measurement of trial cost.
Fresh preflight confirmed the exact engine/class/storage offering and prices
USD0.016/hour compute and USD0.12/GB-month storage. Conservative approved
three-hour cost bound was USD0.8136. The trial operation closed after approximately
7 minutes 9 seconds; its original three-hour clock was never extended.

The native deletion guard was verified before database creation. Its first
creation was rejected because Scheduler requires `DbInstanceIdentifier` in its
universal RDS target, whereas the direct RDS CLI uses `DBInstanceIdentifier`.
The retained error was inspected before retry; a regression failed then passed
with the correction. Existing owned role/policy were reconciled in the same
session. No database existed at that initial refusal; only one was created.
The corrected schedule and zero-ingress/zero-egress security group passed actual
readback. No database connections, workload or public exposure were introduced.

AWS marked the activity completed while the database was creating. Deletion
began immediately. Final independent inventory verified zero trial databases,
manual snapshots, automated backups, subnet groups, security groups, schedules,
cleanup roles and newly created RDS service-linked roles. The last role was
removed through AWS's asynchronous deletion and verified absent. The local
bounded supervisor exits on the closed state. Original project EC2 remains
stopped, no active EC2 or EIPs exist in Stockholm, and retained project disk/table
storage remains under its prior allocation. Project custody, provider cap,
OpenRouter reserve, application services and DNS were unchanged.

Verification: **14 local safety tests passed**, including renewed RDS-only scope,
cleanup ordering, stale deletion flags, Scheduler field spelling, exact ownership,
private encrypted sizing, backup API schema and credential redaction. Application
source did not change. Sanitized evidence:
[final receipt](../eval/evidence/aws-rds-reward-20261029.json). Protected operation
pointer: `.scratch/aws-credit-rewards/renewal-operation.txt`; original approval,
API receipts and executed helper snapshots are retained there.

The remaining USD20 Bedrock reward is unclaimed. Previous applied invocation
quotas were zero; this RDS-only grant authorizes no Bedrock prompt or quota change.
Next project frontier: separately reviewed public startup-link/HTTPS deployment
proposal and acceptance plan. No additional host start, EIP, public activation,
DNS changes or model spending are authorized by this completed trial.
