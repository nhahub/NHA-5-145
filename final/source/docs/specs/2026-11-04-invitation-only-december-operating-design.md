# Invitation-only public operation through the graduation demonstration

**Prepared:** 4 November 2026. **Status:** proposed; owner review required.

This is one consolidated design and cost/resource/rollback proposal. It does not
create resources, enable inference, edit DNS or authorize spending merely by
being committed. Implementation follows approval of this document.

## Outcome and scope

Keep the Controlled Storefront available to invited instructors/testers through
**4 December 2026, 23:59 Cairo (21:59 UTC)**. That exact closing time is the
agent's proposed interpretation of the owner's December target, based on the
recorded 4 December final demonstration deadline. It becomes authoritative only
with approval. Invitation-only supersedes the accidental anyone-with-link answer.

Preserve the accepted topology: a generated CloudFront HTTPS startup link,
invitation-authorized wake, then `https://app.scpilot.tech/` and
`https://store.scpilot.tech/` served by Caddy on the same Stockholm host/EIP.
Testers enter their invitation on the startup page and again in the Copilot.
Shopping links alone cannot wake a stopped host. No real checkout/payment data
or independently operated Storefront is introduced. Physical-phone acceptance
remains excluded by the owner; desktop is the release target.

Retain automatic shutdown after 60 minutes of meaningful inactivity. A cold
start takes time; carts and sessions may reset across a stop/start. Display the
existing recovery guidance and never replay an uncertain Action. This is a
bounded graduation demo, with pauses for exhausted limits or failed checks,
rather than a promise of uninterrupted service.

## Verified starting point

