# CAP-06 offline provisioning design

25 October 2026. **Design for owner review; not execution permission.** This
document was prepared from retained local evidence, without cloud, SSH or network
access, downloads, package installation, Docker startup or changes to the host.
The stopped state below is the last recorded observation, not a fresh cloud check.

**26 October update:** the owner approved this design. The
[local preparation result](../cap06-offline-provisioning-preparation.md) records
subsequent public-source acquisition, signature verification and bounded disposable
Linux rehearsals. That work did not access AWS accounts or change the real host.
The [new resource proposal](../cap06-private-provisioning-proposal.md) still
requires separate approval. The opening historical wording describes the original
25 October design work, not these later approved checks.

**Later26October execution:** the separately approved resource stage also completed;
see [actual results and remaining acceptance](../cap06-private-provisioning-results.md).
The original is provisioned/stopped, helper disposed and EIP released. Earlier
pending-approval/preparation wording in this design is historical; it is not the
current checkpoint or permission for an additional boot.

## Goal and chosen approach

Prepare the existing Controlled Storefront host for native Linux execution:
parallel Python 3.12, the pinned Node.js and Caddy executables, native nftables,
and a modest swap buffer. Preserve system Python 3.9 and all existing application
safety, qualification and accounting gates.

**Proposed decisions made by the author:** repair the stopped root volume using a
temporary rescue instance before booting the original; use native parallel Python
RPMs rather than a copied interpreter; start with **1 GiB of swap**; keep every
application unit disabled throughout provisioning. These are proposals for this
review, not previously granted resource or spending approvals.

The companion [procedure](../plans/2026-10-25-cap06-offline-provisioning.md) lists
the ordered checks, future operations and failure handling. This is a narrow
operator runbook, not a new provisioning framework or daemon.

## Ground truth and limits

The [inspection result](../cap06-first-private-host-results.md) and
[sanitized receipt](../../eval/evidence/cap06-first-private-host-inspection-20261025.json)
record one retained Stockholm t3.small, Standard CPU credits, encrypted 20-GiB gp3
root, SSH-only security group and existing owner public-key import. The instance
was stopped and its only EIP released. No runtime role, application, real model
key or allowance was installed. Storage continues to consume credits. Retention
review remains due 23 December 2026 at 18:00 UTC; this is not deletion permission.

| Observed item           | Retained observation                                                    |
| ----------------------- | ----------------------------------------------------------------------- |
| OS / architecture       | AL2023.12.20261021 / x86_64                                             |
| Kernel / systemd        | 6.18.54-121.166.amzn2023.x86_64 / 252.23-15.amzn2023                    |
| System Python / OpenSSL | 3.9.25 / 3.5.8                                                          |
| Physical RAM / swap     | 2,002,350,080 bytes / none                                              |
| Root                    | XFS, 20-GiB device; 19,636,555,776 bytes available at inspection        |
| Missing components      | Python 3.12, Node.js, nftables and project service accounts/directories |

The inspection queried selected RPMs, not the complete installed package/provider
inventory. It did not capture filesystem UUIDs, PARTUUIDs or Nitro device serials.
Do not infer either a complete RPM dependency closure or a secondary device name.
This design does not establish service sandboxing, boot recovery, memory capacity,
public TLS, metadata isolation or production-interpreter acceptance.

## Recover the timer before the original host boots

The enabled `scpilot-inspection-stop.timer` has both the expired
`OnCalendar=2026-10-24 22:44:06 UTC` and `OnBootSec=90min`, with
`Persistent=true`. A missed calendar trigger can run immediately on activation;
the boot-relative trigger does not postpone it. Never boot repeatedly to race it.
Ordinary replacement user data, cloud-boothook ordering and console access were
not qualified as a recovery mechanism.

The proposed reliable route is **offline repair of the existing root**, using one
separately approved temporary helper in the **same Availability Zone**. Preserve
the original instance and volume identities. No replacement application host,
snapshot, new key pair, IAM profile or general-purpose recovery service is proposed.
The additional helper/root/IP usage needs a new exact resource, cost, duration and
rollback proposal; the completed USD4.50 inspection allocation is not reusable
permission for it.

1. Reconcile ownership and fresh stopped state, exact root volume, attachment
   mapping, AZ, encryption and `DeleteOnTermination=false` before detaching it.
   The helper must have its own encrypted root, no automatic public IPv4, no IAM
   profile and the same SSH-only ingress/HTTPS-only egress constraints. Revalidate
   the operator IP and existing key/host-trust procedure. Give the helper a new
   finite relative shutdown guard and retain API stop/release as the fallback.
