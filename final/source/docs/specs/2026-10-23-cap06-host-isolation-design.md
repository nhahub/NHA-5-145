# CAP-06 host isolation and lifecycle diagnostics

Continue the approved inactive Linux-host preparation in the existing isolated
worktree. No AWS/account/model calls, production keys/state, system installs,
unit activation, host firewall changes, DNS/public TLS, extra spend or push.
Public test-tool acquisition and bounded disposable offline Linux tests are
permitted preparation; all account/model/cloud gates remain open.

## Service and configuration boundaries

Keep Agent UID/group `copilot`; Storefront becomes `copilot-store`, Caddy becomes
`copilot-proxy`, each without login. This is a builder implementation choice, not
actual account provisioning. Agent keeps full HostSettings at
`/etc/shopping-copilot/agent/host.json`; store/proxy receive minimal separately
owned configs under matching `store/` and `proxy/` directories. All config/private
ancestors retain the current protected POSIX checks; do not relax modes/ownership.

New `deploy.component_config` frozen StoreSettings and ProxySettings validate a
production release/fingerprint and outside-release distinct config/state files.
Store schema1 JSON exact fields: version, release, fingerprint, catalogue,
service_secret_file. Proxy schema1 exact fields: version, release, fingerprint.
No Agent config, inference/authority/readiness key or arbitrary fields accepted.
`load_component_settings(path, component, *, read_private=...)` uses the same
default protected reader, duplicates/size checks, generic redacted refusal and
strict component selection. Store reads only its service-secret copy and catalogue;
proxy reads no application secret or catalogue. `host_component.command` accepts
the matching new settings type only; no legacy full HostSettings fallback. Fixed
native executable/version/environment/exec behavior persists.

Move existing stdlib private-file/parent/duplicate-JSON helpers into
`deploy.host_files`, re-export through host_config for compatibility. Add shared
production-release/fingerprint validation there without third-party imports so
the privileged metadata helper never imports the SDK/application graph.

Agent writes only `/var/lib/shopping-copilot/agent`; Store writes only
`/var/lib/shopping-copilot/store`; Caddy only existing `.../caddy`. Catalogue is
store-owned0640 in store-owned/setgid2750 directory, group `copilot-catalogue`.
Agent has that supplementary group and a read-only mount of store state; it needs
read-only catalogue/WAL access for the existing checks. No Store membership of
Agent group. Service-secret bytes are purposefully duplicated into distinct
owner-only files for Agent/Store; readiness/ledger are Agent-only. Caddy cert state
is proxy-only. Root owns immutable code/interpreter and protected config parents;
private files are readable by actual consuming UID. Do not migrate or initialize
real state automatically. Shared catalogue group is not a secret/ledger group.

Units require separate UIDs, ProtectProc=invisible, RestrictNamespaces=yes and
RestrictSUIDSGID=yes. Existing no-new-privileges/capability/cgroup/restart/origin/
model gates remain. Only Caddy retains CAP_NET_BIND_SERVICE. Linux DAC tests must
actually switch UIDs and prove allowed catalogue/service-secret reads and denied
cross-service private files, writes and signal access, not only parse unit text.

## Metadata barrier

New stdlib-only `deploy.host_metadata.render_metadata(agent_uid)` returns an
nftables1.0.4-compatible atomic batch for its own fixed inet table/output chain.
Reject IPv4 169.254.169.254 and IPv6 fd00:ec2::254 except root and the exact
nonzero Agent UID. Do not flush any other table/chain, enable proxying or accept
hostnames/arbitrary rules. Repeated application replaces only that owned chain.

Root CLI `python -B -m deploy.host_metadata --config ABSOLUTE_PATH` reads exact
schema1 JSON fields version/release/fingerprint/agent_uid through protected root
reader, verifies executing production release, requires root and UID equality to
`pwd.getpwnam('copilot')`, then invokes fixed `/usr/sbin/nft --file -` once with
the rendered stdin, clean PATH/LANG, five-second timeout and suppressed streams.
Generic errors only; no table/rule write merely by import/render/validation.

New root-only oneshot `shopping-copilot-metadata.service` has NET_ADMIN only,
RemainAfterExit and no removal on stop. Each application service BindsTo/After
it; firewall failure prevents start, stopping the barrier stops applications and
does not remove protection. No live apply or service installation is performed.
Root is deliberately trusted for administration/boot; this is not root-compromise
containment. Account UID changes require re-provisioned verified binding first.

Require a private network-namespace test, if test tools are available/acquired:
fake metadata bound only inside that namespace, real nft batch, three actual
UIDs, root/Agent allowed and Store/proxy refused; repeat rules without duplication.
Never contact actual IMDS/AWS, mutate the host namespace or claim reboot/systemd/
EC2 acceptance from a container. If the test environment cannot support this,
retain the gap explicitly rather than claim the barrier effective.

## Durable safe diagnostics

New stdlib `deploy.host_diagnostics` CLI accepts only service agent/store/proxy
and event starting/stopped. Fixed per-service log directory
`/var/log/shopping-copilot/SERVICE`, pre-provisioned owner0700 by LogsDirectory.
It verifies nonsymlink protected ancestors, owned directory and private regular
single-link files using descriptor/no-follow/nonblocking I/O. Refuse symlink,
hardlink, FIFO, insecure ownership/modes, full disk or failed bounded rotation.

Write JSON lines with integer time, fixed service/event and bounded outcome only;
starting has outcome none, stopped derives success/failed from exact trusted
SERVICE_RESULT=success, unknown/missing results map to failed. No arbitrary
environment value, child output, code, key, URI, request, exception or path enters
the record. Maximum64KiB per file, two backups, seven-day pruning on each write;
only the three fixed filenames are managed. No automatic creation of private
state or directory scan deletion. Bound writers by an advisory lock and file
checks; a second CLI call must not interleave rotation/write unsafely.

Each unit ExecStartPre records starting, failure prevents application launch;
ExecStopPost records stopped/failed even after native exec or abnormal exit.
Streams remain null. LogsDirectory/private mode and per-service write path only.
These are process lifecycle diagnostics, not HTTP/TLS/model readiness or continuous
health metrics. Disk failure cannot guarantee a record, but must not launch an
unobservable service. Existing legacy Diagnostics/supervisor remains unchanged.

## Verification and handoff

TDD strict config/role/refusal and CLI boundaries; fixed privileged invocation,
no third-party import and bad root/UID/release refusal; descriptor-safe bounded
logger/events/redaction/retention/concurrency. Unit dependency/user/path checks
and fresh release packaging, actual native Storefront restart/auth/catalogue tests.
Linux default-reader/multi-UID DAC and logger tests, real isolated firewall proof
where feasible. Update the previous Linux probe for new component configs without
weakening its upstream/derived-artifact distinction. All affected Agent/action/
admission/lifecycle/recovery regressions, relevant format/lint/test/build, fresh
whole-slice review and local commit. No cloud/model or production readiness claim.
