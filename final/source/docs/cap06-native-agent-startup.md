# CAP-06 native Agent startup with synthetic authority

24 October 2026. The packaged Agent now has actual Linux Uvicorn startup,
signed closed readiness and graceful shutdown evidence. This continues host
preparation; actual AWS authority and qualified model readiness remain open.

The unchanged native release is from commit
`2dbe015115822d0e2821b194645e416c71d20d30`, archive SHA256
`bb525fcf8a218fa9f6aa1d475cb8dc01ee57f842456bad26d044f5a984ce134a` and manifest SHA256
`bbf04fb131f066492876218bccacf8907a9b19db78408e1eb4eb57ae1ba31944`.
The [prior native release guide](cap06-native-release-openrouter.md) retains its
original, narrower running-loop refusal result. No artifact or manifest rewrite
was needed for this subsequent proof.

## What executes

The retained AL2023/Python3.12.15 image installs the exact28runtime wheels offline
with hashes. The real native Storefront runs on loopback4000. The real Agent uses
its default protected POSIX reader, release-root binding, model factory,
OpenRouterClient, Uvicorn configuration and original application lifespan on
loopback8000. Its provider key and allowance are synthetic.

Only the existing sdk_factory external-authority seam is injected. The bounded
read-only double supplies fixed existing metadata and generation1 lifecycle rows
through the actual DynamoInvitationStore/DynamoLifecycle protocol. It rejects
unbound reads and unsupported operations; no real SDK is constructed. An outer
lifespan observer invokes the existing concrete checks and records cleanup; it
does not replace their results or change the provider gate.

The actual native observations are:

- Ordinary HTTP health reports Agent availability. The release, native Storefront,
  admission and enabled allowance checks each return true; the unchanged default
  provider check returns false.
- A correctly signed health request returns signed ready=false and no-store.
  An invalid MAC returns403 before any additional datastore read.
- An unauthenticated speech request returns the existing401 identity refusal.
  No model attempt, external socket attempt or control-store write occurs.
- The enabled synthetic USD0.73 allowance, retained USD0.04 uncertain reservation,
  catalogue and original release manifest remain unchanged.
- SIGTERM completes the original lifespan cleanup within10seconds. Uvicorn0.35
  then re-raises the signal to the original OS handler, yielding process exit-15.
  Cleanup was recorded before that re-raise; the work/admission/check workers are
  closed and the authority double closes exactly once. No signal handler was
  replaced to force a zero exit.
- A separate generation0 startup refuses with the fixed redacted error and also
  closes every constructed owned resource. Both runs use the actual OpenRouter
  client with zero model metadata records.

## Bounds, verification and limits

The disposable container has no network, a read-only root, UID/GID10001, no Linux
capabilities or new privileges,1CPU,1GiB RAM without additional swap,128PIDs,
64MiB temporary storage,512MiB executable work storage and32MiB synthetic Caddy
storage. No ports, owner checkout/home/credential directories or Docker socket
are exposed. The outer deadline is180seconds; exact named-container removal was
also tested with a controlled2second timeout and subsequent missing-container
inspection. The retained official image remains; no application image or
persistent container stack was created.

Nine new real-protocol checks pass. The focused Agent launcher/bootstrap/checks
batch passes71tests with two upstream deprecation warnings. Ruff/format272files
and pipcheck pass. Production and TypeScript code are unchanged. Previous complete
suite results and their unchanged browser-cleanup exception remain recorded;
this slice does not relabel that run as uninterrupted green.

The first native attempt exposed case-sensitive header lookup in the harness;
the second exposed its incorrect403 expectation for the existing401 identity
boundary. Both failed receipts are preserved. The final complete native proof
passes with no stderr. Review also found a timeout command-prefix error in the
ignored orchestrator; its fix passed the controlled removal check. No application
safety rule or qualification callback changed.

This proves startup against synthetic external authority. Actual DynamoDB/IAM/
account access, production interpreter/AMI/security adoption, real host users,
systemd/PID1/reboot/capabilities/metadata/logging, selected-provider qualification,
protected key/remaining-credit custody and qualified capacity remain open. Current
Free-plan balance, exact costs/resources/rollback and public desktop/Android
acceptance still gate cloud activation. No AWS/provider request, actual state/key
change, service install, public DNS/TLS, push or merge occurred.

Machine-readable evidence:
[native Agent startup](../eval/evidence/cap06-native-agent-startup-20261024.json).
