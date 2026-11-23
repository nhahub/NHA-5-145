# CAP-06 host isolation and diagnostic contracts

Date: 2026-10-23. Reviewed baseline: `c6924a5f30d8102b29e6afbcd17c489bbc5899c1`.
Scope: public primary-source research and read-only local tool inventory. This
report does not install or activate services, apply firewall rules, acquire RPMs,
contact metadata/AWS accounts/models, or establish AL2023/systemd/EC2 acceptance.

## Repository seam and recommended minimum

The baseline's three host services all use `User=copilot`, and both component
launchers load full `HostSettings`, including the readiness key and inference
configuration. All three discard stdout/stderr. The current private reader rejects
group-readable files, and its private-file ancestor validator accepts only
root/current UID; that validator is not called on the catalogue by the baseline
`HostSettings`/`catalogue_status` path.
These observations come from `deploy/host_config.py`, `deploy/host_component.py`,
`deploy/host_agent.py`, and the three service units, rather than an exploit test.
`CONTEXT.md`, the newest checkpoint/handoff and `docs/cap06-apply-proposal.md`
preserve the provider, approval, safety and uncertain-outcome gates.

Use three fixed, different, non-login service UIDs: existing `copilot` for Agent,
`copilot-store` for Storefront, and `copilot-proxy` for Caddy. Resolve the numeric
Agent UID from the protected system account database when producing the rule
batch; reject root, missing accounts, duplicates and unexpected identity
bindings. Do not make an external username or arbitrary numeric value a firewall
argument. Distinct UIDs provide ordinary file/process isolation; the metadata
firewall supplies the network restriction. AWS explicitly documents local
process-owner firewall restrictions for IMDS, including allowlisting selected
users. IMDSv2 alone does not distinguish these local services.
[AWS IMDS access restrictions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-metadata-limiting-access.html)

| Consumer                     | Required private input                                                                         | Required writable state                                       |
| ---------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Agent (`copilot`)            | Full Agent host settings, Agent copy of service secret, readiness key, inference configuration | Existing Agent inference ledger and required Agent state only |
| Storefront (`copilot-store`) | Minimal protected Storefront settings and its own service-secret copy                          | Storefront catalogue subtree only                             |
| Proxy (`copilot-proxy`)      | Minimal protected release/fingerprint settings; no application secret                          | Its own Caddy certificate/state subtree only                  |

