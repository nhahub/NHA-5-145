# Invitation-gated startup and idle shutdown

## CAP-06 runtime factories and authenticated observation — 22 October 2026

Explicit startup/controller factories now compose the injected durable authority,
async queue notifier, generation/operation-filtered worker and fixed-host EC2
observer. Accepted wake may enqueue dispatch; status enqueues observe, which can
stop but never start. Fresh signed readiness binds the expected release and wake
generation; ordinary /health liveness cannot admit shopping. The host-side reply
helper remains inactive pending real readiness/work integration. No deployment,
secret provisioning, environment-selected factory or reliable scheduler is added.
See [runtime handoff](cap06-controller-runtime.md) for interfaces and remaining gates.

## CAP-06 CloudFront/Lambda access preparation — 22 October 2026

The shared waiting page now supplies SHA-256 of the exact POST body for Lambda
OAC signing, with fail-closed hashing and no code URL/storage/logging. The pure
access renderer prepares separate startup/controller IAM policies, exact
CloudFront Function URL permissions and private S3 prefix access, sigv4 OAC and
uncached control forwarding. No resources or policies have been applied. See
[the access handoff](cap06-cloud-access.md) for the prepared interfaces and
remaining Lambda runtime, readiness and deployment qualification work.

## CAP-06 command and startup HTTP preparation — 22 October 2026

`agent/lifecycle/executor.py` adds an injected worker for one fixed Stockholm EC2
instance. Each execution durably claims at most one pending command, refreshes
its deadline/invitation authority, rechecks bounded client configuration and calls
StartInstances or StopInstances once. Only a validated matching EC2 response can
acknowledge a command. Errors and malformed/lost replies are uncertain; failed
settlement is not retried. Neither acknowledgement nor HTTP acceptance establishes
readiness. A claimed or uncertain command cannot be taken over or replayed.

The deadline is checked again after invitation I/O, and EC2 client policy after
authority I/O. These checks reduce timing gaps but cannot make an invitation check
atomic with an EC2 API. The generation remains a DynamoDB protocol, not an EC2
generation token. Investigating/unlocking abandoned commands remains owner work.

`agent/lifecycle/startup.py` prepares an injected Function URL HTTP-v2 handler for
the eventual generated CloudFront origin. GET / serves the existing nonce-CSP
waiting page with the fixed https://app.scpilot.tech/ destination; GET /status
returns only the safe lifecycle view; POST /wake validates exact Origin, bounded
JSON and invitation, then returns durable acceptance. No route dispatches an EC2
command, redeems shopping access or extends meaningful activity. Codes stay out
of URLs, responses and storage. A separate trusted worker still has to observe
readiness and advance commands.

Three fixed DynamoDB rate rows bound http/wake/poll to240/10/120per minute.
Metadata markers prevent deleting a row and reopening its lane as unused.
Strong reads and conditioned transactions retain counts across handler instances;
conflict, corruption, clock rollback and uncertain writes fail closed without
retries. Application limits do not cap edge requests or Lambda/DynamoDB charges.

The handler has no listener, SDK/credential factory or runtime selection. AWS_IAM,
CloudFront OAC, edge cost bounds, actual Lambda scheduling and fixed instance
configuration remain deployment requirements. Existing local HTTP, SQLite stores,
host services and active provider are unchanged. Tests use dummy credentials,
Moto DynamoDB and botocore-stubbed EC2 only. The rate concurrency harness serializes
Moto server transactions because its backup/rollback simulator is not thread
isolated; reads/CAS still contend. Real AWS conflicts and durability remain
unverified. See the
[design](specs/2026-10-22-cap06-command-startup.md) and
plan.

## CAP-06 remote lifecycle decision component — 21 October 2026

`agent/lifecycle/dynamodb.py` now prepares the remote wake/work/drain state machine
against the injected DynamoDB invitation authority. Existing local factories and
SQLite rehearsal remain unchanged. This component does not dispatch EC2 commands,
serve Lambda HTTP or activate a production controller.

One bounded lifecycle item serializes generation, revision, meaningful activity,
at most128work leases and one command. Every mutation includes metadata identity
and lifecycle revision conditions. Wake and start-command claims validate the
invitation in that same transaction; earlier wake reads are not permanent start
permission. Status reads create no commands and do not advance activity.

