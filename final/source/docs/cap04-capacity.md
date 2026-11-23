# Combined concurrency rehearsal

Local Ticket 08 is resolved, recorded 2026-10-18. Desktop and physical Android
Chrome acceptance pass locally; candidate EC2 capacity remains unverified. This
is not cloud acceptance or a production throughput claim. No paid inference is used.

## Reproduce locally

Use Python 3.12 with the repository development requirements, pinned Node/pnpm,
Playwright browsers, OpenSSL and a previously verified native Caddy executable.
The output parent must be writable; each output directory must be new. Ports
4000, 8000 and 4443 must be free: the runner refuses to replace another service.

```powershell
python -B -m eval.capacity.runner --channel chrome --output outputs/capacity-chrome-new
python -B -m eval.capacity.runner --channel msedge --output outputs/capacity-edge-new
python -B -m eval.capacity.runner --channel chrome --mobile-emulation --output outputs/capacity-mobile-new
```

Run these serially. By default Caddy is read from the existing ignored local tool
path `.scratch/cap04-cloud-readiness/tools/caddy.exe`. Override it with
`--caddy /absolute/path/to/verified/caddy`. The runner builds an actual release,
uses its emitted Storefront JavaScript and Panel assets, and starts a single
Agent worker and the real Caddy routing. It cleans up its own process trees and
disposable certificate private key even after failure.

The two HTTPS sibling origins are `panel.copilot.test:4443` and
`store.copilot.test:4443`. Their disposable certificate is pinned only inside the
temporary browser launch. No operating-system CA, hosts file, public DNS, firewall
or public listener is changed. This trust arrangement does not establish ordinary
phone/browser certificate trust. No global TLS-verification bypass is used.

Child processes receive an allowlisted OS environment and explicit fixture
configuration; dotenv is disabled. No real provider key is inherited. The model
is an injected, bounded decision fixture, not a network client or language
interpreter. Its fixed product ID is test data, not a production interpretation
rule. The artificial ledger allowance and accounting are not real API spending.

## Concrete local limits

| Control                                                | Rehearsed value                    |
| ------------------------------------------------------ | ---------------------------------- |
| Agent workers                                          | 1                                  |
| Simultaneous model work / waiting                      | 2 / 3                              |
| Maximum queue wait                                     | 8 seconds                          |
| Active application HTTP / SSE streams                  | 16 / 16                            |
| Sessions globally / per browser                        | 20 / 2                             |
| Application requests per minute globally / per browser | 1,000 / 120                        |
| Request body                                           | 2,621,440 bytes                    |
| Allowance / admission database maximum pages           | 1,024 each                         |
| Provider fixture calls / queue measurements            | At most 64 / 128                   |
| Process measurements                                   | At most 600 samples, 100 ms apart  |
| Caddy diagnostic rotation                              | 1 MiB, 2 retained rolls, 168 hours |

These bounds are a starting configuration for five invited Shoppers on the
tested workstation. Registry capacity and session limits are not a throughput
measurement. Retain the independently enforced shared allowance, invitation
quotas and Stop lane. Do not increase concurrency to hide a slow provider.

## Measured results

Windows workstation, 12 logical CPUs. Installed Chrome 155.0.8059.84 and Edge
155.0.4283.62. Mobile emulation uses desktop Chrome with a 390-pixel viewport and
touch support; it is not Android hardware. Each cohort uses independent browser
contexts, fresh invitations, different cart quantities and real HTTP/SSE/cart
Actions. Each row is one bounded run, not a percentile estimate.

| Browser                 | Shoppers | Completed / paused | Browser completion range (ms) | Maximum queue wait (ms) | Agent peak RSS (MiB) | Agent CPU (% of one core) |
| ----------------------- | -------- | ------------------ | ----------------------------- | ----------------------- | -------------------- | ------------------------- |
| Chrome                  | 1        | 1 / 0              | 1,211                         | 0                       | 72.0                 | 10.6                      |
| Chrome                  | 5        | 5 / 0              | 1,319–2,471                   | 765                     | 75.4                 | 31.9                      |
| Chrome                  | 8        | 5 / 3              | 550–3,904                     | 1,985                   | 78.1                 | 38.7                      |
| Edge                    | 1        | 1 / 0              | 1,558                         | 0                       | 72.9                 | 8.0                       |
| Edge                    | 5        | 5 / 0              | 1,708–2,634                   | 907                     | 76.3                 | 29.0                      |
| Edge                    | 8        | 5 / 3              | 490–3,320                     | 1,281                   | 79.1                 | 36.3                      |
| Chrome mobile emulation | 1        | 1 / 0              | 1,057                         | 0                       | 72.5                 | 15.3                      |
| Chrome mobile emulation | 5        | 5 / 0              | 1,336–2,556                   | 719                     | 75.9                 | 32.6                      |
| Chrome mobile emulation | 8        | 5 / 3              | 524–3,220                     | 1,547                   | 78.6                 | 35.9                      |

