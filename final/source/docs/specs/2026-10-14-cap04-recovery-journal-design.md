# CAP-04 recovery journal: superseded no-domain proposal

Date: 14 October 2026. Status: not selected; not implemented.

The owner initially approved this proposal, then purchased `scpilot.tech` before
implementation began and approved sibling origins instead. Retain this document
as decision history, not an active implementation plan. See the
[replacement HTTPS plan](../cap04-domain-https-plan.md). No journal or
production runtime changes were made.

## Intent and constraints

Keep the no-purchased-domain, zero-cash controlled demo while preserving separate
Panel and Storefront origins. Allow Chrome/Edge privacy settings to deny embedded
web storage without losing Action deduplication or navigation recovery. Preserve
existing cart isolation, bound Confirmation, Undo and no uncertain Action replay.
No extra cloud database, model calls, prompt changes or phrase interpretation.

## Comparison and recommendation

The sibling-hostname local experiment removes the storage blocker while retaining
different origins and existing Strict host-only cookies. It needs a shared domain
we control. Different generated CloudFront distribution hostnames do not supply
that relationship because cloudfront.net is a public suffix. Same-origin paths
would remove the DOM isolation boundary; reversing the frames would move the
storage problem into the Panel, which also requires browser storage.

Under the current no-domain requirement, prefer a first-party Action journal.
If the owner chooses to supply a suitable domain instead, prefer the simpler
sibling-hostname layout and do not implement this journal migration just in case.
The experiment does not qualify any AWS topology, account entitlement or cost.

## Proposed ownership

The top-level Panel hosts a narrowly scoped Action journal backed by its own
sessionStorage. The embedded Bridge uses a request/reply channel and never opens
embedded sessionStorage. This is not a generic remote-storage API: the journal
exposes reservation, navigation preparation/reconciliation and task retirement.
It stores Action identity/order, retirement and minimal pending-navigation data,
not chat text, DOM snapshots, product recommendations or credentials.

The journal is a client-side replay/recovery guard. Existing Agent ownership and
Storefront revision/idempotency/Confirmation checks remain authoritative; possessing
journal data does not authorize a Mutation or prove an uncertain Action succeeded.

## Channel and namespace

- Bind messages to exact configured origin, exact current frame WindowProxy,
  protocol version, linked Shopper context, current Agent session and tab lease.
- Initialize only after authenticated Shopper linking and Agent session resolution.
  Initial read-only Snapshots may bootstrap session reconciliation before journal
  readiness; no Action executes until both current ownership and journal are ready.
- Issue a fresh document channel nonce for each iframe navigation and a fresh
  binding epoch on relink or lease change. Reject delayed replies/requests from
  old documents, tabs, Shopper generations, sessions or retired epochs.
- Namespace persistent state by linked Shopper generation, Storefront origin,
  Agent session and tab authority. Do not carry a previous Shopper's journal into
  a new binding. An iframe cannot choose an arbitrary namespace or storage key.
- Match a reservation to the exact pending Action delivered to that frame by the
  Panel; an iframe-supplied identifier alone cannot nominate a new authorized Action.
  Match full typed Action semantics when deciding whether a retry is identical.

## Journal operations and persistence ordering

| Operation             | Required behavior                                                                                                                                                                      |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reserve Action        | Atomically validate active task/order, persist acceptance before execution acknowledgement; return duplicate/stale for a consumed Action.                                              |
| Prepare navigation    | Persist pending Action identity and target before DOM navigation or guarded form submission starts.                                                                                    |
| Reconcile document    | Return only the pending navigation allowed by the bound session, then reconcile a fresh Snapshot against Agent state. Never infer a Mutation succeeded merely because a record exists. |
| Finish reconciliation | Idempotently acknowledge completion after the corresponding Agent result is accepted; a lost acknowledgement may resend the same result, never re-execute the Action.                  |
| Retire task           | Persist retirement and reject older queued reservations, including reordered Stop and late Action deliveries.                                                                          |

Serialize state transitions within the Panel journal. The Bridge must not implement
an asynchronous read-modify-write reservation across separate storage RPCs. Write
the resulting record successfully before acknowledging; a quota or storage error
prevents execution. Put conservative payload/record limits around the interface.

A known-empty new Agent session may initialize a journal once. Missing or corrupt
state for an existing session does not become a fresh ledger: reconcile and stop
execution until authority can be recovered or the user explicitly starts a fresh
Shopping Task. The implementation must define that bootstrapping distinction using
actual Agent session state, not rely solely on a marker lost with the same storage.

## Refresh, navigation, takeover and failure

An iframe navigation gets a new document channel but can reconcile the journal
owned by the same first-party tab. A full Panel refresh restores sessionStorage,
reauthenticates/reacquires ownership and issues fresh channel authority. Tab closure
may discard that tab's journal; it must not cause uncertain work to replay.

Lease takeover follows the existing Agent reconciliation contract. Do not copy
another tab's authority or reset order counters to make the new tab work. While
reconciliation is uncertain, permit observation and Stop but no new Mutation.
Agent-only restart invalidates task authority while preserving a surviving cart;
Storefront restart changes Shopper context and invalidates old journal bindings.

Timeouts, duplicate responses, storage loss, invalid data and channel closure
produce visible safe refusal. No in-memory fallback, direct iframe DOM access,
privacy-setting change, wildcard postMessage destination or automatic replay.

## Verification before adoption

Primary seam remains the actual browser through the HTTPS proxy with an unrelated
Storefront site, real third-party blocking and the independent cookie negative
control. Only the Storefront cookie becomes Secure/SameSite=None/Partitioned.
Exact origin/CSRF checks stay in place. Test desktop Chrome and Edge; report Android
hardware as unverified until tested, not as covered by desktop emulation.

Use focused journal/channel tests for concurrent duplicate reservation, delayed
old-document replies, wrong source/origin, forged Shopper/session/tab bindings,
retirement races, storage exceptions/corruption/loss, and write-before-execution.
Use browser tests for product navigation, Agent cart Mutation, visible Confirmation,
Undo, two Shoppers, two tabs/takeover, iframe navigation and Panel refresh, plus
SSE disconnection after an actual Action. Check authoritative cart revision and
Mutation request count, not only text or a connection-status indicator.

Introduce and verify one concern at a time: atomic journal behavior; bound channel;
Bridge integration and reconciliation; strict-profile browser acceptance. Run the
existing relevant safety suite and independent reviews before any production
adoption. Ticket 03 remains blocked until these results pass. This proposal does
not close ticket 01 or CAP-04 and does not authorize AWS resources or spending.
