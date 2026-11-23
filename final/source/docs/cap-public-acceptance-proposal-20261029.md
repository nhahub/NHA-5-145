# Controlled Storefront public acceptance — consolidated proposal

29 October 2026. **Prepared for review; no deployment approval or public exposure.**
This resumes the main project after private CAP-07 acceptance. It does not reopen
the local MVP, independent-storefront generalisation or the reward activities.
It follows the approved generated startup link plus direct Caddy HTTPS design.
This is a public follow-up to CAP-07/CAP-04 ticket08, not a renumbering of the
academic CAP-08 deliverables.

## Outcome and verified starting point

An invited tester opens the generated CloudFront HTTPS startup link, requests a
wake, then uses `app.scpilot.tech` with its embedded `store.scpilot.tech`.
Desktop Chrome/Edge and the owner's CMF Phone 1 Android Chrome must trust public
HTTPS without a certificate exception. OpenRouter remains explicitly selected.
Closing every browser must still allow genuine automatic idle shutdown.

Actual host isolation, signed readiness, reboot persistence and captured 1/5/8
capacity already passed. Authority is stopped at generation3; the original
host/root/table/profile and resident canonical allowance are retained. Reconcile
them from receipts and inspect first; do not upload an old PC ledger or reset
identities, attempts, reservations, invitation counts or lifecycle history.

Fresh local preparation: 72 focused tests passed across public HTTPS, cloud access,
observation and Lambda packaging. Both current-source ZIPs rebuilt, independently
verified and passed isolated smoke tests. The read-only regional Lambda account
result reports400 total/unreserved concurrency and0 functions, permitting the
candidate reservation of1 per function without consuming the100-unit reserve.
CloudFront ListDistributions succeeded, but its count query returned null;
inventory/name absence and creation eligibility are still unproven. These checks
make no AWS writes or model calls. See the
[artifact/evidence receipt](../eval/evidence/public-acceptance-preparation-20261029.json).

## Proposed exact execution authority

One consolidated acceptance session, maximum **four hours from first AWS write**,
up to **USD2 additional existing AWS credits**, active **Free plan / USD0 cash**.
No upgrade or advanced-feature activation. Refresh account, prices, ownership,
quotas and time bounds immediately before execution. Begin only with enough time
for DNS cache expiry, real idle/drain observation and teardown. Do not start the
clock while waiting for owner sign-in or registrar access.

Reuse the original retained t3.small with Standard CPU credits, encrypted20GiB
root, dedicated SSH group/key, runtime role/profile and initialized DynamoDB
namespace. No new instance, volume, table, host role, profile or keypair. Permit
**at most two StartInstances transitions**: one maintenance staging start and one
invitation-authorized cold wake. No guest reboot is needed. Stop after staging;
the public wake must pass the existing durable START claim, not an operator bypass.
Never reset an uncertain command to force the second start.

Proposed new resources (all operation-owned, unique names checked before create):

| Resource             | Maximum and restrictions                                                                                                                                                                                                                                                                                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Temporary EIP        | One address, attached only to the existing host, retained across the two starts and released during teardown.                                                                                                                                                                                                                                                            |
| S3                   | One private SSE-S3/BucketOwnerEnforced bucket `scpilot-public-{account}-{operation8}`; public-access blocks on; waiting-page and approved artifact prefixes only; at most1GiB objects, no versioning. No keys, codes or live allowance backups in S3.                                                                                                                    |
| Startup delivery     | One pay-as-you-go CloudFront distribution using its generated certificate/hostname, two always-sign SigV4 OACs, one control origin-request policy. No custom alias, Virginia ACM, flat-rate plan, viewer Function or public S3 website.                                                                                                                                  |
| Control functions    | Two Python3.12/x86_64 ZIP functions `scpilot-public-startup` and `scpilot-public-controller`, each256MiB/30s/512MiB temporary storage/reserved concurrency1, no VPC/layers/provisioned concurrency; AWS_IAM URL on startup only.                                                                                                                                         |
| IAM/logs             | Two dedicated Lambda execution roles and inline policies, two explicit log groups with7-day retention, each runtime limited to its own streams. Actual policies rendered from exact retained table/namespace/instance and returned distribution/function IDs.                                                                                                            |
| External observation | One dedicated group/schedule `scpilot-public-observation`/`tick`, one invoke-only role/inline policy, one fixed-dimension EMF completion metric and two standard alarms with actions disabled. One-minute ticks, explicit finite session dates, retry0/age60 at delivery and controller async layers; create DISABLED and enable only after target/configuration checks. |
| DNS/ingress          | Only app/store A records at the existing registrar to the EIP, TTL300 where supported. No nameserver change or hosted zone. SSH22 only from the fresh verified operator IPv4/32; public80/443 only during qualified TLS/application acceptance. No public4000/8000 or IPv6 ingress.                                                                                      |

