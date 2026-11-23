# CAP-06 prepared host isolation and lifecycle diagnostics

23 October 2026. Local implementation and disposable Linux proof only; no AWS
login/API/model, real credentials, users, host firewall, unit installation or
activation, DNS/public TLS or new spending authority. Free/Stockholm/USD0cash
and existing qualification/authority/rollback gates persist. The additional
oneshot is local host software, not another AWS service.

## Provisioning and custody

| Consumer   | Proposed user/group                              | Private config                         | Writable state                  |
| ---------- | ------------------------------------------------ | -------------------------------------- | ------------------------------- |
| Agent      | copilot/copilot; supplementary copilot-catalogue | /etc/shopping-copilot/agent/host.json  | /var/lib/shopping-copilot/agent |
| Storefront | copilot-store/copilot-store                      | /etc/shopping-copilot/store/store.json | /var/lib/shopping-copilot/store |
| Proxy      | copilot-proxy/copilot-proxy                      | /etc/shopping-copilot/proxy/proxy.json | /var/lib/shopping-copilot/caddy |
| Metadata   | trusted root                                     | /etc/shopping-copilot/metadata.json    | Own kernel nft table/chain      |

Dedicated no-login accounts are not created by this code. Root must own immutable
release/interpreter/executables and protected config ancestors. Private JSON/raw
keys use consuming UID ownership and0400/0600; root0600 is unreadable to ordinary
services. Root-owned0755 component config directories with private files satisfy
the reader. Do not use another service's private directory as an ancestor. Moved
private-reader checks are unchanged: links, unsafe ancestors and group/other file
access remain refused. Real provisioning/secret custody still needs verification.

Agent retains full HostSettings and existing disabled-ledger/history validation.
Store schema1 accepts exactly version/release/fingerprint/catalogue/
service_secret_file; proxy accepts version/release/fingerprint. Both require
production release/origins/fingerprint. Full Agent settings/extra fields are
refused by native component launchers. Store reads only its config/service-key
copy and catalogue; proxy reads no application key or catalogue.

Service-secret bytes are intentionally duplicated into distinct owner-only
Agent/Store files under their respective config directories. Readiness key and
ledger remain Agent-only; proxy certificate state proxy-only. Never reinitialize
allowance, invitation/lifecycle identities or uncertain reservations during the
split, deploy, rollback or host replacement. No real migration ran here.

Catalogue directory: Store-owned, group copilot-catalogue, setgid2750; database0640
with that group. Store umask0027 preserves group-readable WAL/SHM. Agent gets the
catalogue supplementary group and a read-only mount of Store state, with no
database write or sidecar creation. Store has no Agent-group membership. Each
application writes only its state/logs; PrivateTmp, ProtectProc=invisible,
RestrictNamespaces, RestrictSUIDSGID, NoNewPrivileges and existing limits remain.
Only Caddy retains CAP_NET_BIND_SERVICE.

Live WAL and two native Node Storefront restarts passed with Agent reads under a
different UID and denied writes/signals. With Store closed and WAL/SHM removed,
Agent fails closed; no immutable=1 or write workaround. Store startup prepares
sidecars. Unit After ordering observes initial exec, not HTTP readiness; signed
readiness must refuse/recover while Store is unavailable.

## Metadata barrier

Standard-library-only deploy.host_metadata requires root, exact schema1 fields
version/release/fingerprint/agent_uid and nonzero UID matching pwd's copilot.
It verifies protected root inputs and executing production release before one
fixed `/usr/sbin/nft --file -` call, clean PATH/LANG, timeout5, no retry, suppressed
streams and fixed errors. Native approved nft installation remains required;
extracted test tools are not a production package lock.

Its fixed inet scpilot_metadata/output batch allows trusted root/Agent UID and
rejects169.254.169.254 and fd00:ec2::254 for other UIDs. It flushes only its own
chain. Repeated application replaces rules without duplicates; kernel handles
may change. Invalid batch leaves the previous policy intact. Other tables remain.
EC2 metadata IPv6 remains disabled in the proposal; testing the extra IPv6 rule
does not activate it in AWS.

shopping-copilot-metadata.service is root/NET_ADMIN-only, AF_NETLINK, oneshot,
RemainAfterExit and PartOf the host target. Applications Requires/BindsTo/After
it. Failure prevents their startup; stopping it stops applications but leaves
rules installed. No ExecStop removes protection. Restarting the barrier alone
does not automatically restart applications. Root is trusted: changing UIDs needs
verified rebind; root deletion of rules is not detected by oneshot state. Actual
systemd252 boot/failure/reboot behavior remains unverified.

## Private lifecycle diagnostics

Application ExecStartPre/ExecStopPost invoke deploy.host_diagnostics with fixed
service agent/store/proxy and event starting/stopped. LogsDirectory creates0700
`/var/log/shopping-copilot/SERVICE`. Records contain integer time, service, event
and outcome: null for starting, success only for exact SERVICE_RESULT=success,
otherwise failed. No CLI path override/free message, raw environment/error,
request, child stdout/stderr or key is recorded. Process lifecycle is separate
from readiness; manager/dependency failures before hooks may leave no record.

Descriptor traversal refuses unsafe/symlink ancestors and wrong owner/mode.
Only lifecycle.jsonl and two numbered backups are managed, <=64KiB each; seven-day
pruning happens on write. Directory flock acquisition is bounded to one second.
Regular single-link private files use no-follow/nonblocking I/O and bounded size.
File/directory fsync complete before success. Foreign, linked, FIFO, oversized or
insecure files refuse startup. Short-write/full-disk/sync/rotation failures
propagate and failed pre-start logging prevents launch. An I/O failure cannot
guarantee its own record. Logs are not tamper-proof against their UID; local Linux
only, not NFS. Production disk-headroom/reboot retrieval remain gates.

