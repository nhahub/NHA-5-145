# CAP-06 prepared controller runtime and readiness protocol

22 October 2026. These components are tested offline. No Lambda handler is active,
no service has been deployed and no owner key or cloud resource was created.

The later [inactive external observation preparation](cap06-observation-delivery.md)
adds the exact internal `{"kind":"tick"}` event: fresh current observation then
at most one already-authorized pending command, tick-only EMF completion and
redacted failed invocation for Lambda Errors. Dispatch/observe contracts below
remain unchanged. Its proposed Scheduler/IAM/alarms bundle is always disabled;
actual service adoption, timing, costs and cloud delivery still need qualification.

## Factories and control flow

`agent/lifecycle/lambda_runtime.py` exposes frozen `ControlSettings`,
`create_startup_runtime` and `create_controller_runtime`. Application bindings are
explicit; the module creates no SDK client at import and reads no environment
configuration to activate cloud operation. Its default SDK builder, when called
in the eventual Lambda bootstrap, uses the ordinary role credential chain with
fixed Stockholm HTTPS endpoints, verified TLS, no proxy/endpoint override, one
attempt and five/fifteen-second connect/read timeouts. Tests inject every client.

Startup uses DynamoDB and Lambda clients only. An accepted invitation POST records
the durable wake intent before enqueueing a tiny Event invocation containing kind
and generation, without the invitation code. HTTP202 establishes queue acceptance,
not worker success or host readiness. Unknown/lost acceptance returns generic503
while preserving the recorded intent; a later accepted wake coalesces that same
generation. There is no SDK/application retry or quota refund.

GET /status can enqueue observe, never dispatch. It does not extend meaningful
activity or authorize a shopping Action. Denied/malformed requests do not notify.
The existing local waiting app has no notifier and remains a loopback rehearsal.

Controller uses DynamoDB and EC2 only, with a fixed host and authenticated HTTPS
probe. Its strict event contains only dispatch|observe and a positive generation.
Dispatch attempts at most one command and observes; observe captures host state
and may dispatch only a pending stop, including deadline cleanup. Operation and
generation filters apply inside the durable claim snapshot. Duplicate delivery
cannot acquire a consumed claim; stale generation and revision observations refuse.
Unknown SDK results and abandoned commands remain locked for owner investigation.

`ControlObserver` captures the lifecycle token before DescribeInstances/probe I/O.
It requires exactly the designated instance and a coherent EC2 state. AWS's
internal high byte of the uint16 state code is ignored; the documented low byte
must match its name. Malformed/error/terminated observations are unknown, never
proof of stopped or ready. Polling and health observations do not replay Actions.

## Authenticated readiness

The existing /health response is process liveness and is deliberately insufficient.
`HTTPSReadinessProbe` only contacts https://app.scpilot.tech/health, with verified
TLS, no environment proxy or redirects, identity encoding, bounded streamed body
and finite HTTP timeouts. It checks its monotonic body deadline on each raw chunk,
without rechunking that could conceal a slow drip. HTTPX timeouts apply per phase;
this is not a promise of an exact two-second total wall-clock response.

The probe sends a fresh32-byte nonce, expected wake generation and the SHA-256
fingerprint of the selected release.json bytes, authenticated with a
domain-separated HMAC. The response MAC binds those fields and a strict ready
boolean. Ordinary liveness, old replies, altered readiness, reflected request MAC,
wrong release/generation, duplicate JSON keys, oversized/invalid body or errors
are unhealthy. No key/proof/nonce/response is logged.

The `readiness_reply` helper authenticates the request and compares it with trusted
host-local generation/release before signing a response. An explicit injected
[host aggregate](cap06-host-boundaries.md) now connects it to Agent /health;
the default application remains ordinary liveness. Deployment must supply actual
service/catalogue/admission/allowance and qualified-provider checks. No default
ready=true is supplied. The MAC protects transport authenticity, not correctness
of a misconfigured host aggregate.

Provision a private32–64byte random key separately into restricted controller and
host configuration, outside releases/browser builds/logs. No production key is
generated or selected here. Settings repr omits its key. Key/release rotation must
be coordinated; mismatched values refuse readiness rather than falling back.

## Activation still requires

- Actual Lambda bootstrap, Linux dependency package and restricted settings loading.
- Actual host readiness checks/bootstrap and durable service configuration; the
  injectable async work and signed-health interfaces are prepared locally.
- Costed approved observation delivery when browsers close or hosts are impaired.
  Browser polling and future host heartbeats do not establish reliable outage/idle
  scheduling. No EventBridge/SQS, Lambda sleep or self-invocation loop was added.
- Effective IAM/OAC, actual hostname/instance bindings and event configuration:
  reserve controller concurrency1, function-error retries0 and finite event age on
  the invoked unqualified function. Account quota eligibility remains unverified.
  AWS can still duplicate/throttle/system-retry events; claims remain mandatory.
- Qualified Bedrock access, final credit/resource/cost/rollback approval, public
  TLS, operational recovery and Android/desktop cloud acceptance.

Source contracts:
[AWS runtime research](research/2026-10-22-cap06-controller-runtime-contract.md),
[design](specs/2026-10-22-cap06-controller-runtime.md),
plan.
