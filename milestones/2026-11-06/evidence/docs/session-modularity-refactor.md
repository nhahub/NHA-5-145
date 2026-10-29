# Session modularity refactor

Authorized: 2 October 2026. Baseline: `50a01b2`. Scope: preserve the existing runtime while separating responsibilities currently concentrated in `agent/sessions.py` (1,822 lines).

The owner clarified that implementation is carried out by the owner and coding assistant; other listed team names are not available contributors. The assistant now owns this refactor. It does not depend on outside team help. CAP-02 remains incomplete and deferred: collection preparation is not a frozen dataset release.

## Design and constraints

Keep the public `SessionStore` methods, imported domain records/errors, HTTP routes, wire payloads and execution behaviour compatible. Use composition and explicit delegation rather than mixins, dynamic forwarding or a new framework. Shared records describe state; the registry owns lookup/expiry/lease rules; task modules own their respective transitions. HTTP/SSE delivery stays outside task policy.

No prompt, phrase interpretation, safety policy, state transition, retry budget or feature change is authorized here. Existing scripted fixtures remain test fixtures. No tests are added or changed to accommodate the extraction. No paid model runs are needed to verify a structural refactor.

## Extraction sequence

1. Extract shared session/task records and `SessionRegistry`: creation/lookup, exact 30-minute inactivity semantics, activity touch, lease assertions and takeover. Keep the registry's state independent of task policy.
2. Extract the existing SSE encoding and polling/delivery adapter, preserving cursor validation, event ordering, ownership filtering and disconnect handling.
3. Separate task interpretation, execution feedback/answers and refresh recovery. Share only the existing runtime dependencies and common policy operations. Retain `SessionStore` as the stable entry point used by HTTP handlers and regression tests.

The task extraction may leave large individual methods where splitting their branches would become a separate behavioural-risk change. This pass makes responsibility ownership explicit without claiming that every remaining complexity is resolved.

## Verification and completion

- Baseline: existing session/recovery checks, 29 tests, passed before editing.
- Run the full existing Python suite after each extraction; preserve its 458-test scope.
- Check moved implementations structurally against the baseline where practical, allowing only dependency routing and import/location changes.
- Run repository formatting, lint, TypeScript tests/build and independent Spec/Standards review before final completion.
- Record actual results and remaining limitations after verification. Preserve unrelated working changes and the `mvp-1` tag; commit only this work.

## Verification ledger

- Registry/state extraction: **458 Python tests passed in 395.80 seconds**. Baseline task methods and moved registry methods were AST-compared: only the activity method name/delegation changed. Commit `b47ea0d` contains only this runtime slice.
- TypeScript regressions: **155 passed** (84 Bridge, 32 Panel, 39 Storefront); workspace builds/typechecks and ESLint passed. No TypeScript source changed.
- SSE adapter extraction: **458 Python tests passed in 389.86 seconds**. Encoding function and route body AST-match the original implementation. Commit `46a941d` contains only this slice. Independent Spec and Standards reviews passed for registry/SSE.
- Task extraction: **96 focused existing tests passed**. All 15 moved task methods and five shared policies AST-match the baseline after normalizing dependency routing; public signatures are unchanged. Final full suite: **458 Python tests passed in 388.99 seconds**. Independent Spec and Standards reviews found no actionable findings.

## Module map after extraction

| Module                         | Owns                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `agent/sessions.py`            | Stable public SessionStore entry points and domain exports; explicit composition.                          |
| `agent/session_registry.py`    | Session storage, lookup, inactivity expiry, activity touch and tab ownership.                              |
| `agent/session_state.py`       | Shared session/task records, statuses and errors.                                                          |
| `agent/session_stream.py`      | HTTP event cursor validation, SSE encoding, polling and owner-filtered delivery.                           |
| `agent/task_runtime.py`        | Injected dependencies and shared origin, observation, Confirmation offer and uncertain-mutation policy.    |
| `agent/task_interpretation.py` | Model-call lifecycle, clarification context, catalogue/advice completion and interpretation retry/failure. |
| `agent/task_commands.py`       | Shopper messages/answers, bound Confirmation consumption and Stop.                                         |
| `agent/task_results.py`        | ActionResult identity checks, duplicate handling and execution progression.                                |
| `agent/task_recovery.py`       | Refresh state and reconciliation without replaying uncertain Actions.                                      |

Task modules depend on the registry/shared runtime, never on the SessionStore facade. Shopper commands can enter interpretation; the interpretation module does not call back into commands. Recovery shares policy helpers rather than calling back into HTTP. Mutable domain records remain explicit; this is an in-memory design, not a persistence or concurrency redesign.

The ActionResult handler remains a large method (513 lines before formatting changes). Its branch logic was preserved deliberately in this pass. High-level responsibility ownership is improved; a later, separately verified extraction can split its cart, guarded and navigation result paths. The public facade adds delegation lines, so total project line count is not a meaningful success metric.

## Completion — 2 October 2026

All three extraction stages passed the unchanged full 458-test Python suite separately. Ruff lint/format checks, repository Prettier checks, 155 TypeScript tests, workspace builds/typechecks and ESLint passed. Both independent review axes reported no actionable findings. Documentation links were checked. No test expectations, LLM files, prompts, safety policy, provider budget or live inference changed. The two earlier slices are separate commits; the final task extraction and working-arrangement documentation are committed separately.

The facade is 203 lines versus 1,822 originally. Responsibilities are now independently located; this is not a claim that the underlying state machine became simpler or that all future edge cases are proven. The remaining large ActionResult method is explicitly deferred to a later bounded refactor. Existing mutable state, in-memory storage and concurrency assumptions are preserved.
