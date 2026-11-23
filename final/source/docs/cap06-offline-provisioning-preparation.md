# Offline provisioning preparation results

26 October 2026. The owner approved the
[provisioning design](specs/2026-10-25-cap06-offline-provisioning-design.md)
and local preparation. This stage performed public-source research/acquisition
and bounded disposable Linux checks. **No authenticated AWS request, resource
change, SSH connection, real host boot, installation or model request occurred.**
No actual provider key, ledger, allowance or invitation state was accessed.

## What passed

- **Caddy provenance:** the retained archive and checksum list passed Cosign3.1.4
  verification with the exact Caddy release workflow identity, GitHub OIDC issuer,
  SCT/transparency checks and explicit authenticated trust material. Altered bytes,
  wrong identity and wrong issuer each refused. The verifier itself was obtained
  through official HTTPS/checksum trust, with that bootstrap limit recorded.
- **Native RPM signatures:** all14 retained nftables fixture RPMs passed native
  signature checking against the pinned Amazon public key in a private RPM
  database. Tampered bytes and an empty keyring refused. No package or scriptlet
  was installed/executed. These fixtures are not the actual host transaction.
- **Exact systemd252 offline editing:** native `252.23-15.amzn2023` tools masked
  both old inspection units after their regular files were backed up, enabled the
  new calendar-free90minute timer and passed unit verification. The old fixture
  failed the acceptance predicate before repair. Seven unsafe ownership/type/
  permission/override cases refused without changing their synthetic roots.
- **Mounted XFS transition:** with two newly created images sharing an XFS UUID,
  the second mount refused without `nouuid`; `ro,nouuid,norecovery` inspection
  succeeded; a writable remount refused. Unmount, non-modifying clean-log check
  and a new `rw,nouuid` mount succeeded. Timer-file repair on that filesystem
  passed, and its original filesystem UUID remained unchanged.
- **Swap-file preparation:** a fully written1,073,741,824-byte file on disposable
  XFS had exactly that many allocated bytes, root ownership, mode0600 and a valid
  swap header. Native util-linux2.37.4 reported1,073,737,728usable bytes on its
  4096-byte page platform. **No swap was activated**, and no live sysctl changed.
- **Configuration guards:** synthetic fstab/sysctl staging preserved originals;
  an exact repeat made no write. Seven foreign/duplicate/linked/conflicting
  configuration or swap destinations refused without changes.

The [sanitized evidence index](../eval/evidence/cap06-offline-provisioning-preparation-20261026.json)
binds receipts, probe sources, input inventories and hashes. Owner-held detailed
records stay in ignored scratch directories. Existing runtime/wheel/release pins
are unchanged; `production_interpreter_approved` remains false.

## Isolation and actual limits

Signature and synthetic-root checks used the already retained AL2023-based image
by immutable digest with `--pull=never`, network none, read-only root,
no-new-privileges and all capabilities dropped. They used one CPU and512MiB memory
with no extra swap,32PIDs and private tmpfs/disk fixtures. Signature checks ran as
UID10001; synthetic root-owned file checks ran as UID0 without capabilities.
No Docker socket, home directory, cloud credentials or app secret was mounted.
Anonymous fixture volumes and containers were removed after each run.

The actual mounted-filesystem check used existing WSL Ubuntu in a transient,
private mount namespace. Its service was bounded to one CPU,512MiB memory,
MemorySwapMax0,128tasks and240seconds. Root access was used only to allocate loop
devices for the two operation-owned file images, mount those fixtures and clean
them up. Exact backing-file identities were checked before detach. No existing
disk, filesystem identifier or system swap was modified. Final checks report zero
remaining owned mounts/loop devices and removal of the private temporary directory.
This narrow rehearsal supersedes the earlier author preference for file-only
checks; it did not relax the real-host recovery or approval gates.

The WSL kernel was **6.6.87.2**, not the observed EC2 kernel6.18.54. Tools were the
signed native AL2023 systemd252.23, xfsprogs6.12.0 and util-linux2.37.4, privately
extracted for the checks. No system package installation occurred. Thus the result
establishes the procedure on a disposable mounted XFS filesystem, not actual EC2
boot/shutdown, the original root's clean log, service sandboxing or capacity.

Two test-environment issues were investigated rather than bypassed: systemd's
verifier requires its hardcoded private `/tmp` workspace, and xfs_repair's default
32Phase2workers exceeded the32PID container ceiling. The latter abort was retained;
the same bounded check passed with `-o phase2_threads=1`, supported by the exact
upstream source. That option does not bound every later worker pool. Capture and
check the helper's actual tool versions; a refusal/timeout means stop, not retries
with modifying repair, discarded logs or broader privileges. The WSL tool export
also needed the already retained matching OpenSSL library to load native systemd;
it was verified and privately extracted, not installed into WSL.

## Corrections now carried by the procedure

1. Never reboot the rescue helper with the original root attached; duplicated
   boot identifiers can select the wrong root. Detach it from a stopped helper
   before any helper restart.
2. Never turn an XFS `norecovery` mount writable with remount. Unmount, perform
   the reviewed clean-log diagnostic, then make a new writable mount only on a
   clean result. No UUID change, force detach, log discard or modifying repair.
3. Distinguish1GiB of file bytes from usable swap bytes, which exclude the header
   page. Activation and reboot persistence remain real-host acceptance checks.
4. `systemctl --root is-enabled` reports `masked` with exit1, while the new timer
   reports `enabled` with exit0. Check exact states and bytes; do not treat every
   nonzero exit as an unknown condition or confuse enabled with active.

Primary sources and retained acquisition details:
[recovery contract](research/2026-10-26-cap06-offline-recovery-contract.md) and
[signature record](research/2026-10-26-cap06-provisioning-signatures.md).

## Next boundary

The [exact private operation proposal](cap06-private-provisioning-proposal.md)
recommends **USD0.25 incremental eligible AWS credits**, based on a fresh public
estimate of USD0.14078071, or USD0.16893685 with20%buffer. It covers one temporary
same-AZ helper and its encrypted disk, bounded original-host runtime, one
sequential temporary EIP and helper-only disposal. It needs a separate owner
decision under `the project's operating rules`; design approval did not authorize these resources.

The complete installed RPM/provider inventory remains unavailable until the
approved detached-root inspection. Freeze an additive transaction against that
inventory before installing; if it cannot be established, finish timer recovery,
stop and keep installation blocked. Fresh Free-plan/credit/custody/permissions
checks belong to the approved AWS stage, not this public-price/local-proof stage.
Actual boot/timer state, swap activation/persistence, UID/IMDS/capability checks,
model custody, signed readiness, capacity and public activation remain unverified.
The original host's stopped/no-IP state is still its last retained observation;
there was no fresh cloud check here.
