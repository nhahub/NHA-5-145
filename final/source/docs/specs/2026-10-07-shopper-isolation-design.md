# Shopper isolation before public deployment

**Status:** owner approved and implemented locally on 8 October 2026; see the
[verification record](../shopper-isolation-verification.md) for checks and remaining deployment gates.
**Requested:** 7 October 2026. The owner authorized fixing the single-shopper limitation before deployment.

## Outcome and limits

Independent shoppers using the Controlled Storefront must have separate carts, cart revisions, Undo records, fictional login state, fictional orders, conversations and Action authority. No shopper may read, clear, confirm, resume, stop or take over another shopper's work, even if they know its identifiers. Preserve normal shopping, ten-second Undo, thirty-minute task expiry and explicit tab takeover. Cart state must outlive a Copilot task and Start over must not empty it.

For this graduation demo, a shopper is identified by a server-issued browser session. Tabs in the same browser profile share that shopper's cart; another browser profile/private context/device is independent. Fictional login remains a demonstration, not real authentication or cross-device account recovery. Persistent commerce storage and production accounts remain outside this slice. Application restart may discard shopping state, with a visible reset and no uncertain Action replay.

The AWS account stays on its Free plan. This work is local and makes no paid calls, account changes or deployment. Public HTTPS, global spending limits, abuse protection and Bedrock qualification remain separate deployment gates in the [CAP-04 constraints](../cap04-credit-only-plan.md).

## Findings before implementation

- `store/src/app.ts` constructs one `GuardedCart` for all requests. Its lines, revision, orders, confirmation ledger, Undo and operation deduplication therefore share one ownerless lifetime.
- Agent session endpoints use session IDs and tab IDs without an independent authenticated shopper binding. Tab leases coordinate execution; they are not an authorization boundary.
- `agent/app.py` registers confirmations against a Storefront URL without identifying the owning shopper. The public registration endpoint is also used by manual cart clearing.
- Fictional login tokens live in a separate set, and `renderOrders()` returns demonstration history rather than the shopper's completed checkout history.
- Storefront test reset/seed/state routes are currently registered unconditionally. They must not become a public bypass.

## Approaches considered

| Approach                                                                   | Consequence                                                                                                                                                    |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Per-shopper state and explicit service ownership binding — recommended** | Fits the current app, supports concurrent testers and preserves ephemeral demo storage. Requires ownership checks in both services and a browser linking flow. |
| One complete application process pair per shopper                          | Stronger process separation but provisioning, routing and resource overhead are inappropriate for the credit-limited demo.                                     |
| Real accounts plus durable database sessions and orders                    | Enables cross-device persistence but introduces a much larger authentication/storage scope than requested.                                                     |

## Identity and service boundary

Use server-generated opaque random browser credentials in HttpOnly cookies. Never accept an arbitrary shopper ID from a form, URL, Snapshot or localStorage as proof of ownership. Cookie values, link tickets and service credentials must not enter LLM context, conversations, event URLs, logs or evaluation traces. Production cookies require HTTPS/Secure, host-scoped paths and explicit SameSite behavior; localhost gets a narrowly configured development exception.

The Storefront owns the shopper's commerce state. The Agent owns its browser credential and binds its sessions to the verified Storefront shopper. Keep credentials host scoped rather than depending on a shared parent-domain cookie or cookies crossing unrelated hosts.

Proposed link flow:

1. The Panel obtains an Agent browser cookie and a short-lived server-stored linking challenge. There is no model call or shopping Action at this stage.
2. Through the existing exact-origin/source-checked channel, the Panel asks the Storefront Bridge to link that challenge. The Storefront authenticates its own cookie and issues a short-lived opaque ticket for that shopper and challenge.
3. The Panel submits the ticket to the Agent with its own cookie. The Agent redeems it over the configured private Storefront service connection. Redemption requires service authentication, consumes the ticket once and verifies audience, challenge, expiry and the Storefront boot generation.
4. Only then may the Agent create or restore a session. A ticket from another browser's challenge cannot replace an existing shopper binding. An intentional identity change clears old browser session references and requires a fresh link; it never adopts old work.

This handshake is infrastructure identity, not an LLM decision. Raw Storefront cookie values need not leave the Storefront origin. A server-managed service credential protects private redemption and Agent confirmation registration; it is never shipped to browser code. Missing service configuration fails closed. Local startup tooling may create a restricted ignored configuration file; examples contain placeholders only. Deployment supplies the credential separately and blocks private routes at the public proxy as an additional layer.

Keep the deployed Panel and Storefront on separate origins within a tested same-site topology. Do not depend on browsers accepting third-party cookies across unrelated public domains. Selecting the domain-free HTTPS topology remains CAP-04 work; this slice must not claim it is solved by localhost tests.

