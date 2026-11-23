# CAP-07 Controlled Host & Application Acceptance

26 October 2026. **Offline design for owner review; not execution approval.**

The owner requests one consolidated private-host session: systemd isolation,
protected OpenRouter custody and startup binding, signed application readiness,
one controlled reboot, bounded capacity checks, then stop and EIP release. Local
preparation must finish before that session; there are no intervening cloud
micro-stages. This document chooses the implementation details below for review.

## Starting point and acceptance boundary

Use the existing Stockholm host and encrypted 20-GiB retained root. The last
observation, **26 October 18:57:44 UTC**, was stopped, no public address and no
allocated EIP. This is retained evidence, not a new account check. The preceding
USD 0.25 provisioning grant is complete and cannot fund another boot.

The observed AL2023 host has systemd 252.23, system Python 3.9.25, parallel
Python 3.12.14, Node 24.22.1, Caddy 2.11.7, nftables 1.0.4, approximately 1.865 GiB RAM,
and a fully allocated root-owned 0600 1-GiB swap file. Six application units were only
statically checked; they remain unenabled. Metadata rules, actual custody,
application serving and reboot persistence were not tested. See
[the provisioning result](../cap06-private-provisioning-results.md).

Keep the installed native release:

- Source: `023d9f621bc9432b871e519d51e6ce57bb7dc204`.
- Archive: `5e5e3843160225b81b81f3dd79bb960fc82507134ae7a7f58896020d5cd28a23`.
- Manifest: `efc1f9da4388c24b9e8b312aed2871c1aa7174f78370a531f2400a8c6b9d0757`.

Pass means this exact runtime can serve the Controlled Storefront privately with
the real authority, protected binding and signed readiness, survive one reboot,
and meet the bounded captured-workload capacity criteria. It does not establish
public ACME, public DNS, the generated automatic-wake link, Android/public-browser
acceptance or live OpenRouter latency/throughput. Those deployment acceptance
items remain visible in the checkpoint. No independent-storefront work is added.

## One resource envelope

The [cost/resource proposal](../cap07-controlled-host-acceptance-proposal.md)
is the approval surface. It proposes a four-hour absolute window, at most one
StartInstances and one controlled reboot of the existing host, one temporary EIP,
and at most USD 0.25 additional eligible AWS credits, with mandatory Free plan and
USD 0 cash. No helper, additional EC2/EBS, NAT, load balancer, CloudFront, Lambda,
S3, public certificate or DNS change is included.

The actual `create_host_app` constructs a DynamoDB invitation/lifecycle backend;
the host currently has no instance profile or control table. Include these
minimum dependencies **in this same session**:

- One Stockholm Standard, on-demand table, string `pk`/`sk`, no indexes, streams,
  PITR, backups, replicas or provisioned capacity. Name
  `scpilot-cap07-control-<operation8hex>`, namespace `cap07_<operation8hex>`.
- One EC2-trusted IAM role, instance profile and inline policy. Host access is
  only `GetItem` and transaction-enclosed `PutItem`, `UpdateItem`,
  `ConditionCheckItem` on that table, with exact non-null `dynamodb:LeadingKeys`
  equal to the namespace and `aws:RequestedRegion=eu-north-1`. Reuse the conditions
  in `deploy/cloud_access.py`; omit its Lambda log/controller permissions. No host
  EC2 control, IAM, Bedrock, S3 or general DynamoDB grant. Initial Query/creation
  operations run under the existing operator identity, not the host role.
- Initialize invitation and lifecycle authority once through the existing
  `DynamoInvitationStore.initialize` / `DynamoLifecycle.initialize` APIs. Retain
  their identities. A nonempty namespace, conflicting resource, unexpected
  policy or uncertain create result stops execution for reconciliation; never
  erase/reinitialize it or blindly retry creation.

Use only synthetic invitation/shopper data in this namespace. Table content must
stay below1 MiB, with conservative limits of10,000 write units and 20,000 read units
for the session, counting transaction/size multipliers. The operation driver
bounds requests and retains sanitized consumed-capacity observations; local
rehearsal must prove these ceilings conservatively before cloud entry.

