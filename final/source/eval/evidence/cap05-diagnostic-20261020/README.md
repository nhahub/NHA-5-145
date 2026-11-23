# First Bedrock diagnostic — failed provider request

The owner approved one fixed diagnostic with at most USD0.02 additional AWS credit
use. Exactly one Converse attempt was made for the existing exposed ar-01 case,
openai.gpt-oss-20b-1:0 in Stockholm, intent-v32/schema9, temperature0 and1536output
tokens. At this first closeout, no automatic retries, further model calls, agreement
changes, upgrade, deployment or active-provider switch occurred. The separately
approved second attempt is recorded below.

The request failed with the adapter's provider_http category after1313ms. There
was no returned output or usage. The adapter at that source revision retained
the AWS request correlation identifier privately, but not its exact AWS service
error code or HTTP status. Do not infer invalid input, access denial, model
unavailability or zero billed cost from the broad category.

The local durable ledger retains USD0.015 of its USD0.02 allowance, with one
uncertain attempt. The remaining USD0.005 is not enough for another reserved
diagnostic. The exclusive claim is consumed and must not be deleted or replaced.
Actual monetary cost is unknown; do not refund/reset the reservation. The
allowance was disabled at closeout without changing its balance or uncertain entry.

Read-only account model availability checks returned AUTHORIZED plus AVAILABLE
agreement/entitlement/Region; GetFoundationModel subsequently reported ACTIVE and
ON_DEMAND. These do not prove actual inference succeeds. CloudTrail Event history
lookups initially returned no matching Converse record; absence is inconclusive
and no logging configuration was enabled. A trace may appear later.

The follow-up code preserves allowlisted AWS service error codes and bounded HTTP
status in future metadata, without provider message bodies or credentials. Two
offline RED/GREEN tests cover it; this does not reproduce or fix the failed live
request. No paid replay is authorized by the telemetry change.

The result summary is sanitized. Original claim, allowance database, frozen plan,
raw launcher report and private correlation details remain in the ignored owned
outputs/cap05-bedrock-diagnostic-001/ directory. The strict qualification and any
later separately reported synthetic evaluation remain unexecuted; CAP-05 is open.

## Separately approved second attempt and applied quotas

The owner then approved one additional USD0.02-credit call. Diagnostic002 used
the identical request hash, bound to the unchanged first result, with its own
exclusive claim and ledger. Exactly one additional provider attempt failed in
703ms with ThrottlingException / HTTP429. No output or usage returned. Its
USD0.015 reservation remains uncertain and its ledger is disabled. Both attempts
together retain USD0.03 against USD0.04 cumulative authorization; actual charges
remain unknown. No third call or full set is approved.

[second-result.json](second-result.json) contains the sanitized second result;
[quotas.json](quotas.json) records the subsequent read-only applied quotas.
GPT-OSS20B on-demand requests/minute and tokens/minute are both zero. Nova Lite
on-demand requests/minute, tokens/minute and daily tokens are also zero. Complete
ListServiceQuotas scan: seven pages, no remaining page; GPT-OSS20B RPM also read
through GetServiceQuota. No quota change was requested. These findings establish
a current runtime quota blocker, not a diagnosis of the account-specific reason,
a blanket restriction on all Bedrock endpoints, or the first call's exact error.

Private002 claim/ledger/raw launcher report remains in its separate ignored output
folder. The utility's fixed internal attempt label is the same in each distinct
ledger; the folder and binding distinguish run002. The first result.json is
unchanged, preserving the second plan's hash binding. AWS research found no
guaranteed self-service Free-plan activation or evidenced Paid-upgrade fix;
see [primary-source findings](../../../docs/research/2026-10-20-cap05-access-preflight.md).
CAP-05 remains open; no provider switch or acceptance waiver is inferred.
