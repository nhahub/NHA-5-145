# CAP-07: one private Controlled Host & Application Acceptance session

26 October 2026. **Proposed; awaiting review. No execution or new allocation.**

Run all remaining private-host gates together: systemd 252 isolation/UIDs/Caddy
capabilities/log bounds/IMDS filtering; protected OpenRouter custody and startup
qualification; real signed application readiness; one controlled reboot proving
swap/rules/unit persistence; bounded captured-workload capacity; then stop and
release the temporary address. Preparation and synthetic tests finish locally
before the one cloud session. The [design](specs/2026-10-26-cap07-controlled-host-acceptance-design.md)
defines the checks and plan
defines their order.

## Exact proposed authority

| Item               | Bound and final state                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Account/region     | Existing project, mandatory active Free plan, Stockholm `eu-north-1`, USD 0 cash. Refuse an upgrade or advanced-feature prerequisite.                                                                                                                                                                                                                                                                 |
| Time               | Start within 48 hours of explicit future approval. Record T0 before the first resource write; four-hour absolute maximum across preparation in AWS, both boots and teardown. No reboot after 135 minutes; work ends by 160 minutes, normal stop/IP release by 180 minutes, fallback teardown at 210 minutes. Finish lifecycle idle/drain off-host inside the same four hours. No automatic extension. |
| Compute            | Existing `t3.small` only, Standard CPU credits, at most one StartInstances and exactly one controlled guest reboot if first-boot gates pass. No helper or additional instance/volume.                                                                                                                                                                                                                 |
| Root               | Existing encrypted retained 20-GiB gp3, same mapping/UUID, no resize or replacement. Existing1-GiB swap reused. Existing retention review remains 23 December 2026 18:00 UTC.                                                                                                                                                                                                                         |
| Address/network    | One temporary EIP for at most four hours, then release. Existing SSH-only group may replace a stale rule with one freshly verified operator IPv4/32; no extra source or open 80/443. Existing egress TCP 443 retained; metadata-v2/hop1, no metadata IPv6.                                                                                                                                            |
| Control authority  | One Standard on-demand DynamoDB table with `pk`/`sk`, one operation namespace, <=1 MiB; <=10,000 WRU and 20,000 RRU including transaction/size factors. No PITR/backup/index/stream/replica. Initialize authority once, preserve identity/history.                                                                                                                                                    |
| Host credentials   | One EC2 role/profile/inline policy, exact table+namespace read/transaction permissions only. No host EC2/IAM/S3/model-service privileges.                                                                                                                                                                                                                                                             |
| Retained state     | Stop host; keep protected encrypted-root custody and canonical ledger disabled, apps disabled, safe relative 90 minute guard restored. Keep narrow role/profile/table through existing 23 December retention review; no background compute or poller. Review is not deletion permission.                                                                                                              |
| AWS allocation     | Up to **USD 0.25 additional eligible AWS credits** for this session and its tiny table retention. Does not reuse the completed provisioning grant or extend the existing disk-retention allocation.                                                                                                                                                                                                   |
| OpenRouter custody | Migrate the existing key and canonical 156-attempt ledger UUID, importing only verified missing history/uncertain holds. Retire parallel local key/runtime paths. Owner-only custody outside release and independent startup binding SHA pin.                                                                                                                                                         |
| Model allowance    | Propose **USD 0.10 readiness allocation within the unchanged non-resetting USD 2 key cap**. This is ledger authorization, not a top-up. Preserve 228 known settlements/19 older uncertain holds and conservatively cover the provider aggregate gap. Zero live model POSTs; one bounded existing-key status GET permitted during future preflight.                                                    |
| Capacity           | Private TLS/HTTP/SSE/control lane plus captured-response shopping lane at 1/5/8; <=300 HTTP requests, <=20 minutes total, no real provider POST. Same actual limits/UIDs/Store/proxy/DDB; separate fake capture custody.                                                                                                                                                                              |

Nothing in this proposal authorizes public activation, DNS, ACME, a paid-plan
upgrade, a new OpenRouter key/cap/top-up, renewed Bedrock experiments, a full model
qualification run, or destructive root/authority cleanup.

## Why the table, role and private TLS are included

The installed Agent's real startup uses DynamoDB admission and lifecycle storage.
It cannot honestly pass signed readiness with an absent instance profile/table
or a mocked authority. Create their minimum scope within this session, rather
than another cloud stage. The existing production proxy launcher selects public
ACME; a temporary loopback 443/private-CA profile exercises real HTTPS and Caddy's
capability bounds while ports 80/443 and public DNS remain untouched.

