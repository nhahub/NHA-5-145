# CAP-06 Linux runtime preparation

24 October 2026. Controlled Storefront only; independent-Storefront generalisation
is outside the graduation target. The Step25 proposal is parked and unmerged.

## What this prepares

`deploy/linux-runtime.json` and `deploy/requirements-linux.lock` separately pin
the 28 runtime wheels already rehearsed on CPython3.12/Linux x86_64/glibc2.34.
They preserve the application's exact direct dependencies and Uvicorn's standard
extras, including uvloop0.22.1. Development tools, editable installs and diagnostic
packaging are excluded. Root `requirements.lock` remains the development lock.

The existing release builder validates the new inventory before invoking build
tools, then packages both files under its existing immutable manifest. Changing
the packaged lock is rejected by release verification. This does not make a
Windows-built release a native Linux installation artifact.

The preparation-only `deploy.linux_runtime` module uses the existing development
packaging library. `inventory(source)` validates the explicit target, profile,
direct project roots and exact hash-lock rendering. `verify_inputs(source,wheels)`
also verifies exact file lengths/hashes, wheel metadata identity, Requires-Python,
wheel tags and complete dependency/extras closure under explicit Linux markers.
The wheel directory must contain exactly the selected28files. It performs no
download, extraction, installation, import, model request or service activation.

The public module functions raise the fixed `Linux runtime inputs refused`
category on failure. They are preparation tooling for trusted reviewed input
directories, not a privileged provisioning interface or publisher-signature check.

## Offline input check

Use the existing Python3.12 preparation environment and a fresh wheel directory
containing only the selected28wheels, acquired/verified separately. Retained public
input provenance is in `eval/linux-host-runtime.json` and the earlier Linux guide;
the diagnostic packaging wheel stays outside the runtime wheel directory.

```python
from pathlib import Path
from deploy.linux_runtime import verify_inputs

result = verify_inputs(Path.cwd(), Path("ABSOLUTE_28_WHEEL_DIRECTORY"))
print(result)
```

This returns metadata including wheel count and lock digest, with
`production_interpreter_approved=False`. It does not approve or install an EC2
interpreter, AMI, operating-system packages or runtime services.

## Native proof and reproduction

The [evidence](../eval/evidence/cap06-linux-production-runtime-20261024.json)
records an actual offline installation into disposable storage in the retained
official AL2023 Python image. The container was non-root, read-only, network-none,
with no capabilities/new privileges and finite CPU/RAM/PID/tmpfs limits. It mounted
only synthetic runtime inputs and wheels read-only; no checkout, home, credential,
Docker socket, application state or production key was mounted. No ports opened.

To repeat, prepare a fresh input directory containing:

- `profile.json`: exact bytes of `deploy/linux-runtime.json`;
- `requirements.lock`: exact bytes of `deploy/requirements-linux.lock`;
- `probe.py`: exact bytes of `eval/linux_runtime_probe.py`;
- `packaging.whl`: the separately hash-checked packaging26.3 diagnostic wheel.

Supply the profile's SHA256 to the probe and retain hashes of all four inputs.
The probe checks every runtime wheel, invokes pip with `--isolated --no-index
--require-hashes --no-deps --only-binary=:all: --no-compile --no-cache-dir`, and
checks exactly28installed distributions. The diagnostic wheel is loaded read-only
for closure checks and is never installed into that runtime.

Use the previously retained image only, with `--pull=never`:

```powershell
& 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' `
  --config ABSOLUTE_ISOLATED_DOCKER_CONFIG `
  -H npipe:////./pipe/dockerDesktopLinuxEngine `
  run --rm --pull=never --platform linux/amd64 `
  --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges=true --pids-limit 64 `
  --memory 1g --memory-swap 1g --cpus 1 --user 10001:10001 `
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777 `
  --tmpfs /rehearsal:rw,nosuid,nodev,exec,size=512m,mode=700,uid=10001,gid=10001 `
  --mount type=bind,source=ABSOLUTE_INPUT_DIRECTORY,target=/input,readonly `
  --mount type=bind,source=ABSOLUTE_28_WHEEL_DIRECTORY,target=/wheels,readonly `
  --entrypoint /var/lang/bin/python3.12 `
  public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406 `
  -I -S -B /input/probe.py PROFILE_SHA256
```

Quote mount arguments when paths contain spaces. Use an outer180second deadline;
the pip subprocess has90seconds. The executable tmpfs permits native-extension
mappings. The probe verifies Python3.12.15/glibc2.34, real Linux dependency closure,
six native imports and absence of image-site fallback. It starts no application,
SDK, model client, Caddy or systemd service. The temporary container removes itself;
the official base image remains. This does not build a Shopping Copilot image or
establish a persistent container deployment.

## Provider choice and remaining gates

Verification:47new lock checks,19host-boundary checks,151host/config/launcher
checks,12release checks plus the new pre-build drift refusal,199TypeScript tests,
builds, Ruff, pip and source-scoped lint/format passed. Fresh code/document review
found no actionable issues. The combined Python run had1367passes,2warnings and
one MemoryError during unchanged Moto/Botocore fixture setup. That entire40test
module passed on recheck without edits. The allocation error is retained in the
evidence; its cause is not established and the combined run is not labelled green.

The owner explicitly permits the existing OpenRouter provider if Bedrock remains
unusable. On24October, the current local selection was
`openrouter` / `google/gemini-3.5-flash-lite`. Status output contained only those
labels; no credentials were displayed, balance queried or provider called.
Preserve the non-resetting$2cap, existing
charges/unknown holds and explicit provider selection. No new deposit, higher cap,
silent switch or extra model-call authority follows from the fallback choice.

Protected HostSettings v1 retains its fixed Bedrock selection. Strict v2 now
supports exactly `openrouter` / `google/gemini-3.5-flash-lite`, with an absolute
external `provider_key_file` read through the protected POSIX file boundary. The
key is bounded printable ASCII, excluded from representations and release files,
and passed only through the explicit Agent environment. Inline keys, extra fields,
other provider/model selections and configurable cap overrides are rejected. Both
versions ignore ambient dotenv selection; v2 fixes the non-resetting cap at $2.00
and preserves the existing inference ledger and allowance validation.

The 55 focused configuration tests cover both versions and protected-secret
refusals. Both provider cases at the application seam retain the authenticated
closed-readiness response, zero model calls and unchanged allowance state. These
checks prepare configuration support; they do not establish actual key custody,
verified remaining credit, selected-model qualification or full native Agent
startup. Those bindings remain open. The host provider verifier stays closed;
existing local model evidence does not establish deployed acceptance.

A [clean native Linux release with real Git provenance](cap06-native-release-openrouter.md)
has now passed its bounded offline build, runtime and archive round-trip checks.
Still open: production interpreter/package/security and provisioning acceptance;
actual systemd boot/
reboot/capabilities/metadata isolation; full Agent readiness and measured combined
capacity; selected-provider qualification and account/cost/bound apply approvals;
then public TLS and deployed desktop/Android/safety/recovery/rollback acceptance.

The architecture remains native Python/Node/Caddy services on the selected EC2
host. Docker supplies disposable local evidence. No new deployment architecture,
AWS resource, production state, IAM grant, DNS record or public certificate is
created by this slice.

Subsequent [native Agent startup with synthetic authority](cap06-native-agent-startup.md) verifies the real Uvicorn/lifespan, signed closed readiness and graceful shutdown. Real external authority, selected-model qualification and actual host/systemd acceptance remain open.