## Small modules and ownership rules

- **Storefront shopper registry:** owns cookie-to-shopper lookup, expiry, bounded capacity and one `GuardedCart` plus fictional login state per shopper. Request adapters resolve that state explicitly; no global current-shopper variable. Product catalogue data can remain shared and immutable.
- **Linking and private service adapter:** owns challenges, tickets, expiry/one-time consumption and service authentication. It does not interpret shopping language or grant Confirmation.
- **Agent access adapter:** owns browser-to-shopper binding and session authorization. Apply it to every state, message, answer, result, retry, reconcile, Stop, takeover and SSE route before touching session state or starting paid work. Unknown and foreign sessions return the same non-disclosing response.
- **Shopping Task execution:** retains the existing transition and safety logic. Associate sessions with their verified shopper; resolve internal confirmation registration from this association, never from caller-supplied ownership data.

Agent-to-Storefront confirmations carry the verified shopper and boot generation as authenticated service data, plus the existing task/token/kind/revision binding. Manual confirmation issuance operates only on the authenticated browser's cart, with CSRF protection and server-issued tokens. It must not accept a different shopper target. Existing confirmation expiry, single-use and stale revision guards remain mandatory on both paths.

Storefront routes for cart/state, add, quantity, removal, Undo, clear, checkout and order completion use the request's shopper state. Order history renders that shopper's actual fictional orders. Any demonstration seed history is either explicitly marked and instantiated separately per shopper or removed; never mix another shopper's order into it. Read and write authorization is required even when order IDs are unguessable.

Require explicit origin/CSRF protection for browser mutations; CORS alone is insufficient. Personalized responses and streams must not be cached/shared. SSE authorization must remain valid for the stream lifetime; revoked/expired ownership closes delivery, including narration and conversation events, not just Actions. Private/test routes are disabled in normal startup and enabled only in explicit evaluation configuration.

## Lifetimes and restart behavior

Keep Agent task expiry at thirty minutes. Give commerce state an explicit separate inactivity lifetime (proposed twenty-four hours), bounded registry size and cleanup. Do not evict an active shopper to admit another: capacity exhaustion rejects new admission visibly. Activity and cleanup tests use injected clocks.

After Storefront restart, previously bound Agent sessions must fail closed because their commerce generation no longer exists. After Agent restart, its old cookies/sessions cannot authorize pending work; the surviving Storefront cart may remain, but a fresh link and fresh Shopping Task are required. Browser refresh can resume only the same valid shopper and task after Snapshot reconciliation. Account/session expiry never authorizes pending mutation replay. Keep the future global spending ledger separate from these disposable registries.

## Acceptance evidence

Use existing regression tests and a focused suite at HTTP and real-browser seams. No live LLM is needed to prove isolation.

1. Two independent browser contexts add different products concurrently; quantity edits, removal, Undo, refresh and Start over affect only their own cart. Same-profile tabs share the cart while retaining task lease/takeover rules.
2. Checkout creates an order visible only to its owner. Foreign order URLs, cart-state requests, guessed session IDs and copied tab IDs cannot disclose another shopper's data.
3. Cross-shopper read, SSE, Stop, answer, result, reconcile, retry, takeover, Confirmation and Undo attempts fail without changing either shopper's state. Cover equal cart revisions and identical product variants so revision coincidence cannot mask an ownership bug.
4. Missing/forged cookies, mismatched/replayed/expired link tickets, missing service credentials, hostile Origin/CSRF requests and private-route exposure fail closed. No browser payload can choose an arbitrary shopper.
5. Expiry, capacity exhaustion, Agent-only restart and Storefront-only restart produce deterministic reset/denial; no stale Action or uncertain mutation replays. SSE stops after authority expires.
6. Existing origin, Sensitive Field, Confirmation, duplicate/stale Action, recovery and tab-lease regressions still pass. Scan changed browser/network evidence for credentials; confirm source-controlled files contain no secrets.

Run focused checks during implementation, then format/lint/typecheck/build and the complete existing regression suite once. Independent Spec and Standards reviews must resolve actionable ownership findings before committing implementation. Record exact evidence and remaining cloud gates; passing local isolation does not itself authorize public deployment.

## Review and implementation handoff

This design selects anonymous browser-bound shoppers, separate ephemeral commerce state and a verified cross-service linking boundary. It deliberately does not silently turn the fictional login into real account authentication. The implementation now covers Storefront ownership, linking/Agent authorization, browser integration and adversarial multi-shopper verification in the isolated `feature/shopper-isolation` branch. Unrelated working-tree changes are preserved. Public deployment remains gated separately; see the verification record above.