An acceptance-owned nft rule permits the Agent's HTTPS only to the verified
Stockholm DynamoDB endpoint set. It blocks OpenRouter traffic before the real
ledger is enabled. Real readiness uses the accepted captured qualification,
requires at least USD 0.0831488 available, and makes no model request. Hence the
explicit USD 0.10 reserve and zero-POST rule are compatible. The capture launcher
cannot read the real key/ledger and cannot overwrite either. This session proves
private host/application behavior, not current live-provider latency.

## Conservative cost calculation

These are retained official-price observations, not a fresh online quote:
EC2/IPv4/gp3 were checked 26 October; the Stockholm DynamoDB and transfer rows were
checked 19 October. See [the cost research](research/2026-10-19-cap04-network-cost-refresh.md)
and [provisioning result](cap06-private-provisioning-results.md). Refresh public
prices and verify account/credit eligibility before future execution; never
proceed if the recalculated bound exceeds this allocation.

| Increment                                                                                                 | Conservative estimate, USD |
| --------------------------------------------------------------------------------------------------------- | -------------------------: |
| Existing `t3.small`,4 h x 0.0216/h                                                                        |                   0.086400 |
| One public IPv4,4 h x 0.005/h                                                                             |                   0.020000 |
| DynamoDB 10,000 WRU x 0.67/million                                                                        |                   0.006700 |
| DynamoDB 20,000 RRU x 0.1345/million                                                                      |                   0.002690 |
| <=1 MiB table retained for at most 60 days,0.269/GB-month, decimal-unit rounding, no free storage assumed |                   0.000600 |
| <=0.02 GiB internet output, conservatively <=0.022 GB x 0.09/GB                                           |                   0.001980 |
| Up to 100 chargeable KMS requests x 0.000003, conservative envelope                                       |                   0.000300 |
| Subtotal                                                                                                  |               **0.118670** |
| 20 percent contingency                                                                                    |               **0.023734** |
| Planning bound                                                                                            |               **0.142404** |
| Proposed ceiling, including additional margin                                                             |               **0.250000** |

IAM and instance-profile association carry no separate resource-hour line here.
No CloudWatch Logs ingestion, NAT, surplus T3 Unlimited charges or paid managed
certificate is selected. If unexpected chargeable dependencies are required,
stop before creating them. Request/unit/transfer bounds are operational limits,
not an AWS billing hard cap; the timer/watchdog and finite drivers limit exposure.
Billing/credit application may lag; preserve receipts and report estimates as
estimates until billing settles.

The already approved original root continues accruing approximately
20 x 0.0836=USD 1.672/month while stopped. That pre-existing retention is not made
free by this session and is not charged a second time in the incremental table.
No retention extension or destructive deletion is requested. The OpenRouter USD 0.10
reserve is separate from AWS credits and authorizes no model consumption here.

## Entry, abort and rollback

Before any write, confirm fresh account/profile, active Free plan, eligible
credit coverage including outstanding retention, exact stopped host/root/SG,
fresh operator IPv4 and SSH trust, current key USD 2 non-resetting status, consistent
single-writer ledger history and a complete locally rehearsed bundle. Insufficient
allowance/history, a role/table conflict, access/upgrade denial, price drift,
clock regression or inability to arm the detached stop/release watchdog means
**no start**. No key or live ledger is accessed during today's offline drafting.

Replace the current90 minute guard only after verifying a fixed UTC nonpersistent
acceptance stop timer, deadline startup checks and an independent PC watchdog.
Reboot does not renew T0 or any allowance. No second reboot/start or helper is
authorized for a failed check. Pause, unexpected model activity, OOM, capacity
threshold breach or uncertain mutation enters teardown.

Leave lifecycle generation 0 untouched during provisioning; its 300-second start
deadline begins only when actual custody/configuration/TLS are ready for immediate
application startup. The existing lifecycle also requires 3600 seconds since last
meaningful work and 5 seconds draining to reach its normal stop command. Work ends
by 160 minutes so that, after normal EC2 stop/EIP release, this final authority
reconciliation can finish off-host within four hours. No extra running resource,
API stop, clock change or manual lifecycle-row edit is needed. On failure/pause,
record any remaining non-admitting authority state honestly and stop/release
immediately; do not keep compute on to finish the idle window.

Drain/close work, stop capture, disable and consistently back up the canonical
ledger, disable applications, restore the safe relative guard and remove
acceptance-only TLS/hosts/overrides. Preserve protected custody, all accounting
holds and authority identities. StopInstances; observe stopped; disassociate and
release the exact EIP; observe no public address/no operation EIP. If SSH fails,
API stop/release takes priority and guest cleanup remains explicitly unresolved.
No termination, disk deletion, ledger reset or clearing unknown Actions.

The final receipt must distinguish actual real-custody readiness, captured
capacity, the two boot observations and final stopped/no-EIP state. Public
wake/DNS/TLS/browser deployment and any future live model grant remain separate.
