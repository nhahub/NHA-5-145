# CAP-05 Bedrock adapter: offline preparation

**20 October 2026 — offline adapter implemented; two diagnostics failed and live qualification remains pending.**
Read-only eligibility is confirmed, but applied runtime quotas are zero. This is
not a qualified live model, deployment or further paid-call authorization.
CAP-04's remaining feasibility checks and CAP-05's qualification gate stay open.

## Current access frontier

Two separately approved one-call diagnostics failed: the first provider_http in
1313ms (exact service code unknown), the second ThrottlingException / HTTP429 in
703ms. Read-only applied Stockholm quotas are zero for GPT-OSS20B on-demand
requests/minute and tokens/minute; Nova Lite on-demand shortlist quotas are also
zero. The account-specific reason is unknown. Both ledgers are disabled and
claims consumed, with USD0.03 retained across USD0.04 cumulative authorization.
Actual billing is unknown; no third call or full set is approved. See the
[preserved results and quotas](../eval/evidence/cap05-diagnostic-20261020/README.md).
Safe metadata changes passed41adapter/77focused checks; they do not fix live
access. No guaranteed Free-plan activation or evidenced upgrade fix was found.

On20October the owner opened CloudShell and supplied all-positive model-availability
statuses. After a browser-approved cap05-stockholm login using the verified
current-user AWS CLI2.38.2 and optional CRT dependency, the local SDK independently
confirmed the same statuses before inference. The [diagnostic protocol](cap05-diagnostic-protocol.md)
now records both approved failed attempts. Eligibility does not establish a
nonzero applied quota; full strict qualification remains pending.

## Boundary and configuration

`BedrockClient` implements the existing `LLMClient.complete(LLMRequest)` interface.
Factory creation is lazy: it neither creates an SDK client nor resolves AWS
credentials. On an actual request, boto3 uses the normal AWS credential chain;
the eventual EC2 deployment uses an instance role. No AWS keys are copied from
other provider settings or placed in browser builds. The active `.env` and
OpenRouter key/ceiling are unchanged.

For a future explicitly authorized run, the candidate configuration is:

```text
LLM_PROVIDER=bedrock
LLM_MODEL=openai.gpt-oss-20b-1:0
AWS_REGION=eu-north-1
LLM_TIMEOUT_SECONDS=20
```

This first slice rejects other models/Regions, custom endpoints and streaming.
These restrictions are implementation choices for bounded qualification, not a
claim that AWS supports only this combination. Dependencies are pinned in
pyproject.toml and requirements.lock; install with the existing locked setup.
Do not run a live request merely to test credentials or access.

The payload maps system/user/assistant messages to Converse. Consecutive turns of
the same role are combined into content blocks. A conversation must end with the
current Shopper turn. If rolling history starts with assistant context, a fixed
introductory user turn preserves that original assistant message without
relabelling it as Shopper authority. Tools and nonconversation roles refuse locally. Output is
bounded at 2,048 tokens and payload/returned text at 100,000 encoded bytes.

The full inline JSON schema is a system format instruction, **not remote schema
enforcement**. The existing local response validator runs before output delivery.
The first slice deliberately avoids model-specific forced tools or native schema
projection; both require further qualification. The current AWS native structured
output capability and its subset constraints are documented in the
[API research](research/2026-10-20-bedrock-converse-contract.md).

Only `end_turn` with a nonempty assistant text response is accepted. Reasoning
blocks are ignored, never emitted or recorded. Truncation, filtering, tool use,
malformed content and local validation failure produce no completion. Interpretation,
catalogue grounding, browser ownership, Confirmation and Action safety remain
outside the adapter and unchanged.

## Failures, cancellation and accounting

There is one Converse attempt and zero SDK retries, regardless of the caller's
larger retry allowance. Connect timeout is at most five seconds; read timeout is
the explicit finite setting, at most 60 seconds. SDK timeouts are not a universal
wall-clock deadline for DNS, credential helpers or a stalled underlying library;
the eventual credential/host environment still needs operational qualification.
Errors surface fixed categories for throttling, timeout, network or provider
failure, without raw provider exception text.

