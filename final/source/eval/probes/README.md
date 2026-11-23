# Disposable CAP-04 cross-site browser probe

This is an experiment, **not a production proxy or deployment template**. See
[the unrelated-site negative result](../../docs/research/2026-10-13-cap04-browser-proof.md)
and [the sibling-hostname comparison](../../docs/research/2026-10-14-cap04-sibling-hostnames.md).

Run from the repository root on Windows with Node, pnpm, OpenSSL, certutil and the
project Python/Playwright environment. Build assets first:

```powershell
pnpm --filter @shopping-copilot/bridge build
pnpm --filter @shopping-copilot/panel build
python eval/probes/cap04_cross_site.py --allow-temporary-user-ca --channel chrome
```

Add `--layout same-site` for the approved sibling-hostname layout; the default
`--layout cross-site` retains the unrelated-site experiment. Results are saved as
`result-{channel}-{layout}.json`. In sibling mode the Storefront retains its
original Strict cookie; a separate foreign iframe supplies the cookie negative
control. The probe also checks DOM isolation and disconnects an actual completed
Agent Mutation session to verify native SSE cursor reconnect without duplicate
cart requests or revision changes. The disconnect endpoint is evaluation-only.

`--channel msedge` selects installed Edge; `chromium` selects Playwright Chromium.
Obtain the machine owner's permission before using the explicit CA flag. It adds
a short-lived, name-constrained root to **CurrentUser Root**, then removes that
exact thumbprint. It never edits system-wide trust or DNS. Browser TLS validation
is not disabled. Profiles are temporary; third-party blocking is checked with a
negative control inside the actual iframe.

Ports 4000, 8000 and 4443 must be free; the runner refuses to stop unrelated
services. Only the scripted provider and a scratch catalogue are used. Logs,
results, catalogue and TLS material stay in ignored `.scratch/cap04-cloud-readiness/probe/`.
Do not publish raw logs, credentials or keys. The proxy forwards the actual guards
and SSE, rewrites public origin literals in served assets, and experimentally
changes only Storefront cookie attributes. Never expose this proxy publicly.

A failing browser assertion exits nonzero and records a failure, even when the
experiment successfully discovers an architectural blocker. The full journey is
intentionally unreachable when the privacy/identity preconditions fail.

Normal cleanup stops owned services, closes temporary profiles, removes the CA
and deletes private keys. Cleanup steps are attempted independently, failures are
recorded and the process exits nonzero. If cleanup fails or the runner is forcibly
killed, inspect the ignored
`trust-cleanup.json` and remove **only its exact thumbprint** with
`certutil -user -delstore Root <thumbprint>`. Do not remove unrelated certificates.
The recovery manifest is written before trust is installed.

## Configured runtime mode (ticket 03)

Add `--runtime --layout same-site` to run the actual configured application through
[deploy/Caddyfile](../../deploy/Caddyfile), with no asset origin rewriting. A verified
Caddy 2.11.7 binary must exist at ignored
`.scratch/cap04-cloud-readiness/tools/caddy.exe`; obtain the official platform archive
and compare its SHA-512 with the release checksums before extraction. See
[the deployment rehearsal instructions](../../deploy/README.md).

Runtime mode sets `COPILOT_ENV=production`, builds with public sibling test origins,
uses a separate cookie-control HTTPS listener and a loopback Agent fault-injection
hop, and checks public private/test-route rejection, unknown Host, no-store headers,
periodic heartbeat and Stop in addition to the shopping journey. Ports 8001, 8002 and
4444 must also be free. These auxiliary listeners never belong in public deployment.
Results use `result-{channel}-same-site-runtime.json`. Logs/errors stay local; browser
exception request headers are excluded from the saved result summary.
