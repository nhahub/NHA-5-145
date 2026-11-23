# Private host recovery and offline provisioning completed

26 October 2026. The owner explicitly approved the
[exact proposal](cap06-private-provisioning-proposal.md), its incremental
USD0.25 eligible-credit allocation, mandatory Free plan/USD0 cash and replacement
of a rotated SSH operator IPv4/32. The operator IP was unchanged, so no security
group rule was modified. The owner-requested pause occurred before resource
creation; fresh preflight and a new finite watchdog preceded the resumed run.

**The original host is provisioned and stopped.** Its original encrypted20-GiB
root remains attached with deletion-on-termination false. The temporary helper
was terminated, its root and primary interface were deleted, and the sole EIP
was released. Fresh final AWS checks at18:57:44UTC confirm this custody and an
active Free plan. No application serving, model request, provider-key/ledger
migration, runtime allowance enablement, DNS or public TLS activation occurred.

## Recovery performed

Exactly one same-AZ t3.small helper used the inspected Amazon Linux2023 AMI,
Standard CPU credits, its own encrypted20-GiB gp3 root and the existing SSH-only
group/key. Automatic public IPv4 was disabled, IMDSv2/hop1 enforced, no instance
profile attached and application80/443 ingress remained closed. Its calendar-free
90-minute stop timer was active/enabled before original-root attachment. SSH trust
was bound to the owned EC2 console fingerprint; original-host trust later matched
its retained console-established key. Global SSH configuration was unchanged.

The stopped original root was attached as a secondary with retention preserved,
identified by exact EBS-to-Nitro serial mapping rather than guessed enumeration or
filesystem UUID. Read-only/no-recovery inspection verified OS and exact old unit
bytes and copied the canonical RPM database before querying it. Its complete
494-package inventory was exported without modifying the source database.

After unmount, the non-modifying XFS clean-log diagnostic passed. A new writable
mount archived the exact old timer/service/link metadata and optional owned stamp,
masked both old names and enabled the new `OnBootSec=90min`, `Persistent=false`
timer with no calendar trigger. The tiny backup was retrieved to owner-held
storage. No log discard, modifying filesystem repair, force detach, UUID rewrite,
cloud-init reset or ordinary user-data replacement was used.

The original filesystem UUID/PARTUUID remained unchanged. After clean unmount,
the same disk returned to its original root mapping/retention on the stopped
original instance. Only then was the helper stopped/disposed. The original was
started once, its new timer observed active/waiting/enabled and both old units
observed masked. This is actual boot verification of the timer repair.

## Native provisioning verified

| Component          | Verified installed state                                                                             |
| ------------------ | ---------------------------------------------------------------------------------------------------- |
| System Python      | 3.9.25; resolved executable hash and owning RPM unchanged                                            |
| Parallel Python    | Native3.12.14, final-path venv at `/opt/shopping-copilot/python`                                     |
| Application wheels | Exactly28locked distributions; only bootstrap pip is additional; native imports and `pip check` pass |
| Node.js            | 24.22.1, exact retained executable/license, required `/usr/bin/node` binding                         |
| Caddy              | 2.11.7, exact retained executable/license, required `/usr/bin/caddy` binding; no file capability     |
| nftables           | Native1.0.4; vendor service masked/inactive; no metadata rules loaded                                |
| Release            | Native source `023d9f621bc9432b871e519d51e6ce57bb7dc204`; unchanged archive and manifest hashes      |
| Swap               | Fully allocated1-GiB root0600file;1,073,737,728usable bytes; active before stop; swappiness10        |
| Disk headroom      | 17,889,599,488bytes free before removing the final transfer bundle                                   |

The actual original inventory and fixed repository metadata resolved a minimal
additive transaction. Native RPM version comparison and both helper/original DNF
previews supported exactly these nine packages, with **no upgrade, downgrade or
erase**:

