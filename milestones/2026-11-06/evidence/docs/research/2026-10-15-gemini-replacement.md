# Gemini 3.5 Flash-Lite replacement verification

Date: 15 October 2026. Controlled Storefront, local Chromium, OpenRouter.

## Decision

Accept `google/gemini-3.5-flash-lite` for the local runtime with `intent-v32`,
schema9 and `advice-v4`. This replaces the retiring OpenRouter 2.5 Flash route;
it does not qualify Bedrock, deployed infrastructure or arbitrary stores.

The public [OpenRouter models registry](https://openrouter.ai/api/v1/models)
reports `google/gemini-2.5-flash` expiration **20 October 2026**. The selected
replacement has no listed expiration. Both list $0.30/M input and $2.50/M output
tokens. No listed date is not a promise of indefinite availability. Google's
[Gemini API lifecycle](https://ai.google.dev/gemini-api/docs/deprecations) and
[Cloud lifecycle](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
describe different routes; the OpenRouter route governs this configuration.

Candidate reasoning is mandatory: use minimal effort with reasoning excluded from
visible output. The legacy route's disabled-reasoning setting is not compatible.
Provider price filters, output bounds, structured output, key checks and the $2
non-resetting key limit remain. There is no automatic provider/model fallback.

## Accepted evidence

Local ignored report: `eval/reports/model-qualification-20261014T213739Z/results.json`.
It retains source/case hashes, catalogue snapshot, per-attempt native cost and
latency, case events, the setup interruption and explicit continuation record.

| Check                             | Result                                               |
| --------------------------------- | ---------------------------------------------------- |
| Frozen core gate                  | **43/44**, unchanged gate passed                     |
| Designated safety cases           | **19/19**                                            |
| Filter cases                      | **9/9**, fully understood requests use one Action    |
| Supplemental advice conversations | **7/7**, including follow-ups and actual exact match |
| Core model latency                | median **2,007 ms**, p95 **4,108 ms**                |
| First Action including inference  | median **2,587 ms**, p95 **7,044 ms**                |
| Action execution/settling         | p95 **689 ms**                                       |
| Entire approved additional set    | **72 POSTs, $0.09501011**, no uncertain costs        |

The owner authorized one additional set with a $0.12 maximum inside the existing
$2 key cap. A page-setup assertion interrupted it after 30 completed cases and 37
POSTs, before the next case's model call. Manual continuation imported every
original reservation/settlement into a durable ledger under the same $0.12/120-POST
bound. All completed rows, including the failure, were retained and skipped;
there was no new set or replenishment. The launcher now records the actual claim
amount; the initial marker's default-$0.25 metadata was corrected with its
provenance retained. Actual transport enforcement and results always used $0.12.

The remaining failure is `cart-increase`: the model selected add rather than
relative quantity change, navigated to the product and asked for a missing size.
It did not apply an incorrect cart change. This is a real language/operation
quality limitation, not a safety pass disguised as task success. The original
gate permits this outcome; no threshold was changed after observing it.

Manual review checked every advice turn against the captured catalogue: prices,
colours, sizes and features agree; non-leather remains unverified where absent;
warranty and customer-review data are explicitly unknown. Black/44/under2000 has
no exact match; black/42/under2000 correctly recommends shoe-01. Styling and work
coordination remain opinions; a follow-up distinguishes unverified work suitability.
One Franco reply has awkward wording. All advice turns are read-only, without
Actions or cart changes. These are exposed synthetic cases, not unseen evaluation
or a guarantee of factual/language correctness for all future responses.

## Earlier failures and general fixes

The first cohort had 18 HTTP400 rejections because disabled reasoning is invalid
for the replacement. Its conservative $0.2462835 reservations were retained;
provider-reported key usage did not increase. The approved diagnostic reproduced
the mandatory-reasoning error and retained a separate $0.0096027 reservation.

The subsequent cohort was interrupted by telemetry transport, then resumed with
all charges retained. It finished 42/44 with an evaluation reconnect-fixture defect
and 5/6 advice cases. Another full cohort after generic advice-boundary/fixture
fixes finished 42/44, all safety and 7/7 advice, but failed filter efficiency.
All those reports remain under ignored `eval/reports/`; none is represented as an
initial pass or removed from the experiment history.

Two general interpretation boundaries were corrected:

- Owned outfit descriptions and soft colour preferences can describe things the
  store does not sell. Read-only advice/discovery uses catalogue evidence to
  distinguish verified, unmet and unknown facts, while currency, known product
  identity, cart and Action authority checks remain enforced.
- `intent-v32` and field descriptions explain canonical category/type constraints
  versus literal product-name queries, and browsing versus extra suitability
  requirements. The model must preserve separately requested features/exclusions.
  No phrase matching, query rewriting or language dictionary was added to runtime.

These prompt changes are disclosed post-failure corrections, superseding the
initial unchanged-prompt protocol. Acceptance uses the reviewed new prompt;
earlier model scores are not retroactively changed. Targeted filter checks and
all earlier charges stayed inside the prior approved combined $0.25 allowance.
That ledger retained $0.19968291 plus the separate $0.0096027 diagnostic reservation.
The additional accepted set uses its separately approved $0.12 allocation.

Independent Standards/Spec reviews cleared the runtime, advice-boundary and v32
prompt changes after fixes. A review finding about raw Pydantic exception text was
fixed: evaluation diagnostics retain exception categories and bounded structural
metadata, not rejected input. The final small claim/continuation delta was
self-reviewed and regression-tested; follow-up independent reviewers hit their
usage limit. Do not present that final delta as independently reviewed.

## Runtime and recovery

The active development worktree selects the qualified model in its ignored local
configuration. The separate original checkout remains older code with unrelated
uncommitted documents; do not run that checkout with the replacement setting or
overwrite those documents during integration. Historical 2.5 benchmark records
remain unchanged. Ordinary CI stays scripted and makes no paid calls.

For an operational regression, stop new inference using the configured durable
ledger's owner disable command; retain the ledger and identity through restart or
code rollback. Scripted mode can support an offline demonstration. Do not rely on
the retiring route after expiration or silently renew any allowance. A different
real model/configuration needs its own bounded qualification.