Across these rows, Storefront peak RSS is 65.2–69.2 MiB and Caddy peak RSS is
47.0–55.7 MiB. Their CPU ranges are 2.7–6.1% and 0.0–3.5% of one core. CPU is
the summed service-process CPU-time delta divided by sampled wall time. RSS sums
the owned process tree, including the Windows Python launcher child. Browser,
load generator, OS and build memory are excluded; these numbers cannot size EC2
alone. Very short intervals and CPU tick resolution can produce 0.0%.

Browser completion runs from form submission until that browser observes
completed/paused state. It includes preparation, queueing, fixture work, Action
delivery and Storefront acknowledgement. The eight-request range includes both
successful and refused requests. Queue time measures the GuardedClient semaphore
wait separately from pre-provider preparation. Provider time includes an
intentional hold plus a nominal 400 ms delay: the overload gate keeps slots full
until three refusals are visible, then releases them. It is not a measurement or
prediction of remote model latency. No live model accuracy is evaluated here.

Final ignored desktop aggregate evidence:

- `outputs/cap04-capacity-chrome-002/result.json`
- `outputs/cap04-capacity-edge-002/result.json`
- `outputs/cap04-capacity-mobile-001/result.json`

All three record `paid_calls: 0`, actual queue-full counts, provider peaks,
isolation/refresh assertions and durable allowance outcomes. Earlier Chromium
and installed-browser runs remain diagnostic history. Failed development runs
001–005 exposed an offline pnpm environment omission, an incomplete model fixture,
an invalid equality check on an expiring Undo timer, and the wrong feedback
selector. Those were harness failures, not successful acceptance evidence.

## Physical Android acceptance

The owner supplied a CMF Phone 1 (A015), enabled USB debugging and accepted the
Android SDK licence for official Platform-Tools. Portable ADB 37.0.1-15733141 was
downloaded from Google's official distribution; its Windows executable signature
validated as Google LLC. An initial Windows USB Code 10 cleared after reconnecting
to a different port. ADB subsequently reported authorized device state. After
disabling Chrome's separate USB discovery, the forwarded Chrome metadata endpoint
responded. This sequence does not establish a Chrome or phone firmware root cause.

Actual phone Chrome **155.0.8059.41** ran through USB reverse forwarding on port 4443. The local HTTPS origins were `panel.copilot.localhost:4443` and
`store.copilot.localhost:4443`, without public DNS, Wi-Fi proxy, firewall or phone
CA changes. The owner manually accepted the disposable leaf certificate warnings.
This qualifies the local browser journey with those explicit exceptions; ordinary
trusted public-domain certificates remain a deployment acceptance requirement.
Only the newly created test tab was controlled; existing personal tabs were left
alone. Third-party-cookie restriction was explicitly exercised on the test target.

One physical phone plus four independent desktop contexts completed five cart
mutations with quantities 1 through 5, no cross-Shopper cart leakage, and at most
two concurrent model entries. Foreign-session reads returned 404 in both
directions. Refresh on the phone preserved cart lines/revision without another
cart POST. Combined submission-to-verification elapsed time was **2.328 seconds**,
not a per-request latency percentile. Maximum queue wait in this cohort was
781 ms. Agent peak RSS was 75.6 MiB and CPU 23.0% of one core; the same sampling
limitations as the desktop measurements apply.

A subsequent eight-desktop burst filled the two active/three waiting slots and
paused three excess requests. A further request from the physical phone paused
without changing its existing cart. Observing refusal and verifying unchanged
cart state took **1.187 seconds** including the verification reads. Releasing the
held fixture completed exactly five desktop mutations; the three refused carts
stayed empty. Total fixture calls across both physical-device experiments were
10, with four queue-full outcomes and **zero paid calls**. The earlier desktop
cohorts separately prove shared allowance exhaustion and disable behavior.

Ignored evidence is under `outputs/cap04-capacity-android-001/`:
`physical-result.json`, `provider.json`, `phone-test-page.png` and
`phone-overload-page.png`. The owner-assisted scripts are retained locally under
ignored `work/cap04-android/`; they are experiment records, not a portable Android
runner shipped by this commit. Their first pre-admission check incorrectly
expected 404; actual admission correctly returned 403. That harness assertion was
corrected before the successful cohort. No runtime behavior was changed.

To repeat the hardware protocol, use a new disposable release/state directory,
explicit fake provider, fresh finite invitations and the same limits above. Build
the Panel/Storefront for the two sibling loopback HTTPS origins and create their
disposable leaf certificate. With the owner's authorized USB device, use official
ADB forwarding as follows (the browser port is allocated, not assumed free):

```text
adb devices -l
adb -t <verified USB transport> forward tcp:0 localabstract:chrome_devtools_remote
adb -t <verified USB transport> reverse tcp:4443 tcp:4443
```

