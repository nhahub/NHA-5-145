# Explicit OpenRouter qualification binding

**Owner-approved and implemented with synthetic custody24October2026; native proof passed.** Continue the approved
Controlled Storefront graduation scope. This design covers one missing host
authority boundary, not independent Storefronts, a new model or AWS activation.

**Owner amendment24October:** hash and validate protected evidence/custody at
startup only. There is no runtime file-reading worker or per-request disk hashing.
The20source-file comparison is an offline audit concern and never a runtime
eligibility test. Operator changes take effect through explicit restart/rebinding.

## Intent and evidence

The owner approved the current OpenRouter fallback if Bedrock is unusable.
The retained15October accepted local cohort qualified
`google/gemini-3.5-flash-lite`:43/44core,19/19designated safety and7/7advice.
Its original report remains unchanged. The
[offline reconciliation](../cap06-openrouter-reconciliation.md) reconstructs
the accepted runtime source and proves unchanged synthetic provider payloads.
New authorization/accounting behavior has focused offline regression evidence.
These facts preserve local model-language acceptance; they do not prove deployed
host operation, current key credit or production capacity.

Before this change, the host intentionally always returned provider-unqualified. Implement a
trusted, explicit binding between that accepted model evidence, the executing
release and the configured provider/custody. There is no `ready=true` setting.
Missing, invalid, expired or mismatched startup evidence must refuse.

The owner approved the builder choices below through the explicit implementation
approval in this chat. Approval of this design authorizes implementation/tests with synthetic
custody only. Actual key access/migration, calls/spend, resources, public exposure
and final host/deployment acceptance retain their existing gates.

## Explicit selection and trust

Keep HostSettings v1/v2 unchanged. Add paired optional host CLI arguments
`--qualification PATH` and `--qualification-sha256 HEX`; both or neither are
required. Neither preserves the current closed provider default. A partial pair,
Bedrock configuration or invalid binding bytes/provenance/settings refuses
startup before SDK construction. Validation has two stages: validate everything
available from explicit settings/evidence before assembly, then validate the actual
guard/client after app construction and before serving. A late client mismatch
cleans all constructed resources and refuses; it does not require reordering SDK
construction or imply that an unconstructed client was checked earlier.
No environment variable, bypass flag, inline key or implicit report discovery.

The expected binding SHA256 is an explicit operator choice pinned in the later
root-owned service configuration. It authenticates the exact reviewed binding
bytes; an evidence file cannot approve itself. Changing them requires a fresh
operator pin. This is local trusted-operator authority, not a claim of a third-party
digital signature. Actual configuration installation is outside this slice.

The binding is strict duplicate-free JSON, version1, at most16384bytes, with exact
fields: version, provider, model, release_fingerprint, configuration_fingerprint,
accepted_report_sha256, reconciliation_sha256, provider_key_sha256,
ledger_identity, issued_at and expires_at. Provider/model are fixed to the approved
OpenRouter route. SHA256 fields are64lowerhex; ledger identity is the configured
canonical UUID; time fields are strict integer UTC seconds, with
issued_at<=now<expires_at and a maximum60day interval. No extra keys or interpolation.

Its accepted report digest must be the recorded immutable15October acceptance.
Its reconciliation digest identifies the reviewed offline evidence and code
bindings; neither can be an arbitrary caller-supplied passing score. The exact
accepted report/reconciliation digests are maintained in code and change through review.
This first implementation supports this single accepted model/evidence tuple;
future models need their own acceptance, not a generic self-certification tool.

The canonical reconciliation bytes are
`eval/evidence/cap06-openrouter-reconciliation-20261024.json`, SHA256
`8ae076766b9ac6609b437007f363e1ddd95676a19e99d315f8dffc05112fb9a9`.
That record pins accepted runtime39f03ef and current source8afa7d1. Its
`current_model_contract_sources` supplies the exact20canonical Git-byte SHA256
values for all Python files in agent/llm and agent/inference, plus agent/advice.py
and agent/catalogue_retrieval.py. Those source hashes remain offline provenance;
runtime never walks or pins these20files. A reviewed bugfix/new release requires
normal release verification and a newly pinned binding, not a runtime source-table
edit. The
original accepted-report SHA256 is
`7a168063cc6b179cd484e7c6098923a8592b737752dd3908e0dd3a0e1853fd98`.
The public reconciliation stays an offline audit record; only the separately
protected, operator-pinned binding can be consumed by the runtime verifier.

