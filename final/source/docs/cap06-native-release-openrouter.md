# CAP-06 native release and protected OpenRouter preparation

24 October 2026. The Controlled Storefront now has a production-origin release
built by the existing builder in native Linux from a clean, genuine Git checkout.
The deployment architecture remains Python/Node/Caddy services under systemd on
EC2. Docker supplies disposable local verification; no custom application image or
persistent container stack was created. Independent Storefronts remain outside
the graduation scope.

## Bound result

| Item                    | Verified value                                                     |
| ----------------------- | ------------------------------------------------------------------ |
| Source commit           | `2dbe015115822d0e2821b194645e416c71d20d30`                         |
| Source tree             | `ff109049c131baab1ac15f29ebf5dc66bc875ef9`                         |
| Source snapshot SHA256  | `f47490964f3fd741b615a245482fa39f0c2d435f04bab99f288d819504ab3a98` |
| Release manifest SHA256 | `bbf04fb131f066492876218bccacf8907a9b19db78408e1eb4eb57ae1ba31944` |
| Native archive SHA256   | `bb525fcf8a218fa9f6aa1d475cb8dc01ee57f842456bad26d044f5a984ce134a` |
| Native archive size     | 4,392,960 bytes                                                    |

The release retains `source_dirty=false`, `local_rehearsal=false`, and the existing
production origins `https://app.scpilot.tech` and `https://store.scpilot.tech`.
These labels do not establish DNS, public TLS or deployment acceptance.

[`eval/native_release_source.py`](../eval/native_release_source.py) captures only
the original shallow Git objects, exact HEAD/tree and minimal fixed configuration.
It refuses dirty source, tracked links/submodules, oversized inputs and output
overwrite. Owner configuration, hooks, credentials, historical objects and ignored
files are excluded. The Linux consumer creates an empty refs directory and uses
real Git checkout/fsck/status; neither provenance nor the release manifest is
rewritten to adapt a Windows-built artifact.

An independent Linux extraction with the standard tar data filter verified all
943 manifest entries (files and links), 192 relative symlinks and 39 contained hardlinks. The manifest
digest, original source commit and public-origin labels survived the round trip.

## Toolchain and offline package inputs

The retained official image is
`public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406`:
AL2023, CPython 3.12.15, Linux x86_64 and glibc 2.34. Native Node 24.13.0, pnpm
11.19.0 and Caddy 2.11.7 are independently digest-bound in the proof profile. Git
2.50.1 was extracted with its licence from the matching AL2023 repository RPM after
published checksum and supplier-signature verification in a temporary private
RPM database. Its native dependencies were present; no host package was installed.
These candidates still require production interpreter/package/security adoption.

The project-only pnpm store contains the 359 locked entries and 6,333 verified
content paths, plus its index. Its canonical manifest SHA256 is
`04df8140b7fb96959eb60a594de1d295caffe75277b0677dee63568441d2cc82`.
It excludes other projects, configuration and credentials; the owner's store is
unchanged. The Python runtime uses the separate 28-wheel hash lock described in
[the runtime guide](cap06-linux-production-runtime.md). Diagnostic packaging 26.3
is external, read-only preparation tooling and is not installed into that runtime.

pnpm's separate supply-chain verifier requests registry metadata even when package
installation uses `--offline`. A metadata-only preparation therefore ran normal
frozen, lockfile-only, script-disabled checks against `https://registry.npmjs.org/`
for the workspace's 359 entries and the exact production deployment's 68 entries.
No packages were materialized and no lifecycle scripts ran in that preparation.