Initialization is explicit and exclusive. A lifecycle identity marker in the
invitation metadata prevents deleting the lifecycle item and initializing fresh
state to reset its command history. Missing, mismatched, malformed or uncertain
state refuses operation; there is no migration, TTL cleanup or reset command.

Work admission and stop commitment contend on the same revision. Meaningful work
can cancel uncommitted drain. Once stopping is committed, no new work is admitted.
Accepted finite leases may renew through degraded health; stale generation/token
authority cannot be reacquired. Readiness observations bind both generation and
revision before the external probe; intervening state changes invalidate them.
Health remains independent of drain state, so unhealthy idle drain cannot admit
new work while existing leases may still renew.

The command interface durably claims one pending start/stop and returns a private
receipt. Only that exact receipt can settle once. A claim never expires into a new
dispatcher. Unknown outcome locks the state failed; even an observed stopped host
cannot permit another generation while a command is claimed or uncertain. Certain
late start completion requires cleanup stop. Certain stop acknowledgement plus
observed stopped is required before restart. There are no automatic command retries.

This lock is deliberate: EC2 APIs do not enforce this component's generation
number. The eventual executor must obey one claimed entry and prove completion;
this offline decision component does not establish end-to-end EC2 fencing. An
abandoned/uncertain claim currently requires owner investigation, with no automated
unlock path. An HTTP startup service, bounded durable rate lanes, scoped IAM,
single executor, host readiness checks, async Agent integration and actual
stop/outage recovery acceptance are still required before deployment.

Offline checks use the optional pinned Moto extra and dummy SDK credentials:

```text
python -m pytest agent/tests/test_lifecycle_dynamodb.py -q
```

No actual AWS requests, real host commands or model calls are made. Emulator
success does not qualify AWS conflicts, durability, IAM, cost or operational
latency. See the [design](specs/2026-10-21-cap06-remote-lifecycle.md)
and [transaction research](research/2026-10-21-cap06-dynamodb-invitation-contract.md).

## Existing local rehearsal

This is the local Ticket 07 rehearsal. It does not provision EC2, Lambda, DNS,
IAM or a managed control store. Automatic cloud wake remains conditional on
Ticket 02's account eligibility and complete cost estimate.

## Authority and state

The waiting service remains outside the simulated shopping host. Its initialized
SQLite lifecycle file and invitation authority survive host stop/restart. The
local Agent reads the same external authority; this shared-filesystem transport
is deliberately rejected in production configuration. A remote AWS control-store
adapter, its authentication and resource-scoped IAM still require qualification.

Opening the waiting page or polling status never starts the host. Only a valid
invitation in a same-origin POST body requests startup. Wake validates the absolute
window and revocation without consuming or creating an application grant. The
Shopper enters the code again after startup; normal ownership, quotas and
invitation revalidation still apply. No code enters URLs, browser persistence or
model context. Both services disable access logs; waiting responses are no-store
with restrictive CSP and no-referrer policy.

Concurrent requests share one durable generation. Startup HTTP finishes before
boot; a separate controller reconciles idempotent commands for its single fixed
host. Readiness requires built Agent, Storefront, Panel and state prerequisites,
not only a running process. Health observation happens outside the database writer
lock, with generation revalidation afterward. Failed prerequisites remove ready
status and deny new work; surviving work leases can finish safely.

## Bounds and shutdown

| Control                                       | Local policy                                                    |
| --------------------------------------------- | --------------------------------------------------------------- |
| Genuine inactivity                            | 3,600 seconds                                                   |
| Startup deadline / minimum startup grace      | 300 / 120 seconds                                               |
| Browser status polling                        | Every 5 seconds, at most 60 attempts, 5-second HTTP timeout     |
| Drain/recheck                                 | Separate durable decision, at least 5 seconds before commitment |
| Work lease / renewal                          | 45 / 10 seconds                                                 |
| Maximum live work leases                      | 128                                                             |
| Anonymous HTTP / status / wake                | 240 / 120 / 10 per minute globally, durable counters            |
| Active waiting requests / body / read timeout | 8 / 1,024 bytes / 5 seconds                                     |
| Failed commands                               | At most 3 attempts, 10-second backoff                           |
| Stop completion / restart cooldown            | 120 / 60 seconds                                                |

