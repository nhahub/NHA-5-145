# CAP-05 offline Bedrock adapter

The owner selected the next step described in the conditional deployment handoff:
implement the narrow adapter with mocked tests, before separately authorized live
qualification. This slice changes no active provider, credentials or cloud state.
CAP-04 and live CAP-05 remain open. Builder implementation choices below do not
represent a qualified model or account access claim.

Use the existing Python LLMClient/LLMRequest boundary. Add an explicitly configured
Stockholm Bedrock Converse client for the first candidate
`openai.gpt-oss-20b-1:0`. Use boto3 and its default credential chain; construct the
SDK client only when a request is actually made, never during configuration or
factory creation. No custom endpoint, inference profile, arbitrary Region, tools,
streaming or automatic fallback is part of this slice.

Converse receives the existing system/conversation plus the full locally expanded
JSON schema as output-format instructions. This avoids claiming model-specific
forced-tool or native strict-schema support. Existing response_validator remains
authoritative; invalid JSON, incomplete/blocked output, unexpected content or
validator failure produces no output. No language heuristics or prompt changes
outside provider-format instructions. Accept reasoning blocks without exposing
or storing them; reject tool/image/other unexpected blocks. Tool execution and
browser authority remain outside the provider.

One Converse operation uses zero SDK retries, finite connect/read timeouts and
bounded output. Offload blocking SDK work from the event loop. Cancellation must
not release its inference slot while its SDK worker is still running; drain that
bounded worker and discard late output. Authorization is checked immediately
before dispatch and again before output. A canceled request never publishes
late text or refunds an uncertain reservation.

Keep bounded metadata with model, prompt/schema versions, attempt identity,
provider request identity where valid, latency, normalized usage and a fixed
failure category. Never persist response bodies, exception messages, prompts,
headers or credentials in metadata. Expose safe application pause categories for
throttle, timeout, network and provider failures. No retries, even when the caller
allows two attempts.

Reservation sizing shares the same schema expansion as provider formatting,
preserving reference siblings instead of overwriting them. The existing durable
allowance reserves before calls and retains reservations
when the adapter has no verified cost receipt. Initial Bedrock monetary cost is
explicitly unknown; token usage is evidence, not an invoice. Enforce at least the
dated candidate on-demand rate floor USD0.07/M input and USD0.30/M output so this
slice cannot under-reserve the documented route. Do not settle from unqualified
token counts. Cache/reasoning/pricing semantics and live cost receipt reconciliation
remain CAP-05 qualification work. Production requires the existing durable guard;
the OpenRouter key/configuration and USD2 ceiling remain unchanged.

Verify the SDK wire contract without network using a fake client and botocore
Stubber. Cover validation, one-attempt failures, authorization, cancellation/late
output, metadata redaction and bounded history, factory/configuration, guard
reservation retention and refusing under-priced configuration. Run existing safety
regressions and full repository checks once after focused tests. Record exact
offline evidence; do not close CAP-05 or claim speed/accuracy until paid
qualification is authorized and passes its existing thresholds.
