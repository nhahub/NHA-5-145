# CAP-06 offline root recovery: documented contract

26 October 2026. Primary-source research for the owner-approved
[provisioning design](../specs/2026-10-25-cap06-offline-provisioning-design.md)
and ordered plan.
This research made public documentation requests only. It did not call AWS APIs,
authenticate, inspect credentials, start a container, mount a disk, enable swap,
install units or repair the original host. Command blocks below are future
procedure candidates, not execution receipts. The parent task owns local rehearsal.

## Conclusions affecting the procedure

1. **Unmount and make a new mount before writing.** XFS mounted with `norecovery`
   cannot transition from read-only to read-write by remount. Use the initial
   `ro,nouuid,norecovery` inspection, cleanly unmount, check the log without
   modification, then make a new `rw,nouuid` mount only on a clean result. Do not
   silently replay a dirty log to get past this gate.
2. **Do not reboot the helper with the original root attached.** Duplicate
   filesystem labels, UUIDs or PARTUUIDs can make boot select the wrong root.
   Attach the original only after the helper has booted. Unmount/detach it before
   a helper restart or helper termination. Changing the original UUID/label is
   outside this repair's scope.
3. **The proposed timer replacement fixes the right mechanism.** Keep the old
   calendar-based timer masked and use the new calendar-free relative timer.
   Offline enable/mask operations operate on the target filesystem, without
   asking the helper's system manager to start or stop anything.
4. **Distinguish swap file bytes from usable swap bytes.** A 1-GiB file has exactly
   1,073,741,824 bytes; the active swap area excludes its header page. On a 4096-byte
   page host the expected usable area is 1,073,737,728 bytes. Measure page size;
   do not require `swapon SIZE` to equal file length.

## Timer behavior and offline unit edits