2. Detach only the original stopped instance's recorded root; attach it as a
   secondary helper volume. Match the AWS volume ID to the Nitro serial/by-id
   mapping and inspect partitions. Never guess `/dev/nvme1n1`. The helper and
   original roots may share an XFS UUID if based on the same image. Never reboot
   the helper with the original attached: duplicate boot identifiers can select
   the wrong root. If it stops unexpectedly, detach the original before any
   helper restart; never solve this by changing the original UUID/label.
3. Inspect the identified filesystem read-only without log replay first. The
   candidate XFS options are `ro,nouuid,norecovery`; verify them against the exact
   tools/manuals and rehearse before the future operation. Discover and record
   UUID/PARTUUID without changing either. Verify target OS and expected timer
   files, and prove the mount is not the helper's own root. If clean writable
   mounting would require an uncertain log recovery or repair, stop for a revised
   recovery plan; do not discard the log, run `xfs_repair -L`, force-detach, format
   or repartition. No filesystem repair is authorized by this design.
4. After the read-only checks, perform only the named timer repair on a clean
   writable mount. First unmount the `norecovery` inspection mount; never remount
   it writable. Run the reviewed non-modifying clean-log check while unmounted,
   then make a new `rw,nouuid` mount only after a clean result. The bounded local
   rehearsal used `xfs_repair -n -m 256 -o phase2_threads=1`; the thread option
   avoids a demonstrated default-worker/PID-limit failure. Capture actual helper
   tool compatibility before using it. Back up exact unit bytes, ownership,
   permissions, enable link
   and any exact owned persistent stamp in a root-only operation directory.
   Copy that small recovery record to owner-held storage before helper teardown.
   Do not clear `/var/lib/systemd/timers` globally. The candidate stamp
   `/var/lib/systemd/timers/stamp-scpilot-inspection-stop.timer` was not observed;
   verify its actual path/type/ownership before touching it. Unexpected files or
   drop-ins stop the operation.
5. The old unit files are regular files, so a naive `systemctl mask` would collide
   with them. Move the two verified old files into the backup, remove only the
   old timer's verified enable link, and mask both old names with guest `/dev/null`
   links. Archive the exact old stamp if present. Do not use `--now`, chroot into
   the guest or execute binaries from the detached root.
6. Install and enable only the new provisioning timer below in the guest root.
   Check the final symlinks, absence of unexpected drop-ins and unit syntax with
   compatible systemd tooling. Do not run `cloud-init clean`, reseed the original
   instance or change its ordinary user data as part of this repair.
7. Flush and cleanly unmount; verify the mount is gone before detach. Reattach the
   same original volume at its recorded root mapping, preserve retention, and
   reconcile attachment state. Original boot remains forbidden until this check
   and the separately approved operation's remaining preconditions pass.

Proposed replacement `/etc/systemd/system/scpilot-provisioning-stop.timer`:

```ini
[Unit]
Description=Bounded private provisioning window

[Timer]
OnBootSec=90min
AccuracySec=1s
Persistent=false
Unit=scpilot-provisioning-stop.service

[Install]
WantedBy=timers.target
```

Proposed `/etc/systemd/system/scpilot-provisioning-stop.service`:

```ini
[Unit]
Description=Stop private provisioning host

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl --no-block poweroff
```

There is **no calendar deadline** in this replacement. The future operation must
also have a fixed external stop/IP-release deadline and stop permission checked
before starting; the guest timer is not a spending cap. Verify the timer is
enabled, active and scheduled in the future immediately after boot. On failure,
stop through AWS, release the temporary IP and return to offline recovery.
Do not extend the window by rebooting. A later production activation must explicitly
retire this provisioning-only 90-minute shutdown guard and install its approved
lifecycle controls; do not carry it silently into public service.

## Pin the native installation inputs

Use the fixed AL2023.12.20261021 repository metadata and actual installed-provider
inventory to calculate a minimal additive RPM transaction. Keep the existing
[runtime inventory](../../deploy/linux-runtime.json) and
[28-wheel lock](../../deploy/requirements-linux.lock) unchanged.

| Input          | Chosen pin and existing evidence                                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python         | `python3.12` and `python3.12-libs`, `0:3.12.14-2.amzn2023.0.1.x86_64`; native Amazon RPM signatures verified in retained acquisition receipts                        |
| venv bootstrap | `python3.12-pip-wheel`, `0:23.2.1-4.amzn2023.0.12.noarch`; use native ensurepip; global `python3.12-pip` is not required by default                                  |
| Node.js        | Official `node-v24.22.1-linux-x64.tar.xz`; retained signed checksum verification against pinned official release keys                                                |
| Caddy          | `caddy_2.11.7_linux_amd64.tar.gz`; retained SHA256/SHA512 comparisons; publisher identity/issuer and transparency verification passed on 26 October                  |
| nftables       | `nftables-1:1.0.4-3.amzn2023.0.3.x86_64`; retained repository checksum evidence; all 14 retained fixture RPM signatures verified on 26 October                       |
| Application    | Native release source `023d9f621bc9432b871e519d51e6ce57bb7dc204`, tree `ade5f9f5d6960a9a263f01589df0f70c7c37cc87`; 4,423,680-byte archive verified during inspection |

