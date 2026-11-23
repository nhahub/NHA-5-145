# Captured OpenRouter concurrency: native measurement

25October2026. This closes a local captured-qualification concurrency regression.
It does not establish EC2 capacity, remote model latency, public-browser capacity
or actual production custody. All native provider responses, key/allowance and
external authority are synthetic. Real model and SDK request counts are zero.

The earlier desktop capacity fixture injected a different client. The native
startup fixture also used1active/1waiting/1second rather than the proposed2/3/8.
A new bounded measurement binds2active,3waiting and8seconds at startup, constructs
the actual OpenRouterClient inside the host assembly and consumes its actual
GuardedClient completion path. Every request uses the real lifecycle work.check
for authorization. MockTransport supplies the fixed key/status response and a
small valid output after0.4seconds; network access and real SDK construction are
forbidden. The existing OpenRouter lock is unchanged.

## Reproduction and narrow fix

The frozen probe first ran against genuine source4deaf586. One request completed
in each1/5/8cohort; the remaining4and7requests failed LifecycleUnavailable before
reservation/model access. The legacy provider callback's single-flight task slot
was denying overlapping captured in-memory verification. This was a failed
capacity gate despite the measurement process exiting0. That receipt stays intact.

Three new regressions for2/5/8parallel work checks all failed before the fix.
Source023d9f6 calls the exact owned ProviderQualification directly for its pure
in-memory observe/recheck operations. It keeps expiry, type/proof and closure
checks plus the later lifecycle/generation checks. Legacy async callbacks retain
their bounded single-flight timeout/cancellation/draining path. No qualification
worker, runtime disk hash, source pin table, lock bypass, higher queue limit or
spending permission was introduced.

A fresh focused review found no material issue. The55focused tests pass; the full
Python suite passes1555tests in934.43seconds with2upstream deprecation warnings.
Ruff281files/format pass. TypeScript is unchanged; prior199test acceptance remains
historical evidence. Source formatting checks exclude ignored generated proofs;
known default workspace lint/format diagnostics remain documented in the earlier
[provider guide](cap06-provider-qualification.md).

## Same-probe native result

The unchanged probe SHA256 is
c9efedf576fcc942c89e794032dcf8b01ce9968ce62d1fa9e0152d0498b16ac3.
It ran serially against the new clean native archive under the same signed
AL2023 Python3.12.14/Node24.22.1 runtime and resource/headroom bounds.

| Requested calls | Completed | Refused         | Last completion | Maximum guard queue wait |
| --------------- | --------: | --------------- | --------------: | -----------------------: |
| 1               |         1 | 0               |          0.406s |                  0.014ms |
| 5               |         5 | 0               |          2.020s |               1214.315ms |
| 8               |         5 | 3inference_busy |          2.020s |               1215.217ms |

All11synthetic provider POSTs settled their fixed fake receipts. The three overload
refusals created no reservation or model call. Original synthetic USD0.04uncertainty,
ledger identity/allowance, catalogue and release manifest were preserved. No new
uncertain attempt or pending task remained. Every owned service/verifier closed.

Peak actual mock POST concurrency remains1because the adapter holds its lock
across key lookup and completion. Two guard slots therefore do not mean two
parallel remote POSTs. Native app/probe process peak RSS was73.51MiB; measured CPU
was1.48–2.47percent of one core. The sampler excludes browser, OS, other services,
whole-instance memory/swap/credit throttling and a real provider. These numbers
cannot size the proposed EC2 instance or establish live response time.

Clean source023d9f621bc9432b871e519d51e6ce57bb7dc204,
treeade5f9f5d6960a9a263f01589df0f70c7c37cc87, built in107.06seconds. Archive SHA256
5e5e3843160225b81b81f3dd79bb960fc82507134ae7a7f58896020d5cd28a23;
manifest SHA256efc1f9da4388c24b9e8b312aed2871c1aa7174f78370a531f2400a8c6b9d0757.
The captured-capacity run took22.02seconds. Default/explicit qualification startup,
zero runtime private reads, copied-evidence deletion, expiry refusal, wrong-key/
expired/bad-evidence pre-SDK refusal and owned shutdown passed again in37.03seconds.
Independent extraction verified945files,192relative symlinks,39contained hardlinks
and1228archive entries. All passing runners exited0 with empty stderr. Docker
Desktop was stopped after confirming no running proof container.

The [machine-readable receipt](../eval/evidence/cap06-captured-capacity-20261025.json)
contains both failed and passing gates, unchanged probe hash, original profiles,
actual results, memory/cleanup and new source/archive/manifest identities. Earlier
accepted model/native reports remain unchanged; no historical proof is relabelled.

The next actual cloud step is the separately reviewable
[first private host inspection](cap06-first-private-host-inspection.md). Its
resource/cost/stop decision remains unapproved. Actual protected custody and
finite runtime allowance, full HTTP/SSE Shopper workload, candidate host and live
provider qualification remain separate gates.
