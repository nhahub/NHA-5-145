# CAP-06 custody and accounting preflight

24 October 2026. The owner's continuation authorizes this read-only check and
synthetic capacity work. No key or ledger was migrated, enabled, reset or funded;
no model request, resource creation or public activation occurred.

One bounded authenticated GET to the fixed OpenRouter key endpoint confirms the
existing USD2 non-resetting cap and positive remaining limit. Exact live usage and
remaining limit stay in the private receipt. Key bytes, key digests and ledger
UUIDs are absent from the public evidence. The active worktree explicitly selects
Gemini3.5FlashLite. The canonical D: checkout still selects the older2.5 model;
both currently contain the same key. Neither configuration was changed. A future
host must consume its explicit protected configuration, not either local dotenv.

Two retained qualification databases were inspected using SQLite read-only,
immutable connections after confirming no journal/WAL/SHM sidecars. query_only,
quick_check and before/after SHA256 checks pass. Runtime constructors were avoided:
the current AllowanceLedger status path opens a writable transaction.

The shared historical ledger has156attempts and USD0.19968291 accounted. Its
remaining USD0.04071439 is qualification remainder. The accepted cohort's separate
ledger has72attempts and USD0.09501011 accounted, leaving USD0.02498989. Both have
zero unsettled entries in those databases and unchanged bytes. Neither remainder
is an authorized deployment grant, and both are below the current readiness
maximum-reservation requirement of USD0.0831488.

The broader journal inventory covers60unchanged JSON/JSONL inputs. It identifies
228settled attempts totaling USD0.29469302. The same228cost receipts appear in
measurement telemetry; adding them again would double-count costs. The final
qualification and later routing journals share the first retained ledger; they
are not independent grants or additional ledger totals.

Nineteen older reservations remain uncertain:18from the rejected first set and
one diagnostic hold. Conservative per-attempt nanodollar rounding retains
USD0.255886201. Their HTTP failures do not prove refunds. The current provider
aggregate also exceeds costs attributable to this collection; that difference
must not be assumed zero or converted into available allowance. Aggregate usage
is not per-attempt attribution, and this preflight does not claim complete history.

## Custody handoff still required

The first host handoff must explicitly choose the authoritative runtime ledger
and a finite spending authorization inside the unchanged key ceiling, preserving
all prior charges and uncertainty. An unused qualification remainder is not such
authorization. Do not initialize a fresh allowance, merge snapshots by summing
cumulative totals or release unknown holds as a convenience.

Keep the selected ledger UUID/history and source receipts bound to the explicit
release/configuration and protected Agent key. Use the existing per-service layout
from [host isolation](cap06-host-isolation.md), with private custody outside the
release. The handoff needs quiescence, independently checked copies, owner-only
permissions and one authorized writer. Retained local backups must not become
parallel spendable deployments. Retiring current local key/runtime paths and
installing the operator pin are concrete custody operations; none occurred here.

Actual Linux installation, systemd/UID/metadata/log/reboot evidence and measured
capacity remain separate. The existing desktop capacity fixture uses a different
client path; its numbers cannot qualify captured OpenRouter concurrency. The
new native synthetic measurement will report that path without changing its lock
or qualification semantics. Actual host capacity remains unqualified.

The [public receipt](../eval/evidence/cap06-custody-preflight-20261024.json) records
sanitized observations and private-receipt hashes. It grants no model spending,
AWS resources or public activation. The earlier binding implementation stays
approved; it does not need another design approval.