SHA256 pins for the key inputs, distinct from signatures:

```text
b0110c2dd0a9e7335826a8fbbf9222dbc0df2f9d10dd38189382645065175889  python3.12 RPM
2f411ef99fe7380111a3d689855db0f13fd08a87e65458e606f3b8e08c23d2ca  python3.12-libs RPM
576f2dfc8a55a1f539fa24702aea406ab6a6290555d293da714db303b7605c35  python3.12-pip-wheel RPM
6c172a9ab6718f7b801fb5a7bd486af2ee5e32758086a04b84fcce2aa77095e6  Node archive
e32e2d16081cf644f88392934288086e7662529d0d43277c34f7aad2207cfafb  Node executable
727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b  Caddy archive
678ade3bfc088749c81a681adc603333ee0bb023b6a6cfe3c0f58bef8ff854e9  Caddy executable
f04fa5408e365de1a2ad1f1ed9b50f5c29d2287f1061e58af47ef3a1ece12ab1  nftables RPM
5e5e3843160225b81b81f3dd79bb960fc82507134ae7a7f58896020d5cd28a23  release.tar
```

Retained provenance and security-adoption records are described in
[runtime adoption](../research/2026-10-24-cap06-production-host-adoption.md),
[host contract](../research/2026-10-23-cap06-linux-host-contract.md) and
[nftables contract](../research/2026-10-23-cap06-host-isolation-contract.md).
They are historical records, not a new claim about current security status.

The extracted 19 Python-related RPMs and 14 nftables-related RPMs were diagnostic
tool closures, **not the host install list**. For example, the Python fixture
does not supply native `ncurses-base` if a new ncurses package needs it. Do not
overwrite newer host libraries or copy extracted libraries into `/usr`.

During the future offline-root inspection, collect the complete RPM inventory and
providers from a copy of the target's discovered canonical RPM database, using
compatible helper tooling. Do not execute the target's RPM or mutate its mounted
database. Resolve only missing providers against the fixed cached metadata. If
the complete inventory cannot be obtained reliably that way, split off a bounded
inventory-only boot after timer repair; stop again before approving installation.

Before any install, freeze the exact NEVRA, file size, SHA256, trusted signing-key
fingerprint, dependency closure and scriptlet effects for every selected RPM.
The [26 October signature receipt](../research/2026-10-26-cap06-provisioning-signatures.md)
closes these checks for the retained Caddy/nftables inputs. Every newly selected
RPM still needs the same checks. Refuse unexpected
erases, downgrades, replacements of installed libraries, Python 3.9 or kernel
changes. Repositories stay disabled during installation, weak dependencies off,
local RPM signature checking on. No `latest`, `--nodeps`, `--allowerasing`,
`--skip-broken`, network fallback or wildcard installation of fixture RPMs.

## Runtime layout and installation behavior

- **Python:** install the native parallel RPMs, then create the venv at its final
  `/opt/shopping-copilot/python` path with `/usr/bin/python3.12 -m venv --copies`.
  Use native ensurepip's retained wheel; do not copy `/var/lang` or relocate a
  prebuilt venv. Install the 28 locked application wheels with isolated pip,
  `--no-index --require-hashes --no-deps --only-binary=:all: --no-compile` and
  `--disable-pip-version-check`; suppress inherited pip configuration.
  System-site-packages stays off. Record system Python 3.9's path, symlink target,
  owning RPM and version before/after. No alternatives change or global pip.
- **Node:** install only the verified executable and license into root-owned
  `/opt/shopping-copilot/runtimes/node-24.22.1/`. Bind `/usr/bin/node` to that
  executable only if no unmanaged file or RPM-owned path conflicts. No npm,
  corepack, compilers or source build on EC2; use the retained native release.
- **Caddy:** similarly install the verified executable and license into
  `/opt/shopping-copilot/runtimes/caddy-2.11.7/`, with checked `/usr/bin/caddy`
  binding. These `/usr/bin` paths are required by existing `deploy.host_component`.
  Use only the prepared service's ambient `CAP_NET_BIND_SERVICE`, never `setcap`
  or a second vendor Caddy service. No ACME or public listener during preparation.
- **nftables:** native RPM installation supplies `/usr/sbin/nft`. Its retained
  scriptlet invokes the systemd unit installation helper. Prevent vendor
  `nftables.service` auto-preset/start with a verified persistent mask before the
  transaction, and check it remains masked/inactive afterwards. Do not globally
  change preset policy, load a vendor ruleset or flush the host firewall. Later,
  only the reviewed metadata oneshot manages its own `inet scpilot_metadata`
  table; actual enforcement needs its separate acceptance tests.
