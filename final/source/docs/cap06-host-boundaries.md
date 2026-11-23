# CAP-06 prepared async host boundaries

22 October 2026. This slice connects injectable host boundaries to the Agent.
The default application remains local; no cloud backend, key, resource or
qualified provider was activated. It does not establish cloud acceptance.

## Async authority and work

`AsyncAdmissionPolicy` computes immutable subjects on the event loop and runs
remote invitation reads/redemptions/session allocation in a bounded worker pool:
four workers, at most64 retained calls. Every HTTP/model ownership use awaits the
policy. Owner/session mappings are checked again after external waits. Cancelled
or unknown writes retain consumed allowances; no automatic retry or refund.

`BoundedIO` retains the real submitted future and its capacity through caller
cancellation. Close drains submitted work without blocking the event loop. Its
capacity bounds queued plus running operations; SDK connect/read limits remain
the responsibility of the explicitly injected datastore client. It cannot kill
an entered synchronous SDK call. These objects belong to one Agent event loop.

`AsyncLifecycleWork` serializes at most64 retained logical jobs with one backend
worker. Lifespan initializes one generation before serving and refuses generation0,
stopped/failed authority or reconstructed pending work. SessionStore and browser
records stay on the event loop. The existing synchronous local work adapter keeps
its interface; `invoke` awaits either local return values or remote coroutines.

Accepted request protection transfers to pending Tasks without new admission,
including through degraded health. Known leases renew every10seconds; failed
renewal or generation change permanently fences the process. No expired lease is
resurrected and no uncertain Action is replayed. Cancelled begin jobs retain their
slot; only a known returned token is cleaned up afterwards. Unknown outcomes leave
finite orphan protection until expiry. Close drains jobs and leaves pending or
uncertain protection to finite expiry. A future host must still run one Agent
worker and supply bounded SDK settings and durable catalogue/allowance storage.

Only existing successful explicit interaction routes advance meaningful activity.
Polling, health, ownership checks and background model work do not. Remote
`check_work` requires matching generation, ready/draining state and persisted
healthy=true without mutating activity or allocating a lease.

## Signed health hook

`create_app` now accepts explicit `lifecycle_work_factory(lifecycle, sessions)`
and optional `readiness_factory(app, work)`. No environment selector or host CLI
was added. Lifespan initializes work, runs maintenance, and awaits work/admission/
service cleanup even when initialization fails.

Ordinary `/health` stays process liveness. Proof headers require an injected
`HostReadiness(work, secret, release, checks)`; without it, proof requests refuse.
The aggregate requires exactly five async checks: `release`, `storefront`,
`admission`, `allowance`, `provider`. There are no default true checks. Request
HMAC/generation/release is authenticated before authority/dependency I/O. Each
check must strictly return True. Failure or exception produces signed ready=false
with no private error detail. Invalid proof returns generic403; uninitialized
work returns503. Proof responses use no-store and no proof logging.

The response has a1.5second async deadline inside the controller's two-second
HTTPS deadline. One retained aggregate slot covers both authority reads and the
checks; slow cancellation cleanup retains that slot after a false response.
Further proof requests return false until it finishes; shutdown drains it before
closing work authority. A final authority read after checks rejects generation change or
stopping/stopped/failed state. Starting requires its existing deadline to remain
live; health never extends it. Cancelled remote I/O still occupies its retained
bounded slot until the actual SDK operation completes.

Callbacks are a trusted bootstrap interface, not evidence of actual readiness.
The [concrete checks](cap06-host-checks.md) now cover verified release bytes,
authenticated catalogue service, durable admission and funded allowance. Deployment
must wire these resources and an actually qualified provider with restricted
configuration and correct cleanup ownership.
Checks must avoid recursively calling the Agent aggregate. Local success cannot
override Bedrock's zero applied quotas or fabricate qualification. No production
key was generated or selected.

## Remaining activation work

Actual host checks/bootstrap and restricted configuration/key loading, Linux
Lambda dependencies, a costed reliable external observation mechanism, effective
IAM/OAC/account eligibility and approved resource/cost/rollback deployment remain
pending. Browser polling and future host heartbeats alone are not reliable idle/
outage scheduling. No scheduler service or Lambda sleep/self-invocation was added.
Free plan, Stockholm, zero cash and the existing Bedrock gate remain unchanged.

See the [design](specs/2026-10-22-cap06-host-boundaries.md),
plan and
[controller protocol](cap06-controller-runtime.md).