Keep two distinct regular `0400` UID-owned files containing the same service
secret for Agent and Storefront; avoid a shared group-readable secret. Existing
private-file/ancestor/nonsymlink/hardlink checks continue to apply. Minimal
Storefront/proxy settings must validate the exact executing release and
fingerprint without importing Agent admission/inference/SDK machinery or reading
its private inputs. Do not accidentally preserve full `HostSettings` loading as a
shared prerequisite. The proxy receives no service/readiness secret in its clean
environment. Ordinary permission checks are not granted by `ReadWritePaths=`;
they must be provisioned for each real consuming UID.
[systemd 252 filesystem sandboxing](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html#ReadWritePaths=)

Catalogue proposal: a Storefront-owned `2750` directory, dedicated
`copilot-catalogue` group, Storefront-owned `0640` database, and Agent-only
`SupplementaryGroups=copilot-catalogue`. The exact directive spelling is
`SupplementaryGroups=`. It adds to groups from the account database; explicitly
audit all three accounts' memberships. Agent must have a read-only mount view of
the entire Storefront subtree, use SQLite read-only access, and fail catalogue
permission validation if this custody is violated. If explicit filesystem custody
validation is added for the catalogue, scope it to the expected Storefront
UID/catalogue GID; the baseline only resolves the path and opens SQLite with
`mode=ro`. Do not relax private-secret ancestor checks globally. The setgid directory
inherits the group for newly created children; actual DB replacement/sidecar
modes and SQLite journal behavior still require a real Storefront/Agent test.
[systemd 252 supplementary groups](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html#SupplementaryGroups=),
[Linux directory setgid semantics](https://man7.org/linux/man-pages/man2/open.2.html),
[SQLite read-only database opening](https://www.sqlite.org/c3ref/open.html)

Use `ProtectSystem=strict`, narrow `ReadWritePaths=`, `NoNewPrivileges=yes`,
`ProtectProc=invisible`, `RestrictNamespaces=yes`, and the existing restricted
address families. Agent/Storefront keep an empty capability bounding set; only
Caddy retains `CAP_NET_BIND_SERVICE`. In particular none receives
`CAP_NET_ADMIN`, `CAP_SETUID`, `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE` or a sudo path.
The namespace restriction blocks creating/switching user/network namespaces
through the relevant clone/unshare/setns operations on supported architectures.
`ProtectProc=invisible` is defense in depth: it requires non-root execution,
absence of `CAP_SYS_PTRACE`, and kernel per-mount hidepid support; the documented
setting can silently have no effect on a kernel without that support. It does
not protect against root or compromise of the Agent UID itself.
[systemd 252 namespace and proc settings](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html#ProtectProc=),
[systemd 252 namespace restrictions](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html#RestrictNamespaces=),
[Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)

## Atomic metadata rule batch

AWS documents metadata at IPv4 `169.254.169.254` and IPv6 `fd00:ec2::254`.
Both must be covered even when the selected host currently disables the IPv6
endpoint. Filter locally generated output; do not change unrelated input,
forward, Docker, WSL, or host firewall state. Root and the single numeric Agent
UID are the only intended exceptions.
[AWS metadata retrieval endpoints](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html)

The following is an inert shape, with the non-executable placeholder `AGENT_UID`.
The trusted helper must substitute a validated decimal UID, never free text:

```nft
add table inet copilot_metadata
add chain inet copilot_metadata output { type filter hook output priority 0; policy accept; }
flush chain inet copilot_metadata output
add rule inet copilot_metadata output ip daddr 169.254.169.254 meta skuid { 0, AGENT_UID } return
add rule inet copilot_metadata output ip6 daddr fd00:ec2::254 meta skuid { 0, AGENT_UID } return
add rule inet copilot_metadata output ip daddr 169.254.169.254 drop
add rule inet copilot_metadata output ip6 daddr fd00:ec2::254 drop
```

Use one `nft -f -` transaction, including add/flush/repopulation, with the entire
bounded batch on stdin. Native `-f` scripts apply atomically; if a command fails,
the transaction does not partially replace the policy. `add table` tolerates an
existing table; `create table` does not. Likewise `create chain` is exclusive,
whereas `add chain` is the ordinary non-exclusive command. `flush chain` removes
that chain's rules, so repeated successful starts do not append duplicates. The
table/chain must exist before flushing, which is why the add commands are inside
the same batch. Never use `flush ruleset`, global `flush table`, separate
flush/load invocations, or best-effort deletion to obtain idempotence.
[Netfilter nft manual: tables/chains](https://netfilter.org/projects/nftables/manpage.html#lbAF),
[Netfilter atomic replacement](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement),
[Netfilter chain operations](https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains)

Here “owned table” means a dedicated administratively reserved namespace, not
the modern nft table `owner` flag. Do not use `owner`, `persist`, or `destroy`
as an assumed AL2023 1.0.4 feature. Do not depend on undocumented behavior when
the named chain already exists with a different hook/type/priority: inspect and
reject conflicting preexisting objects during approved provisioning, and include
incompatible-chain cases in the disposable test. No other service may manage the
dedicated table. The additive batch must preserve an unrelated sentinel table in
tests. Metadata exceptions return from this base chain; they do not override a
drop in another chain. Unknown/no-socket metadata traffic reaches the unconditional
drop, unlike relying only on a negated socket-UID comparison.
[Netfilter base-chain processing](https://wiki.nftables.org/wiki-nftables/index.php/Configuring_chains),
[Netfilter metadata expressions](https://netfilter.org/projects/nftables/manpage.html#lbAV)

Priority `0` assumes this dedicated host has no earlier output DNAT/redirect
rewriting the destination. Qualify the complete installed ruleset; if an earlier
redirect exists, resolve that explicitly in the reviewed policy rather than
claiming UID filtering covers it. An unprivileged application must not be able to
open allowed-UID sockets, receive passed Agent sockets/credentials, or route
through a privileged local metadata proxy. The Agent itself is trusted with its
role; this design does not protect credentials after Agent/root compromise.

The root oneshot helper should use Python stdlib only: check root euid, read a
root-owned owner-only nonsymlink bounded configuration, verify the exact reviewed
release and its fingerprint without importing Agent/runtime code, resolve and
cross-check the fixed service accounts through `pwd`, construct only the fixed
table/endpoints/decimal UID batch, and invoke only `/usr/sbin/nft` with a fixed
argument vector, clean environment, no shell, bounded timeout and discarded
child stdout/stderr. Validate the executable's protected provenance. A generic
fixed refusal may be emitted; raw config, nft parser output, exception text,
environment and command output must not enter diagnostics. No command/endpoint/
binary/table override belongs in the production CLI. Passing stdin avoids a
second writable rule file and shell interpretation. This is a proposed local
implementation seam, not permission to invoke nft against the host now.
[Python subprocess fixed argument/input/timeout contract](https://docs.python.org/3.12/library/subprocess.html#subprocess.run),
[Python pwd account lookup](https://docs.python.org/3.12/library/pwd.html)

## systemd 252 lifecycle and fail-closed boundary

Prepare an inactive `shopping-copilot-metadata.service` with `Type=oneshot`,
`RemainAfterExit=yes`, root identity, fixed helper command and explicit bounded
`TimeoutStartSec=`/`TimeoutStopSec=`. Oneshot startup has no default timeout, so
the explicit bound matters. Root needs network administration in the initial
network namespace; do not put this unit in `PrivateNetwork=yes` or a private user
namespace. Its process may exit after committing rules; the rules remain in the
kernel namespace. Provide no `ExecStop=`/`ExecStopPost=` rule deletion.
[systemd 252 oneshot behavior and timeouts](https://www.freedesktop.org/software/systemd/man/252/systemd.service.html#Type=),
[Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html)

Every application member, including direct starts, should explicitly carry
`Requires=shopping-copilot-metadata.service`,
`After=shopping-copilot-metadata.service`, and
`BindsTo=shopping-copilot-metadata.service`. `BindsTo=` already implies the
requirement behavior; retaining `Requires=` makes the intended gate explicit.
`After=` orders completion but does not activate a dependency on its own.
`Requires=` plus ordering prevents starting after dependency activation failure;
`BindsTo=` plus ordering also stops the application when the dependency becomes
inactive or is skipped. Avoid a `ConditionPathExists=` gate that merely skips the
metadata unit. A configuration/helper/nft error must fail startup. Preserve target
stop/restart propagation and the explicit legacy-unit conflict/order.
[systemd 252 requirement, ordering and binding semantics](https://www.freedesktop.org/software/systemd/man/252/systemd.unit.html#Requires=)

The target's `Wants=` does not establish readiness and may leave the target
active when a member fails. Existing `Type=exec` also proves only successful
exec of the Python launcher, not successful Storefront/Caddy second exec, health,
signed readiness or provider qualification. Retain the existing independent
bounded application restart policy and authoritative readiness gate. An explicit
metadata-unit stop/restart should stop dependents while retaining kernel rules;
restarting it does not inherently restart every application. Recovery should
re-start the owned target/services only after the failure is understood.
[systemd 252 Wants/PartOf](https://www.freedesktop.org/software/systemd/man/252/systemd.unit.html#Wants=),
[systemd 252 exec behavior](https://www.freedesktop.org/software/systemd/man/252/systemd.service.html#Type=)

`BindsTo=` tracks unit state, not firewall liveness. If root or another firewall
manager deletes the table while the oneshot remains active, applications do not
automatically stop. Prevent conflicting rule managers and make real boot/reboot,
direct-start, dependency failure, retained-rules-on-stop and owner-deletion
limitations explicit acceptance items. A bounded helper timeout after a possible
commit is an uncertain outcome: stop/keep applications closed, retain rules and
inspect rather than deleting them or assuming the transaction failed.

## Fixed-vocabulary diagnostics

Keep child stdout/stderr suppressed. Add a small bounded helper invoked by
`ExecStartPre=` for a fixed `start_attempt` event and `ExecStopPost=` for a fixed
`stopped` event. Use fixed component choices `agent`, `store`, `proxy`, `metadata`;
do not serialize the caller's strings, arbitrary argv, paths, identifiers,
exception objects, secrets, prompts, HTTP data or child output. An event from
`ExecStartPre=` means an attempt; do not label it healthy/ready. The pre hook must
complete successfully before `ExecStart=` runs. A logging error should refuse
startup if durable diagnostics are a required gate, and should never trigger a
firewall cleanup. Stop-hook logging failure must not conceal the original
service result or prevent bounded shutdown.
[systemd 252 startup and stop-post hooks](https://www.freedesktop.org/software/systemd/man/252/systemd.service.html#ExecStartPre=)

`ExecStopPost=` covers failed starts and runtime exits; `ExecStop=` alone does
not. Read `SERVICE_RESULT` from the hook's environment and map it through an exact
allowlist. For v252 the source defines `success`, `resources`, `protocol`,
`timeout`, `exit-code`, `signal`, `core-dump`, `watchdog`, `start-limit-hit`,
`oom-kill`, and `exec-condition`. Map missing or any future/hostile value to a
fixed `unknown`; do not echo it. The short result table in the manual omits two
values which its later summary and v252 source include. Raw `EXIT_STATUS` need
not be recorded at all. Some dependency/start-limit/manager failures can happen
before hooks execute; the helper is not an exhaustive manager-event stream.
[systemd 252 result environment](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html#%24SERVICE_RESULT),
[systemd v252 service result source](https://github.com/systemd/systemd/blob/v252/src/core/service.c)

The selected implementation proposal is a bounded private local file logger,
with one opened protected component-directory fd used for `flock`, then all
log-file open/stat/rename operations relative to that fd. A directory lock avoids
an additional lock file and keeps the serialization inode stable across log
rotation. Use `LOCK_EX|LOCK_NB` with a monotonic finite acquisition deadline;
never an unbounded blocking lock in a stop hook. Cooperating writers must take
the same directory lock before rotation/open/append, and the directory itself
must not be replaceable by a different UID. Use local Linux filesystem semantics,
not an assumed NFS/SMB lock contract. `flock` is advisory and associates locks with
the open file description; it does not prevent malicious unlocked writes by the
same UID. This is operational evidence, not an audit boundary against compromise
of its writer UID.
[Linux flock semantics](https://man7.org/linux/man-pages/man2/flock.2.html),
[Python dir_fd operations](https://docs.python.org/3.12/library/os.html#files-and-directories)

Validate directory/file identity and owner/mode/nonsymlink/regular/single-link
constraints on the opened fds; reject unsafe existing rotation targets. Bound
each record and the total number/size of rotations, handle short writes, fsync
the file after appending, and fsync the directory after creating/renaming its
entries. File fsync alone does not establish persistence of the directory entry.
Hold the common lock across the whole rotation/append/sync operation. Permission,
space, lock-timeout, write and fsync errors must return a fixed refusal with no
raw exception text; actual durable storage/reboot and failure behavior remain
acceptance items. A finite flock wait does not by itself bound a kernel fsync;
the systemd hook timeout is the outer bound, and a timeout may leave uncertain
record durability.
[Linux fsync persistence boundary](https://man7.org/linux/man-pages/man2/fsync.2.html)

The system journal remains useful for manager failures outside helper execution.
If journal persistence is claimed, qualify `Storage=persistent` or an existing
persistent directory, retention/disk bounds and reboot retrieval separately.
Default `Storage=auto` is volatile without `/var/log/journal`; persistent storage
can fall back to runtime during early boot/unwritable disk, and a datagram send
is not proof of durable storage. No new remote logging service is proposed.
[systemd 252 journal storage and synchronization](https://www.freedesktop.org/software/systemd/man/252/journald.conf.html#Storage=)

## Available local tools and disposable proof boundary

Read-only command on 2026-10-23:
`wsl -d Ubuntu -- sh -c 'command -v nft; command -v ip; command -v unshare; nft --version; ip -Version; unshare --version; systemd --version'`.
Observed `/usr/sbin/ip` (iproute2 6.1.0), `/usr/bin/unshare` (util-linux 2.39.3),
systemd 255.4; `nft` was not found. Additional path/package inventory found no
`nftables`, `libnftables1` or `libnftnl11` installation; `libmnl0:amd64` is
1.0.5-2build1. No namespace, firewall, service or package mutation was attempted.
Ubuntu/systemd 255 static verification cannot establish target systemd 252
behavior. The requested `docs/graduation-scope.md` is absent in this baseline;
the existing primary-workspace `D:/agent depi/docs/graduation-scope.md` was read
without changes and retains the approved Controlled Storefront scope, local MVP
gates, cloud safety/deployment acceptance and no production-readiness inference.

A separately approved disposable `--network none` AL2023 container can later
hold fake metadata listeners at the two reserved addresses in its own network
namespace. It needs container-only network administration for loopback/address/
rules setup and tightly bounded UID/GID/file-custody operations; it must not
mount host credentials, Docker socket, home, or host network. Test successful
root/Agent requests, refused Storefront/proxy/unrelated UID requests, ordinary
loopback traffic, repeated identical application without duplication, atomic
failure preserving the old policy, unrelated sentinel-table preservation, and
actual process-environment/file permissions. Numeric UIDs in the proof are
synthetic fixture identities. No real IMDS request or AWS SDK is needed. Exact
kernel/nft/backend behavior and helper timeout paths must be retained as evidence,
and actual systemd252/EC2 reboot/readiness acceptance remains separate.
[Docker network-none isolation](https://docs.docker.com/engine/network/drivers/none/),
[Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html)

## Public AL2023 package metadata for a later test-tool fixture

Only public metadata was retrieved, in memory; no RPM was downloaded, extracted,
installed or executed. The fixed
[2023.12.20260930 x86_64 mirror list](https://cdn.amazonlinux.com/al2023/core/mirrors/2023.12.20260930/x86_64/mirror.list)
resolved to repository GUID
`5775d799f6e8c33e94d68682d3490cae250052e8798e544edd2d76501d867228`.
Its [repomd.xml](https://cdn.amazonlinux.com/al2023/core/guids/5775d799f6e8c33e94d68682d3490cae250052e8798e544edd2d76501d867228/x86_64/repodata/repomd.xml)
declares [primary.xml.gz](https://cdn.amazonlinux.com/al2023/core/guids/5775d799f6e8c33e94d68682d3490cae250052e8798e544edd2d76501d867228/x86_64/repodata/primary.xml.gz)
SHA256 `3f3cf51a7be2af556cc8b5cf201967882f326ad766f9a46a36378fd7d0d1f0b1`
(8,012,147 compressed bytes). The fetched compressed metadata's SHA256 matched.
This is HTTPS/CDN plus metadata-digest evidence; no RPM signature verification
has occurred. The dated official release notes also list
`nftables-1.0.4-3.amzn2023.0.3`.
[AWS AL2023 release notes](https://docs.aws.amazon.com/linux/al2023/release-notes/relnotes-2023.12.20260803.html)

The following URLs and SHA256 values are literal package entries in that primary
metadata. They are candidates for an ignored, extracted **test-tool** tree, not
an approved production lock or newest/security-qualified version claim. Metadata
requirements indicate compatibility with AL2023's glibc 2.34; actual ELF/loader
closure against the retained Lambda image remains untested. In this repository
the `nftables` RPM supplies `libnftables`; no separate `libnftables` package entry
was found. Runtime extraction does not mean running RPM installation scriptlets.

| RPM                                                                                                                                                                                                                            | SHA256                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| [nftables-1.0.4-3.amzn2023.0.3.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/f04fa5408e365de1a2ad1f1ed9b50f5c29d2287f1061e58af47ef3a1ece12ab1/nftables-1.0.4-3.amzn2023.0.3.x86_64.rpm)                             | `f04fa5408e365de1a2ad1f1ed9b50f5c29d2287f1061e58af47ef3a1ece12ab1` |
| [libnftnl-1.2.2-2.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/07a5c6de366eb6c61def60beb0905e41ea832858467df65c4bb09cc9d30cde63/libnftnl-1.2.2-2.amzn2023.0.2.x86_64.rpm)                             | `07a5c6de366eb6c61def60beb0905e41ea832858467df65c4bb09cc9d30cde63` |
| [libmnl-1.0.4-13.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/3070d3abc261ab0270717aae200b702861924c35fee59ad2abcf7bdf807462c7/libmnl-1.0.4-13.amzn2023.0.2.x86_64.rpm)                               | `3070d3abc261ab0270717aae200b702861924c35fee59ad2abcf7bdf807462c7` |
| [gmp-6.2.1-2.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/79a25d459594c41cc4c5ec18ad42d4011da65cb27355421cb9975f5157169fdf/gmp-6.2.1-2.amzn2023.0.2.x86_64.rpm)                                       | `79a25d459594c41cc4c5ec18ad42d4011da65cb27355421cb9975f5157169fdf` |
| [jansson-2.14-0.amzn2023.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/4b17c5ffaf7d5621092e4c58e6fb7d9bd712bd4054fd3848b171bbd1c0810d27/jansson-2.14-0.amzn2023.x86_64.rpm)                                         | `4b17c5ffaf7d5621092e4c58e6fb7d9bd712bd4054fd3848b171bbd1c0810d27` |
| [readline-8.1-2.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/be2fdf97635292954f3e72f4b9a0eb0c2ba0efa4909352801290dbd0b5758a8d/readline-8.1-2.amzn2023.0.2.x86_64.rpm)                                 | `be2fdf97635292954f3e72f4b9a0eb0c2ba0efa4909352801290dbd0b5758a8d` |
| [ncurses-libs-6.2-4.20200222.amzn2023.0.6.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/27a1b1af4e31ef737261336f59e27608e53800cd859a60ea9822bbda7572df16/ncurses-libs-6.2-4.20200222.amzn2023.0.6.x86_64.rpm)       | `27a1b1af4e31ef737261336f59e27608e53800cd859a60ea9822bbda7572df16` |
| [ncurses-base-6.2-4.20200222.amzn2023.0.6.noarch.rpm](https://cdn.amazonlinux.com/al2023/blobstore/cf22ad6a84e56f5172a4b28ead36c11274adf48a9b9f080fd4e5154444737ea0/ncurses-base-6.2-4.20200222.amzn2023.0.6.noarch.rpm)       | `cf22ad6a84e56f5172a4b28ead36c11274adf48a9b9f080fd4e5154444737ea0` |
| [iptables-libs-1.8.8-3.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/322786a8e3df9b8dde62b3543f1a932b44eed307917c154a42c97b50ee7c5553/iptables-libs-1.8.8-3.amzn2023.0.2.x86_64.rpm)                   | `322786a8e3df9b8dde62b3543f1a932b44eed307917c154a42c97b50ee7c5553` |
| [libnetfilter_conntrack-1.0.8-2.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/6f1f29d39be88e61943e8b20f37d7fa4a4514aa2476de3480118b881bcc70ccd/libnetfilter_conntrack-1.0.8-2.amzn2023.0.2.x86_64.rpm) | `6f1f29d39be88e61943e8b20f37d7fa4a4514aa2476de3480118b881bcc70ccd` |
| [libnfnetlink-1.0.1-19.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/cc984aa33225910676443523274eba0f4bd95808695113fe180919033d06c859/libnfnetlink-1.0.1-19.amzn2023.0.2.x86_64.rpm)                   | `cc984aa33225910676443523274eba0f4bd95808695113fe180919033d06c859` |
| [libpcap-1.10.7-1.amzn2023.0.1.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/68cbe995a044f4cc3f6874368a2e6d518d8e7a9abccfa9c9f6110eae44b7aa92/libpcap-1.10.7-1.amzn2023.0.1.x86_64.rpm)                             | `68cbe995a044f4cc3f6874368a2e6d518d8e7a9abccfa9c9f6110eae44b7aa92` |
| [libibverbs-48.0-1.amzn2023.0.1.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/70de30ec5cb05de1c61ae37436c77385ed3f0e9e1faa2c81ff158308739bce5b/libibverbs-48.0-1.amzn2023.0.1.x86_64.rpm)                           | `70de30ec5cb05de1c61ae37436c77385ed3f0e9e1faa2c81ff158308739bce5b` |
| [libnl3-3.5.0-6.amzn2023.0.2.x86_64.rpm](https://cdn.amazonlinux.com/al2023/blobstore/c1048cd31386ee70d3bc497bf140ef8e873b537ac115d3e671c6c6cf5af80a47/libnl3-3.5.0-6.amzn2023.0.2.x86_64.rpm)                                 | `c1048cd31386ee70d3bc497bf140ef8e873b537ac115d3e671c6c6cf5af80a47` |

The nftables RPM's metadata requires `/bin/sh`, `libgmp.so.10`,
`libjansson.so.4` including its `libjansson.so.4` symbol version, `libmnl.so.0`
including `LIBMNL_1.0`, `libnftnl.so.11` including `LIBNFTNL_11/13/14/15/16/17`,
`libreadline.so.8`, `libxtables.so.12`, GNU-hash loader support and
`libc.so.6(GLIBC_2.34)`. Metadata shows the transitive chains
`readline -> libtinfo (ncurses-libs)`,
`iptables-libs -> libnetfilter_conntrack + libpcap + libm`,
`libnetfilter_conntrack -> libnfnetlink + libmnl`,
`libpcap -> libibverbs`, and `libibverbs -> libnl3 -> libgcc_s`.
Existing retained-image glibc/libm/loader/libgcc may satisfy the base libraries;
verify them rather than replacing the image's libc. `ncurses-base` is a package
metadata dependency, not necessarily needed for a noninteractive extracted nft
binary. This list is a bounded package-candidate inventory, not proof of minimal
ELF DT_NEEDED closure or permission to use any package-manager resolver.

The upstream v1.0.4 documentation endpoint was blocked by its public Anubis bot
challenge during research, so no claim is made that the v1.0.4 source was read
successfully. The command shape uses longstanding add/flush/UID/IP constructs
documented by Netfilter; exact 1.0.4 parser/transaction acceptance remains a
required disposable execution check.

## Evidence still required

Local meaningful checks should cover separate component configuration parsers,
cross-UID private-file/env/proc reads, catalogue read-only access and persistence,
fixed-event/result sanitization including malicious/missing/oversized inputs,
helper fixed-command/timeout/error handling, absence of child stream leakage,
and the isolated packet proof above. Static unit verification must identify
which systemd version and any inert stub executable/account layout it uses.
Real native AL2023 systemd252 startup/stop/reboot/failure/capability/UID behavior,
persistent redacted local-log retrieval (and journal retrieval if claimed),
actual EC2 metadata restrictions, signed readiness, capacity,
provisioning/production lock, model qualification and all
existing cloud/account/cost/apply gates stay open until their own authorized
evidence exists. No change here authorizes deployment or replay of an Action
whose outcome is uncertain.
