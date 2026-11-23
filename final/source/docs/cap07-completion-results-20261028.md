# CAP-07 private host and application acceptance passed

The remaining captured shopping capacity check passed on the retained Stockholm
host on 28 October. The host is stopped, has no public IP, and its temporary EIP
is released. Guest/API teardown reported no errors. Applications and the real
canonical ledger are disabled; the final protected ledger backup and safe
relative shutdown guard are retained. All three acceptance invitations were
verified revoked off-host. Public activation remains a separate gate.

## Actual captured results

| Concurrent shoppers | Completed | Expected busy refusals | Observed cohort seconds |
| ------------------- | --------- | ---------------------- | ----------------------- |
| 1                   | 1         | 0                      | 2.928485                |
| 5                   | 5         | 0                      | 9.825428                |
| 8                   | 5         | 3                      | 11.319521               |

The passing attempt used 140 HTTP requests and 22 fake model POSTs. The capture
transport remained separate from real custody and could not open the real key
or ledger. Signed readiness at generation 3, wrong-generation/key/stale/unsigned
refusals, UID separation, capability/resource bounds, metadata restrictions,
model egress denial and swap configuration passed again after restoring the real
application. Canonical accounting was byte-logically unchanged across the
shopping checks, including all 248 existing attempts. Zero live model POSTs,
zero new provider status GETs, zero additional reboot, and no custody reset or
upload occurred. The earlier actual reboot-persistence and control-capacity
evidence remains valid; this session did not repeat the reboot.

Minimum available host memory was 1,541,951,488 bytes (about 1.44 GiB), maximum
swap usage was zero, and every sampled resource/CPU/OOM guard passed. These are
captured-response host results, not measurements of live-provider latency.

## Inspect-first repair and exact request amendment

SSH first retrieved the previous driver's retained stderr, last sampler records,
generic failure receipt, fixture metrics and bounded journal before changing
guest assets or running load. Stderr was empty because the driver discarded its
exception. The last sample was resource-safe; fixture metrics showed completed
fake POST activity for cohorts 1/5. No hardware failure was established.

Code tracing and a delayed-event regression exposed a driver race: `once=true`
returns only currently queued SSE events. The driver now keeps one bounded stream
open until a terminal outcome. Its safe failure receipt records stage, exception
class, request count and HTTP status without tokens or response bodies.

The first current attempt reached cohort 8 but hit the outer 10-second timeout
at 130 requests. Raising that timeout exposed the separate HTTP read timeout on
the second attempt, also at 130 requests. Both exact diagnostics were retrieved
locally before any teardown. Both fake fixtures and their evidence were archived
separately. The HTTP read and cohort observation timeouts are now 30 seconds,
with connect bounded to 5 seconds. The application's 8-second queue wait and all
resource/safety limits are unchanged. The passing 8-shopper cohort took 11.32
seconds, which exceeded the old driver timeout.

The owner explicitly approved one final attempt and raised only the session HTTP
ceiling from 300 to 450; actual total was **400**. This amended the exact request
bound; it did not increase the USD0.15 allocation or the original four-hour
deadline, start another host, allocate another EIP, or permit live model calls.
There were 66 fake POSTs across the three separate synthetic fixtures, 22 in each.
No phase-start, custody, lifecycle history or accounting flags were reset to
force replay. The final attempt used a separately guarded acceptance-only phase.

## Teardown, accounting and verification

The single Start/EIP session ran from T0 19:29:28 UTC to verified stop/IP release
at 19:44:19 UTC. Fresh AWS reads independently confirmed stopped/no public IP/
zero operation EIPs. The active Free plan and credit eligibility were checked
before mutations. The conservative incremental estimate is **USD0.022704 in
existing credits**, rounding compute/IP to 15 minutes and retaining the full
original request/transfer/table/KMS envelope plus contingency. This is not final
billing. Existing retained root/table storage continues under its prior allocation.

Normal lifecycle bookkeeping completed at20:44:19UTC, inside the fixed23:29:28UTC
end. The verified final receipt reports authority stopped/generation3/recoverable,
stop intent settled, finish_done and operation_closed. The finite local worker
finished without keeping EC2 running. The previous generation-2 worker also
completed cleanly before this Start.

Local verification: 57 private operator regressions and 27 driver tests pass.
The full Python suite passed 1,599 tests in 1,010.10 seconds, with two existing
websockets/uvicorn deprecation warnings. Python lint and formatting checks passed.
Production application/release bytes are unchanged. Only acceptance driver/tests,
private operator helpers and evidence/documentation changed. No push, merge,
DNS, ACME, public activation, extra Start or renewed paid-model grant occurred.

Evidence: [dated sanitized receipt](../eval/evidence/cap07-completion-20261028.json).
Protected operation pointer: `.scratch/cap07-controlled-host-preparation/completion-operation.txt`.
Next: verify the off-host final receipt, then prepare the separately reviewed
Controlled Storefront public activation/startup-link proposal. No further cloud
Start or deployment is authorized by unused allocation.
