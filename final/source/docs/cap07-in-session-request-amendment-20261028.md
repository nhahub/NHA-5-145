# CAP-07 in-session request amendment — owner approved

The owner explicitly approved “one final attempt; maximum 450 HTTP requests total.”
The [completion results](cap07-completion-results-20261028.md) record the pass,
400 total requests, and immediate stop/EIP release. The proposal below was prepared
before that approval; its exact approved version is retained in protected custody.

The current single-Start completion session remains active and private. Retained
logs were retrieved before reconciliation/load. The previous driver used a
single current-event snapshot as completion; that race was fixed with a bounded
terminal SSE stream. The first current attempt passed cohorts 1/5 and reached
cohort 8 but hit the 10-second outer observation timeout at 130 requests. Raising
that timeout exposed the HTTP client's separate 10-second read timeout on the
second attempt, also at 130 requests. Full diagnostics for both are local;
memory/swap/OOM/CPU/service-presence checks remained healthy. No live model calls.

The concrete repair sets both observation and HTTP read bounds to 30 seconds,
with connect limited to 5 seconds. Inference queue wait remains 8 seconds; queue,
capacity, memory, CPU, ingress and safety checks remain. All 27 driver tests pass.

Request approval for exactly one final 1/5/8 attempt in the same active SSH window,
at most 150 HTTP requests, raising the whole-session ceiling from 300 to 450.
Expected total is 400 (130 + 130 + 140). No extra Start/reboot/EIP, time extension,
credit allocation, provider call or public access is requested. USD0.15 eligible
existing AWS credits, Free/USD0cash, zero live POST/new provider GET and original
four-hour fixed deadline remain. Existing DDB write/read and transfer envelopes
remain hard bounds. Archive each fake fixture/diagnostic separately, preserve real
custody and compare canonical accounting afterward. Immediately teardown and
release EIP on pass; retrieve complete bounded diagnostics before any abort.

Execution refuses without an explicit owner approval receipt for 450 requests.
Absent approval, no new load is permitted; perform safe teardown within the
current authorization/deadline and retain the diagnosed harness repair locally.