Pin the existing admission defaults explicitly in host configuration:
maximum_bytes=2621440, global_rate=1000/minute, browser_rate=120/minute,
maximum_requests=16, maximum_streams=16, maximum_sessions=20, browser_sessions=2.
Use separate bounded invitations for the control and captured lanes, each with
at most 16 redemptions/16 session creations and expiry at the session deadline.
Use distinct synthetic browser identities per cohort member; eight shoppers are
not eight tabs under one browser allowance. Preserve invitation counters, revoke
the two invitations on teardown, and never reset authority to replenish quotas.

Retain the table, narrow role/profile and protected encrypted-root state for
continuity through the existing **23 December 2026 18:00 UTC retention review**.
That is a review deadline, not deletion permission or an extension of root
retention. The stopped host may retain the narrow profile. There is no ongoing
poller, scheduler or compute. No table may silently become a fresh authority on
the next stage.

## Isolation and bounded storage

Enable the existing host target and component units under systemd 252. Keep the
legacy combined service and vendor nftables service masked. Preserve:

- Distinct `copilot`, `copilot-store`, `copilot-proxy` users; root-owned immutable
  runtime/release; per-component private files and writable state only. Catalogue
  sharing uses `copilot-catalogue`, directory2750/database0640, including correct
  WAL/SHM ownership. Agent reads catalogue without writing its state/sidecars.
- NoNewPrivileges, strict system filesystem, protected home, private temporary
  directory, restricted namespaces/SUID/address families, invisible other
  processes, explicit writable paths. Verify actual PID UIDs, groups, mount
  namespace and cgroup limits, not just `systemctl cat`.
- Agent/Store/proxy MemoryMax1 GiB/256 MiB/256 MiB, TasksMax64 each, descriptor4096;
  metadata128 MiB/8 tasks/256 descriptors. Do not raise limits to pass capacity.
- Caddy effective, permitted, bounding and ambient capabilities contain only
  CAP_NET_BIND_SERVICE; the binary has no file capability. Other app processes
  have no capabilities. Metadata oneshot is root/CAP_NET_ADMIN-only/AF_NETLINK.
  Inspect the low-port sysctl before interpreting a no-capability bind test;
  do not change the global sysctl just to manufacture a passing demonstration.

Verify negative cross-UID file access and writes to runtime/configuration, plus
positive service access. Use harmless bounded fixture files for denial tests;
never print real secrets, process environments, response tokens or whole logs.

The metadata unit must load its existing owned `inet scpilot_metadata` rules
before any component starts. Allow only trusted root and the Agent UID to reach
IMDS; reject Store/proxy/other UIDs for IPv4 `169.254.169.254` and IPv6
`fd00:ec2::254`. Require IMDSv2, hop limit1 and disabled metadata IPv6. An Agent
token request may return a token that is discarded without logging; do not fetch
or print role credentials. Verify denied UIDs with short, no-proxy token requests,
rule counters and ruleset inspection. IPv6 is a ruleset denial proof while the
EC2 IPv6 endpoint remains disabled, not a claimed successful IPv6 network test.
Test failed metadata activation prevents application startup. Restore the valid
configuration and explicitly restart the host target after the negative test.

Add a bounded persistent journald drop-in: SystemMaxUse64 MiB, RuntimeMaxUse16 MiB,
SystemKeepFree1 GiB, MaxRetentionSec7 days, RateLimitIntervalSec30s,
RateLimitBurst200. This intentionally affects this dedicated host's journal.
Preserve app stdout/stderr suppression and existing private lifecycle logs:
64 KiB current plus two backups per component, seven-day retention. Caddy retains
1 MiB current plus two backups, seven days. Prove rotation/redaction and refusal
on bounded synthetic quota/full/lock fixtures; never fill the real root or use
the allowance database as a log test. The journal is not the spending ledger.

## Custody without a reset

Provider selection stays explicit: OpenRouter `google/gemini-3.5-flash-lite`,
fixed API endpoint, total key cap USD 2.00 non-resetting, current guarded price
ceilings USD 0.30/2.50 per million input/output tokens, effective timeout30 seconds,
queue2 active/3 waiting/8 seconds. No Bedrock attempt, new key, top-up or cap increase.

