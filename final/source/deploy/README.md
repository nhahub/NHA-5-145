# Local production-style HTTPS routing

## Approved December operating preparation — 4 November 2026

The owner approved the [invitation-only operating design](../docs/specs/2026-11-04-invitation-only-december-operating-design.md).
Implementation is being verified before public activation. Version-3 host
configuration binds both the finite operating policy and an absolute
`operating_attempt_ceiling`; runtime defaults to that ceiling and rejects a
conflicting override. The qualification fingerprint and actual GuardedClient
must agree. No counter, key, uncertain hold or allowance is reset on reboot.
The cloud guard and one-time stop schedule complement the existing idle controller;
the remaining preparation/launch gates are tracked in the execution plan.
Historical preparation notes below do not claim this ongoing window is deployed.

23 October continuation: [the inactive host service bundle](../docs/cap06-host-services.md)
now prepares separate Storefront/Agent/proxy units and one target around the
public profile. No unit is installed/enabled or public HTTPS activated. The
historical preparation description below predates those separate launchers.

## CAP-06 public HTTPS profile: prepared locally

`deploy/Caddyfile.public` is the separate public-ACME candidate for the approved
Stockholm ingress. It serves exactly `app.scpilot.tech` and `store.scpilot.tech`,
with fixed loopback Agent/Storefront upstreams. It enables normal automatic HTTPS
and redirects, uses Let's Encrypt as its explicit ACME issuer, and restricts the
HTTP server to HTTP/1.1 and HTTP/2. It retains the existing route allowlists,
private-route refusal, CSP, secret-header stripping, no-store and SSE settings.

The existing `deploy/Caddyfile` below remains the static-certificate rehearsal
profile. Both files are hashed into immutable releases; changing either file
after packaging fails release verification. Packaging the public profile does
not start it: neither the release runtime nor its current service launches Caddy.
This is preparation, not deployed HTTPS or permission for public exposure.

The public profile consumes only these trusted service configuration values:

| Variable                | Requirement                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| `COPILOT_PANEL_ROOT`    | Absolute path to the verified release's built `panel/dist`, matching the two fixed public origins     |
| `COPILOT_CADDY_STORAGE` | Dedicated absolute directory outside releases, on retained encrypted storage, restricted to its owner |

Host, bind, Agent upstream and static-certificate overrides used by the rehearsal
are deliberately ignored. Do not select this profile for arbitrary build origins.
Retain the storage directory, including certificate keys and ACME account state,
across stop/start and compatible code rollback. Never copy it into an artifact or
restore an old inference/invitation allowance alongside it. The eventual host
installation must enforce these path, ownership and release-origin requirements;
this template does not validate its environment or install a service.

At this preparation stage, the supported public-profile check is **adaptation
only**, with the two variables set in the invoking process to disposable absolute
paths:

```text
caddy adapt --config deploy/Caddyfile.public --adapter caddyfile
```

