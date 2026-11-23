# CAP-06 concrete host readiness checks

Continue host-bootstrap preparation in the existing Python deployment system.
Implement concrete checks behind the already reviewed HostReadiness interface.
No cloud activation, credentials, keys, AWS/model request, spend, new service or
deployment is part of this slice. Actual bootstrap/config loading stays pending.

## Decisions

Builder choice: add deploy/host_checks.py, a single event-loop-owned HostChecks
resource. Constructor takes explicit release directory and expected SHA256 of
release.json bytes, external catalogue path, an existing AsyncAdmissionPolicy and
GuardedClient. It creates no SDK or model client and mutates no environment.
All inputs refer to already opened authority; no init/reset/enable operation.
Catalogue and allowance paths must be distinct existing files outside the release.
Release mode must be production with the exact app.scpilot.tech/store.scpilot.tech
origins. Local synthetic production-shaped manifests are test fixtures only.

checks(provider) returns exactly the five callbacks HostReadiness requires.
provider must be an explicit async trusted verifier; no true default, no model
call and no qualification artifact format invented. Add unqualified_provider()
returning False for the current blocked candidate. Tests can supply deterministic
doubles. Production bootstrap must retain unqualified_provider until CAP-05 is
actually passed; this slice cannot declare the host ready for graduation.

Bound synchronous file/SQLite checks with BoundedIO workers2/capacity8. Existing
remote admission uses its own retained bounded policy pool. Never put browser or
SessionStore state on threads. Every check catches ordinary dependency failures
and returns strict False; cancellation propagates. Close drains retained work.
The consumer must close HostReadiness first, HostChecks second, then work/admission.
No cache: every signed aggregate rechecks the current dependencies.

release(): off-loop verify the release manifest and every packaged file using the
existing deploy.artifact.verify; pin its manifest byte fingerprint before and
after verification, require exact production origins and mode. A changed file,
manifest, missing path or wrong release is false, never rebaselined.

storefront(): off-loop catalogue_status checks the external SQLite integrity and
revision, then make a fixed read-only authenticated POST to
http://127.0.0.1:4000/__internal/catalogue/search with the existing empty lexical
SearchQuery. Validate SearchResult, require lexical ranking, no unknown requirements
and matching local revision. Recheck SQLite revision/content fingerprint after
HTTP so intervening catalogue changes invalidate this observation. Secret comes
from explicitly supplied StorefrontService configuration and must validate exact
production sibling origins and fixed private origin; repr/logs exclude it.
This proves the configured authenticated catalogue endpoint, not all shopper
journeys or process supervision. Do not call the Agent aggregate recursively.

HTTP uses injected optional transport for tests, trust_env=False, no redirects,
identity encoding, timeout1s, at most32768 raw bytes and an overall1s async deadline.
No retried requests, no conditional cache or query-supplied destination. Parse JSON
rejecting duplicate keys; a valid empty catalogue search is healthy. HTTP failure,
redirect, oversized/compressed/invalid response, stale revision or closed owner is
false. HostReadiness's existing1.5s response bound still covers aggregation.

admission(): add DynamoInvitationStore.check() metadata-only read and
AsyncAdmissionPolicy.ready() which awaits it through the existing retained pool.
No redemption/quota allocation, invitation codes or shopper bindings. Missing or
replaced authority returns False; lifecycle generation remains a separate check.

allowance(): off-loop read the exact GuardedClient ledger; require matching bound
identity, enabled=True and remaining USD at least the conservative maximum supported
request reservation: (260096*input_price + 2048*output_price)/1000000. Prices are
from that GuardedClient. This is a health observation, not a reservation or promise
of future capacity. No reset/enable/settle/refund; uncertain charges remain held.
Existing allowance refusal still arbitrates actual requests. Mutated client/
ledger/price bindings must refuse instead of silently checking another authority.

No host factory or environment selector is added until restricted configuration,
real qualified-provider evidence and reliable external observation are resolved.
Linux Lambda packaging and resource/cost/rollback approval remain pending.

## Verification

RED/GREEN concrete checks, missing/tampered manifest/catalogue/authority/ledger,
disabled/exhausted allowance, request binding and bounded/cancelled HTTP. ASGI signed
health with real Moto admission and durable SQLite/release fixtures: explicit
unqualified provider signs false even when all four concrete checks pass. Verify
no counters or meaningful activity change. Mocks intercept all network and use
dummy AWS credentials. Fresh artifact contains the new module. Run affected
admission/host/lifecycle/allowance/safety tests, lint/format and independent review.
