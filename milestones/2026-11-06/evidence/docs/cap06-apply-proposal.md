# CAP-06 resource, cost and rollback proposal

**23 October 2026 — inactive preparation; blocked, not ready for apply approval.**
The [inert inventory](cap06-apply-inventory.json) fixes proposed names, quantities,
settings and required evidence. It is not a CloudFormation/Terraform stack, CLI
input or permission to create anything. No AWS account/credential/model API,
resource, production key, unit, DNS record or public certificate was changed.
The existing Free-plan, Stockholm and USD0cash constraints remain binding.

Recorded consistency checks and review limits are in
[the evidence record](../eval/evidence/cap06-apply-dossier-20261023.json).

The owner selected automatic wake through a generated HTTPS startup link and
direct shopping HTTPS. That selection continues. This dossier consolidates the
[handoff](cap04-deployment-handoff.md), [access bundle](cap06-cloud-access.md),
[host services](cap06-host-services.md),
[Linux rehearsal](cap06-linux-host-rehearsal.md) and
[cost reconciliation](research/2026-10-23-cap06-inventory-reconciliation.md).
It does not close CAP-04/05/06/07 or adopt the conditional observation services.

## Concrete proposal and ownership

The following names and provisioning details are **builder proposals for review**,
not choices the owner has already approved. Before creation, inspect for name
collisions; do not adopt or replace an existing resource merely because its name
matches. Attach an agreed deployment ownership marker to supported resources,
record every returned ID, and verify account/Region/ownership before later edits.
The shared VPC, route table, IGW, NACL, DHCP and registrar nameservers stay outside
the create/delete inventory. If the existing network cannot be used as specified,
stop and revise this package; do not create a new VPC/NAT or alter shared routing.

| Resource               | Exact proposed quantity and binding                                                                                                                                                                                                                                                                                                                |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EC2                    | One `scpilot-capstone-host`, `t3.small` x86_64 Linux candidate, Standard CPU credits; exact authorized subnet/official AMI still required. One Agent worker, IMDSv2 required, hop limit1, IPv6 metadata/tags disabled, no extra automatic public IPv4.                                                                                             |
| Storage/address        | One encrypted20GiB gp3 root volume, baseline IOPS/throughput, retained on termination; one retained VPC EIP and its association to that instance. Termination protection proposed; stop/start is normal operation.                                                                                                                                 |
| Host administration    | One dedicated `scpilot-capstone-host` security group; one `scpilot-capstone-admin` EC2 public-key import. Proposed SSH22 only from verified owner IPv4/32 during maintenance, application80/443 opened separately after gates. No public4000/8000, IPv6 ingress, new SSM/bastion service or private key in AWS configuration.                      |
| Host identity          | One `scpilot-capstone-host` EC2-trusted IAM role, one instance profile, one inline policy. Initial policy is scoped DynamoDB runtime authority only; model grant remains held. No host EC2-control, S3 artifact/backup or administrative permissions.                                                                                              |
| Authority              | One `scpilot-capstone-control` Standard on-demand DynamoDB table, string `pk`/`sk`, namespace `scpilot-capstone`. No indexes/streams/PITR/TTL/replicas. Deletion protection proposed. Separate owner initialization; runtime never creates/reinitializes authority.                                                                                |
| Private objects        | One `scpilot-capstone-{verified_account_id}-eu-north-1` general-purpose S3 bucket; exact resulting name must be checked for availability. All public access blocks, BucketOwnerEnforced, SSE-S3; no versioning or automatic expiry proposed. `waiting/`, `releases/`, `catalogue-backups/` only. No participant/code/key/allowance backup objects. |
| Startup delivery       | One pay-as-you-go CloudFront distribution with generated hostname/certificate, two origins, two always-sign SigV4 OACs (S3 and Lambda), one custom control origin-request policy. Managed disabled-cache policy is referenced, not created. No viewer Function, custom alias/certificate, flat-rate plan or second distribution.                   |
| Startup/control        | Two Python3.12 x86_64 ZIP Lambdas: `scpilot-capstone-startup` and `scpilot-capstone-controller`, outside VPC, each proposed256MiB/30s/512MiB temporary storage, no provisioned concurrency/layers. One AWS_IAM Function URL on startup only. Reserved concurrency1 each is a candidate requiring quota evidence, not a budget cap.                 |
| Lambda identities/logs | Two same-named Lambda-trusted IAM roles, one inline policy each; two explicit `/aws/lambda/NAME` log groups, retention7days. Precreate groups; runtime may only create/write its own streams.                                                                                                                                                      |
| Public shopping        | Two existing-registrar A records, `app.scpilot.tech` and `store.scpilot.tech`, pointing only to the bound EIP; proposed TTL300 where supported. One host target owns three application services and a required root metadata oneshot. Caddy retains ACME state outside code.                                                                       |