Do not add `--validate`, or run `caddy validate`, `run`, `start` or `reload` against
the public profile during offline preparation. Adaptation parses configuration;
validation additionally provisions modules. The real-Caddy tests use only `adapt`,
without loading certificates, creating certificate storage or starting listeners.
Missing Caddy makes those tests explicitly skip; the recorded local evidence uses
the pinned Caddy 2.11.7 executable with no skipped checks.
[Caddy command semantics](https://caddyserver.com/docs/command-line#caddy-adapt).

Later cloud use still requires the separately approved resource/DNS changes,
authoritative A records to the designated retained address, permitted TCP80/443
ingress and outbound issuer access, and a qualified Caddy service installation.
Certificate acquisition/renewal, exact SNI/Host behavior, HTTP redirects and public
browser trust must be measured on the host. No renewal occurs while EC2 is stopped;
prewarm and verify both trusted shopping origins before reporting ready. Adaptation
does not establish any of those outcomes. Bedrock qualification, remote invitation/
lifecycle authority and deployment acceptance remain open.
[Approved ingress](../docs/specs/2026-10-19-cap04-stockholm-ingress-amendment.md),
[automatic HTTPS requirements](https://caddyserver.com/docs/automatic-https).

## Existing rehearsal routing

CAP-04 ticket 03 uses Caddy with built Panel/Bridge assets and the existing
Storefront/Agent on loopback. This configuration is a tested local routing
boundary. Invitations and durable allowance have separate local implementations;
the release guide below covers built packaging and recovery. AWS ingress/origin
protection, public certificate issuance and deployment remain later gates. Do not
expose this demo publicly before those gates pass.

## Public configuration and build

For the selected domain layout, set these server/build environment values:

```text
COPILOT_ENV=production
COPILOT_PANEL_ORIGIN=https://app.scpilot.tech
COPILOT_STORE_ORIGIN=https://store.scpilot.tech
COPILOT_STORE_PRIVATE_URL=http://127.0.0.1:4000
```

Supply `COPILOT_SERVICE_SECRET` through restricted server configuration; production
requires an explicit value of at least 32 characters and ignores the development
identity file. Do not put the value in this document, source, browser configuration
or command history. Provider credentials and service secrets stay outside releases.
The existing local development command paths retain their localhost defaults.

Real-provider production startup also requires the explicitly initialized
[durable inference allowance](../docs/cap04-inference-allowance.md). Keep that
ledger outside releases and use one Agent worker; never restore an old balance
when rolling back code. Scripted rehearsals make no paid calls.

Build with the public environment in effect:

```powershell
pnpm --filter @shopping-copilot/bridge build
pnpm --filter @shopping-copilot/panel build
pnpm --filter @shopping-copilot/store build
```

Panel build defines only the three public origins. In production, Agent shares the
Panel origin; an explicit `COPILOT_AGENT_ORIGIN` may only equal that origin. Build
requires explicit public Panel/Storefront values, rejects malformed origins and
requires them to differ. Serve the bundle on the origin used at build time.
Rebuild when changing it; no response-body string rewriting occurs. Bridge reads
validated public-origin metadata from Storefront HTML, validates the serving
Storefront origin and retains exact parent-origin/source checks. Host-only Secure/
HttpOnly/Strict cookies and existing sessionStorage recovery stay unchanged.

Start one Agent worker and one Storefront process (in separate service terminals):

```powershell
python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000 --no-access-log
node store/node_modules/tsx/dist/cli.mjs store/src/server.ts
```

The Storefront uses the existing TypeScript loader without a watcher/reloader;
server packaging/service installation is release work in ticket 06. Keep the
catalogue path in `COPILOT_CATALOGUE_DB` outside disposable releases. Both services
refuse test/reset routes in production even when evaluation flags are present.

## Caddy inputs and startup

Use Caddy 2.11.7 for this rehearsal. The evaluation copy is downloaded separately
from the official release and checked against its published SHA-512 archive digest;
it is ignored and never committed. A later deployment must pin and verify its own
platform artifact. See [official releases](https://github.com/caddyserver/caddy/releases/tag/v2.11.7).

| Variable                 | Required value                                                                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `COPILOT_TLS_CERT`       | Absolute path to a supplied PEM certificate chain covering both public hosts                   |
| `COPILOT_TLS_KEY`        | Absolute path to its restricted private key                                                    |
| `COPILOT_PANEL_ROOT`     | Absolute path to the built `panel/dist` directory                                              |
| `COPILOT_CADDY_STORAGE`  | Dedicated restricted Caddy data directory, outside disposable releases                         |
| `COPILOT_PROXY_BIND`     | Defaults to `127.0.0.1`; later network exposure requires the approved ingress configuration    |
| `COPILOT_AGENT_UPSTREAM` | Defaults to `127.0.0.1:8000`; the rehearsal overrides it with its loopback fault-injection hop |

Use slash-separated paths on Windows and preserve the quoted placeholders in the
Caddyfile. All inputs come from trusted owner/service configuration, never browser
requests. The admin API, config autosave and automatic HTTPS issuance/redirects are
disabled. Supplied certificate renewal is therefore an operational requirement;
this configuration does not request a public certificate. A CloudFront viewer
certificate alone is not an EC2 origin certificate. [Domain/HTTPS plan](../docs/cap04-domain-https-plan.md).

```powershell
caddy validate --config deploy/Caddyfile --adapter caddyfile
caddy run --config deploy/Caddyfile --adapter caddyfile
```

The configuration has explicit TLS virtual hosts, strict SNI/Host matching and
fixed server-side upstreams. Agent routes and Panel files are allowlisted. Storefront
internal/test/probe paths are rejected, and browser-supplied service-secret headers
are removed before forwarding. Cookies, CSRF, Origin, query parameters and native
Last-Event-ID reach the real services. Private responses are `no-store`; no CDN or
proxy cache is enabled by this configuration. [Caddy proxy behavior](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

SSE is flushed immediately with no response collection, uses a 30-minute stream
lifetime and native reconnect, and receives authorized keepalive comments initially
and every ten seconds. Comments neither advance event IDs nor touch activity.
Proxy diagnostic logs remove request headers and URLs; access logging is disabled
on the Agent command above. External rotating diagnostics and the disk/recovery
policy are documented in [the release guide](../docs/cap04-release-recovery.md).
[Caddy filtered logging](https://caddyserver.com/docs/caddyfile/directives/log#filter).

## Local browser acceptance

Use the existing owner-approved temporary name-constrained test CA and isolated
Chrome/Edge profiles; do not add public-domain names to that CA or disable TLS checks:

```powershell
python eval/probes/cap04_cross_site.py --allow-temporary-user-ca --channel chrome --layout same-site --runtime
python eval/probes/cap04_cross_site.py --allow-temporary-user-ca --channel msedge --layout same-site --runtime
```

The runner builds with `.test` sibling public origins, sets production mode and
uses this Caddyfile. Evaluation controls run separately on loopback ports 8001/8002
and 4444, outside Caddy's public routes. They provide a genuine foreign-cookie
negative control and a bounded SSE interruption. Production services use a scripted
provider; no model spend is needed. Missing/occupied ports, invalid configuration
or failed cleanup stop the run. Results/TLS/logs/catalogue remain ignored.

The selected domain is still not pointed at these services. Local evidence does
not establish AWS service access, CloudFront caching/forwarding, Android hardware,
public certificate issuance, latency or deployment acceptance.

Invited AI access now requires the explicit production settings and owner commands
in [the admission guide](../docs/cap04-invited-access.md). Create tester codes when
needed; implementation tests use disposable codes without contacting participants.

Build, install, preflight, backup/restore and safe restart commands are in
[the release and recovery guide](../docs/cap04-release-recovery.md). Storefront
production releases run emitted JavaScript with pinned production dependencies;
the earlier direct `tsx` command above remains a source-checkout rehearsal only.

## Finite invited operation

The December deployment uses an explicitly initialized `OperatingPolicy` in the
existing DynamoDB namespace. Host configuration version 3 and control configuration
version 2 bind its operation, immutable manifest, original instance and absolute
closing time. Missing, changed, deleted or expired authority refuses admission;
the controller can still observe and stop a closed operation. Every start dispatch,
including maintenance and uncertain outcomes, consumes one of 100 durable slots.
Invitations have a separate ten-code ceiling, two redemptions and 100 sessions per
code. Host admission permits at most eight simultaneous sessions.

The qualified provider remains OpenRouter, `google/gemini-3.5-flash-lite`. The host
configuration pins the absolute lifetime attempt ceiling into its qualification
fingerprint. Protected evidence is checked at startup; requests use the existing
in-memory qualification checks. Root custody preserves the ledger UUID, all charges
and uncertain holds. Public headroom is baseline accounted spend plus USD0.20;
USD0.10 remains unexposed inside the unchanged non-resetting USD2 key cap. A temporary
transactional launch fence permits at most two new smoke-test reservations and is
removed only on a subsequent clean boot after recorded acceptance.

The normal 60-minute meaningful-idle stop remains active. A private five-minute
guard checks finite authority, daily Free-plan/credit/traffic observations and the
eight-hour uninterrupted-run ceiling. A separate Scheduler target directly stops
the original instance at closing; guest systemd timers provide another stop path.
The guard cannot start an instance. Shutdown does not rely on this PC remaining on.
The credit guard uses delayed AWS observations, so it is not a hard billing cap.

At closing, public admission and controller starts are fenced independently of a
successful DynamoDB write. The owned EIP is released only after all four pinned
authoritative nameservers prove app/store A, AAAA and CNAME absence, a continuous
7,200-second interval and a fresh final check. Unknown or renewed DNS references
restart the safe interval. After the approved 48-hour cleanup tail, unresolved DNS
requires an incident with the host stopped and ingress closed; it never permits
releasing an address still referenced by the domain.

The private operator under `.scratch/december-operation/` separates preflight,
disabled provisioning, verified independent safety, reserved maintenance, custody
staging, DNS/TLS, maintenance stop, real invited cold wake, desktop acceptance,
genuine idle observation, signed accounting and handover. It retains intent before
each exact-owned mutation and does not automatically replay uncertain outcomes.
Only a passed deployed acceptance establishes a launch; offline tests alone do not.
