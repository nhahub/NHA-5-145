# CAP-06 restricted host configuration and explicit startup factory

Continue the approved Python/Stockholm host design. No real AWS/model/credential
request, resource/key/DNS/TLS creation, scheduler, upgrade, spend or deployment.
This prepares an explicit startup API, not an activated environment selector/CLI.

## Configuration

Builder choice: deploy/host_config.py supplies frozen HostSettings and
load_host_settings(config_path). Strict JSON version1 exact fields: version,
release, fingerprint, catalogue, table, namespace, invitation_identity,
lifecycle_identity, service_secret_file, readiness_secret_file, inference,
admission_limits. No duplicate JSON fields, extra keys or interpolation.
config <=16384bytes. Secrets are separate raw files (service secret32..128ASCII
non-whitespace characters; readiness key32..64bytes), omitted from repr/errors.
No keys generated or copied from another provider; no AWS credentials in config.

All paths absolute, existing, distinct canonical files outside the release;
release is an existing directory with pinned64lowerhex manifest fingerprint.
Strict production sibling origins and private127.0.0.1:4000 are fixed in code.
Authority identities canonical UUIDs, table/namespace match existing bounds.
inference is exactly agent.inference.config.REQUIRED string keys; reuse current
load_llm_settings/configured_guard validators with fixed Bedrock GPT-OSS20B,
Stockholm, timeout20, production and lexical catalogue retrieval. No enable/reset.
admission_limits is exactly the existing AdmissionPolicy constructor limit names
with strict integer values, validated using existing constructor (dummy store).
Mapping values are immutable copies; HostSettings construction also validates,
so direct construction cannot bypass the semantic contract.

Default private reader supports POSIX only, refuses on Windows rather than claim
ACL enforcement. Open absolute path with O_NOFOLLOW|O_NONBLOCK; fstat regular file,
one hardlink, owner root/current effective UID, no group/other permission bits and
owner-read. Parent directories must be root/current-owned and not group/other
writable, up to root. Reject symlink parents and compare fstat before/after bounded
read to detect replacement/mutation. Generic error, no content/path disclosure.
Raw key files receive same checks. A trusted read_private(path,limit) injection
exists only for tests; no command-line/environment bypass. Linux filesystem and
owner permissions remain unverified on this Windows machine; test metadata logic.

## Application isolation

create_app gains environment=None. When provided, copy it and use it consistently
for settings, allowance/admission/lifecycle, identity, evaluation/test-clock and
retrieval selection; no dotenv/local identity or ambient environment fallback.
identity_config and catalogue-client selection accept the same explicit mapping.
StorefrontService validates explicit mode and disables proxies for async identity
and synchronous Confirmation calls. Existing default configuration behavior stays
when omitted. Default module app is created lazily via **getattr**('app'), cached,
preserving agent.app:app and from-import usage. Import alone creates no app/client.
No broad module relocation or changed monkeypatch globals.

## Explicit factory

deploy/host_bootstrap.py create_host_app(settings, \*, sdk_factory=existing fixed
Stockholm \_sdk, provider_ready=unqualified_provider, model_client=None,
http_transport=None). Must be called before an event loop starts; refuse an active
loop so synchronous startup validation/DynamoDB reads cannot block serving.
It reads existing authority only, never initializes state. Default SDK is called
only when explicitly invoking this factory. Tests inject Moto/dummy credentials.
No auto launch/systemd/CLI change or current backend selection.

Construct remote invitation/lifecycle authority, owned AsyncAdmissionPolicy,
StorefrontService, and create_app using the immutable explicit environment. The
Agent constructs one GuardedClient through its normal guard path, no double guard.
Pass explicit lexical CatalogueClient to avoid environment-selected hybrid cache.
Readiness factory creates HostChecks against app.state.llm_client plus HostReadiness.
Default factory execution root must equal the selected canonical release before
SDK creation; a named artifact alone cannot establish which code is running.
Synthetic tests patch this private observation only and do not claim deployed
execution. Optional trusted clock injection follows the existing Lambda test seam.

Work subclass awaits strict provider_ready() is True outside the lease actor lock,
then uses AsyncLifecycleWork's normal check before admitting a request or model
entry/output. A shared one-flight verifier has a1sresponse bound and retains slow
cancellation cleanup; health and work cannot accumulate verifier tasks. Pending
renewal proceeds while qualification is unresolved. Recheck remote authority and
local failed/generation after callback. Default unqualified verifier means even
stale persisted healthy=true cannot invoke a model or consume inference allowance.
Stop ownership remains available; pending work renewal never depends on provider.
No new qualification format or configurable ready=true flag is added.

Owned readiness close drains health then HostChecks. Existing app lifespan then
closes work, admission and service. Owned admission drains pool before closing its
shared SDK off-loop exactly once. Factory failure before lifespan cleans every
constructed pool/service/client, generic ValueError without cause/context leakage.
No process lifecycle, provider, state or ledger initialization/reset. Current
Bedrock quotas remain zero and default proof always false.

## Verification

RED/GREEN strict config bounds/types/secret repr, duplicate fields, insecure file
metadata/parents and non-POSIX refusal. Real POSIX enforcement not claimed.
Subprocess import with invalid ambient provider must create no default app.
Explicit app environment overrides conflicting local/evaluation settings without
modifying os.environ, keeps test endpoints closed and exact CORS.
Moto/SQLite/artifact fixture factory+lifespan tests: initialize bound generation,
signed prooffalse and request503 with default unqualified provider, no model SDK
calls or allowance charge, stop available. Invalid/missing authority and malformed
config fail before serving, close exact owned clients/resources. Tests intercept
private HTTP and use fake model doubles, never actual inference.
All Agent safety/recovery regressions, host checks and fresh release packaging,
lint/format/pip, independent review and evidence/local commit.

Remaining: real POSIX deployment permissions/config/key provisioning, Linux Lambda
package, reliable approved external observation delivery/effective IAM/resource
cost/rollback approval, Bedrock qualification and deployed acceptance. No gate closes.
