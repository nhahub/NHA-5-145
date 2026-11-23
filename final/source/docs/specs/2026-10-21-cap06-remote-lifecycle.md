# Remote lifecycle arbitration and command handoff

**21 October 2026 — local preparation of the approved automatic-wake design.**
Use the existing injected DynamoDB invitation authority; keep runtime factories,
Lambda HTTP and real EC2 control disconnected. No AWS calls or resources are part
of implementation. This is a durable decision component, not a deployed controller.

## Purpose and persisted state

Coordinate concurrent wake, accepted work and idle shutdown across EC2 restarts.
Preserve the existing3,600-second idle threshold,300-second start deadline,
120-second ready grace,5-second drain,45-second work leases and60-second failure
cooldown. Background status/health/SSE reads do not advance meaningful activity.

Builder choice: one `lifecycle#host` item in the invitation namespace, containing
its own schema1/UUID identity, revision, generation, state, observed time, activity,
deadline, changed time, grace, last observed health, startup invitation ID, at most128work leases and at
most one command record. Fixed cardinality avoids a scan-vs-admission race and is
well below the400KB item bound. No TTL, auto-initialization, repair, reset or delete.
Initialize explicitly and exclusively under invitation metadata validation.
Initialization also exclusively records lifecycle_identity in invitation metadata;
deleting the lifecycle row cannot permit reinitialization and reset a command fence.

Every mutation reads current state consistently, validates complete shape/bounds,
checks nondecreasing finite caller time and writes through a transaction containing
invitation metadata plus lifecycle identity/schema/revision compare-and-swap.
No application or SDK write retries. Conflicting requests can refuse once; they
cannot overwrite a winner. Reopen must retain generation/leases/deadline/command.
Reads revalidate authority but cannot create a command, lease or fresh generation.

Use the pinned injected Stockholm DynamoDB client policy already required by the
invitation adapter. Recheck it on every operation so a mutated client cannot add
retries or select another endpoint. Errors return LifecycleUnavailable with fixed
text, never raw codes, browser subjects, credentials or service error bodies.

## Wake and work

Wake resolves the code through the invitation adapter, then includes the actual
active invitation condition in the same transaction as lifecycle modification.
No grant/session quota is consumed and raw codes are never persisted. Concurrent
wake coalesces onto the current generation; successful callers see the same one.
Only stopped, or recoverable failed-after-cooldown state, creates a new generation.
No generation can start while a command is pending/claimed/uncertain. Manual start
is a trusted owner-only Python method and has no public bypass endpoint.

`begin_work(meaningful=False, generation=...)` returns a fresh32-hex token only
in ready/draining state and matching generation. Meaningful accepted work cancels
uncommitted drain and updates activity. Nonmeaningful accepted work still blocks
stop while its finite lease lives. Renewal is allowed in ready/draining/unhealthy,
only for a current nonexpired token; expired authority never silently reacquires.
Ending a token is generation-bound and idempotent. Old tokens cannot affect new
work. Full128live leases refuse. Expired leases are pruned atomically on mutation.

Reconciliation observes readiness outside storage. Capture a trusted observation
token containing generation and revision before I/O; reconciliation requires both
still match. Any intervening wake/work/command update invalidates the observation.
Only a running instance plus a healthy trusted application observation can become
ready after an acknowledged start. Running alone, unknown state or failed health
cannot admit new work. Accepted work may renew through degraded health.
Drain retains that health flag independently: unhealthy/unknown idle drain must
never reopen admission merely because its state is named draining.

When idle with no live work and after grace, commit draining; wait at least5seconds,
then atomically commit stopping plus a stop command intent. New work after this
point refuses. A wake cannot cancel committed stop. Observed stopped may finish
a stop only after its command is acknowledged, never while a dispatcher is claimed
or uncertain. Stale observations cannot mark ready/stopped or cancel a newer drain.

## Command safety and uncertainty

EC2 APIs do not consume this component's generation fence. Therefore this slice
does not pretend that a DynamoDB lease alone prevents a delayed external command.
It creates and durably claims commands; a future executor must honor this contract.

A command has random ID, operation start/stop, generation, status pending/claimed/
acknowledged/uncertain and random claim token once claimed. `claim_command()`
atomically changes pending to claimed and returns a private command receipt. Only
one caller wins; there is no lease expiry, automatic re-dispatch or replacement.
Start claim revalidates invitation in that transaction and the start deadline.
Before returning a start receipt, check invitation/deadline again. A failed check
retains the claimed record, even though no executor received its receipt.
`complete_command(receipt, certain=True)` acknowledges only the exact current
command/claim/generation. `certain=False` marks failed and uncertain. Completing
twice or with stale/malformed receipts refuses. Only trusted internal code may
call these methods; no HTTP route exposes them.

Claiming authorizes at most one future executor entry; it does not itself call
EC2 or guarantee an executor does not pause. While claimed, even deadline expiry
or an observed stopped instance must not open a new generation or send another
command. After deadline, fail visibly while retaining the outstanding claim.
A subsequently certain start completion queues bounded cleanup through a stop
intent; an uncertain completion remains locked for owner intervention. No automatic
recovery from uncertainty exists. A successful stop acknowledgement still requires
observed stopped before restart. If stop remains uncompleted after120seconds,
fail visibly and retain the command fence. No automatic retry/timeout-based fence
release is allowed. This deliberately trades availability for late-command safety.

If a start times out while still unclaimed, retire that unclaimed intent as failed
and recoverable; no executor possessed permission to enter. If start was acknowledged
but not ready by the deadline, queue cleanup stop and remain failed. After acknowledged
cleanup plus observed stopped, failed state may become recoverable after cooldown.
Active accepted leases must never be cleared solely due to unhealthy/unknown
observations. Generations only advance after safe stopped/settled state.

## Verification and remaining integrations

Implement using existing Moto dummy-credential SDK tests; inject CAS conflicts,
post-commit lost responses, corruption, backward time and delayed/stale actors.
Prove final drain/admission serialization,128bound, lease renewal/expiry, bounded
command claims, exact receipt binding, no second dispatcher, no restart while
claimed/uncertain, and no model/application Action replay. Strong reads are not an
atomic snapshot; conditions belong in each transaction. Validate row maps and
command/lease values before trusting them; status exposes only safe state fields.

No real EC2 APIs, dispatcher process, wake/status rate HTTP adapter, IAM, DynamoDB
table, CloudFront/OAC, async Agent factory or host readiness integration is included.
The command executor's own crash/outcome protocol, trusted Linux readiness probe,
control-plane outage/manual-stop procedure, clock synchronization, actual AWS
conflicts/latency/costs and CAP-07 public browser tests remain required. Do not
claim a complete automatic-wake deployment from this offline component.
