# CAP-04 cloud readiness specification

> **19 October selected network amendment:** AWS account evidence blocks Virginia ACM without a paid upgrade. The owner selected [generated-host automatic startup plus direct Caddy HTTPS on the owned shopping domains](superpowers/specs/2026-10-19-cap04-stockholm-ingress-amendment.md). Shopping origins and safety contracts remain unchanged. Generated CloudFront HTTPS serves only waiting/control, not the shopping iframe/API. No resources, paid calls, DNS changes or account upgrade are authorized. This supersedes custom-domain CloudFront/Virginia-certificate assumptions below.

**Status:** ready-for-agent

The owner approved the 11 October cloud-readiness design. This specification
formalizes that scope; it does not select an unverified AWS topology or authorize
deployment. The owner confirmed the browser, invitation, availability and cost
decisions after review. Individual implementation tickets are published locally.

**14 October amendment:** the owner purchased `scpilot.tech` through .tech
Domains and approved `https://app.scpilot.tech` for the Panel/Agent and
`https://store.scpilot.tech` for the Storefront. This replaces the no-domain
constraint only; AWS remains credit-only with no account upgrade. Use the
[sibling-hostname evidence](research/2026-10-14-cap04-sibling-hostnames.md) and
[DNS/HTTPS preparation](cap04-domain-https-plan.md). The first-party journal
proposal is not selected; existing recovery remains unchanged.

## Problem Statement

The owner wants to share the Controlled Storefront with independent Shoppers
without running services on their own computer or incurring out-of-pocket AWS
charges. The application works locally, but its localhost configuration, browser
cookie assumptions, ephemeral shopping state and development spending controls do
not yet demonstrate safe public operation. Older infrastructure notes describe a
single supervised Shopper and do not reflect the current SQLite catalogue or
implemented shopper isolation.

## Solution

Prepare a minimal, testable deployment design using one EC2 host and an encrypted
disk for SQLite, while preserving the Shopping Copilot's current behavior. Prove
browser identity across separate HTTPS origins, define bounded demo admission and
durable inference allowances, and rehearse release and recovery locally. Complete
the credit-only network and cost design using actual account evidence before any
provisioning. Keep CAP-04 open when feasibility is unproven.

## User Stories

1. As the owner, I want a shareable HTTPS link so that testers can use the demo independently.
2. As a Shopper, I want my cart and fictional orders isolated so that another browser cannot see or change them.
3. As a Shopper, I want the embedded Storefront to recognize my session with third-party cookies blocked so that ordinary browser privacy settings do not break shopping.
4. As a Shopper, I want unsupported browser conditions explained before a request so that a failed link cannot look like a working session.
5. As a Shopper, I want tabs in one browser profile to retain the established cart and lease behavior so that concurrent tabs cannot silently take over a Shopping Task.
6. As a Shopper, I want refresh to reconcile my existing Shopping Task so that uncertain Actions are not repeated.
7. As a Shopper, I want reconnecting events to preserve progress without duplicate messages or mutations.
8. As a Shopper, I want Guarded Mutations to retain bound Confirmation and Reversible Mutations to retain ownership-checked Undo.
9. As a Shopper, I want an Agent restart to invalidate old task authority while preserving a surviving Storefront cart.
10. As a Shopper, I want a Storefront restart to explain the commerce reset and require fresh linking.
11. As the owner, I want catalogue persistence across deployments so that releases do not accidentally erase products.
12. As the owner, I want verified catalogue backup and restore so that a failed release can be recovered safely.
13. As the owner, I want expiring demo invitations so that sharing the public address does not grant unlimited inference.
14. As a Shopper, I want clear busy, expired-access and budget-exhausted states so that I know when a request was not sent.
15. As the owner, I want global request, queue and inference limits so that new cookies cannot bypass resource controls.
16. As the owner, I want every interpretation, advice and repair call to reserve cost so that the allowance covers the whole Shopping Task.
17. As the owner, I want unknown provider charges to remain reserved so that timeouts cannot replenish spending capacity.
18. As the owner, I want allowance accounting to survive crashes and rollback so that restarting cannot reset the budget.
19. As the owner, I want a persistent inference-disable switch so that I can stop new paid work promptly.
20. As the owner, I want secrets and Sensitive Field values excluded from source, browser bundles and logs.
21. As the owner, I want private service and test routes protected so that public access cannot bypass shopper authority.
22. As the owner, I want an estimate including networking, storage, logs, inference and backups so that hidden services do not consume the credit reserve.
23. As the owner, I want to retain the AWS Free account plan so that this project does not require a paid-plan upgrade.
24. As the owner, I want measured concurrency and latency limits so that the demo's capacity claims are supported by evidence.
25. As the owner, I want reproducible release, rollback and teardown instructions so that unused resources are identifiable and removable.
26. As an evaluator, I want synthetic model results, local browser evidence and AWS qualification distinguished so that one is not presented as proof of another.

