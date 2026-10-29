# CAP-06 concrete host readiness observations

22 October 2026. `deploy.host_checks.HostChecks` supplies concrete checks to the
injected signed-health boundary. It does not select a cloud backend, create clients,
load keys, start services, invoke a model or qualify the current Bedrock candidate.
The default Agent and active provider configuration remain unchanged.

The caller supplies a built release and independently selected SHA256 fingerprint
of its release.json bytes, external catalogue, existing AsyncAdmissionPolicy,
GuardedClient and production StorefrontService. Exact app.scpilot.tech and
store.scpilot.tech origins and fixed private loopback service are required. State
must exist outside the release and catalogue/ledger cannot alias each other.

The four concrete observations are:

- `release`: verify the pinned manifest fingerprint, production origins/mode and
  every packaged file using the existing artifact verifier; reread the manifest
  afterwards. Tampering or a different release refuses rather than rebasing.
- `storefront`: inspect the external SQLite catalogue, send an authenticated
  read-only empty lexical search to the fixed private endpoint, validate its strict
  SearchResult and matching revision, then recheck local revision/content. This
  tests catalogue service and service-secret agreement, not every shopper journey.
- `admission`: read and validate bound remote metadata through the retained async
  policy pool. No invitation is redeemed and no grant/session is allocated.
- `allowance`: require the bound ledger identity, enabled state and enough
  remaining allowance for the most expensive supported guarded request:
  `(260096*input_price + 2048*output_price)/1000000`. This is an observation,
  not a reservation or a guarantee that the next request will be admitted.

`checks(provider)` requires an explicit async provider verifier and returns all
five named callbacks. `unqualified_provider` explicitly returns false and is the
appropriate binding for the current blocked Bedrock candidate. No new pass-report
format or fabricated qualification evidence was introduced. Metadata access alone
cannot satisfy CAP-05; even four successful concrete checks cannot make the signed
aggregate ready with this verifier.

Synchronous release/SQLite work uses two workers with at most eight retained calls.
Remote admission keeps its existing separate bounds. Cancellation retains actual
submitted I/O capacity. Client/ledger/prices/identity/path and admission authority/
service bindings are pinned and checked after awaits. Dependency failures become
strict false; cancellation propagates. Ordinary exception details and secrets are
not logged. Reading allowance status preserves every existing held charge.

Private HTTP uses no environment proxy, redirect, retry or conditional cache. It
requests identity encoding, rejects compression and duplicate JSON keys, and reads
at most32768raw bytes. One-second async timeout covers the service observation;
the outer HostReadiness retains its aggregate slot and enforces the1.5second
response deadline even if dependency cancellation cleanup is slow. These are
cooperative async deadlines, not a way to kill an entered synchronous SDK call.

The bootstrap owns resource lifetime: drain HostReadiness first, then HostChecks,
then work/admission/service. HostChecks.close drains its retained local operations;
it does not close or reset the supplied guard/admission/service. Do not recursively
call Agent /health from one of these checks. There is no cached ready value.

Tests use a synthetic production-shaped artifact, real seeded catalogue/allowance
SQLite, Moto authority with dummy credentials, and intercepted HTTP. The synthetic
artifact is not a deployed or qualified production release. A fresh general release
build includes this module, but Linux Lambda packaging remains separate work.

An [explicit restricted host startup API](cap06-host-bootstrap.md) now prepares
configuration loading and lifetime wiring. Real POSIX permissions/key provisioning
and selecting that API for deployment, qualified-provider evidence, reliable
external observation delivery, effective IAM/OAC/account
eligibility, resource/cost/rollback approval and deployed acceptance remain open.
Free plan, Stockholm and zero cash persist; no scheduler service was selected.

See [host boundaries](cap06-host-boundaries.md),
[design](superpowers/specs/2026-10-22-cap06-host-checks.md) and
[plan](superpowers/plans/2026-10-22-cap06-host-checks.md).