Load the binding and referenced original-report/reconciliation files using the
existing protected POSIX reader, with bounded sizes (report1MiB,
reconciliation1MiB). Paths are explicit, existing, distinct, outside the release
and in an explicitly supplied evidence directory beside the binding, using fixed
filenames `accepted-report.json` and `reconciliation.json`. They must meet the
same owner/permission/no-symlink/single-hardlink checks as current host secrets.
The accepted report currently occupies470510bytes. Hash and validate exact bytes;
do not rewrite line endings, source hashes, case rows, scores or historical costs.

At startup, the private key digest binds the already loaded explicit provider key without
putting key bytes in a report. It is private custody metadata: never include it in
public evidence, repr, errors or logs. Read the protected key file through the
existing reader during startup and capture its identity. No new key, allowance, settlement,
enable/reset or refund is created. A future private binding preparer may write a
new0600file exclusively from explicit protected inputs; no actual key is read
while implementing/testing it. Generating candidate bytes alone is not operator
approval to pin or install them.

## Effective configuration and actual client

Use canonical sorted JSON of the exact non-secret effective provider settings,
the full explicit inference mapping and the versioned model contract identifier
to derive configuration_fingerprint. Define the canonical fields in one helper
shared by preparer/verifier. Include provider/model, fixed endpoint, effective
timeout30seconds, streaming setting, minimal/excluded reasoning, price ceilings,
non-resettingUSD2cap and the existing output/request bounds. Do not hash the
misleading20second environment hint as OpenRouter's effective timeout.

Bind to the actual app's single GuardedClient and its OpenRouterClient, not only
configuration strings. Check the existing ledger identity, configured prices,
client/settings and release fingerprint. Never construct a second model or guard.
The normal OpenRouter key-limit/remaining-credit GET before every POST remains
unchanged; this verifier makes no network/provider request. A provider's later
outage or key revocation can still refuse that request. Qualification is not a
promise of availability or a new credit allocation.

## Lifetime, freshness and refusal

Read/hash/validate the protected binding, report, reconciliation and key custody
once during explicit pre-loop startup, alongside normal release verification.
Validate the actual guard/client after assembly before serving. Capture an
immutable qualification and custody snapshot. Do not create a runtime I/O worker,
watch files or re-read/re-hash evidence/key files across requests or lifecycle
awaits. Protected0600inputs change through operator action/restart; changes to
disk do not silently reconfigure an already running process.

An owned lightweight verifier uses only the captured snapshot, current time,
closed state and bound in-memory client/ledger configuration. Keep the existing
one-flight1second provider bound and1.5second signed aggregate bound. Every
successful observation yields an internal immutable proof token. After awaiting
lifecycle authority, recheck the same in-memory token, expiry and client bindings;
expired, closed or mutated in-memory authority must refuse. The final request
authorization boundary still runs immediately before the provider POST after the
key check. File-based operator revocation is applied on restart; process closure,
expiry and lifecycle authority still refuse at runtime. Define revocation by those boundaries;
do not promise recall of an already sent request or refund uncertain outcomes.
Renewal and Stop remain independent of qualification.

The host owns verifier lifetime explicitly. Close marks it unavailable and drains
provider callbacks, then closes the remaining host resources in their established
order. Startup failure must clean it too. There is no qualification worker to drain.
The existing trusted callback injection remains a test seam; it cannot be combined
with this production binding to override its result. Error text stays fixed and
redacted, with no key, custody digest, path or rejected input.

## Verification and unchanged gates

TDD at the real private-reader/verifier and host-factory seams: exact positive
synthetic binding; absent/partial CLI pair; duplicate/oversized/missing/tampered
evidence at startup; wrong release/model/client/config/key/ledger; forbidden
permissions, links and aliasing; future/expired/too-long intervals; in-memory
revocation/expiry across lifecycle and provider waits; runtime observations perform
zero evidence/key/source reads; disk changes become effective on restart; Stop/
renewal independence; cleanup exactly once on failure and shutdown. A normally
verified/rebound release with a minor source bugfix must not fail on the old20file
table. No actual provider requests or allowance mutations.

Preserve existing v1/v2 default-false tests and all safety regressions. Test valid
synthetic bindings with actual app assembly while intercepting external authority
and provider I/O. Repeat bounded native Linux startup and refusal with the new
release; label synthetic evidence honestly. Run relevant source checks and one
fresh review. Record new source/profile/archive hashes; never relabel old proofs.

Provider evidence does not grant AWS creation, public activation, deployed browser
acceptance or new model spending. Real protected key/remaining allowance custody,
actual host/systemd/reboot/metadata/capability/log acceptance, qualified capacity,
current resource/cost/rollback approval and desktop/Android deployed tests remain
separate. Production stays closed until an authorized operator later installs and
pins an actual valid binding under those gates.