Inspect only the newly created test tab. The owner must handle certificate
warnings. Repeat invitation denial/admission, selected variant and quantity,
the five-Shopper cohort, foreign-session denials, refresh/cart-POST counting and
the held-queue phone refusal described above. Record actual versions and bounded
aggregates. Do not use a live provider or read other phone tabs/data. A fresh
checkout must reconstruct the owner-assisted setup; the desktop runner does not
claim Android support. Public trusted-domain hardware acceptance is repeated
after deployment as part of CAP-07.

After the recorded test, the owned services stopped, the exact test tab closed,
USB reverse/browser forwarding was removed, and the newly started ADB server was
stopped. All owned listener ports and deletion of the disposable private key were
verified. The owner was instructed to disable USB debugging and unplug the phone;
that final phone setting is owner-controlled and not independently verified.

## Safety and lifecycle evidence

For each accepted shopper, exactly one cart POST produces only that shopper's
selected quantity. Refused requests leave empty carts. Another admitted shopper
cannot read the session (404). Refresh preserves business cart state without
another cart POST. Five model calls complete with no more than two active at once;
an eight-request burst makes only five calls and reports three queue refusals.

After the three cohorts, the fixture has exactly 11 charged uncertain attempts.
Exhausting its shared ledger and using a fresh browser/invitation cannot restore
allowance. Disabling inference blocks a further fresh browser too. Reopening the
ledger retains zero allowance, disable state and the same attempt count. Failures
never reset accounting. Reports contain aggregate timings and state counts, not
codes, request text, cookies or headers; output and database files stay ignored.

`eval/tests/test_capacity.py` composes five concurrent real Agent HTTP requests,
two active model entries, three queued entries and unacknowledged Actions with the
actual lifecycle coordinator, invitation authority and allowance ledger. Accepted
work and pending Actions prevent idle shutdown. Fresh activity wins before drain
commitment; a committed stop denies new work. A new generation retains quotas,
charged uncertainty and old-worker fencing. The host and Storefront service in
that test are fakes. Actual built-process restart, lost ActionResult and no-replay
proof is separately established by the
[release recovery](cap04-release-recovery.md) and
[lifecycle](cap04-lifecycle.md) browser regressions, which remain in the full suite.
Do not describe this combination as a five-browser real-host restart experiment.

## Candidate-host qualification procedure

This procedure is a future cloud gate, not authorization to create resources.

1. Confirm account Free-plan eligibility, remaining credits, service restrictions,
   selected Region and the complete cost estimate under Ticket 02. Provision only
   through the separately approved deployment gate; preserve the $0 cash ceiling.
2. Select the exact release revision and candidate Linux instance/storage. Record
   instance type, architecture, CPU credits, RAM, filesystem free space, software
   versions and all admission/inference limits. Use private disposable state and
   the injected fixture; do not copy real provider keys or reset live ledgers.
3. Install the pinned runtime/development tooling and a verified native Caddy on
   the candidate host. On Linux, run the command below as an unprivileged owner
   with a new writable output path. The Linux `/proc` sampler and complete runner
   have not yet been qualified by this Windows evidence. Treat any startup,
   measurement or cleanup failure as a failed gate, not missing data to ignore.

   ```bash
   python -B -m eval.capacity.runner --caddy /absolute/path/to/caddy --output outputs/candidate-001
   ```

4. Repeat the 1/5/8 cohorts serially and inspect every outcome, queue-full count,
   cart-POST count, process sample and durable allowance assertion. Collect host
   memory, swap, disk, CPU-credit/throttling and bounded log sizes independently;
   the in-host browser/build workload contaminates service-only capacity sizing.
   Repeat with an external load generator before claiming deployed capacity.
5. Run the existing real release/lifecycle browser regressions on that operating
   system, including simultaneous wake, drain/activity races, lost results and
   retained authority across stop/start. Verify actual remote control storage,
   IAM and Lambda separately; the local shared-filesystem adapter is insufficient.
6. Through the final trusted public sibling domains, repeat Chrome, Edge and a
   physical Android Chrome journey: invitation, own cart, refresh/reconnect,
   duplicate protection, overload feedback and a second shopper's isolation.
   Record Android/Chrome versions, outcomes and screenshots of test pages only.
   Disable USB debugging and remove temporary forwarding when hardware work ends.
7. Keep the five-shopper claim provisional until the candidate host passes with
   operational headroom. A separately budgeted live-model check then establishes
   provider latency/cost; never infer it from the 400 ms fixture. Do not alter
   bounds or acceptance thresholds silently after a failure.

Physical Android local acceptance is recorded above. Ordinary public-domain
DNS/TLS trust and candidate EC2 capacity remain cloud gates; neither emulation,
test pins nor owner-accepted local certificate exceptions establish those claims.
