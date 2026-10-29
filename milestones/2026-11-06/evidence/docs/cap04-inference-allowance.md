# Durable inference allowance: CAP-04 local ticket 05

This is a local, provider-neutral spending boundary, tested without paid calls.
It is not Bedrock price/access qualification or deployed capacity evidence.

## Ownership and persistence

Use one Agent worker on the approved single host. Every interpretation, advice,
retrieval decision and repair shares the configured LLMClient decorator. Admission
has explicit finite active/waiting bounds and a bounded queue timeout. SQLite
transactions atomically protect the global allowance even across separate ledger
objects/processes. Queue/concurrency bounds are per Agent process; multi-worker
capacity is not qualified and is outside the deployment topology.

The ledger belongs outside disposable releases on the encrypted persistent disk.
Its identity and schema must match configuration. Runtime opening uses `mode=rw`:
missing storage cannot create a new allowance. Corrupt, incompatible, full or
unwritable storage refuses new inference. A ledger that grows beyond its configured
page bound also refuses. Busy/storage/disabled/budget states pause the Shopping Task
before any proposed Action is delivered. Known settlement failure also suppresses
the returned completion. Unknown-cost completion also rechecks persistent storage
and its original reservation before exposing text; it never refunds the reservation.

When this boundary is configured, paid server transcription is unavailable. Its
audio adapter is not yet covered by conservative audio pricing and this ledger;
typing and browser speech remain available. Both availability and transcription
HTTP routes enforce that restriction before entering the audio provider.

Initialize only once, explicitly, as the owner:

```text
python -m agent.inference initialize --path /var/lib/shopping-copilot/inference.sqlite --allowance-usd 0.25
```

This illustrative local allowance is not AWS spending approval. Save the returned
identity in restricted server configuration. Initialization refuses an existing
file, including corrupt storage. Runtime and HTTP routes never initialize a ledger.

Required server variables (none belongs in browser builds):

```text
INFERENCE_LEDGER_PATH=/var/lib/shopping-copilot/inference.sqlite
INFERENCE_LEDGER_ID=<identity returned at explicit initialization>
INFERENCE_PROVIDER=openrouter
INFERENCE_MODEL=<qualified model matching LLM_MODEL>
INFERENCE_INPUT_USD_PER_MILLION=0.30
INFERENCE_OUTPUT_USD_PER_MILLION=2.50
INFERENCE_MAX_ACTIVE=2
INFERENCE_MAX_WAITING=3
INFERENCE_WAIT_SECONDS=2
INFERENCE_MAXIMUM_PAGES=1024
```

The prices correspond to the current bounded OpenRouter price filters, not verified
Bedrock rates. Prices below those native route ceilings are rejected at startup. These
queue values are operating examples, not a five-Shopper EC2 capacity claim.
Production real providers require all variables and matching provider/model.
Development remains unchanged unless this configuration is explicitly supplied.
Scripted production rehearsals make no paid calls and need no allowance.

## Accounting and safe refusal

Amounts use integer nanodollars and conservative upward rounding. Reserve the
configured input price times serialized request bytes plus 4096 protocol bytes,
including fully expanded local schema references; reserve configured output price
times max output tokens. Cyclic/external schema references, tools, oversized inputs
and output bounds above 2048 tokens are refused. This deliberately overestimates
input tokens. Each delegate receives one provider attempt; repairs reserve again.
Provider-specific pricing/token semantics must be verified when qualifying an
adapter. Native provider caps remain unchanged.

OpenRouter's finite non-negative native cost, correlated by attempt identity,
settles once, including charged failed calls with a verifiable receipt. Other
adapters currently provide no verified USD receipt, so their reservation stays
charged; CAP-05 must implement verified Bedrock receipt/rate reconciliation.
Unknown cost, cancellation and process death retain the reservation indefinitely.
Duplicate attempt IDs are refused. Repeated identical settlement is idempotent;
conflicting settlement is rejected. A cost above its reservation is recorded and
persistently disables further inference. No provider fallback is introduced.

The ledger stores random attempt IDs, amounts and state only: no prompts, Shopper
identity, cookies, model responses or credentials. Restrict directory/file access
to the service/owner. SQLite uses FULL synchronization and its rollback journal;
keep the database and temporary journal on the same persistent volume.

## Owner controls and recovery

```text
python -m agent.inference status --path /var/lib/shopping-copilot/inference.sqlite --identity <saved identity>
python -m agent.inference disable --path /var/lib/shopping-copilot/inference.sqlite --identity <saved identity>
python -m agent.inference enable --path /var/lib/shopping-copilot/inference.sqlite --identity <saved identity>
```

Disable stops new provider entries, including requests that are queued. It does
not undo an already admitted call or refund anything. Enable changes only the
switch, never allowance or accounting. When storage is full/unwritable, stop the
Agent as an additional owner control; new reservation writes already fail closed.

Restart and code rollback use the same ledger and identity. Never restore an older
ledger snapshot to regain capacity. Do not delete/reinitialize a lost or corrupt
initialized ledger: stop inference and reconcile accounting before explicitly
authorizing any replacement. Automated recovery does not clear uncertain charges.
This module cannot defend against an administrator intentionally replacing both
the ledger and its identity/configuration; that is outside runtime authority.

## Verification

Public ledger/client/HTTP and owned-process tests cover concurrent final-allowance
reservations, known/unknown settlement, duplicate attempts, persisted switches,
queue saturation/timeout, cancellation, killed provider process and reopen,
missing/corrupt/read-only/full storage, no completion on failed settlement, and
actual interpretation repair using the same allowance. Existing shopping safety
regressions remain required. Public HTTP tests also exercise both legacy and
retrieval advice paths when disabled or concurrently exhausted, and refuse audio
before its provider can be invoked. No paid request or AWS resource is needed for this
ticket's acceptance.

Acceptance on 15 October 2026: **665 Python tests passed in 501.35s**, **198
TypeScript tests passed**, repository format/lint and builds/typechecks passed.
The ledger/runtime Spec and Standards review findings were reproduced and fixed;
no unresolved material finding remains for ticket 05. Owner CLI initialization,
disable/enable without replenishment and duplicate-initialization refusal were
also exercised against disposable local storage. The ticket is resolved locally;
release/restart integration and actual cloud capacity remain separate gates.