The [custody preflight](../cap06-custody-preflight.md) established two existing
ledgers,156 and 72 settled attempts, totaling228 deduplicated settlements and
USD 0.29469302. Nineteen older uncertain reservations retain USD 0.255886201.
Neither existing remainder is a deployment grant or enough for signed readiness,
whose maximum reservation is USD 0.0831488. This plan explicitly proposes a
**USD 0.10 readiness allocation inside the unchanged USD 2 ceiling, with zero live
model POSTs authorized**. The kernel barrier below makes that distinction real.

The selected authoritative ledger is the existing **156-attempt shared ledger**,
preserving its UUID and every original row. A narrowly scoped offline operator
handoff utility is needed; the runtime has no allowance-extension/import API.
Prepare and test it using synthetic custody only before cloud execution:

1. Quiesce every local key user and ledger writer in both checkouts; stop local
   serving/evaluation processes. Keep protected recovery backups, retire active
   local dotenv key entries, and do not leave a parallel spendable local runtime.
   No source control, shell argument or public receipt may contain key material.
2. Validate a consistent SQLite backup, UUID, policy, row identities and exact
   source receipts. Import only the other72 settled attempts absent by verified
   attempt identity, preserving reservation/charge/settled values. Conflicting
   duplicate IDs or unattributable rows refuse the handoff. Never sum cumulative
   snapshots or delete/settle an existing uncertain row.
3. Import the 19 missing uncertain reservations individually, with stable
   receipt-bound IDs and conservative per-attempt nanodollar rounding. Retain a
   private source-ID map. Counts and totals must match the accepted baseline;
   subsequent real activity requires a revised reconciliation, not an assumption.
4. Permit one bounded authenticated **GET of the existing key status**, no model
   call, under future approval. Let S be exact known settled nanodollars, H the
   retained uncertain reservations, and U the upward-rounded provider aggregate
   usage. Preserve an additional unresolved hold of `max(0,U-S)` when positive.
   The conservative accounted baseline B is `S + H + max(0,U-S)`. This covers an
   unattributed provider gap without pretending it is a refund or a known attempt.
5. In one audited transaction set the absolute allowance to `B + USD 0.10`,
   **only if that is at most USD 2 and the current non-resetting key remaining
   limit covers H + USD 0.10**. Preserve identity, original rows and holds; record
   the explicit allocation separately from historical qualification grants.
   Refuse missing/ambiguous cap, unexpected history, insufficient credit or a
   changed model/configuration. Do not initialize a replacement ledger.
6. Copy the canonical disabled ledger and existing key into Agent-owned protected
   paths outside the release, verify independent source/destination manifests,
   and transfer sole writer custody. After the egress barrier is verified, enable
   the ledger for readiness. The72-attempt source and old156-attempt source remain
   disabled protected evidence, not deployable alternatives. If interrupted,
   disable both possible writers and reconcile; never choose the newest filename.

Real key, key digest, ledger UUID, private receipt IDs and readiness/service keys
stay out of public evidence. Files are owner0400/0600, non-link and distinct;
parents are protected and destinations are not inside release/artifact output.
The Store gets only its own service-key copy; proxy gets only its leaf TLS key.

Install the existing accepted report and reconciliation bytes unchanged beside
the binding. Report SHA256 is
`7a168063cc6b179cd484e7c6098923a8592b737752dd3908e0dd3a0e1853fd98`;
reconciliation SHA256 is
`8ae076766b9ac6609b437007f363e1ddd95676a19e99d315f8dffc05112fb9a9`.
Generate the existing strict binding schema against the exact installed release,
configuration fingerprint, canonical ledger UUID and existing key digest. Its
expiry is the session's absolute deadline. Put the independently checked binding
SHA in a root-owned Agent ExecStart drop-in with both qualification arguments.