27. As an invited Shopper, I want the stopped demo to start on demand so that I can test without contacting the owner each time.
28. As a Shopper, I want a clear startup waiting screen and a bounded failure state so that I know whether the demo is becoming available.
29. As the owner, I want shutdown after 60 minutes without meaningful activity so that unused compute does not consume credits.
30. As an active Shopper, I want my ongoing request protected from idle shutdown so that a cost-saving control does not interrupt accepted work.
31. As the owner, I want each tester's invitation independently revocable and limited to an explicit testing window so that rebooting cannot renew access.
32. As the owner, I want manual start and presentation prewarming available so that a failed or ineligible automatic startup path does not block the demo.

## Implementation Decisions

- Retain one Storefront process, one Agent worker and built Panel/Bridge assets behind a production reverse proxy. Avoid an unrelated module refactor.
- Retain SQLite for the catalogue on persistent encrypted storage. The Agent uses authenticated private Storefront reads; it does not open the database directly. No managed database is needed merely because SQLite was introduced.
- Configure exact public Panel and Storefront origins independently from private service addresses. Preserve origin, source-window, ownership, Sensitive Field, Confirmation and replay guards.
- Keep the established model path and existing interpretation contracts. Do not enable experimental catalogue retrieval or change prompts as part of cloud readiness.
- Use the approved sibling HTTPS origins under `scpilot.tech`. Keep host-only Secure/HttpOnly/SameSite=Strict cookies and separate DOM origins. Do not widen cookie Domain to the parent domain. Two CloudFront distributions with these custom aliases remain a candidate; compare private and protected public origin paths and direct HTTPS hosting in ticket 02. Resolve account eligibility, ingress and maintenance/model egress before selecting AWS topology. Exclude CloudFront flat-rate plans under the current Free-account constraint.
- Retain the negative unrelated-site probe as evidence. The sibling-hostname probe passes installed desktop Chrome/Edge with third-party blocking independently verified. Adopt that layout through reviewed production configuration in ticket 03; do not migrate the journal, change privacy settings or expose the disposable proxy. Android hardware remains unverified.
- Disable caching for personal HTML, identity, API and SSE responses; explicitly forward necessary credentials, CSRF, Origin and event-cursor information. Cache only separate versioned public assets.
- Preserve existing asymmetric restart semantics: Agent restart invalidates Agent authority; Storefront restart invalidates commerce authority and resets its ephemeral state. Never replay an uncertain Action.
- Use one owner-issued code per tester, valid for an explicit testing window with absolute start/end times and independent revocation. Bound redemption and admitted-session counts; admission never replaces Shopper ownership. Reboot or wake must not extend invitation validity. Keep invitation secrets out of URLs and logs. Browsing may remain public while the Storefront is running; AI use and wake require admission.
- Apply configurable finite per-Shopper and global limits. Validate settings at startup; public mode must reject missing limits. Publish tested values only after the capacity rehearsal.
- Use a provider-neutral durable allowance boundary with atomic reservations, idempotent settlement, retained uncertain costs and a persistent kill switch. Initial tests use a fake provider; Bedrock-specific pricing, credentials and qualification belong to CAP-05. Initial ledger creation is explicit; disappearance must not silently create a fresh allowance.
- Keep the catalogue, restricted service configuration and allowance ledger outside disposable releases. Require schema compatibility on release and rollback. Restore the catalogue consistently; never restore an old allowance balance as a way to regain budget.
- Use short bounded redacted logs, proposed seven-day retention, finite disk limits and health checks that do not expose secrets. Keep test/reset endpoints unavailable in public mode.
- Use least-privilege temporary AWS credentials through an EC2 role. Separate runtime invocation privileges from any authorized model enablement or infrastructure setup.
- Use the last $100 credit screenshot only as historical evidence. Confirm current balance, expiry and service applicability; calculate a complete two-month envelope with contingency. A proposed $80 envelope is not spending approval.

