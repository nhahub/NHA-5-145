# CAP-06 local Lambda ZIP preparation

This prepares the approved Stockholm startup/controller functions. Nothing is
uploaded or activated. `python3.12`, handler `handler.handler`, and fixed-role
ZIPs are the intended configuration; Linux execution and deployed acceptance
remain pending. See the dated [AWS/PyPA research](research/2026-10-22-cap06-lambda-package-contract.md).
Exact archive hashes, sizes and verification are in the
[local evidence record](../eval/evidence/cap06-lambda-package-20261022.json).

## Acquire dependencies separately

Use the project Python 3.12 environment with build-only `packaging==26.3` from
the existing development lock. The Lambda runtime lock contains exactly 14
pure Python distributions, including the complete Boto3 and HTTPX dependency
closure. Do not install/copy the Windows environment into a package.

Public wheel acquisition is separate from offline assembly. From the worktree,
using an empty wheel destination:

```text
python -m pip --isolated download --index-url https://pypi.org/simple --only-binary=:all: --no-deps --platform any --implementation py --python-version 3.12 --abi none --require-hashes -r deploy/lambda-requirements.lock --dest .scratch/cap06-lambda-package/wheels
```

All transitives are explicit requirements. The builder independently validates
their no-extra Linux CPython 3.12 closure, so `--no-deps` cannot silently omit a
declared runtime dependency. Review lock changes rather than relaxing hashes.
Original acquisition used exact pins; the retained wheelhouse was subsequently
reacquired offline with these target/hash flags and every wheel verified.

## Assemble and verify locally

```text
python -m deploy.lambda_package build --source . --wheels .scratch/cap06-lambda-package/wheels --role startup --output .scratch/cap06-lambda-package/startup.zip
python -m deploy.lambda_package build --source . --wheels .scratch/cap06-lambda-package/wheels --role controller --output .scratch/cap06-lambda-package/controller.zip
python -m deploy.lambda_package verify --archive <zip> --sha256 <independently-retained-archive-sha256>
python -m eval.lambda_package_smoke --archive <zip> --sha256 <same-sha256>
```

Output must be new; rebuilds use a different filename and must be byte identical
for identical inputs. ZIP_STORED, sorted members, fixed timestamps and explicit
POSIX modes avoid host metadata/compression drift. Both Lambda size ceilings are
enforced locally. Exact source files and every installed dependency file have
SHA-256 entries in `lambda-manifest.json`. The independently retained ZIP digest
is the trust anchor; changing a manifest does not authorize changed code.

Wheels must match outer SHA-256, name/version, universal tags, purelib declaration,
Python requirements and complete RECORD hashes/sizes. Unsafe paths, collisions,
links, native code, bytecode and unsupported relocation are refused. The one
declared omission is JMESPath's unused `jmespath-1.1.0.data/scripts/jp.py` CLI:
its bytes are checked before exclusion and listed in `omitted`. Upstream RECORD
is retained as wheel provenance; the package manifest records installed contents.
Botocore service data, CA certificates, licences and metadata are retained.

The isolated smoke uses `-I -S -B`, a temporary extraction and no site packages,
and forbids socket connection/address lookup plus SDK client construction. It
checks import provenance, exact installed versions, three SDK service models,
CA data, no bytecode, missing-config refusal and injected fixed-role delegation.
Existing Moto/Stubber tests separately exercise the actual runtime factories.
This Windows check cannot prove AL2023 execution or effective cloud permissions.

## Runtime configuration contract

No settings, keys or credentials are bundled. Generated `handler.py` fixes the
role literally; events cannot select it. On first invocation only,
`COPILOT_CONTROL_CONFIG` must hold at most 3072 UTF-8 bytes of exact version-1
JSON. Common fields are `version`, `table`, `namespace`, `invitation_identity`
and `lifecycle_identity`. Startup additionally requires `origin` (the exact
generated CloudFront HTTPS origin) and unqualified Stockholm `controller_arn`.
Controller instead requires `instance` and pinned release SHA-256 `release`,
plus a separate `COPILOT_READINESS_KEY_HEX` containing 32–64 bytes as lowercase
hex. Startup refuses that key. There is no secret in an example or log.

Configuration passes the existing strict `ControlSettings` checks before SDK
creation. Initialization is attempted once per execution environment; a failure
stays unavailable until process replacement. Successful runtimes are reused;
invocation errors do not reconstruct or replay them. Responses disclose no
exception details; startup fails with HTTP503/no-store and no CORS, controller
with `state: unavailable`. The later
[internal scheduled tick preparation](cap06-observation-delivery.md) additionally
raises a fixed redacted failed invocation for exact controller ticks, including
latched initialization failure, so Lambda can count Errors. Other event behavior
stays as above. No background scheduler or automatic retry is added.

Before real use: approve and provision runtime configuration/keys/roles, run the
exact ZIP on the intended Linux architecture, resolve reliable external
observation delivery, prove IAM/OAC/event/account eligibility, and approve the
resource/cost/rollback inventory. Host launcher integration, Bedrock model
qualification and all cloud acceptance gates remain open. No paid-plan upgrade,
OpenRouter fallback or new inference allowance is implied by these artifacts.
