# Private host recovery and offline provisioning proposal

26 October 2026. **Prepared for a separate resource/cost approval; not executed.**
The owner has approved the provisioning design and local preparation. This
proposal supplies the concrete next AWS scope required by `the project's operating rules`; it does
not treat that design approval or the completed USD4.50 inspection allocation as
permission to start the retained host or create recovery resources.

Recommended incremental allocation: **USD0.25 of existing eligible AWS credits**,
with no cash, top-up or Paid-plan transition. Public-rate estimate is
**USD0.14078071**, or **USD0.16893685 including a 20% buffer**, under the exact
quantities below. These are planning amounts, not a guaranteed bill cap.

## Exact proposed resources and writes

| Item                       | Proposed quantity and bounds                                                                                                                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Original retained host     | Reuse the recorded Stockholm t3.small; at most 90 cumulative running minutes in this operation; Standard CPU credits, no instance profile, existing encrypted root retained                                                                                  |
| Rescue helper              | Exactly one Linux t3.small in the original root's exact AZ, using the previously inspected Amazon Linux2023 AMI after revalidation; at most 90 cumulative running minutes; Standard CPU credits; shutdown behavior stop                                      |
| Helper root                | Exactly one 20-GiB encrypted gp3 root, baseline3000IOPS/125MiBps, AWS-managed EBS encryption; no performance extras; delete during normal helper teardown and in every case within 24hours of creation if safely detachable                                  |
| Helper network interface   | One helper primary ENI with automatic public IPv4 disabled; normal helper-only ENI cleanup on termination; no interface or networking change to unrelated resources                                                                                          |
| Temporary public IPv4      | Exactly one ordinary EIP allocation, associated with only one host at a time and reused sequentially from helper to original; allocated for at most three cumulative hours, then released                                                                    |
| Existing network/key       | Reuse the recorded subnet, SSH-only SG and imported existing public key after exact account/AZ/ownership/key/IP revalidation; no new SG, key pair, IAM profile, subnet, NAT, snapshot, DNS or load balancer                                                  |
| Original-root repair       | Detach only while the original is confirmed stopped; attach as helper secondary with deletion-on-termination false; inspect, back up and replace only the reviewed timer files/link/stamp; cleanly unmount and restore exact original root mapping/retention |
| Original-host provisioning | Install only the frozen additive native RPM set and pinned Python3.12/Node/Caddy/wheels, stage disabled reviewed units/accounts/empty directories and add the reviewed1-GiB swap file/swappiness10; system Python3.9 unchanged                               |

The helper's own root may use deletion-on-termination true, but helper termination
is permitted only after proving the original root is detached from it and all
required backups/receipts are retained elsewhere. If its own root remains after
termination, explicit deletion is restricted to that exact helper-root volume ID
under this operation's ownership record. No original-volume deletion, original
instance termination, retained-resource replacement or deletion-by-name is included.

Keep the existing SSH ingress restricted to the revalidated operator IPv4/32,
application80/443 closed, egressTCP443only, no IPv6 rules, required IMDSv2/hop1 and
no model credentials. If the owner IP changed, do not silently broaden or modify
the previously bound SG rule; prepare the exact replacement /32 for review before
launch. Establish SSH host identity from owned EC2 console evidence; do not
accept keyscan alone or generate replacement keys.

The original root's continuing storage cost and retention decision are already
covered by its earlier scope. This proposal adds neither another60days nor an
extension. The original retention review deadline stays **23December2026at18:00UTC**.
Its ongoing cost is not zero merely because it is omitted from this incremental
worksheet. No actual invoice or available-credit balance was queried here.

## Proposed finite operation window

New helper creation and the original host's permitted start are limited to
**after this proposal's separate approval, on26–27October2026 and no later than
27October2026at18:00Cairo (15:00UTC)**. Approval after this window
does not roll forward to another date. If prerequisites are not satisfied in time,
leave the original stopped and revise the proposed window.

- Each host may run for at most **90 cumulative minutes**, including boot and
  shutdown intervals. Begin direct API stop by75minutes from its start request,
  leaving15minutes to observe stopped. A failed or partial inspection does not
  authorize another start/retry or an extended running interval.
- Release the sole EIP by the earlier of **three hours from allocation** and
  **27October21:00Cairo /18:00UTC**. Mere disassociation is insufficient. Original
  and helper must both be observed stopped by that same absolute cutoff.
- Both guest guards use the reviewed calendar-free `OnBootSec=90min`,
  `Persistent=false` timer. The original's old inspection timer must be repaired
  before its boot. The external approved cutoff and API stop/release govern;
  neither timer is a spending cap or permission to reboot for another window.
