# Ticket 15: local evaluation gate

This milestone tests complete shopping conversations against the real model and browser. A fixed scenario and an independent assertion make the experiment repeatable; they do not make model interpretation deterministic. Scripted CI proves execution contracts, not language quality.

## Running the evaluation

With the normal local services stopped, set `MILESTONE_EVAL=1` and run `python -m eval.milestone --runs 3`. The runner starts its own loopback services and refuses occupied ports before resetting the Storefront. Normal tests continue to use the scripted provider. `--case <case-id>` selects a diagnostic subset; a subset cannot satisfy the 44-case gate. Reports are timestamped under ignored `eval/reports/`, retain failures, and contain no credentials or request headers.

The live runner pins OpenRouter `google/gemini-2.5-flash`, temperature 0, 1,536 maximum output tokens, reasoning disabled, schema 8 and the recorded prompt version. The existing non-resetting $0.75 key cap and price reservation remain enforced before every paid call. It never changes a key limit or buys credits. Per-call provider token/cost metadata includes repair attempts. Unknown usage stays unknown and prevents a complete measurement verdict.

`eval/milestone_cases.py` defines the 44 cases. Its Arabic, Franco-Arabic, English and mixed-language requests include fragments, misspellings, corrections, pronouns, negations, quantity changes, and ambiguous variants. Two filter conversations deliberately omit the product category and permit one explicit answer; they are marked outside the fully-understood one-Action efficiency denominator before the final runs. All seven fully specified filter cases remain in that denominator even if they fail. Follow-up answers are fixture inputs, never a language interpreter used by the application.

Assertions inspect actual page destinations, exact cart lines, the specific Spotlight target, catalogue facts and recommendation labels, and task-specific events. A completion message alone cannot pass a case. Refresh and reconnect preserve measurement records outside the page. Safety scenarios cover bound clear/checkout Confirmation, cancellation and refresh, Sensitive Fields, untrusted page instructions, same-origin enforcement, stale targets, duplicate delivery, pending-model Stop, and Undo after refresh/expiry. Off-origin and stale-target cases exercise the real Bridge directly and are explicitly labelled runtime guards rather than model-language tests.

The Stop case holds the model response in the evaluation-only service, clicks Stop while the HTTP interpretation request is pending, releases the response, and checks that no Action or cart write follows. Waiting for the message HTTP response before clicking Stop is too late: the application may already have emitted its first Action. The original race-prone test result remains in its historical report.

## Measurements and gate

Each report contains pass/fail, failure category, executed Action count, actual model calls, model TTFT/total time, token use and provider cost. Browser timing separates Snapshot construction, settled-observation JSON serialization, Action execution excluding settle, and settle itself. These are observed samples, not a sum assumed to equal task time. Full-document navigation can unload an instrumentation frame; the parent still measures dispatch-to-result latency. The first-Action measurement inclusive of model interpretation is reported separately from browser Action latency.

Streaming is opt-in for the milestone service. The adapter buffers the entire response and validates completion and schema before yielding anything to the Agent; partial text never grants execution authority. TTFT is measured at first content, not response headers or keepalive comments. Provider error paths retain timing/usage already received; unavailable measurements are not fabricated. The normal application's non-streaming default is preserved. Protocol behavior follows [OpenRouter's streaming documentation](https://openrouter.ai/docs/api/reference/streaming).

For each complete run the gate requires at least 40/44 successes, every designated safety case passing, median browser Action latency at most 2 seconds, at least 80% of fully understood filters completing in one Action, median successful navigation at most 3 Actions, and complete measurement evidence. Missing/duplicate case IDs, absent model records, unmatched Action timings and unknown usage prevent acceptance. `eval/tests/test_milestone_report.py` verifies the report's failure behavior using known numerical examples. Existing browser regression suites remain the cost-free CI coverage for execution and safety.

## Repairs discovered during development

- A complete discovery proposal could omit a required category, enter catalogue evaluation and surface an unrelated error. Runtime now returns that missing prerequisite to the model once; unresolved requests receive a useful clarification. No category is inferred by matching shopper words in code.
- A model could put a direction in the cart operation field or choose a quantity textbox instead of an operation button. Repair feedback now includes the precise rejected schema field and current executable button identities, including when the first draft could not parse. The model still selects the line and operation; existing target, bounds and Confirmation checks apply to the repaired proposal.
- The harness initially lost timing samples on refresh, polled the wrong URL after clarification, omitted fictional checkout setup, and accepted insufficient Spotlight/material assertions. Independent reviews identified these gaps; the checks were tightened. Final review follow-up was not completed; the last changes were checked locally.

The complete result table and remaining acceptance status are recorded in `docs/ticket15-results.md`. Passing these synthetic conversations does not replace Ticket 16's uncoached participant study or establish independent-storefront compatibility.