pnpm itself wrote two genuine success records at 2026-10-24T13:49:02–03Z. The
unchanged 919-byte `lockfile-verified.jsonl` has SHA256
`494dd8387148001eb6766474081f235faec0d67e17ba941aca7ae3c5d84d3e0a`;
the source lock SHA256 is
`2ffe54bac902422627c296d5a7619f66a7ef9c6ad2565e854d4663cf05cf0d80`.
The final proof checks both hashes and restores those bytes in its private HOME.
pnpm's own content-hash lookup accepts the relocated locks. Records are not
fabricated or rewritten. The default 1,440-minute release-age check, tarball URL
binding, required integrity, resolution-shape and dependency-alias checks remain
unchanged, with no exclusions or policy-disabling flags.

## Bounded native verification

[`eval/native_release_probe.py`](../eval/native_release_probe.py) verifies the
sealed profile, tools, caches and source before invoking frozen offline install
and the unmodified `deploy.artifact.build`. Use fresh input/output directories and
the exact profile hash; a changed source, tool or lock needs a new bound run.

The proof used the retained image with `--pull=never`, network disabled, a read-only
root, UID/GID 10001, all capabilities dropped and no new privileges. Limits were
two CPUs, 2 GiB memory with no additional swap, 128 PIDs, 64 MiB temporary storage,
1,536 MiB executable build storage and 32 MiB synthetic Caddy storage. Only sealed
public tools/packages, synthetic state and the shallow snapshot were mounted
read-only; the task-owned output directory was writable. No owner checkout/home,
credential directory or Docker socket was mounted and no ports were published.
The outer build deadline was 480 seconds; dependency installation had separate
180-second pnpm and 90-second pip limits.

The actual release proved 28 installed runtime distributions and six native
extension imports without image-site fallback. The native Storefront started
twice, preserved the catalogue and enforced private API authentication. Its
process environment excluded the provider key. Caddy passed version/adaptation
checks only; it did not run or attempt ACME.

Protected HostSettings v2 loaded through the default POSIX reader, refused a
group-readable provider key and a symlink key, and preserved a disabled synthetic
$0.73 allowance with a retained $0.04 uncertain reservation. SDK/provider calls
were zero. The Agent check establishes only its existing running-event-loop
startup refusal. **Full native Agent startup, qualified readiness, combined
capacity, actual systemd and host reboot are unverified.**

## Explicit provider contract and next frontier

HostSettings v1 retains `bedrock` / `openai.gpt-oss-20b-1:0`. Strict v2 permits
exactly the approved fallback `openrouter` / `google/gemini-3.5-flash-lite`, using a
bounded protected external Agent-only `provider_key_file`. It rejects inline
keys, ambient selection, alternative routes and cap overrides. The non-resetting
$2.00 key cap, existing charges and uncertain holds remain binding. Configuration
support grants no additional model calls, top-up or automatic provider switching.

The current host qualification verifier stays closed. Next are actual interpreter,
AMI/package/security and provisioning acceptance; real systemd boot/reboot,
capability/metadata/logging checks; full native Agent readiness and measured
capacity; and selected-provider qualification with actual protected key and
verified remaining allowance custody. Account/Free-plan balance, complete costs,
exact resource/rollback approvals and deployed desktop/Android safety acceptance
remain required before Stockholm cloud activation. No AWS/account/provider API,
actual secret/ledger migration, service activation, public DNS/TLS or push was
performed by this preparation.

Verification:199TypeScript tests, workspace build, source lint/format,270formatted
Python files and pipcheck pass. Complete Agent suite899passes. Complete Evaluation
suite546passes/2warnings/1failure: the unchanged milestone browser fixture raises
`Browser.close: Response has been disposed` during cleanup. Its whole module passes
on an unchanged recheck (1test,12.78s). The original failure is retained; an
uninterrupted green full run is not claimed. No product code or safety guard was
changed to suppress it.

Machine-readable proof and regression results: [native release evidence](../eval/evidence/cap06-native-release-openrouter-20261024.json).

Subsequent [native Agent startup proof](cap06-native-agent-startup.md) extends the original running-loop-only observation to actual Uvicorn/lifespan execution with synthetic external authority. It preserves the default closed provider gate and leaves real host/cloud qualification open.
