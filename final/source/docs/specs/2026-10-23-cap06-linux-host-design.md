# CAP-06 isolated Linux host rehearsal

The owner requested continuation of full protected Linux host checks. Verify the
actual host configuration modules and native binaries without installing anything
on the PC/WSL or activating AWS, systemd or public HTTPS. No product dependency,
provider, budget authorization, selected cloud inventory or deployment gate changes.

Use the retained official AL2023 Python3.12 linux/amd64 image by its existing
digest, network none, read-only root, non-root UID, no capabilities/new privileges,
finite CPU/process/RAM/temporary filesystem limits, no host credentials, Docker
socket or home/config mounts. Public vendor/PyPI acquisition is a separate step;
run-time installation uses an explicit hash-pinned wheelhouse offline. Existing
project pins stay unchanged; uvloop0.22.1 satisfies the Linux-only Uvicorn standard
extra, with packaging26.3 for diagnostic closure checks. This test manifest is not
an adopted production provisioning lock or a modification of requirements.lock.

Stage vendor Node24.13.0 and Caddy2.11.7 linux-amd64 archives with verified official
digest evidence. Extract only their selected binaries, mount read-only at the
fixed /usr/bin/node and /usr/bin/caddy paths. Node may listen only on container
loopback4000. Never run/start/reload/validate Caddy's public ACME profile: version
and adapt only. A captured proxy exec boundary may verify arguments/environment
without handing off to Caddy run.

Build a fresh production release using the existing builder. The Linux rehearsal
normalizes verified internal Node dependency links to relative Linux symlinks; validate
every resolved target remains inside the source release, reject cycles and bound
archive size/member count. Retain the upstream release-manifest digest and file
provenance. Construct a new manifest after that explicit transformation; do not
claim byte-identical execution of the Windows artifact. The derived artifact is
for rehearsal only, not the approved cloud installation artifact.

Rehearsal ruling: flattening pnpm links breaks Node's realpath-based dependency
resolution (`body-parser` was not found). Preserve the verified package topology,
with root-relative canonical targets in provenance and relative symlinks created
inside Linux. Both the failing native run and a RED/GREEN link-topology test were
observed before the successful full run. No production launcher change is needed.

Inside private temporary Linux storage, load the entire actual HostSettings module
through its default POSIX reader against the complete derived release, synthetic
separate key/config files, fixture catalogue and disabled test allowance ledger.
Check positive binding and representative permissions/symlink/hardlink/FIFO/schema/
secret/release/state refusal. No real key/ledger is read, created or reset. Block
SDK construction and non-loopback Python connections; Docker has no external
network. Verify installed dependency versions, native imports and closed Linux
dependency closure including Uvicorn standard extras, with no image/checkout/site
fallback in the actual probe interpreter.

Exercise the actual Storefront launcher in a child process through protected
config and native Node exec, including restart/catalogue preservation and public
test/private-read boundaries. Import the Agent launcher and verify closed startup
conditions without creating a real SDK. Verify actual Caddy version/adaptation and
captured proxy handoff. Record binary/image/archive/source/runtime digests and
checks with exact limits; no arbitrary host path or command execution interface.

This closes only the tested offline Linux module/configuration/executable seams.
Actual systemd252/PID1, service UID provisioning, capabilities, shutdown/capacity,
public TLS/DNS, IAM/OAC/event/account access and Bedrock qualification remain open.
Separately reconcile the old inventory/cost arithmetic against current primary
sources, explicitly keeping conditional additions and authorizations separate.