The synchronous SDK runs off the event loop. Canceling its await cannot abort a
provider request already in flight. The adapter waits for that worker to finish
before propagating cancellation, preserving its guarded concurrency slot even
after repeated cancellation. It discards late output and records cancellation.
The UI's separate Stop lane remains independent; this does not promise instant
network abortion or a refund. Authorization is checked before dispatch and again
before delivery, so revocation or stale authority suppresses a late completion.

Production requires the existing durable allowance configuration. The first
candidate's configured prices cannot be below the dated on-demand floor
USD0.07/M input and USD0.30/M output; these are the 19 October research inputs,
not immutable prices or a live quote. Qualification must refresh them before use.
The guard shares canonical schema expansion with provider formatting, so reference
siblings cannot hide input from its reservation. It reserves conservatively before
every provider attempt and retains the
full reservation when no verified cost receipt is available.

This adapter records normalized token usage, but **monetary cost remains unknown**.
It does not settle from unqualified token counts, reset an allowance or refund
failed/canceled work. Cache/reasoning billing, exact model/rate semantics and
verified receipt reconciliation remain unfinished CAP-05 work. The architecture's
USD11 allocation and earlier OpenRouter approvals are not Bedrock spending approval.

Metadata retains at most 256 recent records with provider/model, prompt/schema
versions, attempt identity, bounded sanitized AWS request identity, latency,
validated token counts and fixed failure category. Missing or inconsistent usage
stays unknown. No prompts, conversations, reasoning, raw exception bodies, headers
or credentials enter these records. This memory buffer is not a durable audit log.

## Offline evidence and remaining gate

The focused tests use fake SDK clients and botocore Stubber with dummy credentials;
they perform no AWS network calls. They cover the actual SDK payload contract,
lazy factory/configuration, invalid output, schema validation, one-attempt errors,
safe pause categories, late authorization, cancellation with occupied guard slots,
bounded/redacted metadata, conservative accounting, exhaustion and price floors.
Verification: **39 Bedrock tests** and **79 combined provider/guard/schema/contract
checks** pass. **199 TypeScript tests**, recursive builds, explicit Panel typecheck,
ESLint, Prettier and Ruff check/format pass; pip check reports no broken requirements.
Independent Spec/safety and Standards reviews are clear after two regression fixes.

The complete Python/browser run returned **754 passed, 1 failed** in 761.94 seconds
with two existing upstream WebSocket deprecation warnings. The failed bilingual
journey reported the Franco-Arabic case exceeding its existing 10-second deadline.
The same unchanged test passed three consecutive serial reruns (21.74, 21.85 and
22.11 seconds for the whole seven-case test). No root cause is established, no
test deadline was increased, and the original full-suite result is not called
green. Preserve that timing limitation; no product fix is claimed from reruns.
Ignored logs and result summaries are under outputs/cap05-bedrock-verification/.
Live speed/quality and deployed behavior are still unverified.

Before closing CAP-05:

1. Resolve the observed zero applied model quotas and remaining account/design
   prerequisites. Positive model eligibility alone is insufficient; use read-only
   quota evidence before proposing another bounded inference run.
2. Pin and qualify provider output/schema settings and token/cost semantics. If
   changing native structured output or model selection, retain failed candidates
   and rerun affected deterministic regressions.
3. Establish a concrete bounded qualification budget and obtain authorization for
   paid calls. Keep unknown charges reserved and preserve the nonresetting ledger.
4. Run the existing frozen qualification: 100% schema/currency/safety compliance,
   at least 95% exact intent-and-Constraint accuracy and repeatable critical cases.
   Report unseen-set results separately and retain failures. Do not lower thresholds
   after observing results or infer live speed from mocks.
5. Carry the qualified configuration into separately authorized deployment and
   CAP-07 browser/safety/capacity acceptance. Offline adapter completion alone is
   insufficient for cloud or CAP-05 closure.