Base IAM count is **three runtime roles, one profile and three inline policies**.
S3 bucket policy and the two startup Function URL invoke statements are resource
policies, not extra IAM roles. EC2's primary network interface, instance-profile
association and root-volume attachment are instance dependencies; record their
ownership/IDs if required for teardown, but do not allocate a second interface,
address, volume or profile. Registrar records are updates, not a new hosted zone.
No new customer-managed KMS key, ECR, Secrets Manager, NAT, ALB, RDS, Redis, WAF,
paid support or notification channel is proposed.

The candidate egress scope is TCP80/443 for reviewed HTTPS/ACME/package needs;
resolver behavior requires host/network verification. Security groups cannot
filter AmazonProvidedDNS, so this is not a DNS security boundary and no DNS
Firewall service is added. [AWS security-group rules](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html).
Internet egress for provisioning, uploads/downloads and maintenance must fit the
costed transfer quantities, not be presumed free.

Static origin proposal: private regional S3 REST domain with origin path
`/waiting`, default root object `index.html`, and a verified existing managed
static cache policy. Keep `/wake` and `/status` on the exact uncached Lambda
behavior. The control policy's seven-method CloudFront allowance is a transport
requirement; the handler still rejects unsupported methods. No additional custom
cache policy is counted or required by this proposal.

The **conditional addition** is exactly one dedicated Scheduler group
`scpilot-capstone-observation`, schedule `tick`, invoke-only execution role of the
same group name with one inline policy, one fixed-dimension EMF custom metric and
two standard alarms. This makes four runtime/execution roles and four inline
policies only if separately adopted. Existing controller is reused; no third
Lambda/SNS/SQS/DLQ. The renderer always returns a DISABLED one-minute schedule,
finite UTC window, retries0/age60/flexible OFF/completion NONE, and alarms with
actions disabled/no action ARNs. Controller async retries0/age60 applies to all
its asynchronous invocations, not just ticks. Dates and adoption remain unbound.
Schedule/metric/alarm charges remain possible even when the host is stopped;
schedule completion NONE leaves retained configuration requiring teardown.

## Binding stages and permission boundaries

Null fields in the inventory are deliberate, not sample deployed identifiers.
Generated IDs cannot exist before creation. There are three separate stages:

1. **Before any creation:** verify account identity, Free plan/current eligible
   balance and other usage; authorize existing network/image/admin path; approve
   exact names/settings/costs/finite window/retention and rollback. Resolve the
   model prerequisite and production build/provisioning/isolation gaps below.
   No fresh account check occurred in this preparation. Prior availability
   AUTHORIZED/AVAILABLE and zero applied model quotas remain historical evidence.
2. **Private creation receipts, after a future bounded approval:** capture returned
   instance/volume/EIP/security-group/keypair/role/profile/table/bucket/distribution/
   OAC/policy/function/log identifiers and configuration digests in a protected
   execution record. Record generated values rather than guessing them. Creation
   authority is not exposure, model spending or permission to alter unrelated
   objects. A failed stage preserves receipts for targeted recovery; never rerun
   the whole creation sequence against uncertain outcomes.
