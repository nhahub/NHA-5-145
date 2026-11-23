# CAP-06 reproducible Lambda package preparation

Continue the approved Stockholm startup/controller topology with a locally
reviewable Python 3.12 ZIP for each fixed role. No resource creation, upload,
runtime selection, credential discovery, model calls or deployment is authorized
by this preparation. Existing safety, zero-cash, Free-plan, Bedrock qualification,
external observation delivery and resource/cost/rollback gates remain open.

## Artifact contract

Build offline from an explicit control-source allowlist and exactly 14 universal
Python wheels identified by distribution, exact version, filename and SHA-256 in
`deploy/lambda-wheels.json`. Keep a matching pip hash requirements file for
separate acquisition. Package all Boto3/HTTPX runtime dependencies, SDK data,
licences and CA data. Exclude development dependencies, local environments,
credentials, configuration, keys, databases and bytecode.

The builder verifies the wheel outer hash, purelib/universal tags, Python 3.12
compatibility, no-extra Linux dependency closure and every RECORD payload hash
and size. Verify then explicitly omit JMESPath's unused standalone
`jmespath-1.1.0.data/scripts/jp.py` CLI, recording it in the manifest. The retained
upstream RECORD remains wheel provenance, while the package manifest describes
installed files. Reject every other unsupported `.data` relocation, links, native binaries, unsafe
paths, duplicate/case-colliding names and unexpected wheel inventory. It supports
these selected wheels, not arbitrary wheel installation. Packaging is a build
tool using the existing pinned `packaging==26.3`, not a Lambda dependency.

ZIP root exposes `handler.py` and imports directly. The handler role is literal
in generated source and cannot be changed by an event or environment. Include
only the required `agent` modules and `waiting.html`. Emit sorted paths, fixed
1980 timestamps, POSIX regular files 0644 and directories 0755, and ZIP_STORED
for cross-build reproducibility. Enforce 50 MiB archive/250 MiB extracted limits,
including an internal manifest with SHA-256 of every other file and dependency
provenance and declared nonruntime omission. Publish with exclusive creation; refuse overwrite. Verification
requires an externally retained archive SHA-256 as well as the manifest; the
manifest alone is integrity bookkeeping, not authenticity.

## Explicit Lambda configuration

`agent/lifecycle/lambda_entry.py` supplies a lazy entry factory for generated
`handler.handler`. Import creates no SDK clients. First invocation copies and
validates a bounded JSON `COPILOT_CONTROL_CONFIG` (version 1, exact fields; no
duplicate keys), then constructs the existing role-specific runtime. Startup
fields: table, namespace, invitation_identity, lifecycle_identity, origin,
controller_arn. Controller fields: table, namespace, invitation_identity,
lifecycle_identity, instance, release. Controller additionally requires the
32–64 byte readiness key as canonical lowercase hex in the separate
`COPILOT_READINESS_KEY_HEX`; startup refuses that key. Keys/configuration are
runtime provisioning concerns and never enter the package or logs.

The environment is read once at first invocation, not module import. Successful
initialization is cached per execution environment. Initialization failure is
latched unavailable until process replacement; do not automatically replay an
uncertain constructor or Action. A startup failure returns generic HTTP 503
with no-store and no CORS; controller failure returns state unavailable. Never
serialize exception details or secrets. Invocation failures cannot reconstruct
the runtime. No scheduler, background loop, SDK retry or fallback is added.

## Verification and remaining limits

Use adversarial synthetic wheels for archive validation and the actual locked
wheelhouse for two role artifacts. Rebuilds from identical bytes must match.
Extract into isolated temporary directories; Python 3.12 `-I -S -B` must import
the artifact without site packages or checkout imports. Mock SDK creation and
exercise missing/invalid configuration plus valid generated-handler delegation;
run existing role factory/DynamoDB/executor/readiness regression tests offline.
Record exact hashes, sizes, dependency inventory and source bytes in evidence.

Windows import and injected runtime tests do not establish AL2023 execution,
Lambda effective IAM/OAC/event behavior, account eligibility, actual model
qualification or deployment acceptance. Linux execution of the exact ZIP remains
a separate required check. Routine implementation details are the builder's call.