Keep the approved semantics: protected evidence/custody hashes and actual
GuardedClient/OpenRouterClient identity are checked at startup; subsequent
qualification observes captured state and expiry. No per-request disk rehashing,
20-source-file runtime pinning or self-authorizing `ready=true` flag. Test wrong
pin/key, expired binding, missing evidence and disabled allowance using synthetic
fixtures, without corrupting the canonical ledger or secretly substituting a
client for the real readiness proof.

## Private TLS, real readiness and a zero-call barrier

The production proxy launcher selects `Caddyfile.public`; that ACME profile is
not appropriate for this session. Prepare an acceptance-only root-owned proxy
ExecStart override using the existing private `deploy/Caddyfile` contract:
`app.scpilot.tech` / `store.scpilot.tech`, **loopback 443 only**, real Agent8000 and
Store4000 upstreams, admin/automaticHTTPS/persistconfig off, private routes and
service-header stripping preserved. Use one short-lived private CA/leaf with both
SANs, no global trust installation. A managed `/etc/hosts` block maps these names
to loopback for the on-host probes. Back up and restore that exact block.

Use real TLS with an explicit SSLContext containing only that CA; preserve SNI
and hostname verification, no `-k` or mocked readiness transport. SG ports 80/443
remain closed, SSH stays restricted to one freshly verified operator IPv4/32.
No public ACME request or DNS mutation is permitted. This accepts the private
proxy profile only; public ACME remains a later deployment check.

Alongside the metadata table, install a separate acceptance-owned nft output table
for the Agent UID: allow TCP443 only to the freshly resolved Stockholm DynamoDB
endpoint address set, reject its other TCP443 destinations. Preserve loopback
traffic, metadata policy and existing SG egress. Resolve and freeze the endpoint
set before enabling real custody; if it changes or cannot be verified, fail closed
rather than widening to all HTTPS. Recreate this table before Agent startup on
both boots. It blocks the fixed OpenRouter HTTPS endpoint, including key lookup;
readiness uses captured qualification and does not need that endpoint. Verify a
short uncredentialed OpenRouter connection is rejected, while actual DynamoDB
authority operations succeed. Never send the real key in a denial test.

Use a root-owned oneshot `scpilot-cap07-egress.service`, AF_NETLINK and only
CAP_NET_ADMIN, with RemainAfterExit and the fixed deadline precheck. Agent, Store,
proxy and the later capture unit get Requires/BindsTo/After drop-ins for this
barrier as well as the existing metadata unit. A failure of either barrier must
prevent serving. Touch only the two operation-owned nft tables, never flush the
host ruleset. Verify an Agent GetItem in a different namespace is AccessDenied;
an empty successful lookup does not prove the IAM boundary.

The operator initializes/advances real lifecycle authority using its existing
conditional APIs. Keep authority `stopped`/generation 0 during OS preparation;
sandbox probes use short fixture commands with the component's exact systemd
properties, not an Agent lifespan against generation 0. After custody, barriers,
Store/proxy configuration and TLS are ready, call `manual_start` once, claim its
start command, verify that the designated EC2 host is already running from the
one observed start, and acknowledge that certain outcome without dispatching
another StartInstances. Start the real application target immediately and finish
signed readiness/reconcile inside the existing 300-second startup deadline. Do not
start this deadline while still provisioning, reset it, or mint another generation
to recover a failed startup. Synthetic metadata-dependency refusal is tested
before the real lifespan, with the target otherwise stopped.
Probe with `HTTPSReadinessProbe`, a fresh nonce, exact release and current real
generation; reconcile healthy only from the verified signed result. All five
real checks must pass: release, storefront/catalogue, admission, allowance,
captured provider qualification. A plain200 or replayed/stale signature is not
readiness. Wrong key/release/generation/nonce and unsigned requests must refuse.

## One reboot without renewing the window

T0 is recorded before the first resource mutation. Hard end is T0+4 hours, shared
by creation, first boot, reboot, testing, StopInstances and EIP release. At
T0+210 minutes begin mandatory teardown; all optional tests cease. No reboot after
T0+135 minutes. All capacity/meaningful-work activity ceases by T0+160 minutes;
normal guest cleanup and stop/IP release finish by T0+180 minutes. The210 minute
watchdog is a fallback, not the normal schedule. Reserve the remaining window for
the existing lifecycle idle/drain policy **after EC2 is stopped and the EIP is
released**, as described below. A requested usage pause immediately enters
teardown and does not require waiting for a successful application gate.