Record existing DNS values/TTLs first. A CNAME/AAAA conflict or long existing TTL
that prevents safe rollback within the session is a blocker, not permission to
change unrelated records. Owner registrar interaction may be required; prepare
the exact returned address and record edits for review. Do not request passwords.

## Provider and request bounds

Preserve the existing non-resetting OpenRouter USD2 key cap, canonical ledger,
qualification/configuration fingerprint, uncertain holds and existing USD0.10
readiness reserve. No top-up, replacement key, allowance reset, provider switch
or full qualification rerun. Startup-only protected hashing remains unchanged.

The proposal requests separate approval for **at most four live model POSTs and
at most USD0.10 total additional OpenRouter usage inside the existing USD2 cap**,
only if conservative reservation and remaining canonical authority cover them.
The existing readiness reserve is not repurposed. Authorize at most five read-only
provider key-status GETs: the existing mandatory check before each possible POST,
plus at most one independent freshness check. Do not cache or remove the client's
per-POST check to fit an artificial GET limit. No Bedrock call.

The previous private-session binding has an expired session interval. Explicitly
authorize an operator-issued **time-only binding renewal** for this session and
its new startup SHA pin, using the same verified accepted report/reconciliation,
model/provider fingerprint, resident key digest and ledger UUID. Pin expiry to
the absolute session end. This does not renew model evidence, reset spending or
relax startup verification. Inspect custody first, validate the renewed candidate
with the existing loader, and record old/new digests without secret contents.
If accepted evidence is invalid or report/custody/configuration identities differ,
stop before inference; no silent report replacement or new qualification set.

Before paid activation, implement and prove a fail-closed four-attempt fence
through the existing canonical ledger reservation transaction. The current
GuardedClient does not supply the ledger's optional maximum_attempts limit;
manual request counting alone cannot bound internal repairs or concurrent calls.
Capture the existing attempt count and pin its absolute ceiling at that count+4
for this session; never replace, subtract or reset historical attempts/holds.
The fifth attempt must fail before provider network access, including across
concurrency and process restart. The existing adapter's USD0.02 per-attempt bound
then limits four admitted attempts to USD0.08, within the proposed USD0.10.
Any ambiguous attempt consumes its slot. Preserve the original key cap and all
normal GuardedClient checks. Include this narrow local implementation and its
synthetic safety tests in the proposed approval; no cloud writes until it passes.

Use two predefined shopping prompts: one Egyptian-Arabic desktop task and one
English Android task, within the four-POST aggregate including repairs/advice.
Preserve the remaining budget when a case needs more calls; record a blocked
result rather than increasing the ceiling. Captured capacity evidence is reused,
not replaced by eight live model calls.

Operator-generated bounds: at most1000 application HTTP requests,2000 startup-edge
HTTP requests and1000 invocations of each Lambda including scheduled ticks, at
most240 tick deliveries,1GiB public output and1GiB administrative/artifact transfer,
100MiB combined new cloud logs and1GiB temporary S3 objects. Limit the two scoped
test invitations to the session, finite redemption/session counts and revocation.
These are operational stop thresholds, not hard AWS billing caps or bounds on
hostile traffic. Monitor actual counters; close admission/disable delivery on
unexpected activity rather than leaving the demo unattended.

## Cost worksheet and stop conditions

Reuse the detailed [regional rate worksheet](research/2026-10-23-cap06-inventory-reconciliation.md)
as a dated basis; refresh official rate/eligibility evidence before writes. Do not
reuse its old60-day/USD80 illustrative envelope or AWS-model allocation. Today's
observed balance179.74 does not authorize spending it. No free-tier usage allowance
or unearned reward is subtracted.

For four hours, t3.small Standard compute at0.0216/hour is0.0864; EIP at0.005/hour
is0.0200. The existing root's four-hour20GiB gp3 share at0.0836/GB-month is~0.0093
(retained storage continues under its earlier allocation). For2000 invocations
plus240 ticks,256MiB at a conservative **40 billed seconds each including INIT**
and0.0000166667/GB-second gives~0.3734 plus requests. Reserve0.50 for the fixed
metric/two alarms without relying on proration,0.30 for the two transfer allowances,
and0.20 for DynamoDB, S3, logs, Scheduler and control/API usage. Subtotal~1.4891;
25% contingency~1.8614, below the proposed USD2. Provider USD0.10 is separate,
inside its unchanged key cap; AWS credits cannot fund OpenRouter charges.

