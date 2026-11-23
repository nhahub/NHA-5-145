# CAP-06 host services contract: offline preparation

Researched 23 October 2026 against official documentation and existing repository
sources. This is a design contract, not target-host acceptance. No services,
Docker containers, AWS APIs, credentials, certificates or model calls were used.
No topology, service inventory, cost or deployment authorization changes follow
from this note.

## Target platform and dependency semantics

AWS's 14 October 2026 AL2023 advisory lists systemd
`252.23-15.amzn2023` for x86_64. Use the versioned systemd 252 manuals when
preparing units; verify the actual selected host package/version later rather
than inferring it from an AL2023 image label.
[AWS AL2023 advisory](https://alas.aws.amazon.com/AL2023/ALAS2023-2026-3224.html)

| Setting on A referring to B | Contract                                                                                                                                                      |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Wants=B`                   | Starting A pulls B in; B's startup failure does not fail A.                                                                                                   |
| `Requires=B`                | Pulls B in. With `After=B`, B's activation failure prevents A's start. Explicit stop/restart of B propagates to A. It is not continuous liveness enforcement. |
| `After=B`                   | Orders jobs only; pulls nothing in. Joint shutdown reverses startup order.                                                                                    |
| `PartOf=B`                  | B's stop/restart propagates to A, one way. Does not pull B in or start A when B starts.                                                                       |
| `Conflicts=B`               | Starting either stops the other. Add `Before=` or `After=` for stop-before-start ordering.                                                                    |

Conditions can skip required units; spontaneous deactivation need not propagate
through `Requires=`. `BindsTo=` plus `After=` is stronger, but would be a separate
lifecycle policy choice. `WantedBy=` belongs in `[Install]` and creates dependency
symlinks on enable; it does not itself activate anything.
[systemd 252 unit dependencies](https://www.freedesktop.org/software/systemd/man/252/systemd.unit.html)

## Application to the existing three processes

Design inference: give the bundle target explicit membership and give each member
`PartOf=` the bundle. Put ordering between services: Storefront before Agent,
Agent before Caddy. Put legacy-unit conflict **and ordering** on each service
whose direct activation could overlap the combined runtime; a target-only
conflict does not protect independent member activation. Existing units and
fixed ports are recorded in
[host launcher](../cap06-host-launcher.md),
[Agent unit](../../deploy/shopping-copilot-agent.service), and
[legacy runtime](../../deploy/runtime.py).

Choose membership deliberately: target `Wants=` permits partial process startup;
target `Requires=` makes member activation/explicit-stop dependencies stronger.
Neither means the target is healthy. `PartOf=` supplies target stop/restart
propagation in either design. Do not silently add continuously enforced upstream
dependencies or promise automatic whole-bundle recovery after any member crash.
Those are policy decisions requiring runtime tests.

Targets automatically order themselves after their configured wanted/required
members with default dependencies. Do not add `After=bundle.target` to those
members: that can create an ordering cycle. Targets are grouping/synchronization
units, not health monitors.
[systemd 252 targets](https://www.freedesktop.org/software/systemd/man/252/systemd.target.html)

`Type=simple` is started after fork; `Type=exec` waits for the initial executable
to execute. When that executable is Python, neither type waits for Python's
validation, its subsequent Node/Caddy exec, a bound listener, signed Agent
readiness or provider qualification. `Restart=on-failure` is per service, is
subject to start limits, and does not undo an intentional systemd stop. These
mechanisms cannot replay or authorize an uncertain Action.
[systemd 252 services](https://www.freedesktop.org/software/systemd/man/252/systemd.service.html)

## Native process replacement and environment

Python `os.execve(path, argv, env)` replaces the Unix process and preserves its
PID; success never returns. It does not search PATH, and the supplied environment
replaces the current one. Exec errors raise `OSError`; buffered output is not
automatically flushed.
[Python 3.12 exec functions](https://docs.python.org/3.12/library/os.html#os.execve)

Design inference: validate the existing protected host configuration/release
first, select fixed absolute installed Node/Caddy paths, set the verified release
working directory, and exec an exact argument vector with a newly constructed
role-specific environment. Do not use a shell, PATH lookup, arbitrary command
field, ambient `os.environ` merge or a persistent Python subprocess supervisor.
Do not forward Agent/service secrets to Caddy. A copied clean environment must
also exclude ambient `NODE_OPTIONS`, loader injection and proxy settings. Exact
executable installation and its provenance remain host acceptance requirements;
this note does not assert that a proposed path exists.

For a later authorized bundle stop, retain `KillMode=control-group` and bounded
shutdown. systemd initially sends SIGTERM and can escalate after
`TimeoutStopSec`; ordering therefore does not guarantee graceful cleanup finishes
before the deadline. Test actual child cleanup and timeout outcomes.
[systemd 252 process termination](https://www.freedesktop.org/software/systemd/man/252/systemd.kill.html)

## Caddy invocation, storage and privileges

The service process should exec Caddy's foreground `run` command with explicit
`--config ABSOLUTE_RELEASE_PATH/deploy/Caddyfile.public --adapter caddyfile`.
Avoid background `start`, ambient Caddyfile discovery, `--environ`, `--envfile`,
`--resume` and `--watch`. For offline checks use only `adapt --config ...
--adapter caddyfile`, without `--validate`. Adaptation converts configuration;
validation loads and provisions modules, making it a stronger and different
operation. SIGTERM requests graceful Caddy shutdown. Current documentation says
startup exit code 1 should not be automatically retried unchanged; decide any
`RestartPreventExitStatus=1` policy explicitly.
[Caddy CLI](https://caddyserver.com/docs/command-line)

The current public profile consumes only `COPILOT_PANEL_ROOT` and
`COPILOT_CADDY_STORAGE`. Caddyfile `{$ENV}` substitution happens before parsing
and can introduce multiple tokens/lines. Trusted input still needs bounded,
absolute path validation and rejection of control/config-injection characters;
quoting alone is not a validator.
[Caddyfile environment substitution](https://caddyserver.com/docs/caddyfile/concepts#environment-variables),
[public profile](../../deploy/Caddyfile.public)

TLS storage contains keys, certificates and other durable state and must remain
persistent and writable. Caddy's normal data/config defaults derive from HOME or
XDG variables; use explicit trusted locations outside immutable releases.
[Caddy file locations](https://caddyserver.com/docs/conventions#file-locations)

The existing profile already selects `storage file_system` explicitly and turns
off admin and config persistence. Keep those decisions; `persist_config off`
disables active-config autosaving, **not** TLS storage. Do not substitute the
evaluation certificate profile or create a new admin/reload interface.
[Caddy global options](https://caddyserver.com/docs/caddyfile/options#storage),
[prepared public profile](../../deploy/Caddyfile.public)

With default Linux privileged-port policy, non-root Caddy binding 80/443 needs
`CAP_NET_BIND_SERVICE`; the per-network-namespace threshold defaults to 1024.
Do not change that sysctl to make a test pass.
[Linux kernel IP sysctls](https://docs.kernel.org/networking/ip-sysctl.html#ip-unprivileged-port-start)

Use only that capability in the Caddy unit's bounding and ambient sets. Ambient
capabilities survive exec of an ordinary unprivileged executable; setuid/setgid
or file-capability executables clear the ambient set. Verify the installed Python
and Caddy chain rather than adding file capabilities as an assumed workaround.
[Linux capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)

`NoNewPrivileges=yes` prevents gaining privileges through later exec. Ambient
capabilities are the documented mechanism for non-root service capabilities.
`ProtectSystem=strict` makes the hierarchy read-only; narrow `ReadWritePaths=`
exceptions permit intended state writes but do not grant ordinary Unix file
permissions or override a read-only underlying filesystem. Leave release/config
read-only; allow only required external Caddy state/log paths. Directories must
already be provisioned appropriately unless using explicit directory-management
settings. `StateDirectory=` can recursively change ownership when existing owners
differ; do not apply it to an undifferentiated shared state tree. Sandboxing may
be unavailable in some container environments.
[systemd 252 execution environment](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html)

Starting the public profile is a network/certificate operation: public automatic
HTTPS needs appropriate DNS, externally reachable ports, bind permission and
persistent writable storage. Plain adaptation proves none of issuance, renewal,
browser trust or public reachability. Do not use public `run`, `start`, `reload`,
`validate` or `adapt --validate` as an offline unit test.
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[existing offline restriction](../../deploy/README.md)

## Evidence boundary and later acceptance

`systemd-analyze verify FILE...` loads specified and referenced units and checks
items including unknown directives, missing required dependencies and missing or
non-executable command paths. Its unit search path includes the supplied files'
directories and the normal host paths; `--root=` can check a prepared root tree.
An intentional fixture/stub can support an offline parser check only if recorded
as such. It cannot prove the actual installed commands, accounts or sandbox work.
[systemd 252 verification](https://www.freedesktop.org/software/systemd/man/252/systemd-analyze.html#systemd-analyze%20verify%20FILE%E2%80%A6)

Static parsing, mocked exec arguments and Caddy adaptation are preparation
evidence. Later authorized AL2023 acceptance must exercise actual PID 1 systemd,
protected files and exact installed release; direct member starts and legacy
switching; bundle start/stop/restart; startup failure, crash/rate-limit and signal
paths; capabilities and storage permissions; signed readiness and qualification;
public HTTPS/renewal and safe recovery without Action replay. A Lambda AL2023
import container or a non-systemd container cannot close that host acceptance.