- Initial support covers desktop Chrome/Edge and Android Chrome; iPhone/Safari is excluded from initial acceptance. Test a target of five simultaneous Shoppers before claiming that capacity on EC2.
- Prefer on-demand EC2 availability with shutdown after 60 minutes of genuine inactivity. Explicitly show the accepted commerce reset after a Storefront restart; browser refresh alone does not clear the cart.
- Conditionally use a small Lambda startup endpoint and an always-available waiting page if current account eligibility and the complete cost estimate permit it. Validate invitations using durable state outside EC2 before requesting startup. A minimal managed control store is allowed for invitations/lifecycle state; SQLite remains the catalogue. Do not add a standing server or a mandatory NAT gateway merely to support wake.
- Serialize startup and shutdown decisions with a durable lifecycle generation/lease. Coalesce concurrent authorized wake requests; never wake on ordinary URL visits, health probes or unauthenticated status requests. Rate-limit both authorized and unauthorized traffic, restrict control permissions to the intended instance, and expose only non-sensitive readiness status.
- Lambda requests finish promptly; do not sleep while EC2 boots. The browser polls at bounded intervals with a deadline and useful failure/retry instructions. Ready means application health and linking prerequisites succeed, not merely that EC2 reports running. Invitation expiry and revocation still apply at application admission.
- Track meaningful authenticated shopping activity separately from SSE heartbeats and health checks. Idle shutdown requires no active admitted interaction, model request, queued accepted work or in-flight Action. Use finite renewable presence leases so abandoned tabs cannot hold the host indefinitely; showing a waiting page alone does not extend activity.
- Drain and recheck before stop; serialize admission with that decision so new accepted work cannot be killed by a stale idle check. A request arriving after shutdown is committed waits for a fresh startup instead of being accepted by the draining host. Include startup grace, bounded retry/cooldown and crash/stale-lease recovery in the lifecycle policy; preserve uncertain Action outcomes without replay.
- Retain manual owner start and presentation prewarming as fallback. Automatic wake is conditional, not a promise of lower overhead than manual start. Cost savings come from stopped compute; EBS and any retained addresses or other standing resources remain in the estimate.

## Testing Decisions

- Primary seam: an actual browser through the HTTPS reverse proxy, operating the existing Panel, Bridge, Agent and Controlled Storefront together. Reuse current browser isolation, guarded-cart, SSE, tab-lease and restart scenarios.
- Preserve both layouts in the disposable HTTPS probe: unrelated sites document the negative result, sibling hostnames qualify the selected browser layout. Use valid browser trust and explicit privacy settings; in sibling mode verify blocking with a separate unrelated iframe. Record versions, DOM isolation, host-only cookies, persistent storage and tested versus untested browsers. Public-domain acceptance is still required after deployment.
- Assert visible results and authoritative state: two browsers never share carts, requests cannot target foreign sessions, stale Confirmation/Undo fails, off-origin Actions fail and a disconnect does not duplicate a Mutation.
- At the Agent request boundary, use a fake provider with controlled costs, delays, failures and call counts. Check denial before a paid request, atomic reservations under concurrency, crash-before-settlement, duplicate settlement, all interpretation/advice/repair paths and durable shutdown.
- Exercise service restart, read-only/full storage, incompatible catalogue release, ledger corruption/loss and rollback through process or service interfaces, not mocks of private implementation details.
- At the browser/service lifecycle boundary, use a fake EC2 control service and real persistent coordination to verify admission, concurrent wake, bounded waiting, invitation expiry/revocation, idle expiry and stop/admission races. No cloud resources are needed for this rehearsal.
- Use account evidence and official pricing for infrastructure feasibility. Local tests cannot establish AWS entitlement, origin connectivity or cloud latency. Actual deployed acceptance belongs to CAP-07.
- Run focused regressions during each slice and the relevant full formatting, lint, test and build checks before closure. No paid model calls, resources or broad new test matrix are necessary for the initial local slices.

## Out of Scope

AWS provisioning or account upgrades; new spending permission; Bedrock adapter and
model qualification; actual cloud acceptance; RDS, Redis, Kubernetes, high
availability or automatic scaling; initial iPhone/Safari support; persistent shopping histories; real payments,
production customer accounts or arbitrary retailer support; prompt changes,
phrase matching, experimental retrieval activation or retraining classifiers.

## Further Notes

This is cloud-readiness work associated with CAP-04, not a replacement for the
CAP-05 through CAP-08 gates. CAP-04's parent remains unchanged and open. The final
design must distinguish completed local preparation from deployment procedures
and cloud tests still to be executed. Keep tracker copies local and ignored;
retain sanitized documentation in the repository. Only the owner and assistant
are available to do the work.