- Delete the exact helper-only root as soon as clean teardown permits, and no
  later than **24hours after its creation**. The latest possible deadline under
  the launch window is **28October18:00Cairo /15:00UTC**. Normal cleanup must finish
  in the active execution session; the24hour storage quantity is a conservative
  contingency, not permission to leave untracked storage or create an automation.

Times were anchored to the client-specified Africa/Cairo date and a fresh UTC
clock read, with explicit Cairo-zone conversion for27–28October (UTC+3). Do not
derive dates from the execution host's default timezone.

## Start conditions and authorized sequence

Approval of this proposal is necessary but does not make the following incomplete
checks pass. Preserve the [approved design](specs/2026-10-25-cap06-offline-provisioning-design.md),
ordered procedure and
[primary recovery contract](research/2026-10-26-cap06-offline-recovery-contract.md).

1. Reconcile the [local preparation evidence](cap06-offline-provisioning-preparation.md):
   retained publisher/RPM signatures, exact systemd252 offline timer edits,
   duplicate-UUID mounted-XFS transition on WSL6.6 and XFS swap-file preparation
   now pass. Capture actual helper-tool versions before the real-root procedure.
   Managed config repeat/refusal checks also pass. Reconcile exact archive
   hashes/immutable inputs before original-host installation. EC2 boot, active swap,
   persistence and capacity remain unverified; they are not implied by local proof.
2. During a separately approved operation, verify current active Free-plan
   eligibility, credit coverage, account/region/owned resources and stop/release/
   helper-only cleanup permissions without printing credentials or identities.
   Stop if AWS requires Paid/advanced features, if current rates exceed this
   reviewed estimate/ceiling, or if cloud custody differs from the retained record.
3. Persist an operation UUID, exact resource IDs, fresh operator /32 and fixed
   deadlines privately before mutation. Launch the helper with an idempotent
   client token and explicit Standard credits; verify its finite stop guard,
   exact own root/ENI, SSH trust and original stopped state before detaching root.
4. Attach the original only after the helper has booted. Never restart the helper
   with that secondary root attached. Resolve the EBS volume ID through its Nitro
   serial to the actual partition, not an assumed device number or duplicate UUID.
   Inspect read-only, cleanly unmount and apply only the verified clean-log/new
   writable-mount procedure. No modifying filesystem repair, log discard or UUID
   change is permitted.
5. Collect complete RPM/providers from a protected copy of the original database.
   Freeze the minimal additive transaction against fixed metadata. If closure
   cannot be established, finish timer recovery only; an inventory-only original
   boot may use its single approved window, but package installation then waits
   for a revised frozen transaction. Do not improvise missing packages or reboot.
6. Back up/replace the timer, verify offline unit/link state, flush/unmount and
   reattach the unchanged original root with original retention. Retrieve small
   backups/receipts before helper destruction. Stop the helper, detach the original
   from it conclusively, then release/move the sole EIP sequentially and dispose
   of only the exact helper instance/root/ENI as approved.
7. If input closure is complete and time remains, start the original once, verify
   its new guard immediately, install only the fixed offline bundle and swap,
   keep all application units disabled/inactive and reconcile system Python,
   package diff, versions, file ownership, disk headroom and swap file/usable size.
   No model client, ACME, app lifespan, public listener or metadata-rule activation.
8. Stop the original and release the EIP within the earlier deadlines, verify
   actual stopped/no-IP state and retained original volume attachment, and publish
   a sanitized result with every incomplete acceptance check identified.

No new runtime model grant, real key/ledger migration, allowance initialization,
model call, DNS/public TLS, application ingress or production-ready flag is
included. Existing OpenRouter non-resettingUSD2cap and held reservations remain.

## Refreshed public-rate worksheet

These unauthenticated official public sources were fetched on26October2026.
No free-tier capacity, transfer allowance, KMS allowance or credits were subtracted.

| Item                                              | Verified public USD rate | Source identity                                                                                                                                                                                                      |
| ------------------------------------------------- | -----------------------: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux t3.small, shared OnDemand, no paid software |              0.0216/hour | [EC2 Stockholm Linux pricing map](<https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Stockholm)/Linux/index.json>), `RZ2CPJT3JCVWXCQM.JRTCKXETXF.6YS6EN2CT7` |
| gp3 storage                                       |         0.0836/GiB-month | [EBS pricing map](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ebs.json), Stockholm `Storage General Purpose gp3 GB Mo`, `H33YTQG3Y9XKNSF3.JRTCKXETXF.6YS6EN2CT7`                          |
| Ordinary IPv4 in use or idle                      |       0.005/address-hour | [VPC Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/eu-north-1/index.json), `H24SU884XW7MB5WC` / `2M69N79CPJC2EXZ3`                                                    |
| Internet egress, first paid tier                  |                  0.09/GB | [DataTransfer Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/eu-north-1/index.json), `DRTM7T5YA7E492Z3.JRTCKXETXF.Q3Z75P77EN`                                    |
| Incidental symmetric KMS requests                 |         0.000003/request | [KMS Stockholm catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awskms/current/eu-north-1/index.json), `2S77H5MZU5BVWEXS.JRTCKXETXF.6YS6EN2CT7`                                                      |

