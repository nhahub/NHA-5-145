# CAP-04: domain and HTTPS preparation

> **19 October superseding selection:** the owner approved [direct Caddy-managed public HTTPS for app/store and a generated CloudFront startup link](specs/2026-10-19-cap04-stockholm-ingress-amendment.md). The account explicitly blocks Virginia ACM without upgrade. The conditional custom-alias/ACM procedure below is historical for this account, not the selected deployment path. DNS will use A records to a retained EIP for app/store; public ACME issuance/renewal needs its own qualified Caddy configuration. No records or certificates have been created.

Date: 14 October 2026. Status: owner-approved browser layout; local ticket 03 routing implemented.

See [configured-runtime evidence](research/2026-10-14-cap04-production-origins.md) and
[operating instructions](../deploy/README.md). The DNS/AWS steps below remain
future work; no public endpoint has been created.

## Decision and evidence

Use the owner-provided `scpilot.tech` domain, purchased through .tech Domains.
The owner approved the following origins after the sibling-hostname browser proof:

| Purpose                        | Public origin                | Private destination on the one host           |
| ------------------------------ | ---------------------------- | --------------------------------------------- |
| Panel assets and Agent API/SSE | `https://app.scpilot.tech`   | Built Panel assets; Agent on `127.0.0.1:8000` |
| Storefront and Bridge          | `https://store.scpilot.tech` | Storefront on `127.0.0.1:4000`                |

Both origins use HTTPS and share a registrable site, but retain distinct DOM
origins. Keep exact postMessage origin/source checks, host-only Secure/HttpOnly/
SameSite=Strict cookies, CSRF and authenticated private reads. Do not set
`Domain=scpilot.tech`, enable wildcard CORS, redirect shopping to generated CDN
hostnames or merge the two applications under one origin. The existing Bridge
journal stays in Storefront sessionStorage; the proposed first-party migration
was not implemented. [Browser evidence](research/2026-10-14-cap04-sibling-hostnames.md).

The owner screenshot shows registration expiry on 14 October 2027 and auto-renew
off. That is registration evidence, not a public TLS or deployment test. A read-only
NS lookup on 14 October returned `tech-domains.{venus,mars,earth,mercury}.orderbox-dns.com`.
The registrar and current authoritative delegation are identified; authenticated
DNS editing access, existing records and any provider charges are not verified.
Keep that DNS provider unless a concrete requirement warrants a change. No Route 53
hosted zone, nameserver transfer, additional purchase or renewal is required by
this plan. AWS remains Free-plan/credit-only; the domain purchase does not authorize
AWS card spending or change the OpenRouter cap.

## HTTPS and DNS sequence

1. Finish local ticket 03 using configurable sibling origins and the real built
   services. The probe's JavaScript origin rewriting is evaluation scaffolding,
   not a deployable configuration mechanism.
2. Ticket 02 selects the ingress/egress topology using current account eligibility,
   complete two-month costing and idle/wake behavior. Compare two standard
   CloudFront distributions with custom aliases (private or protected public EC2
   origin) against direct EC2 HTTPS. Domain ownership now makes the latter possible;
   it does not prove it cheaper or compatible with the always-available waiting page.
3. If CloudFront is selected, request a public ACM viewer certificate in `us-east-1`
   with SANs `app.scpilot.tech` and `store.scpilot.tech` during separately authorized
   provisioning. This certificate Region does not select the EC2/Bedrock Region.
   CloudFront requires a certificate covering its aliases. Origin TLS, where used,
   is a separate certificate/hostname requirement; a viewer certificate does not
   by itself secure the origin hop. [AWS certificate requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html).
4. Copy the exact certificate-validation CNAME names and values returned by ACM
   into the existing authoritative DNS zone. Preserve validation records for
   renewal. Do not invent tokens or replace unrelated records. Review existing CAA
   policy if issuance is blocked. [ACM DNS validation](https://docs.aws.amazon.com/acm/latest/userguide/dns-validation.html).
5. Once the certificate and distributions are ready, assign the two custom aliases,
   then add `app` and `store` CNAMEs to their respective generated distribution
   endpoints. These targets are currently unknown: no usable deployment records
   can be issued yet. Do not use URL forwarding. External DNS can host these CNAMEs;
   Route 53 is not a prerequisite. [CloudFront aliases and DNS](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html).
6. If direct EC2 HTTPS is chosen instead, replace steps 3–5 with a reviewed
   certificate issuance/renewal and address-stability procedure. Price retained
   IPv4/storage while stopped and define the independent wake/waiting path before
   choosing it. Do not reuse ACM viewer-certificate instructions as EC2 installation
   instructions.
7. Verify authoritative DNS, browser-trusted certificates, exact origin routing,
   linking, isolation and recovery on the real deployed names in CAP-07. Local
   `.test` hostname evidence is not evidence that these public names work yet.

No DNS writes, ACM requests, distributions, EC2 resources or account changes have
been made. Public hostname names are configuration, never credentials.

## Ticket 03 implementation handoff

Replace hardcoded browser origins without changing interpretation or recovery:

| Surface                      | Current files                                                 | Required behavior                                                                                                                                                       |
| ---------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Panel browser configuration  | `panel/src/main.ts`, Panel build/shell                        | Provide exact configured Agent and Storefront origins before linking; reject invalid public configuration. Agent API shares the Panel origin in this layout.            |
| Bridge browser configuration | `bridge/src/runtime.ts`, Storefront asset serving             | Supply the configured Panel origin before bootstrap; preserve source-window checks and the existing journal.                                                            |
| Service validation           | `agent/storefront_service.py`, `store/src/identity-config.ts` | Validate public origins independently from the fixed private destination; reject malformed URLs and insecure production origins.                                        |
| Production reverse proxy     | New isolated deployment configuration                         | Route only the two configured hosts to loopback services; no evaluation routes or asset rewriting. Reject unknown hosts and public access to private/test/reset routes. |
| SSE delivery                 | `agent/session_stream.py`, proxy configuration                | Flush events, disable buffering/cache, supply keepalive within configured idle limits, forward cursor and credentials.                                                  |

Use `COPILOT_PANEL_ORIGIN=https://app.scpilot.tech`,
`COPILOT_STORE_ORIGIN=https://store.scpilot.tech` and
`COPILOT_STORE_PRIVATE_URL=http://127.0.0.1:4000` for service configuration.
`COPILOT_ENV=production` is required for the public deployment. Browser configuration
contains public origins only; never bundle the service secret or provider key.
The browser build/metadata contract is implemented in ticket 03; use the linked
operating instructions for exact commands. This document is not an executable
deployment template.

Ticket 03 acceptance uses the same trusted local sibling-hostname browser journey
with no probe rewriting, plus malformed-host/origin checks, public-route exclusions,
Stop, SSE heartbeat/reconnect and cache isolation. Five-Shopper capacity, hardware
Android, restart/release, admission, durable allowance and deployed acceptance
remain their own gates. No infrastructure selection can waive these controls.

## Remaining infrastructure inputs

Ticket 02 still needs current Free-plan status, remaining credit/expiry/applicability,
Region/service availability, origin protection, maintenance/model egress, traffic
and inference assumptions, complete running/stopped cost, and optional Lambda/wake
eligibility. The earlier $100 screenshot is historical. Resource creation is a
later explicit approval against a costed, reviewable configuration; no new paid
calls are needed for this local preparation.