Before disabling the current90 minute boot guard, verify both a detached PC-side
stop/release watchdog and a replacement acceptance stop timer. The acceptance
timer uses one fixed future UTC OnCalendar deadline, `Persistent=false`; it is
never recomputed from boot. An ExecStartPre deadline check on application and
metadata/acceptance-barrier units refuses startup after that same epoch, including
a boot that missed the nonpersistent timer. Old expired inspection units remain
masked. Clock synchronization and non-regressing UTC are preconditions. The PC
watchdog retains durable exact resource IDs and observes AWS state independently
of SSH; loss of SSH never cancels teardown. Guest poweroff alone cannot release
an EIP. If the watchdog cannot be armed/verified, do not start the host.

Once first-boot gates pass, drain/close streams and leases, mark lifecycle
unhealthy through its conditional API, leave the same generation/identities and
enabled units in place, then request **exactly one controlled guest reboot**.
Do not implement a reboot by Stop/Start. Record the requested reboot and distinct
pre/post boot IDs; reconnect by the retained SSH host key and same EIP. Automatic
systemd startup must recreate both nft tables before the Agent, reactivate the
same swap file and swappiness10, and restore all app units without manual start.

Require no unexpected OOM/coredump/unit restart, the same ledger identity/rows/
allowance and closed uncertain Actions, preserved DDB identities/generation, and
a fresh successful signed readiness proof before conditional healthy reconcile.
Probe ordering from both boot journals and actual rules/processes. A failure ends
the session; it does not authorize another reboot, boot, runtime upgrade or helper.

## Bounded private-host capacity

Capacity has two explicitly labelled lanes inside this session, after reboot:

1. **Real-custody control lane:** actual services, real protected binding and DDB,
   valid TLS, synthetic invitations, session creation/state, catalogue calls and
   authenticated SSE open/close/reconnect at cohorts 1/5/8, with no shopper message
   endpoint and no provider POST. Verify ownership/refusal and refresh without
   replay. Keep a final real-custody signed readiness proof.
2. **Captured shopping lane:** temporarily stop only the real Agent and run a
   hash-frozen acceptance launcher with identical UID, sandbox, resource limits,
   actual Store/proxy/DDB and HTTP/SSE routes, but a separate fake key/ledger and
   an injected captured HTTP transport in the actual OpenRouterClient. Its unit
   makes the real Agent custody paths inaccessible. Keep the network barrier.
   Use the accepted fixed safe catalogue-search response and actual GuardedClient,
   lifecycle authorization and queue2/3/8. Never label its readiness or spending
   as the real-custody result. Synthetic fixture ledger identities/holds are
   independent and may never be copied back over the real ledger.

The capture launcher injects `OpenRouterClient(..., transport=...)` through the
existing `model_client` seam; it does not mock `create_host_app`'s generic
`http_transport`, which also carries real catalogue/readiness dependencies.
No runtime production-client patch or transport replacement after startup sealing
is permitted. Fixtures and the capture binding are explicitly synthetic.

Prepare/rehearse both drivers locally before cloud entry. Run each1/5/8cohort
once per lane, maximum 300 total HTTP requests, maximum 10 minutes per lane,
maximum 20 minutes combined, no automatic retries/ramp/soak. SSE streams last at
most 30 seconds. Captured response delay is0.4 seconds; captured cohorts 1/5 complete
all calls, cohort 8 completes5 and refuses3 as `inference_busy`, with at most one
mock POST in flight, no reservation for overload and no newly uncertain attempt.
Require completion within 10 seconds for these captured cohorts and no leaked
task/lease/socket. Compare against the frozen native probe described in
[the captured-capacity result](../cap06-captured-capacity.md), not a live-model
latency promise. If HTTP scheduling changes that exact admission outcome, fix and
rehearse the deterministic driver offline before entering AWS, not by loosening
the host queue or interpreting a zero process exit as a passing gate.

