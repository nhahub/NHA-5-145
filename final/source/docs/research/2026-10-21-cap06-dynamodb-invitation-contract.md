# CAP-06 DynamoDB invitation contract: offline preparation

Checked 21 October 2026 against public primary AWS documentation using agent-reach's
Jina web reader. This note recommends an implementation contract for the existing
`agent/admission/store.py`; it does not establish account access, provisioning,
cloud acceptance or production readiness. No authenticated requests, resources,
installs, model calls or emulator execution occurred. CAP-05 remains blocked by
the recorded Stockholm account quotas; this research grants no spending authority.

## Preserve the local contract

Keep SHA-256 code and subject digests, independently generated high-entropy raw
codes returned only at issue, absolute finite windows of at most 31 days,
1–20 redemptions and 1–100 cumulative sessions per invitation, and at most 1,000
issued invitations. Expiration/revocation must not free capacity, restore counters,
or delete grant history. Same-subject redemption of the same currently active
invitation succeeds without another redemption; a different currently valid grant
blocks replacement. These are existing repository requirements, not DynamoDB
defaults.

A suitable bounded layout is one configured table, `pk=<namespace>`, and `sk` equal
to `meta`, `invitation#<UUID>`, `code#<SHA256>` or `grant#<subject-digest>`. The code
item maps its digest to an invitation ID. Read this base-table key directly with
`ConsistentRead=True`; a GSI cannot provide strong reads. Validate schema version,
configured authority identity and item shapes before trusting data. Missing or
incompatible metadata denies access; runtime must never create/repair authority.
This layout and validation policy are recommendations. [AWS read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html).

## Transaction facts and consequences

`TransactWriteItems` commits all actions or none. It accepts at most 100 distinct
items and 4 MB total; an individual item cannot exceed 400 KB. It cannot target an
index. A transaction cannot both `ConditionCheck` and `Update` the same item:
put the conditions on that item's update instead. [AWS TransactWriteItems API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html).

Recommended write shapes:

- **Issue:** one metadata update conditioned on schema/identity and issued count
  below 1,000, incrementing the cumulative count; conditional puts for the fresh
  invitation and code index. Never calculate capacity using a scan/count followed
  by an independent write.
- **Redeem:** metadata identity check, code mapping check, target invitation
  counter update conditioned on active absolute window, not revoked and remaining
  redemptions, plus a conditional grant put/replacement. All conditions and the
  increment belong to one transaction. A replacement must bind the exact observed
  old grant and establish that its old invitation is invalid in that transaction.
  Do not include a second action for the target invitation when the keys coincide.
- **Allocate session:** condition the grant on its observed invitation and update
  that invitation only if active, unrevoked and below its cumulative session cap.
  Include the metadata identity condition. Revocation updates that same invitation
  under the metadata condition, so it participates in the serialization boundary.

These are applications of AWS conditional transaction actions, not a claim that a
pre-read authorizes a later write. A shared metadata `ConditionCheck` validates
identity; only its issue-time conditional update enforces the global count.
[AWS transaction actions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-apis-txwriteitems).

Transactions are serializable with other transactions and individual standard
reads/writes. Several separate strong `GetItem` requests do not form one snapshot:
a concurrent transaction can fall between them. `TransactGetItems` supplies an
atomic snapshot, also bounded to 100 items/4 MB. For pointer discovery, first read
the grant/code, then transactionally read metadata, pointer and referenced
invitation together and reject if the pointer changed. Alternatively, bind every
observed dependency into the eventual write conditions. Revalidate active window
and revocation on every access; cached grants are insufficient. Time predicates
use a trusted application clock: DynamoDB does not supply a server-side `now()`
in these conditions. A supplied timestamp cannot advance during a slow request;
check expiry again before returning positive authority, without refunding a
committed counter. [AWS isolation and transactional reads](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-isolation),
[AWS condition-expression operands](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.OperatorsAndFunctions.html).

## Idempotency, conflicts and uncertain outcomes

Use an explicit stable operation token with a frozen request payload.
`ClientRequestToken` accepts 1–36 characters and deduplicates for ten minutes after
the first request completes. Changing another parameter inside that window causes
`IdempotentParameterMismatchException`; after the window the same token represents
a new operation. This is not durable application idempotency and must not replace
the same-subject grant condition. Regenerating a token or changing `now` creates a
different request contract. [AWS token contract](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html#API_TransactWriteItems_RequestParameters).

Explicitly configure `Config(retries={"mode": "standard", "total_max_attempts": 1})`
and bounded connection/read timeouts. This means one attempt including the initial
request; environment defaults otherwise permit SDK retries. Keep application write
retries disabled for this slice. [Boto3 retry configuration](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html).

A transaction canceled for a condition failure/conflict makes no partial changes;
fail closed and map only known safe reason codes. Transport timeout, HTTP 500 or
`TransactionInProgressException` must not be treated as proof that nothing
committed. AWS documents that a write returning 500 may have succeeded. A read
showing no change cannot prove an in-flight request will not later commit.
Therefore retain consumed/uncertain quota state and deny automatic replay. A fresh
authoritative snapshot may establish an already-committed same-subject redemption;
it must still pass current revocation/window checks. Session allocation has no
durable operation receipt in the candidate layout: do not promise exactly-once
retry recovery for it, or silently refund a possibly consumed session. Any future
replay/reconciliation protocol needs a separately specified durable operation
identity. [AWS conflict handling](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html#transaction-conflict-handling),
[AWS write-error uncertainty](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Programming.Errors.html),
[AWS in-progress transaction error](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html#API_TransactWriteItems_Errors).

## Persistence and offline verification limits

Do not enable TTL deletion for authority items. TTL removes expired items within
days, so it is neither immediate revocation nor a safe retention policy for
nonresetting counts. Initialization/migration is an explicit owner-controlled
operation against a fresh authority, never startup behavior or recovery from
missing metadata. [AWS TTL behavior](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html).

DynamoDB Local >=2.6.0 requires Java 17 or newer. It accepts fake credentials;
use explicit test-only credentials, Region and loopback endpoint, with no profile
or credential-chain fallback. AWS's `localhost:8000` example is a client address,
not proof that the server listens only on loopback. Verify/isolate its listener;
do not expose it to a LAN. The documented default CORS allowlist is `*`. Disable
telemetry with `-disableTelemetry`. Use isolated disposable authority state for
tests; persistence/restart tests need a retained database path rather than
`-inMemory`. These safety controls are recommendations grounded in the emulator's
documented behavior. [AWS Local prerequisites](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html),
[AWS Local usage notes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.UsageNotes.html).

Local is for development/testing and does not reproduce cloud throughput,
account/Region isolation or transactional conflict exceptions. Exercise the real
SDK against it for expressions, atomic counters, replacement, persistence and
revocation, then inject conflict, timeout-after-commit and corrupt/missing-state
faults at the client boundary. Local success does not qualify IAM, cloud race
behavior or deployed durability. Status queries require pagination through
`LastEvaluatedKey`; even strong paginated queries are not one transactional
snapshot. [AWS Local differences](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.UsageNotes.html#DynamoDBLocal.Differences),
[AWS Query pagination](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.Pagination.html).
