# Anonymous shopper isolation

Implementation date: 8 October 2026. Scope: the local Controlled Storefront.
The [approved design](superpowers/specs/2026-10-07-shopper-isolation-design.md)
and [implementation plan](superpowers/plans/2026-10-08-shopper-isolation.md)
define the boundary. This does not close CAP-04 or authorize public deployment.

## Implemented boundary

Each browser profile receives separate opaque HttpOnly Storefront and Agent
cookies. Storefront state owns its cart, revision, Undo, confirmations, fictional
login and completed orders. Tabs in one profile share commerce; task takeover
still requires the existing lease operation. A new task never clears the cart.

The Panel links its Agent authority through a 60-second challenge and one-use
Storefront ticket. Only the authenticated private service can redeem tickets or
register Agent confirmations. Manual confirmation uses the owning browser's
cookie, exact Origin and CSRF token. Public browser payloads cannot select an owner.
Personal responses and SSE use no-store caching.

Every session route checks ownership before task access. Streams check authority
and task expiry before each event; interpretation and advice check authority before
model calls and before publishing results. A non-authorizing context digest stays
outside semantic Snapshots and binds document/cart refresh data and Bridge envelopes
to the linked shopper. A cookie change cannot silently attach an old chat to a new
cart. The marker is not a credential and grants no server access.

First navigation/linking/session restoration is serialized across tabs with Web
Locks. Losing authority or a terminal event-connection failure disables chat and requires reload.
Transient SSE interruptions reconnect with cursor deduplication and fresh server
authorization; reconnecting does not resubmit shopping commands.
Only linking may retry once with a fresh challenge; shopping commands and uncertain
Actions are never automatically replayed.

| Lifetime / limit                            | Behavior                                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------------- |
| Commerce and Agent browser authority        | 24 hours without relevant browser activity                                      |
| Shopping session                            | Existing 30-minute inactivity expiry                                            |
| Storefront shoppers / Agent browser records | 100 each; reject excess rather than evict an active owner                       |
| Sessions                                    | 8 per browser; 800 globally, with expired-record cleanup and bounded tombstones |
| Link tickets                                | 60 seconds, one use, 400 globally and 4 per shopper                             |
| Agent challenges                            | 60 seconds and 4 pending per browser                                            |
| Agent restart                               | Old authority invalid; fresh task/link, surviving Storefront cart retained      |
| Storefront restart                          | Old generation invalid; empty commerce and fresh task/link                      |

These limits are conservative demo defaults, not measured public capacity. Deleting
a browser cookie cannot retroactively revoke the credential already presented on an
open connection: the next request observes the loss; a changed Storefront document
or cart response also invalidates the Panel. Server-side expiry/revocation closes
delivery directly.

## Regression and review evidence

Focused HTTP and browser checks cover equal-revision independent carts, copied Undo
and Confirmation tokens, fictional order privacy, foreign session route denial,
CSRF/Origin failures, ticket replay/expiry, capacity, in-flight revocation, between-event
expiry, document/SPA/cart-refresh identity changes, two-tab startup, and both process
restart directions. Existing fixtures now bootstrap real browser authority instead
of relying on global reset or unauthenticated session access.

The first integration checks exposed a chat-before-session startup race and lost
CSRF fields in refreshed cart forms. Independent Spec/Standards review then exposed
identity changes between documents/cart JSON, latest-order fixture selection,
between-event expiry and advice calls after catalogue-time revocation. These were
fixed with focused regressions. Both reviewers report no remaining actionable
findings on their final inspection.

Verification on 8 October 2026:

- All **511 distinct Python tests** have passing evidence across the full and focused
  runs; their IDs were compared with a fresh collection of the entire suite.
- All **169 TypeScript tests** passed across the package runs: Bridge 85, Storefront
  46 and Panel 38. Workspace builds, test-inclusive Panel/Bridge typechecks, ESLint,
  Ruff, repository formatting and Git whitespace checks passed.
- Independent Spec and Standards reviews have no outstanding actionable findings.
  The final SSE reconnect correction received an additional focused Spec review.
- Changed/staged-file credential-pattern and temporary-artifact checks passed.
  Evaluation services used ephemeral credentials; no local or provider secret was
  included. Local logs stay under ignored `work/shopper-isolation/`.

This is not a claim of one uninterrupted green full run. The full Python invocation
passed 468 tests before an outdated login fixture failed; that fixture was corrected.
The continuation passed 33 before exposing an SSE reconnect regression: transient
transport errors incorrectly reset the shopper. The client now preserves temporary
reconnects while terminal errors and explicit authority resets close delivery. The
credentialed SSE mock and its in-flight teardown were also corrected, then affected
SPA/isolation checks were rerun: the final combined set passed **14/14 in 160.37 seconds**.
The ten remaining usage checks passed separately.
An earlier integration run interrupted during review fixes is excluded from evidence.
No language interpretation, prompt or provider setting was changed.

## Operation and remaining gates

Run `python scripts/init_local_identity.py` once for normal local startup. It creates
an ignored, restricted `work/local-identity.json` and prints no credential. Production
must inject the service secret through server configuration and exclude
`/__internal/*` at the public proxy. Normal startup disables evaluation routes.
Configured public origins require HTTPS except explicit local development origins;
browser/cloud origin wiring remains a deployment task.

No provider calls, AWS resources, account changes, spending-cap changes, push or
deployment were performed for this slice. Public same-site HTTPS/cookies, durable
global inference allowances, abuse controls, qualified Bedrock access and measured
concurrency remain CAP-04/05/06 gates. Fictional login remains demonstration UI;
this is not real account authentication, durable commerce or production readiness.
