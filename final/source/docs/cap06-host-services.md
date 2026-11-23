# CAP-06 host service bundle

Current23October revision: [host isolation](cap06-host-isolation.md) supersedes
the shared-UID/config/no-diagnostics statements and command paths below. Store
now uses `/etc/shopping-copilot/store/store.json`, proxy `.../proxy/proxy.json`,
Agent `.../agent/host.json`. Three separate application UIDs require a fourth
root metadata oneshot and use bounded private lifecycle logs. The remainder is
historical evidence for the earlier bundle; no unit/account/firewall is activated.

23 October 2026. This bundle is prepared and tested locally. No unit is installed
or enabled, no public listener was started, and no certificate, production key,
AWS resource, DNS or policy change was made. The provider remains unqualified.

The prepared entry points are:

```text
python -B -m deploy.host_component --config /etc/shopping-copilot/host.json --component store
python -B -m deploy.host_component --config /etc/shopping-copilot/host.json --component proxy
```

They use the [existing protected host settings](cap06-host-bootstrap.md) and must
execute from the exact verified production release. The module checks settings,
release, required files and component-specific state, runs a bounded version
check, then uses execve to replace Python with the fixed Node or Caddy executable.
There is no shell, downloader, arbitrary command/profile argument, cloud SDK
construction or provider call. Pre-exec errors print only
`Host component startup refused`. Native-process errors after exec are handled by
the service's standard-stream policy, rather than caught by the replaced Python.

| Component  | Executable and inputs                                                                                | Child environment                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Storefront | `/usr/bin/node RELEASE/store/src/server.js`, Node 24 >=24.13.0, existing catalogue checked read-only | Production mode, fixed public origins, lexical ranking, catalogue path and service secret    |
| Caddy      | `/usr/bin/caddy run --config RELEASE/deploy/Caddyfile.public --adapter caddyfile`, exactly 2.11.7    | Verified Panel root and fixed retained certificate-storage path; no service/readiness secret |

Both environments start empty except fixed PATH `/usr/bin:/bin` and LANG
`C.UTF-8`. Parent environment is not modified. Node injection, loader overrides,
proxies, evaluation flags, AWS credentials and inference configuration are not
copied into either child. Version checks use the same environment, a five-second
timeout and suppressed output; installed executable authenticity remains part of
trusted host provisioning.

Panel paths are normalized to forward slashes before Caddyfile interpolation.
Quotes, backslashes remaining in POSIX names, control characters and DEL are
refused before exec; ordinary spaces remain supported. This prevents a valid
filesystem path from being interpreted as Caddyfile syntax after handoff.

Caddy storage is fixed to `/var/lib/shopping-copilot/caddy`. It must already be an
owner-only rwx directory owned by the effective service UID, outside the release,
with protected nonsymlink ancestors. The launcher never creates or clears it.
Retain certificates and ACME account state across stop/start and code rollback.

## Unit ownership and availability

`shopping-copilot-host.target` Wants the Storefront, Agent and proxy units. Each is
PartOf the target; explicit target stop/restart propagates to its members. Only
the target is intended to be enabled later. Storefront launches before Agent,
then proxy. All members and the target conflict with, and are ordered after, the
legacy combined `shopping-copilot.service`; the legacy implementation is unchanged.
Members are not ordered after their own target, avoiding a dependency cycle.

Wants permits independent bounded failure restarts. A failed member does not
force siblings down, and an active target does not prove all members are healthy.
Type=exec observes initial Python execution; it does not wait for validation,
native exec, HTTP, certificates or model readiness. The existing signed readiness
flow remains authoritative, and its default provider verifier stays false. No
restart path replays an Action whose result is uncertain. See the
[primary-source contract](research/2026-10-23-cap06-host-services-contract.md).

All units use the existing copilot account, read-only release/config paths,
no-new-privileges, private temporary space, owner-only umask, bounded restart rate
and a 20 second stop deadline. Agent retains its 1 GiB ceiling; Storefront and proxy
each have 256 MiB ceilings and 64 tasks. These are ceilings, not measured capacity
or a host-memory allocation. Aggregate workload, shutdown timing and instance
sizing still require host acceptance. Storefront and Agent have empty capability
bounds; Caddy alone has ambient/bounding CAP_NET_BIND_SERVICE and can write only
its retained storage directory. Authentic ordinary executable provisioning and
actual ambient-capability inheritance through Python to Caddy remain to be
demonstrated. Standard streams are discarded as in the earlier unit. Redacted
durable host diagnostics and capacity remain open acceptance items.

## Local evidence and remaining checks

The generated Storefront environment was exercised against a fresh packaged
production Storefront on loopback twice. Test-reset routes returned 404; private
catalogue reads required the service secret; catalogue history remained unchanged.
The Windows test harness selects the installed Node binary and adds SYSTEMROOT;
this does not establish actual `/usr/bin/node` or POSIX exec execution. Agent and
Caddy were not started by that check.

Pinned Caddy 2.11.7 adaptation tests passed. They parse only: no run/start/reload,
validate/module provisioning, certificate issuance, storage creation or listener.

Ubuntu/WSL systemd 255 static verification accepted all five unit files with no
errors, using a disposable root with inert target/interpreter/directory stubs and
generators/man execution disabled. No service was run. AL2023's systemd 252 target
behavior, actual stop/restart, capabilities and runtime permissions remain open.

Eleven actual Linux filesystem checks passed for the exact source-extracted
private-file/storage functions: owner-only files/storage accepted; group-readable,
oversize, symlink, multiple-hardlink, FIFO, public-storage and unsafe-ancestor cases
refused. This is primitive-level Ubuntu evidence, not full HostSettings loading,
real keys, service UID provisioning or eventual target-host acceptance.

Evidence: `eval/evidence/cap06-host-services-20261023.json`. Ignored local logs use
`outputs/cap06-host-services-*`. Remaining gates include target-host/config/key/
capability checks, observability/capacity, public DNS/TLS and trusted origins,
effective IAM/OAC/event/account access, observation inventory/cost reconciliation,
Bedrock quota and qualification, separate resource/cost/rollback apply approval,
deployment and cloud acceptance. No gate or spending cap is waived.

Final post-fix regression: 1,107 passed with no skips, including fresh release
packaging and browser recovery, with two upstream websockets deprecation warnings.
Independent review ran 78 focused tests before the path fix. The primary verified
that finding with eight RED/GREEN cases, the final full suite and real Caddy
adaptation of a path containing spaces. No deferred review findings remain.
