# CAP-06 Lambda factories and trusted observation runtime

Continue the approved automatic-wake topology with offline-tested runtime wiring.
Do not create resources, invoke AWS, run models, generate deployment secrets or
activate a provider/backend. Bedrock, effective IAM, costs and cloud gates stay
open. Existing local factories remain unchanged.

## Decisions and interfaces

Builder calls: use the existing boto3/httpx and standard-library HMAC. The present
public /health liveness response is insufficient for remote readiness. Add an
inactive host-side reply helper and a fixed HTTPS probe; actual host health/Agent
integration is subsequent work. A simple HTTP 200 must never mark the host ready.

`agent/lifecycle/readiness.py` provides `readiness_reply(headers, *, secret,
release, generation, ready)` and `HTTPSReadinessProbe(secret, release,
transport=None).check(generation)`. Require a bytes secret of32–64bytes and exact
64-lowercase-hex release fingerprint (SHA-256 of the selected release.json bytes).
No default secret, certificate bypass, alternate URL, proxy, redirect or model call.
Probe only https://app.scpilot.tech/health with a fresh32-byte random nonce,
generation, release and request HMAC headers. Domain-separated request/response
MACs bind exact generation/release/nonce and the response ready boolean. Reply
helper checks requested generation/release against trusted host-local values and
authenticates the request before signing. The caller must aggregate real host,
catalogue, admission, allowance and qualified-provider readiness before ready=true.
It is not connected to /health by this slice.

Use TLS verification, trust_env=false, redirects disabled, 2-second HTTPX timeout,
one connection, streamed response bounded to1024bytes, strict UTF-8/duplicate-key
JSON and exact response fields/types. Any error/mismatch/ordinary liveness reply
is unhealthy. No response, nonce, MAC or secret logging. Fresh nonce prevents old
readiness replay; this is not an EC2 generation token or an atomic external fence.

`agent/lifecycle/controller.py`: injected `ControlObserver(lifecycle, client,
instance, probe).observe(generation)` captures revision/generation before external
I/O, validates the same bounded Stockholm EC2 client policy as the executor and
DescribeInstances for exactly that instance. Require HTTP200, one reservation,
one matching instance and coherent named/numeric EC2 state. Validate uint16 code
and compare only its documented low byte, ignoring AWS-internal high bits; apply
the same correction to executor acknowledgements. Unknown/error maps to
unknown/unhealthy, never proof of stopped or readiness. Only running uses the
authenticated probe. Reconcile using the original observation token; stale I/O
cannot mutate a newer revision/generation.

`ControlWorker(...).handle(event)` accepts exactly kind=dispatch|observe plus a
strict positive generation. No caller-selected host, code, URL or receipt. Stale
events refuse before EC2. Dispatch attempts at most one pending command, then
observes; observe observes, then may dispatch only a pending STOP (including
deadline cleanup), never START. Add optional operation/generation filters to the
durable claim/executor interface; enforce them in the claim transaction snapshot,
not a pre-read-only filter. Keep existing no-argument interfaces compatible.
No retry, waiter, sleep loop or automatic takeover. Acknowledgement is not ready.

`agent/lifecycle/lambda_runtime.py` supplies explicit injected startup/controller
factory functions. A frozen validated settings object binds mode, table,
namespace, invitation/lifecycle identities and the role-specific origin/controller
ARN or instance/release/readiness key. Default SDK factory is lazy, Stockholm-only,
standard endpoint, one attempt,5/15second timeouts; imports create no client or
credential lookup. Factories support a test SDK factory so all calls are intercepted.
Deployment supplies application settings explicitly; no environment-selected app
factory or dummy active handler is added. The default SDK uses its normal role
credential chain when explicitly constructed inside the future Lambda runtime;
it specifies TLS verification, no proxy/configured endpoint override and no keys.

Startup factory composes existing HTTP-v2 handler and durable rates with a bounded
async Lambda notifier. Valid accepted POST /wake enqueues dispatch for its current
generation; valid GET /status can enqueue observe for active/nonstopped state only.
Unknown/malformed/denied requests never notify. Await only queue acceptance, never
boot. Failed/uncertain enqueue returns generic503 while retaining durable intent;
subsequent accepted wake can enqueue the same generation without replaying a claim.
Only exact target controller ARN and Event invocation; compact payload kind/gen
only, no code. Require response StatusCode202, bounded zero-retry SDK config, no
application retry or response/event logging. Startup has no EC2 client.

Controller factory has no Lambda client and returns only safe lifecycle view or
fixed unavailable state. Concurrency1, async retries0 and finite event age are
deployment prerequisites, not substitutes for durable claims. Duplicate delivery
cannot dispatch a command twice; stale generation delivery cannot affect a newer one.

## Explicit remaining gate

Observation delivery while a host is impaired or the browser closes is not solved
by this code. No EventBridge/SQS or Lambda sleep/self-invocation service is silently
added. Browser polling and future host heartbeats are useful inputs but do not
prove reliable outage/idle deadline scheduling. A costed approved delivery design,
actual handler/package assembly and host readiness/work integration remain required
before claiming automatic wake/stop or exposure. Real HMAC key provisioning and
rotation must use restricted owner configuration; no key is generated here.

## Verification

Use Moto DynamoDB, botocore Stubber EC2/Lambda and HTTPX MockTransport only, dummy
credentials. Test wrong/replayed proofs, body/redirect/error bounds, unknown EC2
responses, intervening revision changes, stale/duplicate async events, observe
never starting, queue uncertainty retaining intent and role-specific factory SDK
creation. Existing invitation/lifecycle/HTTP/browser/allowance safety regressions,
fresh release packaging, repository lint/format and independent review remain.