- **Ownership and units:** follow the existing
  [UID/state isolation contract](../cap06-host-isolation.md). Root owns code,
  runtimes and protected ancestors. Stage no-login service accounts and empty
  private directories, but no actual key, catalogue, ledger, allowance or
  invitation state. Keep `shopping-copilot-host.target`, its metadata/Agent/Store/
  proxy units and legacy `shopping-copilot.service` disabled and inactive. No
  enable/start or provider construction is a provisioning smoke test.

Exact re-runs may verify an identical owned installation and do nothing. Conflicts
or partial transactions require inspection; never overwrite an unknown venv,
binary, symlink, service account or configuration. A failed install is a stopped,
unaccepted host, not an instruction to retry with relaxed validation.

## Swap and disk policy

Propose **1,073,741,824 bytes (1 GiB)** at `/swapfile.scpilot` on the existing
encrypted root, root-owned `0600`. Create exclusively as a regular, single-link,
fully written non-sparse file; verify blocks before `mkswap` and `swapon`. Prefer
full zero-writing over an allocation method that may leave holes. No extra EBS
volume, filesystem UUID change, hibernation or Btrfs-specific tuning is needed.

Add one marked `/etc/fstab` entry and
`/etc/sysctl.d/90-scpilot-swap.conf` containing `vm.swappiness=10`, preserving
originals and refusing conflicting settings/paths. The entry is:

```fstab
# scpilot-provisioning swap; exact operation ID recorded in the backup manifest
/swapfile.scpilot none swap defaults,nofail 0 0
```

`nofail` preserves recovery access if swap cannot activate; that boot still fails
swap acceptance. Verify the file is exactly 1 GiB; usable active swap excludes its
header page (1,073,737,728 bytes on a 4096-byte page host). Check the measured page
size and initialized header, then verify activation/persistence during the later
approved host session/reboot. Do not raise
application concurrency, MemoryMax, overcommit or disable the OOM killer.
Existing Agent/Store/proxy/metadata MemoryMax values remain 1G/256M/256M/128M;
they are limits, not guaranteed concurrent reservations or capacity proof.

Swap is a transient OOM margin, not a substitute for RAM. A move to 2 GiB requires
measured pressure and review. Later bounded capacity checks must observe memory
and swap activity, PSI, cgroup OOM counters and response latency; sustained paging
or any OOM means no capacity acceptance. No model load is authorized here.

Budget 1 GiB of installation/staging headroom and retain at least 4 GiB free after
installation and the swap allocation; these are proposed conservative stop
thresholds. Current retained runtime/release inputs are about 99 MiB compressed;
cap the future transfer bundle at 128 MiB unless its new manifest is reviewed.
Do not add duplicate wheelhouses or build caches to the host. Bound journal and
staging retention without deleting unrelated files. Recheck actual free space.

For swap rollback, do not delete an active swap file or force `swapoff` under
pressure. If RAM cannot absorb it, defer removal to a separately bounded safe
maintenance/offline-root window; remove only the operation's exact fstab/sysctl
additions and owned file after proving swap inactive.

## Acceptance and review boundary

Provisioning is accepted only with the original root identity preserved; old
inspection timer masked; new relative timer verified after boot; system Python
unchanged; exact native runtime versions/hashes and locked wheel imports checked;
RPM transaction reconciled; vendor nftables service inert; swap/disk checks
recorded; all application services inactive; and final stopped/no-IP custody
reconciled. Record partial failure honestly and stop; package uninstall is not
assumed to reverse scriptlets or restore a clean base.

The owner approved this design and the bounded local preparation now verifies
systemd252 offline editing, the duplicate-UUID XFS mount transition on WSL6.6,
1-GiB XFS swap-file preparation and retained publisher/RPM signatures. Execution
still needs complete actual host RPM inventory and a frozen additive transaction,
actual helper-tool compatibility, and a new exact helper/host/disk/IP cost,
duration and teardown approval under the Free plan and USD0 cash. Local proof is
not actual EC2/kernel6.18 boot, swap activation or deployed capacity evidence.
No cloud operation, signature download or test boot is authorized by this document.
No change to `production_interpreter_approved=false` follows from writing it.

Application activation, model qualification binding, real key/ledger migration,
new runtime spending, signed readiness, cross-UID/IMDS checks, capacity, DNS and
public HTTPS remain later gates. The explicit OpenRouter fallback and non-resetting
USD2 key cap, settled receipts and uncertain holds remain untouched.

An independent builder review of this design and its companion procedure found
no important unanswered design question. It did not execute or qualify any of the
future operations or replace the owner's design/resource approvals.