3. **Before activation:** bind exactly those receipts into existing
   `CloudAccessBindings`, `ControlSettings`, `ObservationBindings` and HostSettings.
   Record actual CloudFront origin/Function URL, approved release/ZIP hashes,
   authority and ledger identities, key-custody reference, rollback release and
   final phase-specific approval. Public exposure and any ENABLED schedule require
   separate acceptance of the fully bound result. Changing one binding invalidates
   its dependent policies/configuration/readiness proof; regenerate and review.

Deploying CloudFront and then scoping origins to its returned distribution ARN is
a staged process: start private/disabled, establish actual origins and exact OAC
policies before enabling delivery. Do not use a public S3 bucket, anonymous
Function URL or wildcard SourceArn to break a creation-order dependency.

Two binding requirements are conditional, not universal creation prerequisites.
Observation adoption approval is required before creating its conditional
resources, and before unattended automatic-wake acceptance; it is not required
for an otherwise approved base-only private preparation stage. A prior rollback
release hash is required only when a previously qualified compatible release
actually exists and code rollback is proposed. First deployment instead uses
the explicit safe-stop recovery branch below, with no invented fallback hash.

The existing access renderer binds Lambda runtime DynamoDB GetItem plus
transactional PutItem/UpdateItem/ConditionCheckItem to the exact table/namespace,
with the required EnclosingOperation conditions. No fictitious
`dynamodb:TransactWriteItems` IAM action, Query/Scan/DeleteItem, initializer or
table-admin grant belongs in runtime roles. Startup may invoke only controller;
controller may Start/Stop only the exact host. Region-bound DescribeInstances
uses Resource `*`; it is not arbitrary instance selection by callers.

Host policy documents still need a bound review: reuse the same narrow table/
namespace runtime actions, omit Lambda log and EC2-control grants, and later add
only `bedrock:InvokeModel` for the exact qualified regional foundation model.
The current adapter uses Converse, whose IAM action is InvokeModel; do not add
streaming, wildcard-model, profile-routing or BedrockFullAccess permissions.
The model grant is withheld until explicit spending/qualification conditions are
met. [AWS Converse permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html).

Owner deployment and initialization authority stays separate from those roles:
resource creation/tagging, scoped PassRole, policy attachment, authority
initialization/issue/revoke/status and backup custody are privileged operations.
There is no newly created administrator IAM user/role in this proposal. The
owner must verify their existing session can perform the exact approved actions;
do not escalate, upgrade or broaden runtime permissions when denied.

## Host build, credentials and retained state

Proposed provisioning is an owner-controlled native Linux build of clean reviewed
source, followed by SSH/SCP of verified artifacts and independent digest checking.
The Windows-derived rehearsal ZIP is never the installation artifact. The28
runtime wheels in `eval/linux-host-runtime.json`, including uvloop0.22.1, are a
candidate Linux lock; exclude packaging26.3 (diagnostic only). Production lock
adoption, exact Python3.12 interpreter provenance, AMI/kernel/security approval
and a fresh native build/runtime check remain required. Node24.13.0 and Caddy2.11.7
candidate vendor digests are already retained; they are not claims of newest or
currently approved secure versions. Verify licence/provenance/security and do not
download/install packages from first-boot user-data with unpinned scripts.

Only `shopping-copilot-host.target` is intended for later enablement. It owns
three application services and a required metadata oneshot, with the legacy-unit
conflict preserved. Separate service users/config/state and the root firewall
exception are specified in [host isolation](cap06-host-isolation.md). No users,
permissions, firewall rules or units are installed by this dossier. Provisioning
must prove root-owned immutable code/interpreter, private per-consuming-UID files,
catalogue group/read-only mount and native service behavior before activation.

