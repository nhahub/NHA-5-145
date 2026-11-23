# Invited demo access: CAP-04 local ticket 04

## CAP-06 remote invitation component — 21 October 2026

`agent/admission/dynamodb.py` now implements the invitation-store contract against
an injected low-level DynamoDB client. This is the first remote control component;
the active admission factory and existing SQLite configuration remain unchanged.
No AWS table, IAM role, deployed service or new public endpoint has been created.

The candidate table has string `pk`/`sk` keys and an explicitly initialized
namespace identity. Separate metadata, invitation, code-hash index and subject-hash
grant records retain absolute windows, revocation and cumulative usage. Strong
base-table reads and conditioned transactions keep final-slot consumption and
grant binding atomic. Initialization refuses nonempty namespaces, including
orphaned rows with missing metadata. No TTL/deletion/restore resets authority.

Same active grant redemption consumes no additional slots. Replacing an expired
or revoked grant preserves its old usage. Wake validation creates neither a grant
nor a session; the later lifecycle adapter must revalidate it in the atomic wake
decision. There is no remote EC2 command adapter or active cloud integration yet.

The injected client must use Stockholm's standard HTTPS endpoint, connect/read
limits of at most5/15seconds and total_max_attempts=1. Unknown write outcomes
refuse access without replay or refund. Fresh post-write validation can deny an
expired/revoked invitation while retaining already committed counters. A fresh
transaction token is bounded AWS idempotency, not an indefinite operation ledger.
Status validates the queried rows and exposes only the existing safe fields.

Optional offline tests use Moto5.2.4 with dummy credentials, not an AWS account:

```text
python -m pip install -r eval/requirements-cloud.txt
python -m pytest agent/tests/test_admission_dynamodb.py -q
```

The extra is separately pinned and excluded from release runtime requirements.
Moto does not qualify AWS transaction conflicts, IAM, durability, costs or latency;
failure/timeout paths also use explicit injection. Before activation, complete
remote lifecycle arbitration and fenced host commands, async host integration,
scope IAM, actual table initialization, clock/cost checks and deployed acceptance.
No new environment variable or CLI command selects this backend yet.
[Design](specs/2026-10-21-cap06-remote-invitations.md),
[primary API evidence](research/2026-10-21-cap06-dynamodb-invitation-contract.md).

## Existing local implementation

Implementation and verification need no real testers. The owner issues their codes
later. Storefront browsing stays public while running; using the Copilot requires
a valid code when admission is configured.

## Access and persistence

The existing linked browser identity, CSRF and Shopper/cart/session ownership are
still required. Admission cannot share carts, authorize a Mutation or replace
Confirmation. Code exchange uses a POST body, never a URL. The Panel clears the
code input after submitting and never saves codes in browser storage.

Codes contain 192 random bits. SQLite stores only SHA256 hashes and random public
invitation IDs. Each invitation has explicit absolute start/end timestamps,
independent revocation, a cumulative redemption limit and a cumulative session
creation limit. Same-browser repeat redemption is idempotent. Concurrent claims
are atomic. A replacement code may supersede an expired/revoked grant without
refunding the old code's usage.

Grants bind browser authority and Storefront identity. Refresh retains admission.
Agent restart invalidates browser/task authority; fresh redemption consumes
another slot if available. Neither restart nor code reentry extends the window or
resets quotas. Windows are at most 31 days, with at most 20 redemptions and 100
session creations per code. Storage is capped at 1024 SQLite pages/1000 invitations;
it refuses when full instead of deleting accounting. Missing, corrupt or
wrong-identity storage refuses access. Runtime opens mode=rw, never initializes.
Keep the database outside releases, restrict file access and never restore older
quotas to regain capacity. This supports one Agent worker.

## Explicit configuration

Unconfigured local development preserves its access flow. Production requires all
settings, including scripted public rehearsals. These are local operating examples,
not a measured five-Shopper EC2 capacity claim:

```dotenv
ADMISSION_DB_PATH=/var/lib/shopping-copilot/admission.sqlite
ADMISSION_DB_ID=<identity from initialization>
ADMISSION_MAX_REQUEST_BYTES=2621440
ADMISSION_REQUESTS_PER_MINUTE=1000
ADMISSION_BROWSER_REQUESTS_PER_MINUTE=120
ADMISSION_MAX_ACTIVE_REQUESTS=16
ADMISSION_MAX_STREAMS=16
ADMISSION_MAX_SESSIONS=20
ADMISSION_MAX_BROWSER_SESSIONS=2
```

Global rates cover new cookies and anonymous requests; IP is not identity. Excess
work receives 429 without automatic retry. At most 16 ordinary requests/16 SSE
streams are active, with zero HTTP waiting capacity. SSE slots last until close
or cancellation, with two per browser in this example. The separate inference
guard retains its configured active/waiting bounds and durable spending policy.
Bodies, including chunked ones, are bounded before parsing and have a five-second
read timeout. Health/CORS preflight never enter model work.