Successful accepted shopping requests and explicit, authenticated interactions
advance meaningful activity. Visible trusted keyboard/pointer events are reported
at most once per 30 seconds; the Bridge sends only a context-bound activity signal,
never field values. A stationary page, health checks, Snapshot reconciliation,
status polling and SSE traffic do not advance activity. Interaction authority is
finite: it extends the inactivity deadline once, without a timer renewing it.

Accepted HTTP/model/queued work holds renewable work leases. A delivered Action
retains a work lease after its HTTP request finishes, until its existing Task
state resolves or expires. Human questions do not become immortal work. A crashed
worker loses its lease; expired worker authority is latched closed and never
silently reacquired. Generations fence both admission and lease renewal.

Drain and admission serialize through the same durable transaction. A request
winning before commitment cancels drain; a request after commitment receives 503
and must return to the waiting page. Authority is checked again after asynchronous
Storefront validation and before event/model delivery. The controller never
replays Actions. Failed stop is visible as failed, not falsely reported stopped;
after bounded failure the owner must inspect and stop the designated host. A new
generation requires observed stopped state and the cooldown.

## Local owner rehearsal

Use an existing built local release and the external configuration from
[release recovery](cap04-release-recovery.md). Keep the external invitation and
lifecycle files outside the simulated host's release/state directory. Initialize
the lifecycle explicitly; missing files must never create fresh authority:

```powershell
python -B -m deploy.lifecycle initialize --path C:/demo-control/lifecycle.sqlite
```

Add the returned identity and absolute path as `LIFECYCLE_DB_ID` and
`LIFECYCLE_DB_PATH` in the restricted local-rehearsal configuration. Point
`ADMISSION_DB_PATH` at the initialized outside-host invitation authority. Then:

```powershell
python -B -m deploy.lifecycle serve --release C:/demo/releases/local --config C:/demo/state/runtime.env --logs C:/demo/logs
```

Open `http://localhost:4200/`. The waiting service is loopback only. It owns only
the designated built release's services on 4000/4100/8000; it will not replace
unrelated processes occupying those ports. Ctrl+C closes its owned processes.
For owner manual startup/presentation prewarming, add `--prewarm`. It uses the
same lifecycle and automatic idle stop; it does not bypass Shopper admission.

A Storefront restart starts a fresh cart, fictional orders and commerce authority.
Agent-only restart invalidates Agent authority while the surviving Storefront
cart remains. Page refresh alone does not reset commerce. Check the cart before
retrying any request whose outcome was uncertain.

The lifecycle file is exclusively initialized and integrity/identity checked;
missing, corrupt, full or inaccessible coordination denies automatic wake/work.
Time moving backward fails closed. Clock synchronization and control-plane
outage/manual stop procedures remain part of actual cloud acceptance. The fake
control object survives coordinator reopens; killing the entire Windows launcher
or installing a real Linux control-plane service is not qualified by this proof.

## Verification boundaries

Final serial verification on 18 October 2026: **713 Python/browser tests passed
in 728.29s**, **199 TypeScript tests**, builds/type checks, lint and formatting.
Both independent reviews cleared after the reproduced failure/race fixes. Local
07 is resolved; 08 combined concurrency and 02 account/network feasibility remain
open. The two Python warnings are existing dependency deprecations exposed by the
waiting server's WebSocket auto-detection; no test failed.

Controller/HTTP regressions use real persistent files, concurrent callers, fake
time and a designated fake host. They cover invalid/revoked/expired invitations,
coalescing, readiness loss, deadlines, cooldown, bounded failure, stale leases,
slow health probes and admission/stop races. The browser rehearsal starts actual
built shopping processes from the waiting page, rechecks revoked admission,
performs a cart Mutation and verifies fresh commerce after stop/start without
renewing invitation quotas. Existing release recovery regressions retain the
lost-result, stale Confirmation and Undo checks. None of this establishes cloud
costs, AWS entitlement, IAM correctness or EC2 capacity.