## Agent event records

The Agent also records structured events (requests, Shopping Task steps, model
calls, errors) in the same private folder, as `events.jsonl` and two numbered
backups of about 1.7 MB each. They use the same append step as the lifecycle
records above (descriptor traversal, link and owner checks, directory flock,
seven-day pruning on write), with two differences: records are queued and written
by one background thread so a slow disk cannot slow a request, and event records
skip fsync (best effort; a crash can lose the last few). A full queue or failed
write is counted, never raised. Ordinary records accept only allow-listed ids,
numbers and fixed values, so they never contain Shopper text, model output,
error text or an invitation code; errors are recorded by type and code location.

**Debug switch.** While root-owned `/etc/shopping-copilot/debug-logging` was
touched less than 60 minutes ago (and not in the future), the Agent also writes
debug records containing the Shopper's message, model output and full error
text. The Agent can read `/etc/shopping-copilot` but never write it, so only the
owner can turn this on (`sudo touch` over SSH); the marker must be a single-link
regular file not writable by group or others, in a folder with the same rule.
Debug records are marked `"debug": true`, go only to this host file (never to a
terminal or off the host), and are capped at 8000 characters each.

**Shipping to CloudWatch.** A background thread in the Agent sends new complete,
non-debug lines from these files to the CloudWatch Logs group
`/scpilot/agent-events` (stream `agent-<release>`) every 15 seconds, using a
host-owned client pinned to eu-north-1 with one attempt per call. It reads the
files and writes its checkpoint (`/var/lib/shopping-copilot/agent/log-shipper.json`)
through descriptors with the same checks as above. The checkpoint records the
file's identity (device, file number, first line), offset and the last shipped
record's time, so a restart resumes without gaps and a rotated or pruned file is
never sent twice; delivery is at-least-once (a crash between sending a batch and
saving the checkpoint can repeat that batch). Records CloudWatch would refuse
(older than 13 days, more than 90 minutes ahead, oversized, or a batch it rejects)
are counted and skipped so they cannot block later records; unreachable or
throttled calls retry on the next interval and lose nothing. The log group, its
30-day retention and the host role's permission to write it are created
separately (owner-approved AWS change).

**Storefront event records.** The Storefront keeps its own `events.jsonl` (and two
numbered backups) in `/var/log/shopping-copilot/store`. Each cart change is one
record naming its type (add, quantity, remove, undo, clear, checkout), outcome and
status; server errors are recorded by type and route template (a Shopper's
malformed request is not an error record). Records never carry a product, size,
colour, quantity, payment field or error message: values outside the fixed lists
are dropped. Records are queued (bounded) and written by one async loop, so a slow
disk never holds up a request. Before each write the folder must be owned by the
Storefront and closed to others, and every managed file must be a single-link
regular file (never a link) owned by the Storefront and unreadable by others;
files older than seven days are pruned. A full queue or failed write is counted,
never raised. These records stay on the host: the
Storefront has no AWS credentials and nothing ships them. The release id reaches
the Storefront as `COPILOT_RELEASE`; locally records print to the terminal.

## Disposable evidence and limits

Evidence: eval/evidence/cap06-host-isolation-20261023.json. Tracked probes:
eval/linux_host_probe.py and eval/linux_host_isolation_probe.py. Ignored inputs/
outputs: .scratch/cap06-host-isolation and outputs/cap06-host-isolation-\*.
Fresh production artifact uses fixed public origins; existing bounded portable
fixture conversion retains193 internal pnpm links and upstream/derived digests.
This is Windows-built diagnostic material, not an approved native Linux release.

Retained AL2023/Python3.12.15/glibc2.34 image, Node24.13.0, Caddy2.11.7 and29checked
diagnostic wheels are unchanged. Non-root native run uses only offline wheels in
tmpfs: full default HostSettings,13 refusals, six native imports, Node exec/auth/
restart/persistence, Agent early refusal and Caddy adapt/captured handoff pass.
No SDK/provider construction or public Caddy run/ACME occurred.

Separate root-bootstrap container: network none/read-only root/no-new-privileges,
1CPU/1GiB/64pids/512MiB disposable workspace; read-only test inputs/binaries/tools.
Bootstrap CHOWN/FOWNER/FSETID/DAC_OVERRIDE/SETUID/SETGID/KILL/NET_ADMIN apply only to
synthetic ownership/UID children, cleanup and its own namespace. Children have
zero effective capabilities. No host home, credentials, checkout, Docker socket
or host network is mounted. IPv6 sysctls affect only this namespace; only loopback
exists. Real cross-UID key/state/environment/signal denials pass.

Fourteen official AL2023 RPMs (2,986,331bytes) were checked against cited official
HTTPS/repository SHA256 metadata and extracted using Windows tar without install
or scriptlets. No RPM signature verification or production security approval is
claimed. Real nftables1.0.4 IPv4/IPv6 fake-endpoint packets allow root/Agent, refuse
Store/proxy/unrelated UID, preserve ordinary loopback, repeated-policy semantics,
invalid-batch atomicity and sentinel table. No actual IMDS/account request.
[Primary contract/provenance](research/2026-10-23-cap06-host-isolation-contract.md).

Six-unit static validation uses Ubuntu/WSL systemd255.4 with inert interpreter/
target/directory stubs; no service starts. It does not prove AL2023 systemd252
enforcement, boot/reboot, native provisioning/lock, Caddy ambient inheritance,
EC2 metadata, full Agent lifespan/signed readiness, public TLS or capacity. Model
quota/strict qualification, account/credits/cost facts and exact resource/cost/
rollback approval stay open. All uncertain-outcome and spending fences persist.
