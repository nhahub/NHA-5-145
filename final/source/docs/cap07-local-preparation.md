# CAP-07 local preparation

27 October 2026. The owner approved proposal `b898b12`: up to USD 0.25 of existing AWS credits, mandatory Free plan and USD 0 cash, a USD 0.10 readiness reserve inside the unchanged non-resetting USD 2 key cap, zero live model POSTs, and verified operator IPv4/32 rotation. Preparation has not started the four-hour cloud clock. No AWS account request, real provider-key/ledger access or host mutation has occurred in this preparation.

The application release remains unchanged. The new operator-only handoff helper preserves the shared ledger UUID, exact settled rows and 19 legacy holds, adds a conservative provider aggregate-gap hold, and creates a disabled canonical destination. It refuses changed caps/history, insufficient remaining balance, duplicate conflicts, unsafe files, conflicting destinations and interrupted copies. The HTTP/SSE driver permits only the two approved private HTTPS origins and bounded admission/session routes. Control mode cannot submit a model message. Limits remain 150 ingress requests and 600 seconds per lane, with one fixed session deadline across reboot.

## Native synthetic rehearsal

A disposable network-isolated container runs the frozen Python 3.12.14, Node 24.22.1 and Caddy 2.11.7 artifact. TLS uses an explicit disposable private CA and the production hostnames over loopback. Store, Agent, GuardedClient, OpenRouterClient, admission and lifecycle code are real application components. Moto and captured responses provide synthetic AWS/provider transport. All custody and allowance are synthetic. This establishes local preparation, not actual EC2 acceptance.

| Lane              | Cohort | Completed | Expected busy refusals |
| ----------------- | -----: | --------: | ---------------------: |
| Control           |      1 |         1 |                      0 |
| Control           |      5 |         5 |                      0 |
| Control           |      8 |         8 |                      0 |
| Captured shopping |      1 |         1 |                      0 |
| Captured shopping |      5 |         5 |                      0 |
| Captured shopping |      8 |         5 |                      3 |

The final rehearsal used 126 control and 140 captured ingress requests. All cohorts completed within ten seconds. Captured traffic used at most one mock POST in flight and preserved existing uncertainty. There were zero real AWS or model calls. Each admitted shopping task needs a catalogue `search` followed by an evidence-grounded `recommend` decision: 22 synthetic POSTs for 11 tasks. The historical 11-POST direct GuardedClient probe is not relabelled as full HTTP capacity.

Conservative synthetic accounting, including transactional size rounding and extra initialization/readiness/reconciliation headroom, bounds the session at 2,344 WRU, 16,523 RRU and 79,308 table bytes. These fit the approved 10,000 WRU, 20,000 RRU and 1 MiB ceilings. Regional SDK wire traffic is recorded separately from internet output: AWS documents same-Region DynamoDB transfer as free. Aggregate private SSH output is capped at 4 MiB; a 16 MiB internet-output envelope includes protocol/receipt headroom and fits the approved 0.02 GiB allowance. The 300-request HTTP limit counts driver ingress; internal SDK requests have their own measured bounds.

The fixture initially exposed obsolete captured decision JSON, missing tab ownership, expected empty/completed-task Stop conflicts, and a cold Store startup race. These were corrected in the harness. Control creates no Shopping Task; captured cleanup accepts only 202 or the exact documented already-finished 409 and runs sequentially. Store/proxy must be listening before the first signed Agent proof. No production behavior was changed.

## Review and verification

The single fresh whole-preparation review used GPT-6 Astra and covered the new code plus private operator sources. Its eight important findings were addressed locally:

- Late watchdog resume still attempts exact stop/IP release; a failed cleanup is recorded without claiming safety.
- Real custody requires a recent matching operation/boot barrier proof and renewed actual allow/deny checks immediately before installation.
- Capacity reads the protected uploaded invitation files consistently.
- Authority, guest and API cleanup run independently, including partial boot. Lifecycle idle completion uses actual activity time, never teardown completion.
- Post-stop transactions are restricted to the approved table/namespace, fixed deadline and verified compute-safe state; resource activation remains closed.
- Synthetic SDK/item-size accounting proves the approved request/storage bounds.
- Both checkouts receive a process inventory, including non-listening evaluators; unknown Python/Node consumers and inherited active provider keys refuse custody transfer.
- Actual guards reject pause, regressing clocks and late work. Sampling refuses missing cgroups, component/host OOMs and threshold breaches; inspection checks restarts, descriptors and isolation.

The same pass preserves loopback HTTPS, compares canonical logical rows/allowance before and after capture, checks capture cannot open real custody, and verifies fresh readiness plus wrong generation/key, replayed and unsigned refusals. Actual host outcomes remain gates for the authorized session.

Native systemd 252.23 verifies the base, deadline, barrier and capture units without starting them; four unsafe UID/address/deadline cases refuse. Offline botocore validation covers ten resource/policy requests and exact namespace permissions without creating an SDK client. Nineteen private synthetic regressions pass. All prepared sources compile. Focused public custody/driver/binding/qualification checks pass 107 tests; repository Ruff check and format check pass. Focused application-source ESLint and edited-document Prettier pass. The root commands additionally scan ignored scratch downloads (2,158 ESLint errors) and 14 older ignored working notes (format warnings); these are recorded separately and left unchanged.

The first full Python run passed 1,593 tests. A subsequent full run passed 1,596 and had one existing browser timeout waiting for the initial message box. That case passed its focused rerun, followed by the complete six-test browser group, without an application change. The failure record is retained. The final full regression run passed **1,597 tests** with two upstream deprecation warnings in 1,008.45 seconds.

Official Stockholm prices were refreshed on 27 October: t3.small USD 0.0216/hour, gp3 USD 0.0836/GiB-month, IPv4 USD 0.005/hour, DynamoDB Standard USD 0.67/million WRU, USD 0.1345/million RRU and USD 0.269/GB-month. The proposal's USD 0.142404 planning bound remains below its USD 0.25 ceiling. See the dated [synthetic evidence](../eval/evidence/cap07-local-preparation-20261027.json) for catalogue URLs, response hashes and exact receipts.

Private payloads and backups belong under owner/SYSTEM-only ACLs in `.scratch/cap07-controlled-host-preparation` and the new operation directory. The old operation grant, state, watchdog and receipts are not reused. Remaining entry gates are fresh account/Free-plan/credits/IP/permission checks, followed by the single approved key-status GET and custody transfer. The one bounded cloud session, controlled reboot, actual capacity and final stop/IP release are still unexecuted. Public wake/DNS/ACME/browser/live-provider deployment remains a later gate.
