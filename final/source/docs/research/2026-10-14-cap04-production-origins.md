# CAP-04 ticket 03: configured HTTPS journey

Date: 14 October 2026. Scope: local production-style service routing; AWS deployment remains gated.

## Implementation

Panel builds receive validated public Panel, Storefront and Agent origins from the
trusted build environment. Production requires explicit HTTPS origins, separate
Panel/Storefront origins and Agent API on the Panel origin. Panel verifies its
serving origin before linking. Service secrets are excluded from those definitions.

Storefront HTML emits validated public-origin metadata beside its existing Shopper
metadata. Bridge verifies the serving Storefront origin and configured Panel origin,
then uses the existing exact parent-window/origin channel, sessionStorage journal
and Action execution/recovery. No prompts, language rules, catalogue interpretation
or journal placement changed.

Both services disable test/evaluation routes in production even if evaluation is
requested, require an explicit service secret and ignore development identity-file
fallback. Agent validates canonical public/private configured origins; browser
Snapshots cannot select the private service destination. Configured public origins
reject malformed hosts, credentials, wildcards, paths and non-HTTPS production
values. [Runtime instructions](../../deploy/README.md).

[The Caddy configuration](../../deploy/Caddyfile) serves built Panel files and routes
fixed loopback services under exact TLS hosts. It enforces SNI/Host matching,
excludes public private/test/probe paths, strips incoming service-secret headers,
sets no-store and frame-ancestor boundaries, and streams SSE without collection or
buffering. Admin API, config autosave and automatic certificate issuance are off;
TLS files and dedicated Caddy storage come from trusted service configuration.
Proxy diagnostic logging removes request headers and URLs. Supplied certificates
need an eventual issuance/renewal procedure; public TLS is not established here.

Agent sends idle keepalive comments initially and every ten seconds, with existing
pending events delivered first. Comments have no event ID and do not touch activity;
authorization, session expiry and ownership checks still precede event disclosure.
The one-shot evaluation stream retains its existing payload format.

## Browser evidence

The [probe](../../eval/probes/README.md) now supports `--runtime --layout same-site`.
It builds with actual `.test` sibling origins, starts both services in production
and runs this Caddyfile. No response-body origin rewriting is used. The scripted
provider uses zero paid calls. An independent foreign-cookie control and forced
stream interruption live in auxiliary loopback evaluation listeners, outside the
public Caddy routes; those listeners are never deployment components.

| Browser          | Version       | Initial idle comment received | Next comment interval | Result |
| ---------------- | ------------- | ----------------------------: | --------------------: | ------ |
| Installed Chrome | 155.0.8059.40 |                         21 ms |             10,191 ms | Passed |
| Installed Edge   | 155.0.4283.45 |                         15 ms |             10,108 ms | Passed |

Both used explicit third-party blocking with a negative control, default browser
TLS verification and the approved short-lived name-constrained user CA. The
browser itself read the heartbeat bytes after Caddy; upstream counters are not
used as delivery evidence. Caddy 2.11.7 Windows archive was verified against the
publisher's SHA-512 checksum before extraction. The binary and generated material
remain ignored, separate from Git.

Both runs passed the earlier [sibling journey](2026-10-14-cap04-sibling-hostnames.md):
DOM separation, journal storage, Strict host-only cookies, two independent carts,
product navigation/add, refresh, second-tab takeover requirement, visible
Confirmation, exact exercised Undo, completed-Mutation SSE reconnect with native
Last-Event-ID and no repeated cart POST/revision, plus missing-CSRF rejection.

Additional runtime checks passed: public test/internal/probe routes return 404,
including an encoded private path; forged Host returns 421 over trusted TLS; both
profiles receive uncached personal HTML/cart responses; initial and periodic
keepalive reaches the browser; Stop cancels pending Confirmation while preserving
cart revision and quantity. The takeover requirement is observed; takeover-and-
resume is not newly qualified by this probe.

Saved ignored files: `result-chrome-same-site-runtime.json` and
`result-msedge-same-site-runtime.json`. Both record successful exact-CA cleanup.
Raw logs, browser cookies, TLS keys, catalogue and binaries are not published.

## Corrections and review

The first Caddy validation failed because Windows paths needed quoted placeholders
and slash-separated values; these are now in the configuration/instructions. A
Playwright API request did not use the browser's local hostname resolver, so
route/cache assertions now execute browser fetches. The separate forged-Host
check uses a loopback socket with CA validation and the correct TLS server name.
A multiline JavaScript string in the heartbeat probe needed a raw Python string;
that harness error was corrected before counting the final results.

Independent Standards review found no actionable issues. Spec review identified
three findings: escaped host acceptance, heartbeat measurement before the proxy,
and initial comment ordering that broke existing revocation regressions. Each was
reproduced and corrected: malformed-host red/green regression, unchanged revocation
regressions now passing, and downstream browser heartbeat acceptance in both
browsers. No outstanding finding is knowingly left unresolved.

## Final verification

The full Python suite passed: **627 tests in 474.65 seconds**, including existing
revocation, expiry, recovery and browser scenarios. All **198 TypeScript tests**
passed (97 Bridge, 38 Panel, 63 Storefront). Workspace builds, Panel/Bridge
typechecks, repository ESLint/Prettier, Ruff lint/format and changed-file relative
links passed. The Caddy configuration was validated by the actual runtime runner.
Both exact runtime-test CAs were independently checked absent from CurrentUser
Root; generated private keys were removed. The original working directory's
unrelated changes were preserved. Ticket 03 is resolved locally; this work is
committed on `feature/cap04-design` without pushing.

## Remaining gates

Ticket 03 establishes local routing and service configuration only. Ticket 02 must
still select and cost eligible AWS ingress/egress and the wake/waiting path using
current account evidence. Ticket 05 durable allowance and subsequent admission,
release/restart, lifecycle, capacity and Android hardware tests remain open. Public
DNS, ACM/other public certificates, CloudFront forwarding/cache behavior, AWS
resources, Bedrock qualification and real deployed acceptance are not established.
No DNS writes, AWS resources, new paid calls or provider-limit changes occurred.
Parent CAP-04 remains open.