Canonical configs: `/etc/shopping-copilot/agent/host.json`,
`/etc/shopping-copilot/store/store.json`, `/etc/shopping-copilot/proxy/proxy.json`,
and root-only `/etc/shopping-copilot/metadata.json`. Catalogue is retained under
`/var/lib/shopping-copilot/store`; inference ledger under `.../agent`; certificates
under `.../caddy`. Private service-secret bytes are duplicated into distinct
Agent/Store owner-only files; proxy receives neither copy. Readiness is Agent-only.
Per-service logs use `/var/log/shopping-copilot/{agent,store,proxy}`. All state/logs
remain on the single20GiB volume. Never initialize state during launch, relax
private checks, install a derived Windows rehearsal fixture or reset authority.
Catalogue backup uses the SQLite backup API; it is not an allowance backup.

One readiness key generation is shared between the protected host raw key and
controller-only `COPILOT_READINESS_KEY_HEX`; startup must not receive it. Lambda
configuration access is privileged secret access. Keep protected local staging,
never paste key/config values into CLI arguments, shell history, logs or source.
Use owner-held custody references in this dossier, not actual secrets. The service
secret remains host-only. Invitation/lifecycle identities are initialized once
by separate owner authority; they are not regenerated on deploy, window renewal,
host replacement or rollback. No new inference ledger/allowance is authorized;
existing uncertain accounting and diagnostic holds must be reconciled first.

**Local implementation and disposable proof are prepared; host activation is
unverified.** Separate UIDs and an own-chain nftables output barrier now reject
IPv4/IPv6 metadata for Storefront/proxy while allowing Agent and trusted root.
Application units BindsTo/After the required barrier. Repeated application is
idempotent in meaning; failed batches preserve the old policy. Actual Linux UID,
packet, catalogue/WAL/restart and bounded redacted-log checks are recorded in
[host isolation](cap06-host-isolation.md). No real IMDS/account was contacted.
IMDSv2/hop1 alone still does not separate local processes. Root is deliberately
trusted; active oneshot state does not detect external root firewall deletion.
[AWS IMDS access restrictions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-metadata-limiting-access.html).

Actual AL2023 systemd252 boot/stop/restart/capability enforcement, native approved
provisioning/runtime lock, Agent SDK/lifespan/signed readiness, measured combined
capacity and durable-log retrieval across reboot remain required. Stream output
is discarded; the new logs record process lifecycle only. Candidate admission/
inference limits are unmeasured; model qualification, prices, allowance and
finite invitation windows remain unapproved/unbound. No cloud gate is closed.

## Cost decision and stop criteria

The dated primary-source worksheet and independently checked evidence are
[here](research/2026-10-23-cap06-inventory-reconciliation.md) and
[here](../eval/evidence/cap06-linux-host-20261023.json). These are60-day gross USD
scenarios before credits/tax, with unmeasured traffic/durations, not bounds:

| Scenario                                                                          |      Amount |
| --------------------------------------------------------------------------------- | ----------: |
| Revised base infrastructure, excluding conditional observation workload           |   46.253592 |
| Additional conditional observation/monitoring allocation under that workload      |  22.1066776 |
| Continuous infrastructure                                                         |  68.3602696 |
| Continuous plus unapproved11future-model planning allocation and separate0.03hold |  79.3902696 |
| Same combined inputs,120EC2running hours                                          |  50.8782696 |
| Same continuous inputs, non-tick Lambda averages30billed seconds rather than2     | 102.7236496 |

The two Lambdas each have100k assumed non-tick executions,256MiB/2s average billed
duration; timeout30s is not billed-duration evidence. Conditional86,400ticks are
separate,256MiB/30s with160RRU/144WRU each. Edge traffic is200k static/control
requests; shared table/log allowances are single-counted. Do not add the old
rounded23allocation again. Agent lease activity, actual INIT/duplicates/bytes,
bot/rejected traffic, delivery geography, admin transfer, resource retention,
budget/metrics API use and other account usage still need measured/approved
quantities. Controller/startup concurrency is not a spending cap.

