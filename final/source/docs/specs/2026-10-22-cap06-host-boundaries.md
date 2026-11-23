# CAP-06 async host authority, work and readiness integration

Continue the approved controlled-host architecture with explicit injected host
integration. No AWS/model calls, cloud backend/environment selection, resources,
keys, DNS/TLS changes or provider qualification are authorized by this slice.

## Design

Builder calls: use bounded ThreadPoolExecutor bridges for synchronous DynamoDB,
serialized async work bookkeeping on the Agent event loop, and explicit optional
factories in create_app. Keep existing synchronous SQLite/local interfaces working.

`agent/async_boundary.py` provides awaitable `invoke(target, method, ...)` for sync
local/async remote methods and `BoundedIO(workers=1, capacity=64).call(...)`. Submit
only under a fixed retained capacity, never an unbounded executor queue. Shield
submitted operations from caller cancellation; hold capacity until the real future
finishes, consume detached errors, and close/drain without blocking the event loop.
No retry. No SessionStore/BrowserAuthority access on worker threads.

`AsyncAdmissionPolicy` wraps the existing remote invitation store with workers4,
capacity64. allowed/redeem/allocate methods compute immutable subject inputs on
the event loop and run only datastore calls off-loop. Existing Policy gets sync
redeem(record, code)/allocate_session(record) wrappers. All HTTP/model ownership
sites await invoke; do not treat an async result as a truthy grant. An async
ShopperAccess ownership check revalidates mapping/owner/session after each await.
Unknown writes retain quotas; cancellation exposes no new authority and never
refunds/replays a transaction. Existing per-browser/in-process request limits stay.

`AsyncLifecycleWork(lifecycle, sessions)` binds one generation in async initialize
during lifespan, refusing preexisting pending work, generation0 and stopped/failed
authority. It serializes up to64retained logical jobs with one backend worker.
initialize/check/begin/finish/refresh/close and maintain are async. Accepted request
leases transfer to pending Tasks through degraded health without new admission;
renew every10seconds and never resurrect expired leases. Only existing successful
explicit interaction paths update activity. Polls, health and model background
traffic do not. Add read-only `DynamoLifecycle.check_work(generation=...)` requiring
matching generation, admitting state and persisted healthy=true.

Caller cancellation does not cancel an entered backend operation or release its
actor slot. A cancelled begin cleans up only its known returned lease, without
activity, after completion. Unknown results remain finite orphan authority; never
retry or invent/refund a token. Failed lease renewal or generation mismatch fences
the worker permanently; existing Task/Action state is never replayed/reconstructed.
Graceful close drains jobs and releases only known nonpending request leases;
pending/uncertain work protection is left to its finite expiry, not reset.

`HostReadiness(work, secret, release, checks)` requires exactly five async trusted
checks: release, storefront, admission, allowance, provider. No default ready=true.
Authenticate existing signed headers before dependencies/I/O. Require initialized
matching generation, nonfailed worker, control state starting/ready/draining/
unhealthy and a live startup deadline. Check each callback strictly returns True;
exceptions/failure sign ready=false. A final authority recheck after dependency
I/O fences intervening generation/state changes. This is not meaningful activity.
The response deadline is1.5seconds; one retained aggregate slot covers authority
reads, checks and cancellation cleanup. Timeout returns false without waiting for
slow cleanup; further requests cannot accumulate aggregates. Shutdown drains it
before closing work authority.
Proof only attests the supplied trusted aggregate; the future deployment bootstrap
must wire actual release/service/store/ledger/qualified-provider checks and may
not fabricate a provider qualification. Current Bedrock quota blocker persists.

`create_app` accepts explicit lifecycle_work_factory and readiness_factory hooks,
keeps current defaults, and awaits sync/async lifecycle calls through invoke.
Lifespan initializes async work off-loop before serving, runs maintenance and
awaits close. /health without proof headers keeps ordinary liveness; injected
readiness handles proof requests with no-store, generic refusal and no logging.
Without injected readiness, proof requests cannot yield a valid signed response.

Do not activate remote backends via environment or add a cloud host CLI. This
integrates injectable boundaries for tests and the later bootstrap; actual checks,
Lambda Linux packaging, credentials/key loading and reliable external scheduling
remain deployment work, not completed by an injectable callback interface.

## Verification

Use real Moto authority with dummy credentials plus injected local test models and
service doubles. Pin event-loop responsiveness under a blocked SDK call, retained
capacity/cancellation, unknown writes, pending lease transfer, expired renewal,
generation changes and no activity on polling. Verify signed health through ASGI,
all-required-checks failure, invalid-proof no dependencies and post-await ownership
changes. Existing admission, ownership/model, guarded-mutation/confirmation,
stale/duplicate Action and refresh recovery regressions remain required. Fresh
release/build, lint/format, pip, independent review; no cloud acceptance claim.
