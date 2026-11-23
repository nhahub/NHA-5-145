# CAP-04 browser identity feasibility: negative result

Date: 13 October 2026. Scope: local ticket 01, not deployed AWS acceptance.

> Follow-up: the owner selected sibling hostnames on 14 October after buying a
> domain. See [the passing comparison](2026-10-14-cap04-sibling-hostnames.md).
> The negative unrelated-site result below remains valid.

## Decision

Do not adopt the proposed unrelated-site topology with only a cookie change.
Partitioned cookies restore embedded cart HTTP authority, but the current Bridge
cannot initialize when the tested browser privacy setting denies iframe
`sessionStorage`. Ticket 03 remains blocked on a successful supported-browser
proof. The parent CAP-04 remains open. No runtime source or provider was changed.

## Reproduction and controls

The disposable [runner](../../eval/probes/cap04_cross_site.py) and
[proxy](../../eval/probes/cap04_https_proxy.mjs) are evaluation-only. They serve built
Panel/Bridge assets and existing services through loopback HTTPS at
`panel.copilot.test` and `store.merchant.test` on port 4443: different registrable
sites, not different localhost ports. Public asset origin literals are rewritten
in transit because production origin configuration belongs to ticket 03. The
proxy changes only the Storefront cookie attributes between three experiments.

OpenSSL generated a two-day CA constrained to the two test domains and a leaf
certificate naming both hosts. The owner approved temporary trust in the Windows
current-user root store. Default browser TLS verification remained enabled; the
probe asserted a secure context and TLS 1.2/1.3. No certificate bypass, public DNS
change or system-wide trust install was used. Each exact CA was removed afterward,
absence verified, and generated private keys removed. Browsers used fresh owned
profiles; personal profiles were never opened.

Each profile set `profile.cookie_controls_mode=1`,
`profile.block_third_party_cookies=true`, and
`tracking_protection.block_all_3pc_toggle_enabled=true`, plus the CDP cookie
restriction and phaseout test flag. The actual iframe received independent
unpartitioned and partitioned control cookies. Every counted run observed the
unpartitioned cookie absent and partitioned cookie present on the next request.
This observed control, not a launch flag alone, establishes cookie blocking.

| Browser on Windows | Version       | Cookie negative control | Strict / ordinary None cookie | Partitioned cart HTTP | Bridge session storage        |
| ------------------ | ------------- | ----------------------- | ----------------------------- | --------------------- | ----------------------------- |
| Installed Chrome   | 154.0.8037.98 | Passed                  | Both 401 / input disabled     | 200                   | SecurityError; input disabled |
| Installed Edge     | 155.0.4283.45 | Passed                  | Both 401 / input disabled     | 200                   | SecurityError; input disabled |

Both browsers returned: `Failed to read the 'sessionStorage' property from 'Window': Access is denied for this document.`
The Agent linked the partitioned Storefront identity and created a session, but
Bridge startup failed before providing the usable Snapshot needed by the Panel.
The relevant dependency is the Bridge bootstrap's direct `window.sessionStorage`
access; it backs the Action ledger and pending navigation recovery. Silently
replacing that storage with an empty in-memory dictionary would lose important
replay/recovery protection and is not an accepted fix.

## Preliminary experiment and limits

Before explicit profile preferences were applied, Playwright Chromium 153.0.8010.12
with CDP/phaseout controls passed the cookie control and the shopping journey:
product navigation/add, quantities 1 versus 3 in separate browser contexts, refresh,
second-tab ownership, visible Confirmation before clear, exact Undo and CSRF
rejection. Embedded cart state also differed from direct top-level Storefront
state. These are preliminary observations under narrower controls, not acceptance
for ordinary browser privacy settings. The initial reconnect check observed no
cart revision change but did not establish that a new SSE connection occurred;
the durable runner now requires an observed new stream, but names this only
connection restoration. Browser B had no Agent Action to replay, so neither check
qualifies Agent Action replay protection. The stronger stream check was not reached
in the strict-profile runs; replay qualification remains open.

An early Chrome 154 CDP-only run accepted the unpartitioned control cookie. It was
rejected as invalid test setup, not counted as an application pass. Explicit fresh
profile preferences exposed the Bridge dependency in both installed browsers.
No claim is made for Android hardware, iPhone/Safari, EC2, CloudFront, five-Shopper
capacity, real model latency or full safety acceptance under the failed topology.
No paid inference or AWS resources were used.

## Next engineering decision

Keep the privacy requirement. Evaluate a recovery journal hosted by first-party
authority with exact Shopper/tab/task binding, or revise the serving topology to
avoid this third-party storage dependency. Either design must preserve completed
Action deduplication, pending navigation reconciliation, Confirmation, Undo and
uncertain-outcome handling through refresh and navigation. A memory-only fallback
or instructing Shoppers to disable privacy is not an acceptable resolution.

Rerun this same negative control and the full browser journey after a reviewed
solution exists, before ticket 03 adopts production routing. Account/network
costing (02) and the independent durable allowance work (05) can still proceed.

## External references

- [Chrome DevTools Network controls](https://chromedevtools.github.io/devtools-protocol/tot/Network/#method-setCookieControls) provide test controls; this probe also verifies their effect through an iframe negative control.
- [Chrome cookie inspection documentation](https://developer.chrome.com/docs/devtools/application/cookies/) describes partition keys and cookie attributes.
- [Google's third-party restrictions guidance](https://privacysandbox.google.com/cookies/prepare/overview) distinguishes settings, policies and test flags. The specific sessionStorage failure above is direct local evidence, not inferred from cookie documentation.

## Verification

Browser experiment produced the explicit negative result above. The full existing
Python suite passed: 619 tests in 512.18 seconds. The two added cleanup failure
tests passed separately after the fix. All 182 TypeScript tests passed (85 Bridge,
38 Panel, 59 Storefront). Workspace builds, repository Prettier/ESLint and Ruff
format/lint checks passed. No new production code was needed for this investigation.

## Standards review

The independent reviewer identified one cleanup safeguard defect: a process-stop
failure could skip certificate removal. Cleanup now attempts each resource
independently, persists failures and exits nonzero. Two focused tests observed red
before the fix and green afterward, simulating process-stop and certificate-removal
failures without touching real trust. The reviewer confirmed resolution; no
outstanding standards findings.

## Spec review

The independent reviewer identified one evidence overclaim: browser B had no Agent
Action to replay, so its reconnect could prove only connection restoration. The
runner label and report now state that replay qualification remains unverified.
The reviewer confirmed resolution; no outstanding spec-review findings. This does
not turn the negative feasibility result into a supported-browser pass.