The proposed USD80 envelope is unvalidated; continuous example headroom is only
USD0.609730 and the sensitivity exceeds it. USD11 is not model-call authorization;
USD0.03 is an existing hold across previously authorized USD0.04, not confirmed
cost or another0.04charge. Do not release/reuse either ledger or assume USD100 is
still available. IPv4 and Scheduler credit applicability, actual Free-plan access
and other usage remain unverified; inability to contact Support does not block
preparation but does not authorize cash charges. Stop if a stage requires Paid
plan/advanced features or a service outside the approved inventory. Disable new
work and follow the owned drain/stop procedure for budget/account failures; a
delayed alert cannot ensure USD0cash. No budget alarm/recipient/action was created
or silently added to the two lifecycle alarms.

## Future activation sequence — not executed

1. Resolve model usable quota/strict CAP-05 qualification and the missing host/
   account/cost/binding evidence. Prepare final bound policies, native release,
   hashes, finite dates, ownership marker and recovery record. Obtain specific
   resource/cost/rollback approval only after that result is reviewable.
2. Under that approval, create only dedicated approved resources, initially
   private/inactive. Capture receipts as each creation succeeds. No public
   application ingress, initialized inference allowance, enabled schedule or
   active distribution is implied. A provisioning host may need narrowly scoped
   SSH/egress and its basic running cost; price and approve that stage explicitly.
3. Bind exact table/namespace and initialize authority once through separate
   owner permission, recording identities privately. Verify no existing state
   would be overwritten. Stage protected configuration/key custody and only the
   separately authorized inference ledger. Verify host/Lambda policies and exact
   Function URL/OAC signing with owned controlled checks; keep runtime model gate
   closed until its real qualification implementation is reviewed.
4. Verify native units/permissions/process metadata isolation/redacted diagnostics
   and bounded real-host readiness with retained authority. If external TLS is
   needed for that acceptance, obtain the specific DNS/TLS exposure approval first,
   inspect conflicting A/AAAA/CNAME/delegation/CAA and preserve a before record.
   Open only required80/443 and update only the two A records. Never grant browser
   access to private/readiness internals or bypass certificate verification.
5. After exact origin/policy binding, enable the generated startup path. If
   Scheduler is adopted and approved, qualify its target/role/log/metric/alarms,
   controller no-retry behavior and owned stop procedure before enabling the
   finite schedule. Alarms have no notification actions; designate an actual
   owner review/stop responsibility before testers enter. Test browser-independent
   wake completion and closed-browser idle drain/stop with uncertain-command fences.
   Without adopted and qualified browser-independent observations, unattended
   automatic-wake acceptance remains blocked. Owner manual prewarming is the
   previously approved fallback, not evidence that the automated path passes.
6. Admit only bounded invitations after desktop/physical Android, safety,
   accounting, shutdown/restart and rollback evidence passes. Preserve origin,
   Sensitive Field, Confirmation, stale/duplicate Action and uncertain-outcome
   non-replay invariants. No public demo or production-readiness claim follows
   from the existing local tests.

## Recovery and teardown order

**First-deployment failure:** no previously qualified cloud release is available
in the current evidence. Keep exposure/admission/provider closed, fence new wakes,
drain owned work and use approved owner-driven observations to confirm the exact
host is stopped. Preserve authority, allowance and uncertain claims/reservations;
never manufacture a prior release hash or select an unqualified checkout. Retain
the stopped resources/state for investigation or use only separately authorized
targeted teardown below. Stopping retains billable storage/address/control state.
This safe-stop mode permits a future bounded creation approval without pretending
that code rollback is available.

