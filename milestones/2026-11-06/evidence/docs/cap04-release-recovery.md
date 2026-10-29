# Built releases, catalogue recovery and safe restart

CAP-04 local ticket 06 rehearses installation and recovery without AWS or paid
inference. The owner-only tools live in `deploy/`; there are no HTTP administration
routes. This is preparation for the selected Linux host, not deployed acceptance.

## State and release layout

| Location                                   | Contents and authority                                                                                                                                                                   |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/opt/shopping-copilot/releases/<version>` | Built Storefront JavaScript, production Node dependencies, Panel/Bridge assets, Agent source, pinned lockfiles, runtime tools and content manifest. Root-owned and read-only to runtime. |
| `/opt/shopping-copilot/current`            | Owner-selected installed release. Change only while the service is stopped.                                                                                                              |
| `/opt/shopping-copilot/python`             | Pinned Python 3.12 environment installed from the release lockfile. Not writable by runtime.                                                                                             |
| `/etc/shopping-copilot/runtime.env`        | Restricted server configuration, provider/service secrets and database identities. Never part of a release, URL, argument value or Git commit.                                           |
| `/var/lib/shopping-copilot`                | Live catalogue, inference ledger and admission storage. Never moved backward on code rollback.                                                                                           |
| `/var/log/shopping-copilot`                | Bounded application diagnostics; no access log, request text, raw child output or provider responses.                                                                                    |
| Separate restricted backup location        | Verified catalogue copies only. An old allowance/admission file is never restored to regain quota.                                                                                       |

Keep the runtime account separate from the owner/build account. The supplied
`deploy/shopping-copilot.service` uses `User=copilot`, `ProtectSystem=strict`,
read-only code/configuration, two explicit writable state/log locations, private
temporary storage, no privilege escalation, bounded tasks/memory/open files and
control-group shutdown. It is a template; no account or system service is installed
by these tools. Host directory ownership, interpreter installation, Caddy service,
TLS and Linux service-manager verification remain deployment work.

## Build and install

Use the pinned Node 24/Python 3.12/pnpm 11.19.0 toolchain with the existing frozen
dependencies installed. The builder uses the offline pnpm store and never falls
back to downloading packages. Its internal build commands disable pnpm's automatic
dependency repair; missing installed build tools or offline packages fail the build.
Build on the target operating system: Windows artifacts are not Linux packages.
Python dependencies remain in a separate pinned environment; they are not bundled.

Set only the approved public origins in the build environment. Do not supply
secrets as CLI arguments. From the source checkout:

```text
python -m deploy build --output <new-artifact-directory>
python -m deploy verify --release <artifact-directory>
python -m deploy install --release <artifact-directory> --output <new-installed-release-directory>
```

For disposable loopback rehearsal only, `build`, `check` and `run` accept
`--local-rehearsal`. That build hardcodes the existing localhost ports and refuses
real providers at startup. It serves built Panel files without Vite. Production
builds require explicit public HTTPS origins and use Caddy for Panel delivery.

The artifact is an allowlisted copy: no `.env`, work directory, test suite or live
SQLite files. Node production dependencies are copied from the pinned offline
installation; checkout links are removed and external links refused. Storefront
and shared modules are emitted JavaScript; no `tsx`, watcher or reloader is used
at runtime. The manifest records file/link hashes, schema compatibility, base Git
commit and whether the source was dirty. Use a clean reviewed commit for a published
release. Hashes detect modification; this is not a signature or a claim that an
untrusted manifest authenticates itself.

Verification rejects Python bytecode/cache files, including files added after
installation. Use `python -B` for every command run from an installed release;
disabling cache writing alone does not prevent Python loading existing bytecode.

Build/install output must be new. Partial work remains in disposable staging and
never becomes the selected release. Existing destinations are not replaced.
Installation preserves internal directory-link semantics on the build platform.

## Preflight, startup and shutdown

Configuration includes the existing production origin/service-secret settings,
absolute `COPILOT_CATALOGUE_DB`, and complete admission/inference settings from the
[admission guide](cap04-invited-access.md) and [allowance guide](cap04-inference-allowance.md).
Keep all three existing databases and their identities external, even in a
scripted rehearsal. Configuration is parsed without interpolation or provider
calls. On Linux it must deny other-account access and group writes; use owner-only
0600 or root/service-group 0640. Apply equivalent restricted ACLs on Windows tests.

```text
python -B -m deploy check --release <installed-release> --config <external-runtime.env>
python -B -m deploy run --release <installed-release> --config <external-runtime.env> --logs <external-log-directory>
```

Preflight checks the manifest, runtime mode/origins, catalogue schema/integrity,
existing allowance/admission identities and a real state-directory write/fsync.
It requires 64 MiB free headroom; the `check --minimum-free-bytes` option permits a
stricter owner check. No operation silently initializes missing databases. Config,
catalogue, allowance and admission must be distinct existing files outside the
release. Schema incompatibility blocks both release and rollback.

One supervisor owns one Storefront process and one Agent worker on loopback. Local
rehearsal also owns the built-Panel server. It refuses occupied ports instead of
resetting another service, waits for bounded health/readiness, checks child exits,
and checks storage while running. An unhealthy runtime stops its owned services.
Application health requests do not invoke a model or create Shopper activity.
On Linux use the unit's control group; Windows rehearsal stops only each exact
owned process tree and waits for socket closure. Do not launch the supervisor
through an unmanaged background shell whose children cannot be stopped.
Abrupt external termination of a Windows venv launcher is not qualified; the
eventual Linux service manager must enforce the supplied control-group shutdown.

The Python public API supports owner-held `restart("agent")` or `restart("store")`
for the disposable acceptance fixture; no restart endpoint is exposed to browsers.

## Catalogue backup and restore

```text
python -m deploy backup --catalogue <live-catalogue.sqlite> --output <new-backup.sqlite>
python -m deploy restore --catalogue <verified-backup.sqlite> --output <new-restored-copy.sqlite>
```

The online SQLite backup API observes one consistent read transaction, including
committed WAL data. Integrity, schema, revision and all catalogue table contents
are checked on both sides. Output reports only revision/schema/content digest.
Existing destinations and allowance/admission databases refuse. Failed copies
remove only the new file created by that operation. Never use filesystem copying
of an active SQLite file as a backup procedure.

Restore into a new disposable copy, review it, then stop services before any
separately authorized live catalogue replacement. Keep the old catalogue for
recovery. These tools deliberately provide no in-place database replacement and
no inference/admission restore command.

## Release and rollback procedure

1. Preserve current catalogue/configuration, allowance and admission paths/identities.
2. Create and verify a consistent catalogue backup. Check the new release against
   the live external state before maintenance; incompatibility means stop here.
3. Stop the supervisor through its service manager and confirm its process group
   and loopback sockets are gone. Do not terminate unrelated processes.
4. Select the new installed directory, retaining the previous code directory.
   Keep all mutable paths unchanged and start exactly one supervisor.
5. Check readiness, linking, admission and the visible cart-reset explanation.
   This full-host release restart resets in-memory Storefront shopping state.
6. On rollback, stop again, check the previous code against the **current** state,
   select that installed directory and restart. Never select a previous ledger or
   invitation backup. Uncertain costs remain reserved; code selection cannot
   replenish allowance or redemptions.

Agent-only restart invalidates Agent tasks/leases while retaining a surviving
Storefront cart. Storefront-only restart discards cart/orders/Confirmation/Undo and
invalidates its old browser binding. Fresh linking/admission is required; fixed
invitation windows and cumulative quotas do not restart. A still-live Storefront
Undo is not invalidated merely because the Agent restarts. Old ActionResults and
Confirmation answers cannot act through the new Agent session. Recovery never
replays an uncertain cart Mutation.

## Diagnostics, disk failure and teardown

Application diagnostics accept only fixed event/service names, rotate at 64 KiB
with two backups, and remove files older than seven days when opened. Raw child
stdout/stderr are discarded, so secrets, invitation input, shopper text and stack
traces cannot leak through those streams. This deliberately limits diagnosis to
safe lifecycle events; local reproducible checks supply deeper evidence. Caddy
keeps access logging disabled, filters request headers/URIs, and rotates external
diagnostics at 1 MiB with two backups/168-hour retention under its configured
storage directory. Restrict that directory and use a 0077 service umask. Retention
is enforced on startup/rotation, not by a new always-running cleanup service.

Headroom or state-write failure prevents startup; missing/corrupt storage or failed
health stops the managed runtime. Existing inference tests exercise real SQLite
page exhaustion and verify that failed reservation cannot call a provider. Logs
also fail rather than buffering without bound when disk writes fail. The demo is
not highly available and does not promise recovery from a full host disk without
owner maintenance.

Local teardown stops only fixture-owned children and removes only its temporary
directories. Cloud teardown is a later authorized checklist: stop traffic/services,
retain restricted catalogue/evidence as agreed, revoke credentials/invitations,
remove selected resources and verify standing charges. None is executed here.

## Evidence and limits

Focused acceptance and final full checks are recorded in PROJECT_CHECKPOINT.md
when complete. Disposable Linux/WSL DAC proof verifies a non-root service identity
can read but not modify code/configuration, can write its state and denies another
account configuration access. The full Linux service unit is not installed or
claimed tested on EC2. Loopback built-browser restart evidence and production-mode
process evidence are separate from historical sibling-HTTPS browser qualification.
No new TLS trust, DNS, AWS resources, participants or paid requests are involved.

Nine focused release checks passed in 149.60s before the additional bytecode
regression. The latter reproduced the review finding and passes after the fix.
Both independent reviews have no unresolved material findings. TypeScript 199
tests, builds/type checks, lint and formatting pass. Final serial full verification
passes **696 Python/browser tests in 691.70s**, including all ten new release
regressions. Local ticket 06 is resolved; the saved log/exit code remain ignored
under `outputs/cap04-release-verification/`. Rollback rehearsal selects two installations of the same compatible
build, not an untested older product/schema version. Every future version must
pass compatibility and acceptance before it becomes a rollback candidate.