Owner Stop has a reserved, bounded lane: four concurrent requests, 100 globally
per minute, ten per browser per minute, and at most 4096 body bytes. Browser
identity, CSRF and session/tab ownership remain mandatory. Ordinary overload or
invitation expiry does not remove this cancellation path. This does not protect
against unlimited network traffic; ingress capacity remains a deployment gate.

Paid server transcription is disabled under admission, matching the guarded
inference runtime: the audio adapter lacks equivalent durable accounting/entry
checks. Typing and supported browser speech remain available.

## Owner-only commands

The database parent must exist with restricted permissions. No command contacts
a provider. Save the generated database identity in server configuration:

```text
python -m agent.admission initialize --path /var/lib/shopping-copilot/admission.sqlite
python -m agent.admission issue --path /var/lib/shopping-copilot/admission.sqlite --identity <saved identity> --starts 2026-10-17T10:00:00Z --ends 2026-10-17T18:00:00Z --redemptions 1 --sessions 8
python -m agent.admission status --path /var/lib/shopping-copilot/admission.sqlite --identity <saved identity>
python -m agent.admission revoke --path /var/lib/shopping-copilot/admission.sqlite --identity <saved identity> --invitation <public invitation ID>
```

Issue prints the raw code once to the owner's terminal. Share privately when ready;
keep that output out of transcripts, screenshots, tickets and Git. Status contains
safe window/quota metadata, no code/hash/browser subject. Initialization refuses
existing files. There is no public issuance/revocation API. The example date is
illustrative; choose the actual fixed testing window later.

## Runtime and verification

Admission covers sessions, messages, answers, results, retry, state/recovery and
events. Each SSE delivery rechecks browser identity and admission after awaited
Storefront validation. Model interpretation, repair and advice recheck live
authority, including after inference queue acquisition and immediately before
each provider POST. These local callbacks never enter prompts/model payloads.
An already sent call cannot be uncharged; revoked output is suppressed and future
work refused. Unknown-cost reservations remain charged.

Denied/exhausted/expired code entry has clear feedback and explicit retry. Busy
HTTP/terminal stream failures have clear notices; streaming recovery requires
explicit Reload and preserves the session reference for reconciliation. No retry
automatically resends work or replays an uncertain Action.

Tests use public storage/CLI, HTTP, ASGI concurrency, fake provider transports and
actual desktop/mobile Chromium. Cases include invalid/valid code, public browsing,
navigation, refresh, exhausted reuse, code absence from URLs/storage, SSE429
recovery, live revocation, foreign-session rejection, fixed expiry, atomic quotas,
new-cookie/chunked-body limits, Stop under overload, revocation during awaited
Action delivery, provider queue/key-check denial and missing/corrupt storage.
No real participants or paid calls are used.

The HTTPS production probe now configures ephemeral admission storage/codes for
future rehearsals; its earlier Ticket03 evidence remains historical. No new CA
trust, public DNS, AWS or deployed capacity is claimed. Automatic wake admission
needs separate durable control state in ticket07; local SQLite does not implement it.

## Local acceptance record — 16 October 2026

Independent Standards and Spec review findings are resolved. Regression checks
first exposed revocation during awaited Storefront validation and missing explicit
SSE429 recovery; both have targeted failing-then-passing coverage. Full-suite runs
then each recorded 684 passes/one failure: the first found an early-Snapshot race
during simultaneous-tab restoration, fixed with a deterministic ownership test;
the second hit the initial five-second code-form wait with an empty page shell.
Only that initial startup assertion now permits 15 seconds, matching existing
browser startup checks. That observation does not prove the startup delay's cause.
Final verification runs builds before browser tests to avoid overlapping writes
to generated modules. Both reviewers cleared these follow-ups.

A subsequent serial run passed 665 tests before the existing mobile evaluation
setup raced initial iframe navigation. Its helper previously wrote location
immediately after DOMContentLoaded, before asynchronous Panel startup selected
the initial Storefront URL. It now waits for Panel readiness and uses awaited
Frame navigation. A real-Panel delayed-start regression fails against the old
helper and passes with the fix. Preliminary synthetic-frame fixture attempts
were discarded because they did not faithfully establish readiness; no runtime
shopping behavior changed. Both reviewers cleared the final harness change.

The focused desktop/mobile admission and simultaneous-tab checks pass (three
tests). Final serial verification passes **686 Python/browser tests in 549.35s**
and **199 TypeScript tests**, plus builds/type checks, lint and formatting. Local
ticket 04 is resolved; no paid or deployed acceptance is implied. The admission
CLI was smoke-tested against disposable storage, including duplicate-initialize
refusal, issue, safe status and revoke. The production probe's isolated `--help`
also passes; its certificate-based journey was not rerun.
