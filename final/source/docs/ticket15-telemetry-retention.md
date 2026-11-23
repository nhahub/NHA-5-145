# Ticket 15: telemetry retention and remaining acceptance decision

**Date:** 2026-10-01. This work repairs future evidence capture; it does not close the historical measurement gap or change the acceptance thresholds.

## What changed

Every OpenRouter attempt has a local UUID, UTC start time and the provider generation ID when one is received. These identifiers remain local telemetry, outside the model instructions. Error events are inspected for accounting before rejection, so usage included in an error event is retained. Missing usage remains unknown. Inconsistent stream generation IDs are rejected and cannot be used for reconciliation. Buffered output still reaches the Agent only after complete response validation.

The evaluation service writes each finished attempt to its own ignored `eval/reports/attempts-<uuid>.jsonl` journal, flushing it to disk. Reports reference that journal. Each wrapper invocation selects metadata by its own attempt UUID, avoiding association with another concurrent call. The journal does not retain request prompts, audio, API keys or raw provider errors. A process killed before an attempt finishes may still leave incomplete evidence; journaling does not guarantee recovery of an identifier never received.

The wrapper explicitly closes the provider iterator before journaling a cancelled/held response, retaining accounting already received. Diagnostic schema fields are allowlisted; raw extra-property names, error messages and free-text model category/type fields are excluded. Independent Spec and Standards reviewers found these cancellation and redaction gaps in the initial patch; both were fixed and re-reviewed without remaining findings.

`python -m eval.reconcile_usage <report.json> --output <new-report.json>` makes only read-only accounting GET requests, and only for a unique generation ID already saved in the report. It verifies the returned ID, exact model, native token counts and total cost. Conflicting observed usage, missing data, invalid numbers or unavailable accounting remain unresolved. It does not retry, dispatch a model completion, guess a nearby generation or replace unknown usage with zero.

The command refuses existing output files, preserves the original report, records its SHA-256, and adds provenance for reconciled fields before recomputing the same gate. Successful task outcomes, Action timings and model TTFT are never substituted from another run. Generation accounting cannot recover an unobserved first-content timestamp. A single failed-measurement run cannot be replaced by a focused case or mixed with arbitrary other runs.

Protocol references: [OpenRouter streaming errors](https://openrouter.ai/docs/api_reference/streaming) can contain a generation ID; [generation accounting](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation) provides native token counts and total cost. Provider response content is allowlisted before saving attribution evidence.

## Historical result

Verification: the full Python suite passed **423 tests**, and all **155 TypeScript tests** plus builds passed. After the review fixes, the **35-test focused telemetry/acceptance subset** passed, including three additional cancellation/redaction cases added after full-suite collection. A subsequent **44-test affected subset** passed after updating the authorized configuration ceiling to $1.00 and checking that larger, nonfinite and nonpositive values remain rejected. Ruff lint/format, ESLint, staged-document Prettier and diff checks passed. These local regression checks made no paid completion calls. This distinguishes the full-suite evidence from the later narrow rechecks rather than claiming a second full run.

The original run-3 report was processed into the separate ignored `eval/reports/ticket15-run3-reconciliation-20261001.json`. Its missing `orders-login` attempt has no saved generation ID, so no accounting lookup was issued for it. The result remains **44/44 tasks, 19/19 safety cases, measurement completeness failed**. The original three reports remain immutable. Their earlier behavior results are valid; complete accounting is still absent.

## Concrete replacement-run plan, authorized 2026-10-01

1. Use the verified telemetry revision and freeze the same 44 cases, model, prompt, schema and parameters.
2. Run exactly one new complete three-run set, retaining failures and all attempt journals. Do not keep rerunning until green.
3. Reconcile missing usage only through exact saved generation IDs and attributable provider accounting, then review all three summaries and provenance. Unknown required metrics leave the gate open.
4. Close Ticket 15 only if all three complete runs satisfy the existing criteria, then proceed to Ticket 16.

The owner explicitly authorized **one replacement three-run set**, with the total key cap increased from $0.75 to **$1.00, reset Never**. A read-only check verified the saved provider setting and **$0.286618458 remaining** before execution. The ignored local `.env` cap was updated to the authorized $1.00. No new deposit or auto top-up is authorized. The prior final set recorded approximately $0.163 plus one unknown attempt; that is a planning estimate, not a guarantee for a new set. No additional replacement set may run without further authorization.

The authorized set subsequently passed the gate after exact-ID accounting reconciliation. See [the replacement results](ticket15-replacement-results.md). The historical missing record remains unresolved; it was not used to close the ticket.