EC2/EBS publication is23October2026at22:13:55UTC. VPC publication is16October,
transfer16September and KMS11September; current relevant effective prices match
the [prior24October worksheet](research/2026-10-24-cap06-first-private-host-cost.md).
The pricing map is Linux OnDemand base compute: explicitly selecting **Standard**
avoids Unlimited surplus-credit charges, which are not in this estimate.

| Incremental item                                       | Conservative formula                            |      Gross USD |
| ------------------------------------------------------ | ----------------------------------------------- | -------------: |
| Helper compute,90minutes                               | 1.5 ×0.0216                                     |     0.03240000 |
| Original compute,90minutes                             | 1.5 ×0.0216                                     |     0.03240000 |
| Helper20GiB root,24hours                               | 20 ×0.0836 ÷28                                  |     0.05971429 |
| One allocated EIP,3hours                               | 3 ×0.005                                        |     0.01500000 |
| At most0.01GiB charged egress, rounded up in decimalGB | 0.010738 ×0.09                                  |     0.00096642 |
| Incidental KMS planning provision                      | 100 ×0.000003                                   |     0.00030000 |
| **Subtotal, before tax/credits**                       | exact Decimal calculation                       | **0.14078071** |
| **Subtotal plus20%buffer, rounded upward**             | exact subtotal ×1.20                            | **0.16893685** |
| **Proposed incremental credit allocation**             | leaves aboutUSD0.08106 beyond buffered estimate |       **0.25** |

The28day storage divisor is an intentionally conservative planning sensitivity,
not a claim that AWS bills every month that way. It includes the full helper-root
retention, running and stopped; do not add its first90minutes again. The original
20GiB root's existing ongoing retention is excluded to avoid double counting.
No cross-AZ transfer is proposed. The fixed bundle is uploaded from the PC; bound
returned logs/inventory/backups within the0.01GiB charged-egress provision. The
100KMS quantity is planning headroom, not an observed or enforced count. No new
customer-managed KMS key or monthly key fee is proposed.

Published prices exclude applicable taxes. Existing Free-plan/no-cash and
eligible-credit conditions are mandatory; this public lookup cannot establish
them. Neither the20%buffer norUSD0.25is an AWS-enforced spending limit. Overtime,
forgotten storage/IPs, retries, other account use or service/plan changes can
exceed it. An increase needs a revised decision; it never authorizes cash.

Public responses, raw/decoded lengths and SHA256/HTTP receipts are retained in
`.scratch/cap06-private-provisioning-prices-20261026/`. `calculation.json` binds
the exact rate records and Decimal arithmetic to their source hashes. The
Firecrawl structured provider was inspected but offers unfiltered regional EC2
pages; bounded direct official page-pricing maps avoided downloading the huge
regional EC2 catalog. No SDK, account API or authenticated AWS request was used.

## Abort and rollback authority

- Any unknown API outcome is reconciled by exact operation ID/client token/resource
  identity before another action. Do not repeat a launch, allocate another EIP or
  infer a failed detach means the original root is still attached.
- If recovery or inventory fails, preserve exact backups, stop the helper, release
  the EIP and return the original root to its stopped original host if that can
  be verified safely. Do not start the original with an uncertain timer repair.
- If helper stop/return-attachment fails, preserve the original volume regardless
  of cost. Do not force-detach, terminate a helper that still has the original
  attached, delete the original, replay/discard a dirty XFS log or relax identity
  checks. Report the exact unresolved state for a revised recovery decision.
- Helper termination/deletion requires original-volume detachment plus retained
  backups and exact helper-only IDs. If those preconditions cannot be established
  within24hours, do not destroy data merely to meet the estimate; report the
  storage overrun and obtain a revised retention/recovery decision.
- A partial package transaction leaves an unaccepted stopped host. No broad
  uninstall, system Python replacement, extra boot or network-resolved repair.
  Never delete active swap; defer removal if safe `swapoff` cannot be established.
- Finish with fresh custody evidence for the original stopped instance/retained
  root, released EIP and helper-only cleanup. Billing remains subject to delayed
  metering; no successful-application or production-capacity claim follows.