**Later code rollback, only with a separately verified compatible previous
release:** first block new wakes/admissions without prematurely removing
the controller/authority needed to stop. Drain accepted work with the existing
generation/lease fences; if a model or EC2 command outcome is uncertain, preserve
its reservation/claim and investigate rather than retry. Stop the owned host
target and verify its cgroup/processes/sockets are gone. Check the previous clean
release against **current** external state/schema/dependencies, select it and
update the protected fingerprint and controller's expected release together.
Invalidate readiness while these bindings differ. Restart one target and verify
signed health/admission before reopening. Rollback restores code, never earlier
ledger, invitation/lifecycle snapshots, key state or counters. Storefront restart
resets its in-memory shopping state; provide the existing explanation/fresh link.

**Failed creation:** stop at the failed stage, retain exact receipts/unknown
outcomes, and inspect those resources under separate authority before retry or
cleanup. A timeout is not proof a creation or command failed. Disassociate/release
only the task-owned EIP when safe; do not delete an existing network or matching
name discovered later. Partial creation can already accrue costs.

**Final teardown, under explicit retention/deletion authorization:**

1. Disable the observation schedule if it exists, block new startup/admission,
   revoke/expire invitation authority and drain active work. Keep controller and
   table until the exact designated host is confirmed stopped. Account/role/session
   compromise needs owner containment; do not restore old counters to recover access.
   Once scheduling is disabled, the approved owner procedure must drive bounded
   authenticated controller observations through drain/stop confirmation; leaving
   its function deployed does not execute those passes. Fence stale START authority
   first. Unknown command outcomes require investigation, not reissuing the command.
2. Disable CloudFront delivery and wait for the actual disabled state; keep its
   exact origin policies bound until no delivery is possible. Remove/restore only
   task-owned DNS changes after comparing current records against the saved
   task-written values. Never overwrite an intervening owner change. Remove the
   exact distribution/OAC/custom forwarding policy and startup Function URL/grants
   after their dependencies release; no shared managed cache policy deletion.
3. Preserve agreed restricted catalogue/accounting/evidence until reconciliation.
   Remove host public/SSH access. After the stopped state is confirmed and
   retention is agreed, disassociate/release the exact EIP, remove profile/role
   attachments and terminate only that instance (disable its proposed termination
   protection deliberately). The retained root volume is a separate deletion
   decision; its delete-on-termination=false does not make it free.
   After the instance/profile association is gone, remove the host role from its
   dedicated instance profile and delete that profile, then delete the dedicated
   host inline policy and role after confirming no remaining attachments/users.
   Explicit approved retention is the alternative; detach alone is not teardown
   of these three inventory objects. Never delete an identically named shared role.
4. Remove the two dedicated functions, their log groups and their role policies/
   roles when no invoker remains; remove both alarms, conditional schedule/group/
   execution role, and verify no other metric producer remains. Disabled alarms
   and retained logs can still charge. A custom metric is not a separately created
   control-plane resource to delete; cease its producer and verify later billing.
5. After final state/charge reconciliation and retention approval, delete only
   dedicated EBS/S3 objects/bucket/table and host security-group/keypair references.
   Review table deletion protection and dependencies before deliberate removal.
   Never delete retained authority/allowance to reset a quota; preserve the agreed
   final restricted record and unresolved diagnostic hold. No shared VPC deletion.
6. Inventory remaining resources and delayed usage/costs until residual charges
   reconcile; stopped host EBS/EIP alone are10.544USD in the60-day worksheet, before
   independent control/storage/log/monitoring usage. No new timed automation,
   follow-up account polling or reminder is created by this checklist.

## Current handoff

This dossier completes the offline inventory/sequence consolidation, not the
blocked prerequisites themselves. Next is **native production provisioning/lock
and actual-host acceptance of the prepared
credential/process isolation and durable diagnostics**, followed by a fully bound
approval/execution package.
Current model quota/qualification and account/credit/workload evidence remain
independent blockers; no further model attempt, sign-in, quota-increase request,
upgrade or resource experiment is authorized here. Continue local work without
repeating the unavailable Support request or weakening any gate.