The versioned systemd252 manual documents catch-up after inactivity for a
persistent calendar timer. Combining calendar and monotonic expressions does not
make the latter delay the former. Separately, `OnBootSec` already in the past
when the timer activates elapses immediately. Therefore the replacement must be
enabled before the next boot, then checked promptly; it does not provide a fresh
90-minute interval when enabled late in an already-running boot.
[systemd252 timer manual](https://raw.githubusercontent.com/systemd/systemd/v252/man/systemd.timer.xml)

Version252's source constructs a system timer's state path as
`/var/lib/systemd/timers/stamp-` plus its full unit ID. The expected path is thus
`/var/lib/systemd/timers/stamp-scpilot-inspection-stop.timer`. The source verifies
the naming rule; it does not prove this file exists on the retained host. Archive
only that exact verified owned regular file if present, preserving its metadata;
do not delete the timers directory. A different timer name avoids inheriting the
old state. [systemd252 timer implementation](https://raw.githubusercontent.com/systemd/systemd/v252/src/core/timer.c)

`systemctl --root=ROOT` with enable/disable/is-enabled and related commands reads
and changes unit-file paths directly. Enable creates installation symlinks; it
does not activate the unit. Mask binds the unit name to `/dev/null` and prevents
activation. The existing regular files must be moved to their verified backup
before masks can occupy those names. Use the helper's compatible command, not
the target root's executable. `--now`, guest chroot and helper daemon reload are
unnecessary. Offline disk state cannot establish that a timer is active.
[systemd252 systemctl manual](https://raw.githubusercontent.com/systemd/systemd/v252/man/systemctl.xml)

Future edit sequence after full path/ownership checks:

```text
archive the exact two old regular unit files and exact enable link target
remove only that verified enable link
move the old unit files out of /etc/systemd/system into the owned backup
archive the exact old stamp, if present
systemctl --root=ROOT mask scpilot-inspection-stop.timer scpilot-inspection-stop.service
write the reviewed new timer/service bytes, root:root 0644
systemctl --root=ROOT enable scpilot-provisioning-stop.timer
systemctl --root=ROOT is-enabled scpilot-inspection-stop.timer
systemctl --root=ROOT is-enabled scpilot-inspection-stop.service
systemctl --root=ROOT is-enabled scpilot-provisioning-stop.timer
```

Expected states are masked, masked and enabled. Check each command's actual
exit status, final link destination and exact new unit bytes. Scan unit/drop-in
search locations for all four exact names before mutation; unexpected overrides
are a refusal. Do not treat a broad `disable` or global timer-state cleanup as an
equivalent narrow edit. Keep the external approved deadline/API stop fallback.

## EBS identity and helper boot constraints

AWS requires stopping an instance before detaching its root. A secondary volume
must be unmounted before detach; force-detach prevents normal filesystem flushes
and can require repair. Wait for reconciled detachment before a new attachment.
Keep the original root's exact attachment mapping and retention property, and
restore those when returning it. No force flag is justified for this planned
maintenance. [AWS detach guidance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-detaching-volume.html)

An EBS volume can attach only within its own AZ. Use the privately retained exact
AZ, not a guessed Stockholm zone. A temporary helper needs its own boot volume.
The documented same-AZ condition does not prove the account has permissions or
credit coverage; those stay in the separate resource gate.
[AWS attach guidance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-attaching-volume.html)

Nitro enumeration can change across starts and differ from the requested block
mapping. AWS recommends stable volume IDs. Amazon Linux's `ebsnvme-id` reports
the EBS ID and mapping; `lsblk -o +SERIAL` exposes the ID without its dash in the
NVMe serial. Match that normalized serial to the approved original volume, then
inspect its partitions and filesystem. Do not mount by a shared filesystem UUID
or assume a particular `nvmeNn1` number.
[AWS Nitro identity guidance](https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html)

AWS describes an attached former root being selected as the wrong boot volume,
including duplicate UUIDs originating from a common image. Its label-changing
workaround is unnecessary for this procedure: keep the helper running while the
original is attached and detach before any helper boot. If the helper stops
unexpectedly, detach the original from the stopped helper before starting the
helper again. Do not change the original root's boot identifiers.
[AWS wrong-root troubleshooting](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-booting-from-wrong-volume.html)

## XFS inspection and clean writable transition

The Linux6.18 XFS manual documents `norecovery` as skipping log recovery, requiring
read-only mode and potentially exposing inconsistent files after an unclean stop.
`nouuid` bypasses duplicate-UUID checks without rewriting the UUID. Thus an
apparently readable `os-release` is an identity check, not proof of a clean log.
[Linux6.18 XFS manual](https://raw.githubusercontent.com/torvalds/linux/v6.18/Documentation/admin-guide/xfs.rst)

Linux6.18's `xfs_remount_rw` explicitly rejects a mounted filesystem carrying the
no-recovery feature. The safe transition here is an unmount followed by a new
mount, never `mount -o remount,rw`. This is upstream behavior for the observed
kernel series; AL2023's exact build and installed xfsprogs must still be captured
and the candidate tested on a disposable filesystem before host use.
[Linux6.18 XFS mount implementation](https://raw.githubusercontent.com/torvalds/linux/v6.18/fs/xfs/xfs_super.c)

Candidate future sequence, with `TARGET_PART` bound by exact volume/partition
identity and `ROOT` a new protected empty mountpoint:

```sh
mount -t xfs -o ro,nouuid,norecovery,nodev,nosuid,noexec "$TARGET_PART" "$ROOT"
# Inspect only expected OS, unit paths, fstab and copied package database.
umount "$ROOT"
# Verify no mount remains for TARGET_PART, then run the non-modifying check.
timeout 120s xfs_repair -n -m 256 -o phase2_threads=1 "$TARGET_PART"
# Only after exit 0 and review of complete diagnostics:
mount -t xfs -o rw,nouuid,nodev,nosuid,noexec "$TARGET_PART" "$ROOT"
# Make only the approved timer-file edit, then flush/unmount before detach.
```

The later [bounded rehearsal](../cap06-offline-provisioning-preparation.md) found
that xfsprogs6.12's default 32 Phase-2 workers exceed a 32-PID container limit;
`-o phase2_threads=1` passes under the same memory/CPU/PID bounds. Check this option
against the helper's actual version; it does not bound every later worker pool.

The proposed 120-second/256-MiB diagnostic bounds are author choices, to be checked
against helper capacity and exact tooling. `-m` is approximate, not a hard memory
limit. The XFS manual defines `-n` as non-modifying and requires an unmounted
filesystem; dirty log exits2 and detected corruption exits1. Any nonzero result,
timeout, warnings requiring recovery or unexpected external log/realtime device
stops this procedure. `-n` is not a complete corruption proof. No modifying repair,
`-L`, forced geometry, log replay or UUID rewrite follows automatically.
[xfs_repair manual](https://man7.org/linux/man-pages/man8/xfs_repair.8.html)

## Small swap file on the encrypted XFS root

The versioned util-linux manual explains why holes and copy-on-write files can be
rejected for swap and recommends full writes from `/dev/zero` as the portable
creation method. XFS preallocation is supported on newer kernels, but full writes
avoid relying on that path. The candidate does not need Btrfs `nocow` handling.
[util-linux2.37.4 swapon manual](https://raw.githubusercontent.com/util-linux/util-linux/v2.37.4/sys-utils/swapon.8.adoc)

The same-version mkswap manual requires creating the file before initialization.
Creating a swap signature is not activation; the original boot remains a later
gate. [util-linux2.37.4 mkswap manual](https://raw.githubusercontent.com/util-linux/util-linux/v2.37.4/disk-utils/mkswap.8.adoc)

Candidate future root-only creation after protected-parent, absence, free-space
and operation checks; never interpolate an arbitrary user-supplied path:

```sh
SWAP=/swapfile.scpilot
umask 077
dd if=/dev/zero of="$SWAP" bs=1M count=1024 conv=excl,fsync status=none
# Verify root owner, regular single-link 0600, exactly 1073741824 bytes,
# and allocated blocks covering the full file; stop if dd was incomplete.
mkswap "$SWAP"
# Re-verify inode identity and exact newly recorded signature before swapon.
swapon "$SWAP"
swapon --show --bytes
```

`conv=excl` is a GNU-dd exclusive-create safeguard; it must be checked with the
installed coreutils during rehearsal. `mkswap` must never be called after failed
creation or with `--force`. A repeat verifies the exact prior operation's inode,
signature and active state; it does not rewrite an existing active swap file.
The owned fstab entry/sysctl proposal remains as designed. Removing swap later
requires a safe `swapoff` or a separately bounded offline window, not `rm` on an
active file. No host swappiness, memory limit or concurrency changed here.

## Retained source provenance and remaining evidence

Firecrawl's developer search was used to locate documentation; cited content was
read from the explicit official/versioned pages. The XFS manual mirror identifies
its upstream xfsprogs source; Linux's versioned manual/source provide the primary
mount behavior. The local record contains twelve successful source responses:

```text
.scratch/cap06-offline-recovery-research/sources-manifest.json
```

That manifest records each saved JSON response's SHA256, extracted content SHA256
and byte length, source URL, scrape ID, cache state and cached timestamp when
provided. It is ignored research evidence, not an approval token. Two guessed XFS
documentation paths and one guessed mkswap path returned404; the correct versioned
paths above succeeded. Firecrawl briefly rate-limited concurrent calls; no
authentication or cloud-action retry was involved.

All results here are **documented**, not host-tested. Remaining acceptance is the
parent's bounded synthetic rehearsal, actual helper tool versions/capacity,
original volume/partition and log state, complete RPM inventory, future AWS
approval/ownership reconciliation, timer state after original boot and swap
persistence/capacity. This research does not declare the stopped instance repaired
or production-ready.