- GitHub `main` is `874c9b1ffcbf82052c70b48b76dbdb3a13802b75`;
  [its Actions run passed](https://github.com/Homd11/shopping-copilot/actions/runs/41619335148).
  Clean release validation passed 1,619 Python tests, 199 TypeScript tests,
  formatting, lint, three builds and HTTP smoke checks. Three local HTTPS tests
  were skipped because the clean checkout lacked the pinned Caddy binary.
- [Actual public desktop acceptance](../desktop-public-acceptance-result-20261103.md)
  independently passed trusted TLS, invitation cold wake, signed readiness,
  Confirmation, isolation, Sensitive Field exclusion, refresh/SSE recovery and
  real idle shutdown after 3,755 seconds. Temporary public resources were then
  deleted; the original host is stopped. Retained storage still consumes credits.
- The accepted native artifact was built from `44e4952`, with the separately
  accepted startup ZIP/header fix. Published `main` and that artifact are distinct
  identities. Build and verify the new approved release; do not relabel old bytes
  with a newer source SHA or rerun model qualification silently.
- The last signed provider accounting has 249 lifetime attempts, 20 legacy
  uncertain holds, USD 1.686132383 accounted, a disabled ledger, and USD 0.10
  readiness reserve. No new uncertain attempt was created in public acceptance.
- A read-only AWS plan refresh on 4 November failed because CLI sign-in expired.
  Current credit balance and plan eligibility remain launch checks. No current
  balance, resource inventory or successful reauthentication is claimed here.

## Selected approach and changes required

Reuse the successful architecture, adding a finite operating policy and a
cloud-resident guard. Keeping the host continuously running would simplify wake
but waste credits; manual start would require owner availability. The owner
already selected automatic wake, so neither alternative is the proposed design.

The prior operator deliberately granted one 120-second cold-start IAM window.
It also depended on a Windows cleanup supervisor that did not survive a restart.
Do not deploy that one-shot harness as the month-long operating system.

### Finite operating authority

Create one immutable operating manifest before the first cloud write. Bind its
UUID/hash, source/artifact hashes, existing account/host/table/namespace, new
owned resource identities, approved opening/closing UTC times, traffic and model
ceilings, retained resource policy and DNS baseline. Actual identities discovered
during creation are appended once to an ownership inventory with receipts.
There is no automatic reinitialization after missing/corrupt authority and no
moving the closing date on resume.

Use the existing DynamoDB table/namespace for one durable operating record and
atomic lifetime start reservations. Allow **at most 100 StartInstances dispatch
attempts in total**, including maintenance, validation, failures and uncertain
outcomes. Each lifecycle intent reserves once before dispatch; service restarts
and duplicate events cannot reset it. Preserve the existing no-retry rule for an
uncertain EC2 start. At most two starts are used for initial maintenance and a
real invited cold wake; the remaining 98 are for subsequent invited wake-ups.

Permit StartInstances only on the designated instance and only between the
approved opening time and closing time, using IAM date conditions as well as
application checks. Expiry can stop but cannot start. Invalid/revoked/expired
invitations, exhausted counters, unknown state or failed storage refuse wake.
Regular status polling never initiates a start. The existing 60-minute idle and
generation/lease/drain arbitration stay intact.

Limit a single uninterrupted host run to **eight hours**, including maintenance.
The guard observes EC2 launch time; a guest timer is an additional measure.
This is a maximum runtime safety stop, not evidence of healthy idle shutdown.
Active testers may need to reopen the startup page after that limit.

Issue **at most ten invitations**, including launch-test credentials, with two
browser redemptions and at most 100 created sessions per invitation. Their windows
end at the operating close and never exceed the existing 31-day invitation limit.
Raw codes are shown privately to the owner once, stored only as hashes in
authority, never committed or put in URLs. The owner distributes codes; no
automated email/message sending is included. Preserve accepted admission/queue
bounds, with at most eight simultaneous shopping sessions; no capacity increase
beyond the tested 1/5/8 scope is implied.

### Independent cloud guard

Add one small private Lambda guard, callable only by the dedicated Scheduler
role/operator. It has no public URL, model key, StartInstances or shell authority.
It runs every five minutes through the operating period and a maximum 48-hour
cleanup tail. Its fixed manifest, resource ownership and timestamps are validated
before writes. It checks runtime, expiry, availability of the finite authority and
daily Free-plan/credit observations. A refusal closes access rather than creating
replacement resources or broadening IAM.

At closure, budget refusal or a proven fault it monotonically marks the operating
record closed, denies new admissions/wakes/work, removes the controller's start
grant, disables startup invocation/public delivery and stops the designated host.
Do not depend on a successful DynamoDB write before performing the independent
IAM/EC2 safety actions. Application request authorization and the startup-only
qualification binding independently enforce the operating expiry. Already
dispatched calls may settle; nothing new may be reserved after closure.

Install an additional **one-time Scheduler universal EC2 StopInstances target**
at the closing minute, with a role restricted to that instance. The controller's
IAM start grant has already expired then. Allow at most two target retries within
15 minutes; the five-minute guard verifies stop and retries stop safely within
the same 15-minute target. AWS schedules have minute precision and can fail: do
not claim a hard second-exact shutdown guarantee or fabricate a successful stop.
An unverified stop is an incident, not permission to extend public operation.

The guardian retains minimal encrypted/redacted receipts for independent final
inspection. No reliance on this PC, interactive AWS login, sleep prevention,
recurring scheduled automation or an owner's browser tab is required to stop compute.
Synthetic checks simulate lost schedules, duplicate invocations, IAM/DynamoDB
failures, clock regression, Windows absence and late commands.

## Exact resource envelope

All regional resources stay in **eu-north-1**, with global CloudFront/IAM and the
existing Free-plan read API only. New resources carry the operating UUID tag.

| Resource                   | Maximum and disposition                                                                                                                                                                                                                                                                               |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Existing EC2               | Reuse one stopped `t3.small`, Linux, CPU credits Standard; no replacement/helper instance, resize, reboot requirement or new disk. Existing encrypted 20-GiB gp3, UIDs, Caddy state, swap, nftables metadata block, service isolation and log limits remain.                                          |
| Existing authority/custody | Reuse the existing DynamoDB table, host profile and canonical OpenRouter ledger/key; add only scoped operating records. Do not delete retained authority or reset identity/history.                                                                                                                   |
| Public address/network     | One new EIP allocation/association, retained across stops; two app/store A records, TTL7,200. Public TCP80/443 only to Caddy; administrative TCP22 only to the verified operator IPv4/32 during maintenance, then removed. No public4000/8000, IPv6, NAT, load balancer, paid DNS or Virginia ACM.    |
| Control/delivery           | One private encrypted S3 bucket (waiting assets, ZIPs, receipts, at most 0.1 GB), one pay-as-you-go CloudFront distribution at its generated hostname, two OACs, one origin-request policy; no paid subscription/flat-rate plan, aliases, WAF, edge compute or access-log expansion.                  |
| Functions                  | Exactly three: startup, existing controller logic with operating bounds, and private guard. Each at most 256 MiB/30 seconds, reserved concurrency1, default512 MiB scratch. No provisioned concurrency; no unbounded async retries.                                                                   |
| Roles/logs/alarms          | Four dedicated roles (one per function plus Scheduler execution), three log groups with seven-day retention, two diagnostic alarms with message/actions disabled. Role writes are limited to the exact approved manifest resources; no account upgrade, new service or wildcard Start/Stop authority. |
| Scheduling                 | One group and exactly three schedules: controller every minute, guard every five minutes, direct one-time closing StopInstances. Fixed start/end times, bounded retries; no self-renewal.                                                                                                             |

The guard can update the owned controller policy, function concurrency/permissions,
distribution enabled state and specified security-group rules; describe/stop the
one host; access the designated authority partition and receipt prefix; inspect
Free-plan status; and release the one owned address **only after safe DNS proof**.
Deletion of roles/functions/bucket/edge dependencies is an explicit operator
teardown, not a permission for a Lambda to delete arbitrary infrastructure.

## AWS credit allocation

Request **up to USD 45 additional existing AWS credits**, **USD 0 cash**, active
Free plan mandatory, from first provisioning through cleanup. Require at least
USD 65 eligible/unexpired remaining credits at launch: USD 45 allocated plus USD 20
unallocated safety margin. This is independent of the OpenRouter allowance.
Historical USD 180 rewards are not treated as a fresh balance.

Use at most 32 days/768 hours before close, plus a48-hour EIP/disabled-control cleanup
tail. Provisioning later shortens the window; it never moves 4 December. Prefer
cleanup by the first safe DNS TTL expiry. The [fresh worksheet](../research/2026-11-04-december-operating-cost.md)
uses gross rates without deducting free service tiers:

| Component/workload assumption                                                 | Conservative USD |
| ----------------------------------------------------------------------------- | ---------------: |
| Continuous host for 768.25 hours, including 15-minute stop allowance          |        16.594200 |
| One EIP for 816 hours including cleanup                                       |         4.080000 |
| Existing20-GiB gp3, 34 days with conservative28-day denominator               |         2.030286 |
| 77,000 Lambda invocations, each using its full256 MiB/30 seconds              |         9.640420 |
| 5 million DynamoDB WRUs and 10 million RRUs                                   |         4.695000 |
| 100,000 edge requests and 1 GB edge egress, rounded at higher published rates |         0.340000 |
| 10 GB direct Stockholm internet egress                                        |         0.900000 |
| 60,000 Scheduler invocations before free allowance                            |         0.060000 |
| S3, bounded logs/alarms, incidental KMS/monitoring provision                  |         2.500000 |
| **Planning total**                                                            |    **40.839906** |
| **Headroom inside 45-credit allocation**                                      |     **4.160094** |

Storage is counted conservatively even where an older retention allocation
already covers it; do not create a duplicate disk or charge the allocation twice.
Idle shutdown should reduce compute usage. This worksheet is conditional on the
stated traffic quantities, not a guaranteed maximum AWS bill or unlimited
unauthenticated traffic. Reserved concurrency/application rates do not eliminate
edge/DynamoDB charges for refused requests, and AWS usage/balance reporting lags.

Use service metrics and the guard to close at the first of the approved time,
runtime/start limits, USD 35 observed credit reduction from the launch snapshot,
remaining credits belowUSD30, inactive/non-Free plan, or operational refusal.
Check plan/credit status at least daily; aggregate deltas include other account
usage conservatively. The USD 35 trip point leaves10 credits of allocation
headroom, but delayed reporting is not a hard billing cap. Missing daily evidence
or sustained traffic outside the worksheet closes access pending review.
No paid-plan upgrade/top-up or automatic spending extension is permitted.

## OpenRouter allowance and qualification

Retain **OpenRouter `google/gemini-3.5-flash-lite`**, the original qualified key,
accepted report/reconciliation, canonical ledger UUID and non-resetting USD 2 cap.
All20 legacy uncertain holds remain fully reserved. A new host binding may name
the verified release/configuration and operating expiry; protected file/report
hashing happens **at startup only**, with no runtime20-file source pinning.

Propose **USD 0.20 of additional live-demo spending**, from existing provider
credit inside the existing key cap, and **at most 100 additional lifetime
attempts** (absolute ceiling349 if the launch baseline is still249). All repairs,
advice, failures and acceptance prompts count; there is no automatic HTTP retry.
Authorize at most two live launch smoke requests **inside** those100 attempts,
then invited interaction within the same shared allowance. This does not promise
100successful answers: money, reservations or uncertainty can stop earlier.

The USD 0.10 readiness reserve must remain inaccessible to public inference.
With the last signed baseline `B=1.686132383`, expose a live ledger allowance of
**`B+0.20 = USD1.886132383`**, not `B+0.30`. Keep the separate readiness reserve
as unexposed provider headroom: `B+0.20+0.10=USD1.986132383<USD2`, leaving
USD 0.013867617 further margin. This changes the current disabled ledger allowance
from `B+0.10` to `B+0.20` (net0.10); it does not reset accounted money, release
holds or make the readiness reserve spendable. No separate public ledger/key.
The existing atomic ledger reservation enforces the public phase limit. Do not
invoke a model against the readiness reserve during this window.

Before activation, verify fresh key status and re-read the signed baseline. If
it differs, recompute without increasing USD 0.20/100 attempts/USD 2 bounds or
reducing the reserve; insufficient headroom blocks inference. Include the
adapter's existing one key-status GET per attempted completion: at most 100 such
GETs, plus at most 10 explicit operator checks for the whole window. No periodic
GET loop, key replacement, new qualification set, reconciliation write-off or
provider/model switch is authorized. Redact credentials and invite codes.

On budget exhaustion, explain the limit to the shopper and keep manual shopping
available while the host is otherwise open. No claim of model availability
through December survives exhaustion. On final closure, expire binding/admission,
preserve a signed accounting receipt and all uncertain outcomes, and disable the
ledger when quiescent custody is available. If abrupt shutdown prevents receipt
or disk verification, report it unverified and retrieve it before another start;
never assume an on-disk disabled flag merely because EC2 stopped.

## Consolidated implementation, release and acceptance

After approval, prepare one implementation plan and finish local code/synthetic
checks before cloud writes. Extend the tested lifecycle/deploy seams and the
operator; do not run a parallel replacement shopping engine. Cover counter
atomicity across restarts/concurrency, expiry and late work,8-hour stop, retained
holds/reserve protection, duplicate/uncertain APIs, manifest ownership and cleanup
DNS safety. Preserve all existing origin, Confirmation, Sensitive Field,
stale/duplicate and refresh invariants. Run relevant format/lint/test/build and
obtain a focused review before release.

Pin one release and all three Lambda ZIP hashes. Rebind qualification against
the accepted evidence; changing a config fingerprint requires an explicit new
binding, not an invented old fingerprint. Reauthentication, fresh Free-plan/
credit applicability, stopped-host ownership, DNS baseline and custody are
pre-write checks. Stop on account upgrade requests or incompatible evidence.

Create control/guard/schedules disabled, verify exact IAM/expiry/ownership, then
enable safety schedules before starting compute. Reconcile expired guest timers
and previous acceptance-only assets inspect-first, without blind base installers.
Perform one maintenance start, bind the one EIP/DNS, verify Caddy TLS/isolation/
signed readiness, stop, and perform one real invitation cold wake plus desktop
shopping/refresh safety check. These are within 100 starts/100modelattempts and the
same allowances. No extra guest reboot or full qualification is required.

Keep the already-passed real60-minute idle acceptance as historical evidence;
do not claim a new deployment's idle observation passed until actually observed.
For this release, observe one real idle stop after the launch browser closes.
Remaining invitations may then be distributed. Do not leave an active tester
page open while measuring idle. Publish the generated startup URL privately with
instructions, invitation expiry, budget limitation and the closing date.

## Closing, rollback and retained resources

Stop public work immediately on acceptance failure; retrieve diagnostics before
rerunning or teardown. Resolve harness/config faults inside the same bounded
maintenance window when safe. No blind starts, deadline reset or infinite retry.
Security/unknown-custody failures stay closed. The owner can request early close;
the same budget and DNS rules apply.

At final close, the cloud guard/date fence/direct stop handle compute independently
of the PC. Close public80/443 and administrative22 ingress after stop. Verify
actual EC2 state; preserve accounting and lifecycle receipts. Disable CloudFront
and verify its deployment state. Restore the captured DNS baseline (normally
delete only app/store A records pointing at this operation's EIP); no nameserver,
email, domain purchase or unrelated DNS changes are included. The existing owner
delegation permits those exact changes if browser access is available; otherwise
ask the owner for the two edits. DNS access is not needed to stop compute.

The guard checks **all four authoritative servers**, A/AAAA/CNAME for both names.
Start the immutable7,200-second cache clock only from complete verified absence
of this operation's target/conflicting routes, never the UI click. No incomplete
DNS proof, timeout, clock regression or unknown ownership permits IP release.
After the full TTL and fresh authoritative recheck, release only the owned EIP.
The48-hour cleanup allowance ends **6 December 2026,23:59 Cairo (21:59 UTC)** if
closing occurs at the proposed latest time. If DNS removal or cleanup is still
blocked then, keep the host stopped/ingress closed, retain the address safely,
record the exception and require an explicit cleanup continuation; do not silently
extend authority or release an address still referenced by DNS. The extra cost
of an unresolved tail must be reported, not hidden as completed teardown.

Delete only the operation's three functions/URLs, edge distribution/dependencies,
three schedules/group, four roles/policies, logs/alarms and private bucket after
copying nonsecret evidence and verifying ownership. The disabled CloudFront
deletion dependency can remain inside the same 48-hour cleanup tail. No blanket
account cleanup or new paid snapshot/backup service. Cloud guard stays until
compute stop and safe IP release are independently established, then the operator
removes it and its schedule/role last.

Retain the original stopped host, encrypted root volume, DynamoDB table/profile,
canonical key/ledger, qualified evidence and protected operator backups under the
existing retention approval. The separate **23 December 2026,18:00 UTC** retention
review is not permission to extend public hosting or automatically delete project
data. After closure, report retained storage separately from deleted resources.

## Decision requested

Approve this consolidated design and its finite deployment/operation authority:
invitation-only through 4 December23:59 Cairo; at most 45 existing AWS credits with
Free/USD 0cash; the resource/100-start/runtime/cleanup bounds above; and up to
USD 0.20 / 100 OpenRouter attempts within the original USD 2 key cap with USD 0.10 reserve
protected. Approval includes local implementation, bounded launch checks and the
specified ongoing invited operation/rollback, conditional on successful local
verification and fresh account/custody gates. It does not authorize another
provider key, upgrade, top-up, independent Storefront or automatic renewal.