Sample whole-instance and component cgroup memory/CPU, MemAvailable, swap usage/
in-out, disk, FD/tasks, pressure, OOM events and T3 Standard CPU credits. Require
MemAvailable>=256 MiB, at least 2 GiB free disk, no OOM/cgroup kill, no sustained
swap-in/out above1 MiB/s for10 seconds, and no sustained memory-full pressure above
10 percent for10 seconds. Stop load on the first breach, service failure, exhausted
CPU credits or unexpected real provider activity. Fixed cohort limits are ceilings,
not a target that overrides safety. Restore the real Agent and verify its ledger
is unchanged and signed readiness succeeds. This proves bounded host behavior
with captured model responses, not live-provider shopping throughput.

## Teardown, evidence and remaining deployment work

Before T0+210 minutes or immediately on failure/pause: close streams, stop capture
units, drain real work, disable the canonical ledger and take a consistent
protected backup. Keep every uncertain reservation and uncertain Action; never
replay to discover the outcome. Stop/disable the app target and component units,
leave metadata protections in place until poweroff, remove acceptance-only TLS/
hosts/capture configuration, and restore the safe90 minute relative provisioning
guard. Remove one-off acceptance timer/deadline overrides only after apps are
disabled. Preserve encrypted-root private custody, catalogue and authority IDs.

StopInstances and observe stopped, disassociate/release the exact temporary EIP,
and observe no original publicIP and no operation EIP allocation. No termination,
disk deletion, general SG widening or data deletion is authorized. If guest
cleanup fails, prioritize API stop/IP release, mark custody/cleanup unresolved
and forbid later startup until reconciled. Do not retry an unknown create/start/
reboot outcome blindly; read its exact identity/state. Stop/release remain the
only permitted recovery writes outside normal procedure.

Do not pretend that EC2 stopped immediately makes the lifecycle row `stopped`.
The current API has no manual-stop transition: it retains a 3600-second inactivity
window and 5-second drain. After work is closed, revoke lane invitations and record
the real last meaningful activity time privately. Reconcile unhealthy and perform
normal stop/IP release first. In the **same bounded operation**, leave compute
off, do offline receipt work, then at `last_activity + 3600 seconds` conditionally
reconcile the observed stopped host to `draining`; at least 5 seconds later reconcile
to its pending stop command. Claim that existing stop command, freshly observe
the exact host already stopped, acknowledge its certain outcome without another
EC2 mutation, and reconcile to `stopped`. Preserve generation and authority IDs.
The T0+160 minute work cutoff leaves this off-host completion before T0+4 hours.
Do not alter clocks, edit lifecycle rows or shorten production idle policy.
If a failed/uncertain operation cannot reach that state through existing APIs,
record its exact non-admitting state/command as unresolved, keep invitations
revoked/apps/ledger disabled, and finish compute/IP teardown anyway. A usage pause
prioritizes this immediate safe state; no unattended follow-up is created.

Publish a sanitized acceptance receipt with phase outcomes, observed boot IDs,
artifact/config fingerprints, unit/rule/capability summaries, bound test counts,
capacity metrics, cost bounds and final AWS state. Keep secret-bearing receipts,
authority IDs, key/ledger digests, signatures/nonces and backups private under the
existing Windows ACL and host ownership rules. Report a gate matrix with pass,
fail or unverified; do not turn skipped gates into passes. Only complete verified
host acceptance can support a later explicit interpreter-approval record; do not
flip `production_interpreter_approved` merely because the proposal was approved.

Public wake-link infrastructure, DNS/ACME, invitation distribution, real-browser
acceptance and any live model spending remain outside this grant. They are the
next deployment work, not more private-host cloud micro-stages hidden in this plan.

## Offline builder review

A fresh read-only builder check identified the initial 300-second lifecycle startup
deadline and the existing 3600-second idle/5-second drain as sequencing constraints.
The procedure above resolves both using existing APIs, without a lifecycle code
change or another cloud stage. The targeted follow-up found nothing important
left. This review validates the design's completeness, not unexecuted host gates.
