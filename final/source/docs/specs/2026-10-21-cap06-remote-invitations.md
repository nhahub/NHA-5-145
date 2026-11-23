# Remote invitation authority: first AWS control component

**21 October 2026 — local implementation under the owner's continuation.**
This implements the invitation portion of the already approved Stockholm
architecture. It does not activate a new runtime backend, deploy resources,
change provider requirements or close CAP-04/05/06/07.

## Intent and boundary

The startup service and shopping host must consult one durable invitation
authority outside EC2. Host restart and code rollback cannot reset testing
windows, revocation or cumulative usage. Implement a DynamoDB invitation adapter
matching the existing InvitationStore interface, tested offline. Keep the SQLite
implementation and existing production/rehearsal configuration unchanged.

This is the first independently testable component of invitation plus wake/stop
control. Remote lifecycle arbitration, fenced EC2 commands, Lambda HTTP/OAC,
host integration and deployed acceptance follow separately. Do not connect the
existing local controller to EC2: its SQLite transaction cannot serialize a
remote DynamoDB decision with an unfenced external command.

## Preserved behavior

- Codes retain 192 random bits; persist SHA256 only. Subject identifiers are
  hashed as in the local adapter. Status exposes neither hashes nor grants.
- Explicit fixed start/end window, at most31days, start inclusive/end exclusive;
  at most20redemptions and100session creations per code, at most1000invitations.
- Same-subject redemption of the same active invitation is idempotent. A valid
  grant cannot switch to another invitation. Expired/revoked grants may be
  replaced without refunding the old invitation's usage.
- Final redemption/session slots are atomic under concurrent requests. Revocation
  and active-window conditions participate in the same transaction as consumption.
- Wake validation returns only a public invitation identifier. It neither redeems
  a code nor grants shopping/session authority. Lifecycle integration must later
  include an invitation condition in its own atomic wake transaction, rather than
  treating this earlier read as irrevocable permission to start EC2.
- Missing, corrupt, mismatched, inaccessible or uncertain authority fails closed.
  Runtime construction never creates a table, metadata, invitation or allowance.
  No TTL expiry, deletion, import or restore operation resets accounting.

## Storage and atomicity

Builder choice: use an existing regional table with string partition key `pk`
and sort key `sk`. A configured non-secret namespace forms the partition key;
this is one demo authority, not a multi-tenant product.

| Sort key               | Stored data                                                   |
| ---------------------- | ------------------------------------------------------------- |
| meta                   | schema1, initialized random identity, cumulative issued count |
| invitation#public UUID | code hash, fixed window, limits/counters, revoked flag        |
| code#SHA256            | invitation public UUID; no raw code                           |
| grant#SHA256(subject)  | invitation public UUID; no raw browser identity               |

All reads use the base table with ConsistentRead=true, not a GSI/cache. Every
write includes metadata identity/schema validation within TransactWriteItems.
Issue atomically increments the metadata count below1000 and inserts invitation
and code index with exclusive conditions. That transaction updates metadata once;
it must not also condition-check the same metadata item separately.

Redeem reads the code index, invitation and existing grant. First/new binding
atomically checks metadata, increments only the active nonrevoked invitation's
redemption counter below its limit and conditionally creates/replaces the exact
previous grant. Repeated same-invitation binding consumes nothing. Allocation
checks the unchanged grant and active invitation while incrementing the session
counter below its limit. Revocation is a monotonic flag update under metadata
and invitation existence conditions. No write can decrement counters or extend
the testing window. Do not automatically retry a failed transaction.

Replacement additionally condition-checks the old invitation as revoked or
expired in the same transaction (four items total). Not-yet-active or corrupt
old authority is not permission to replace it. Validate metadata afresh during
every operation; constructor validation is not cached lifetime authority.

Repeated same-grant redemption uses metadata, invitation and grant condition
checks in one transaction without updating counters. Concurrent contention may
refuse a caller once; it never retries a write to turn that refusal into success.
The backend has no server-current-time condition: check the finite caller clock
again after a successful transaction, and refuse if the invitation window ended
during I/O. Already committed counters remain consumed. Ongoing request/model
authority still needs its existing independent revalidation against revocation.

Explicit owner-only initialize first checks that the namespace is empty and
exclusively puts metadata. Refuse a nonempty namespace even if its metadata is
missing. Existing row writes require metadata, so competing initializers cannot
legitimately populate rows before the single winner's metadata exists.

Status uses a strongly consistent prefix Query for invitation rows,100perpage,
at most11pages/1000rows, validates them and returns the existing sanitized status
fields. A continued or corrupt result beyond those bounds refuses rather than
truncating evidence. No public issuance, status or revocation endpoint is added.

## SDK and uncertain outcomes

Inject a Boto3 low-level DynamoDB client. Require eu-north-1, the normal regional
HTTPS endpoint, finite connect/read bounds at most5/15seconds and
total_max_attempts=1. No client/session construction, credential lookup, endpoint
override, account login, network access or migration happens on module import.
The constructor performs only the explicit identity read through its supplied
client. Table/namespace/identity input is strictly bounded before any SDK entry.

Each write has a fresh UUID ClientRequestToken for that single transaction. The
SDK may not retry it; a returned timeout or unknown provider error refuses access
and remains uncertain. Do not refund, initialize, infer rollback from an immediate
read, or automatically repeat the write. AWS token idempotency is time-limited;
it is not an indefinite operation ledger. Preserve sanitized fixed error reasons
only, never provider messages, credentials, codes or browser data.

Builder choice: validate received record shape, numeric finiteness and window/
counter bounds before trusting it. Validate code/subject types and lengths before
hashing; reject invalid nonfinite owner inputs before storage. Finite clock and
UTC synchronization are prerequisites; lifecycle backward-clock handling remains
a separate component. Independent strongly consistent reads are not an atomic
snapshot; only conditioned transactions authorize quota mutations. Allowed/wake
reads are momentary checks and are revalidated by their eventual consumers.

## Offline verification and limits

Use pinned optional Moto DynamoDB emulation and dummy explicit SDK credentials;
intercept every SDK request in-process without live credentials or listening
ports. Pin the extra separately from base runtime requirements. Docker is not
running and only Java8 is installed; do not start Docker or install Java merely
for this component. Moto is an emulator, not AWS IAM/conflict/durability proof.

Exercise the real Boto3 request path and transaction semantics, reopening clients,
final-slot races, idempotence, replacement grants, revocation and exact boundaries.
Inject conditional conflicts, provider denial, committed-but-response-lost writes
and read failures: no automatic replay, reset, false grants or sensitive errors.
Use botocore Stubber or call instrumentation to pin strong-read/transaction
conditions and API bounds where emulator behavior is incomplete. Preserve all
existing admission/model/lifecycle regressions. No active configuration switch,
AWS request, table creation or paid model call is part of verification.

Before deployed adoption, qualify scoped IAM, actual regional table identity,
concurrency/latency, event-loop integration, costs, clock synchronization, host
restart/recovery, remote lifecycle transactions and revocation during work. This
component alone does not satisfy cloud acceptance or authorize EC2 commands.