- python3.12 and python3.12-libs3.12.14-2.amzn2023.0.1;
- python3.12-pip-wheel23.2.1-4.amzn2023.0.12;
- nftables1:1.0.4-3.amzn2023.0.3;
- mpdecimal2.5.1-3.amzn2023.0.3;
- libnftnl1.2.2-2.amzn2023.0.2;
- iptables-libs1.8.8-3.amzn2023.0.2;
- libnetfilter_conntrack1.0.8-2.amzn2023.0.2;
- libnfnetlink1.0.1-19.amzn2023.0.2.

Every RPM hash/signature was checked against the pinned Amazon key. Scriptlets
were reviewed; the vendor nftables service was masked before its install helper
ran. DNF repositories were disabled, weak dependencies off and local package
signature checks enabled. The installed RPM diff contains only those nine adds.
No diagnostic19/14-package fixture was blindly installed.

The frozen101,767,090-byte transfer bundle stayed below128MiB. The final-path venv
was created with native Python, without relocating a fixture interpreter or venv.
Isolated pip configuration was verified empty at all scopes; installation used
only the28local hash-locked binary wheels, no dependency resolution/index/version
check. No npm, compiler or application build ran on EC2.

Root-owned release/runtimes, no-login accounts and empty protected config/state/log
directories are staged. Agent, Store and proxy accounts executed their respective
runtime/import/version checks. Six prepared units pass native static verification
and remain inactive and unenabled. Agent-only/model custody remains empty. These
checks do not claim actual managed-service sandbox or metadata-barrier acceptance.

## Timing and cleanup

| Bound                                               | Observation-conservative interval | Approved maximum |
| --------------------------------------------------- | --------------------------------- | ---------------- |
| Helper launch request to first stopped observation  | 1,009.048seconds, under17minutes  | 90minutes        |
| Original start request to first stopped observation | 738.773seconds, under13minutes    | 90minutes        |
| Sole EIP allocation request to confirmed release    | 1,890.386seconds, under32minutes  | 3hours           |

The operation wrapper recorded109CLI invocations, including deliberate permission
dry runs, with15successful actual resource mutations and no failed/unknown
resource mutation. Initial expired-session probing/sign-in are separate from that
wrapper count. No resource creation or original start was retried. The finite
watchdog was disarmed after verified final custody.

These are observation bounds, not final billed durations. The approved increment
was USD0.25; billing/metering is not finalized. Original EBS storage continues
under its existing retained-storage scope, with the unchanged23December2026at
18:00UTCreview deadline. That date is not deletion permission. No Paid-plan
transition, top-up or new model spending was performed.

## Recorded operator corrections

The retained failures were resolved without another boot, broader access or
relaxed integrity checks: Windows CRLF affected the saved user-data receipt
comparison; systemd252 help spells optional boolean flags with brackets; verifier
executable checks reject an intentionally `noexec` guest mount; the bundle upload
needed a verified-prefix SFTP continuation after its initial transfer deadline;
and util-linux2.37.4 lacks `swapon --json`.

The filesystem stayed `noexec`. Exact replacement unit bytes were verified using
the trusted helper binary, while the original systemctl ELF hash/mode matched
the helper; the original boot and native post-install unit verification then
passed. Swap activation was not repeated: native byte output was reconciled with
`/proc/swaps` and the file/header/page size. Prior failure receipts are preserved.

## Remaining acceptance boundary

The [sanitized execution evidence](../eval/evidence/cap06-private-provisioning-20261026.json)
binds the detailed owner-held operation receipts. Provider cap/settled receipts/
uncertain holds are unchanged. `production_interpreter_approved` stays false.

Next work is controlled application/host acceptance: protected provider custody
and qualification binding, managed systemd252 UID/IMDS/capability enforcement,
signed readiness and bounded capacity. Swap activation after a later boot and
reboot persistence remain untested. Public activation needs its existing gates
and an explicit replacement of the provisioning-only90-minute stop guard. This
stage establishes host preparation, not a finished public deployment.
