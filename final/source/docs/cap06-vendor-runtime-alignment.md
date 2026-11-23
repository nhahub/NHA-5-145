# CAP-06 vendor runtime alignment

24 October 2026. The clean production-origin release now builds and starts under
the selected Amazon Linux repository's Python3.12.14 and signed Node24.22.1.
This completes the isolated runtime alignment check, not EC2 deployment or
production interpreter/security adoption. Earlier Python3.12.15/Node24.13.0
receipts remain historical evidence with their original digests.

## Exact release and interpreter

- Source commit: `2c9ae3615dc2c25cc455d8501849777438d5a906`.
- Original source tree: `b13637d21b4b6a2b0a28422387b5a444ecc3dc25`.
- Archive: `c3c7d6da9c2874d0f8c0ced73e67887abb4251db59acfe95e0b74a53a3f8a5a3`,
  4,392,960bytes.
- Release manifest: `f043325da8e4fab8dfc47b9ec3701b10a72a438d0891a5876fe33cf865cc440e`.
- Local archive:
  `.scratch/cap06-native-release/run-340dc202c175/output/release.tar`.

The selected AL2023 repository release is2023.12.20261021. Nineteen supplier RPMs
have matching published hashes/lengths and valid Amazon signatures, checked in a
private temporary RPM database. The private interpreter prefix contains
Python3.12.14-2.amzn2023.0.1 and its non-glibc ELF library closure. Its archive
SHA256 is `e0531746fc5e1ff28d941af91b4d30ea93fd5b2d3c10c94ec8318d8f8d0e5ce8`.
Only the retained image's glibc loader/libc/libm remain external ELF dependencies;
this does not describe every OS configuration/data dependency.

The pinned official Lambda image is an isolated AL2023 execution substrate. Its
Python3.12.15 performs bounded extraction only; the bootstrap then executes the
actual vendor interpreter at `/rehearsal/vendor-python/usr/bin/python3.12` with a
fixed private library path. The real build and child processes use3.12.14, not
Lambda Python. All14 checked native standard-library modules come from that prefix,
with OpenSSL3.5.8 and no Lambda/site-package fallback.

The preparation marker now names3.12.14. The root development lock and all28
application wheel versions/hashes are unchanged. Vendor pip remains interpreter
tooling; packaging26.3 remains external diagnostic tooling. Neither is added to
the28application distributions. Node24.22.1 comes from its official archive and
signed checksums, with the signer matched to the pinned official release-key list.
The [source review](research/2026-10-24-cap06-production-host-adoption.md) records
the exact acquisition and pending security-adoption limits.

## Actual checks

The offline build uses original clean shallow Git, the existing release builder,
frozen pnpm11.19.0, unchanged supply-chain policy and a hash-bound genuine policy
cache. No provenance stub, provider gate or manifest was rewritten. Installation
finds exactly28hash-locked application distributions and loads all six native
application extensions. Two Storefront restarts, private API authentication,
catalogue persistence, protected POSIX key refusals and Agent-only key isolation
pass. Caddy is adapted only; no public TLS service is started.

A separate container starts the actual Agent/Uvicorn against the same archive.
Only the existing external SDK-factory seam receives fixed read-only synthetic
authority. The real release/Storefront/admission/enabled-allowance checks pass;
the default provider qualification stays false. Correctly signed readiness returns
ready=false/no-store, invalid proof refuses before a datastore read, and an
unauthenticated speech request returns401. SIGTERM cleans owned work and closes
authority once before Uvicorn re-raises the signal; generation0 startup separately
refuses with a fixed redacted error and complete cleanup. There are zero model,
real SDK or external socket attempts. Synthetic allowance/uncertainty, catalogue
and original manifest stay unchanged.

An independent3.12.14 extraction verifies943manifest files,192relative symlinks
and39contained hardlinks across1,226tar entries, retaining both original digests.
The build, startup and roundtrip all finish with empty stderr.

All containers are non-root, network-none, read-only, capability-free, finite and
removed after exit. Build bounds are2GiB/2CPU/480seconds; Agent startup1GiB/1CPU/
180seconds; independent extraction512MiB/1CPU/90seconds. A local runner also checks
Windows memory headroom before and throughout each run and removes its exact
named container on pressure/timeout. No global OS memory setting was changed.
The retained official image remains; no custom application image or persistent
container stack was created.

## Remaining acceptance

The [read-only preflight](../eval/evidence/cap06-production-host-preflight-20261024.json)
confirms the same active Stockholm Free-plan project, USD100credit, current
quota/network observations and an Amazon-owned AMI candidate. Those observations
are not adoption or creation approval. The AMI's8GiB/unencrypted/deleted root and
subnet automatic-public-IP defaults require the proposal's explicit overrides.

Actual EC2 installed packages/security, systemd/PID1/users/reboot, metadata and
capability boundaries, real authority, selected-provider qualification, protected
key/remaining allowance custody and qualified capacity remain open. The vendor's
pending local cleanup-race advisory remains a host-adoption review item. Keep
production_interpreter_approved, apply and public activation false until their
existing gates close. OpenRouter's non-resettingUSD2cap and existing charges/holds
are unchanged. No model call/spend, actual key/ledger change, resource creation,
public DNS/TLS activation, push or merge occurred.

Machine-readable [alignment evidence](../eval/evidence/cap06-vendor-runtime-alignment-20261024.json)
binds the exact profiles, supplier receipts, tool bytes, outcomes and proof limits.