The Lambda duration, operation counts and other-service allocations need local
validation and actual observation. Handler timeout alone does not bound INIT or
billing. Refuse creation if refreshed prices/quantities exceed USD2 or any service
requires Paid plan. No claim of a guaranteed billing cap follows from this sum.

## One session, ordered gates

1. Complete local operator preparation and synthetic partial-failure/ownership
   checks before cloud writes. Capture old DNS, resource identities, release/ZIP
   hashes, signed-readiness identity, protected binding and rollback settings.
   Verify the original stopped generation3 without reinitialization. Preserve the
   existing guest safety timer unless its verified replacement is needed; an
   expired Persistent timer must not shut down staging or bypass graceful drain.
2. Create dedicated control resources disabled/private, bind returned IDs and
   policies, stage the host during its one maintenance start. Inspect retained
   units/configuration/custody before editing; preserve UID/capability/nftables/
   swap/log bounds and system Python3.9. No base-installer replay. Use verified
   qualification evidence from the resident guest, never the obsolete PC copy.
   Issue only the time-bounded renewed binding above; enable the existing canonical
   ledger and boot target only within this approval. Inspect CAP-07 cleanup:
   confirm expired drop-ins, private certificate/loopback hosts entries and
   test-only egress fences are absent, or reconcile only those recorded owned
   artifacts. Keep the permanent UID-based IMDS barrier, ordinary TLS verification
   and protected storage. Stage the public Caddy profile and exact new session
   fences; do not retain expired acceptance ExecStartPre checks or disable
   permanent isolation to make startup succeed. Permit the fixed OpenRouter HTTPS
   endpoint under the allowance; no broad test-firewall deletion.
3. Qualify DNS/Caddy public ACME and application origin routing with the inference
   gate closed. Keep private paths inaccessible; no cache of personal responses,
   invitation codes in URLs/logs, anonymous Function URL or TLS exceptions. Bind
   the generated startup origin before exposure; prove correct OAC POST digest
   signing and exact readiness key/release/generation, plus negative IAM checks.
4. Stop maintenance without inventing lifecycle readiness. Enable only the finite
   reviewed observation window. From stopped, use a valid invitation to cold-wake;
   invalid/revoked/stale/duplicate controls cannot start/replay. Verify ready is a
   signed application result, not an EC2 acknowledgement. No manual second-start
   fallback if the public wake fails.
5. Within the separately approved live allowance, check desktop and physical
   Android HTTPS/iframe admission, the two prompts, separate cart identities,
   refresh without replay, SSE reconnect, bound Confirmation and sensitive-field
   exclusion. Record browser/version and observed results. Existing captured1/5/8
   host proof remains a separate capacity result.
6. Close all browsers and observe genuine60-minute idle/drain/stop through the
   external controller. Allow its healthy-delivery60–63-minute expectation plus
   session margin; do not accelerate clocks or use synthetic evidence as a cloud
   pass. Unknown claims require inspection, not replay. Reserve the last20minutes
   for teardown, longer if recorded DNS TTL requires it; if time runs short,
   retrieve diagnostics, report incomplete acceptance and stop safely.

## Rollback and completion

Retrieve bounded diagnostic/error receipts **before** shutdown. Close admission,
revoke test invitations and stop new inference; drain accepted work, preserve the
latest canonical accounting/uncertain reservations, stop the instance and settle
normal lifecycle bookkeeping without resetting history. No fresh disk/table
deletion or copying an old ledger back onto the guest. Restore protected settings
and disabled units as recorded; preserve ACME state outside the release.

Disable scheduled/startup access, remove Function URL permissions, restore/remove
only the two edited DNS records and wait their measured TTL before EIP release.
Disable CloudFront immediately, delete after deployed-disable propagation, then
remove its OACs/policy, functions/URL, owned bucket objects/bucket, alarms, logs,
schedule/group and dedicated roles/policies in dependency order. Target complete
teardown within four hours. If CloudFront deletion propagation alone exceeds it,
allow up to24hours solely for disabled-edge cleanup, with host stopped, public
application ingress closed, startup access removed and EIP released. No model or
host activity in that tail, no automatic extension beyond USD2; report the exact
pending dependency and keep a finite local cleanup worker. Do not claim all new
resources deleted before independent inventory confirms it.

Final evidence separates AWS delivery/IAM/TLS, actual phone behavior, live-model
observations, captured capacity, real idle shutdown, bookkeeping and cleanup.
Successful acceptance establishes the deployment procedure; leaving a public demo
available for days/weeks requires its own finite operating-window authorization.
No recurring hosted window or60-day retained EIP is implied by this session.
