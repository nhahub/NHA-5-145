# CAP-04: sibling-hostname browser feasibility

Date: 14 October 2026. Scope: local ticket 01; not AWS deployment acceptance.

## Decision

The owner purchased `scpilot.tech` through .tech Domains and approved
`app.scpilot.tech` for the Panel/Agent and `store.scpilot.tech` for the Storefront.
Adopt sibling HTTPS hostnames for production configuration work. The no-domain
journal proposal was approved first, then superseded before implementation. No
production runtime, prompts, cookies or recovery code changed in this experiment.
AWS remains credit-only. [DNS/HTTPS preparation](../cap04-domain-https-plan.md).

The [unrelated-site failure](2026-10-13-cap04-browser-proof.md) remains valid:
partitioned cookies alone did not make embedded sessionStorage available. The new
result uses a different approved layout; it does not repair or qualify that layout.

## Reproduction and controls

Run the [probe](../../eval/probes/README.md) with `--layout same-site` and installed
`--channel chrome` or `--channel msedge`. Panel is
`https://panel.copilot.test:4443`; Storefront is
`https://store.copilot.test:4443`. These are separate origins under the same site.
The original `--layout cross-site` remains the default negative experiment.

Each browser uses a fresh owned persistent profile with explicit third-party
cookie blocking, CDP restrictions and the phaseout test flag. A separate iframe at
`https://store.merchant.test:4443` verifies the restriction: its unpartitioned
SameSite=None cookie is absent and its partitioned cookie is present. A same-site
Storefront cookie is not used as proof of third-party blocking.

TLS uses default browser verification with a short-lived CA restricted to
`copilot.test` and `merchant.test`, installed temporarily in CurrentUser Root
under the owner's existing approval. No public DNS, personal profile, system-wide
trust or certificate bypass is used. Cleanup removes the exact CA and private
keys and fails loudly if removal cannot be verified. TLS 1.2/1.3 and secure context
are asserted. Services use a scripted provider and isolated scratch catalogue.

## Observed results

| Browser on Windows | Version       | Cross-site negative control | Sibling storage / DOM isolation | Shopping journey |
| ------------------ | ------------- | --------------------------- | ------------------------------- | ---------------- |
| Installed Chrome   | 155.0.8059.40 | Passed                      | Passed                          | Passed           |
| Installed Edge     | 155.0.4283.45 | Passed                      | Passed                          | Passed           |

Chrome updated since the earlier 154 negative run; these versions come from the
current result files, not an assumption of a fixed browser installation.

Both runs observed:

- Storefront sessionStorage round-trip succeeds; the frame cannot read parent DOM
  and the parent cannot access the frame document.
- Existing Storefront cookie remains Secure, HttpOnly, SameSite=Strict and scoped
  to its host. No parent-domain cookie or partitioned production cookie is needed.
- Product-page navigation/add yields quantities one and three in separate browser
  profiles. Panel refresh retains the owner's cart. Direct top-level Storefront
  shares that profile's cart in this layout.
- A second Panel tab shares the cart but requires explicit takeover for the task.
  This probe observes the takeover requirement; it does not claim a completed
  takeover-and-resume test.
- Agent clear-cart waits for visible Confirmation and affects only the owner's
  cart. The exercised Undo restores the exact prior empty cart after an add.
- Browser B completes its own Agent clear-cart before the proxy deliberately
  disconnects B's SSE stream. A new stream is observed with `Last-Event-ID: 7`
  even though its URL's initial `after` query remains zero. After 1.5 seconds
  (more than two server polling intervals), cart revision and cart POST count
  remain unchanged. This qualifies this completed-mutation reconnect scenario,
  not every in-flight disconnect or lost-result case.
- A cart request missing CSRF is rejected with HTTP 403.

The local evidence files are ignored `result-chrome-same-site.json` and
`result-msedge-same-site.json` under `.scratch/cap04-cloud-readiness/probe/`.
Both record `outcome: passed`, zero paid calls and successful CA cleanup. Raw
logs and TLS material are not published. The reproducible harness and this
sanitized report are the reviewable evidence.

## Harness corrections and limits

Initial sibling-mode runs exposed test setup problems: buffered empty-stream
headers made connection counting unreliable, and toggling Playwright offline did
not reliably drop an established stream. The proxy now flushes headers and exposes
a loopback-only evaluation endpoint that disconnects only the requesting browser's
streams, requiring exact Panel Origin and its existing cookies. It is not a
production endpoint. The test verifies a real new stream, nonzero native cursor,
and a prior actual Agent Mutation before counting the reconnect result.

Ticket 01 is resolved for desktop layout feasibility under the approved domain
amendment. Ticket 03 may now implement actual public-origin configuration. Android
hardware remains untested and required in ticket 08/deployed acceptance; desktop
emulation would not establish it. No claim is made about AWS entitlement, public
DNS/TLS, CloudFront behavior, five-Shopper capacity, real-model latency, complete
recovery coverage or production readiness. The parent CAP-04 remains open.

The probe still rewrites public-origin literals in served assets. That technique
must be replaced in ticket 03; this proxy must never be deployed. DNS ownership
solves the browser site relationship, not infrastructure cost or availability.

## Verification and review

Both installed-browser runs passed after the native-cursor assertion was added.
The two cleanup failure regressions passed, along with all 182 TypeScript tests
(85 Bridge, 38 Panel, 59 Storefront), workspace builds, Panel/Bridge typechecks,
repository Prettier/ESLint and Python Ruff checks. Relative document links and
`git diff --check` passed. Both exact test CA thumbprints were independently
checked absent from CurrentUser Root and no generated private keys remained.
The full Python application suite was not repeated for this probe/documentation
change; its earlier 619-test result belongs to the prior report.

Independent Spec review found no actionable findings. Standards review initially
noted stale checkpoint/handoff frontier text; those documents were synchronized
and re-reviewed with no remaining findings. No runtime sources, public DNS, cloud
resources, paid model calls or provider limits changed. This work is committed
locally; no push is part of this step.
