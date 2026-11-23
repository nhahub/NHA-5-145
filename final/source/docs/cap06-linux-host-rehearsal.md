# CAP-06 isolated Linux host rehearsal

Current follow-up: [host isolation](cap06-host-isolation.md) records fresh minimal
component configs, separate UID/WAL/log and private IPv4/IPv6 packet proof. This
page retains earlier evidence; current native Store/proxy launchers refuse the
original full Agent config used by the earlier rehearsal.

23 October 2026. The full default protected configuration reader and native
Storefront launcher passed in a disposable Amazon Linux 2023 container. Caddy
passed version/adaptation and a captured proxy handoff. No host unit, system
package, production key/state, AWS resource, DNS or public TLS was activated.

Use [the evidence](../eval/evidence/cap06-linux-host-20261023.json) for exact input
digests/results and [the runtime manifest](../eval/linux-host-runtime.json) for
the test-only 29-wheel/vendor inventory. The existing production Python lock is
unchanged. Linux `uvicorn[standard]` needs uvloop, absent from the Windows lock;
uvloop0.22.1 is an explicit diagnostic candidate and packaging26.3 verifies the
complete Linux dependency closure. This does not select a production Linux lock.

## Reproduction and input trust

Run only with disposable synthetic state. The probe creates fake private files
and a disabled fixture allowance inside its temporary container; it is not an
installer or production startup command. Do not point it at real keys or ledgers.

1. In an isolated checkout with the pinned Node/pnpm/Python prerequisites, build
   a fresh production-origin release using the existing builder. Set
   `COPILOT_ENV=production`, `COPILOT_PANEL_ORIGIN=https://app.scpilot.tech`,
   `COPILOT_STORE_ORIGIN=https://store.scpilot.tech` and
   `COPILOT_AGENT_ORIGIN=https://app.scpilot.tech`, then run
   `python -B -m deploy build --output ABSOLUTE_NEW_SOURCE_RELEASE`.
   The build is a local compile/package operation. Do not install or activate it.
2. Create a fresh input directory with `wheels/` and `bin/`. Acquire only the
   exact public URLs in `eval/linux-host-runtime.json` outside the runtime
   container. For each wheel, require its exact filename, byte length and SHA256.
   Generate `requirements.lock` with one line per manifest entry:
   `NAME==VERSION --hash=sha256:SHA256`. Do not resolve newer dependencies or use
   pip inside the container to access an index.
3. Require each vendor archive's recorded SHA256 and SHA512, and the official
   checksum evidence described in [the source research](research/2026-10-23-cap06-linux-host-contract.md).
   Read only the regular archive member
   `node-v24.13.0-linux-x64/bin/node` or `caddy`; never extract the whole archive.
   Bound archive/member sizes, require exactly one selected regular member, and
   verify the recorded binary byte length/SHA256. Place them at `bin/node` and
   `bin/caddy`, executable in Linux. Digest comparison is not publisher-signature
   verification. Retain the original vendor archives and their licence notices.
4. Prepare the portable fixture and augmented profile with the snippet below,
   using new external output names. The existing catalogue seed helper creates
   fictional deterministic test data, not a live catalogue backup.

```python
import hashlib
import json
from pathlib import Path
from eval.linux_host_fixture import prepare
from eval.tests.test_release import seed_catalogue

source = Path("ABSOLUTE_NEW_SOURCE_RELEASE")
inputs = Path("ABSOLUTE_NEW_INPUT_DIRECTORY")
seed_catalogue(inputs / "catalogue.sqlite")
profile = json.loads(Path("eval/linux-host-runtime.json").read_bytes())
profile["fixture"] = prepare(source, inputs / "release.zip")
(inputs / "probe.py").write_bytes(Path("eval/linux_host_probe.py").read_bytes())
for key, name in (
    ("probe_sha256", "probe.py"),
    ("catalogue_sha256", "catalogue.sqlite"),
    ("requirements_sha256", "requirements.lock"),
):
    profile[key] = hashlib.sha256((inputs / name).read_bytes()).hexdigest()
(inputs / "runtime-profile.json").write_text(json.dumps(profile, indent=2))
print(hashlib.sha256((inputs / "runtime-profile.json").read_bytes()).hexdigest())
```

The fixture helper verifies the upstream release before/after traversal, refuses
external targets/cycles and bounds traversal bytes/members. It preserves pnpm's
internal package topology through canonical root-relative link targets; the
Linux probe creates relative symlinks only after writing verified regular files.
Flattening links failed native dependency resolution and is not supported.
Original release metadata and manifest digest remain in `fixture.json`; the
probe constructs a new manifest after transformation. This is a **derived test
artifact**, not byte-identical Windows-artifact or cloud-installation acceptance.
Fixture ZIP timestamps may differ between runs; recompute and supply its digest.

Use the retained image only after verifying its repository digest. A missing
image requires a separate public acquisition step; the runtime command never
pulls it. The following PowerShell template assumes `$inputs` is the resolved
absolute input directory and `$profileDigest` is the printed digest above.
Use an isolated Docker config containing only `{"auths":{}}` and an explicit
local desktop-linux engine. No credentials, checkout, home or engine socket is
mounted in the container. The executable mounts are read-only.

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
  --tmpfs /var/lib/shopping-copilot:rw,nosuid,nodev,noexec,size=32m,mode=755,uid=10001,gid=10001 `
  --mount "type=bind,source=$inputs,target=/input,readonly" `
  --mount "type=bind,source=$inputs/bin/node,target=/usr/bin/node,readonly" `
  --mount "type=bind,source=$inputs/bin/caddy,target=/usr/bin/caddy,readonly" `
  --entrypoint /var/lang/bin/python3.12 `
  public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406 `
  -I -S -B /input/probe.py $profileDigest
```

The primary runner imposed an additional 240-second subprocess timeout; the
offline wheel install has 90 seconds, native version checks five seconds,
Caddy adaptation 15 seconds, each Storefront startup 20 seconds and termination
five seconds before forced child cleanup. A timeout is failure, not permission
to relax limits. If an external Docker client timeout leaves the task-owned
container running, inspect/remove only that exact rehearsal container. Never
reset Docker or stop unrelated containers. No ports are published. `/rehearsal`
is executable because native Python `.so` modules require executable mappings;
`/tmp` and synthetic Caddy state are noexec.

## Verified and still open

The actual full modules, default POSIX private-file reader and all 29 pinned
dependencies ran under Python3.12.15/glibc2.34, non-root UID10001. Six native
extensions loaded from the isolated wheelhouse. Thirteen full-configuration
refusal cases passed; configuration/key/state separation and exact release
binding were checked. No replacement private reader or extracted AST functions
were used. Python SDK creation and external connections were refused; Docker
independently excluded external networking.

Native Node24.13.0 executed the real protected Storefront CLI twice, including
production test-route refusal and authenticated private reads. Catalogue history
and the disabled synthetic allowance with an unsettled reservation stayed intact.
The Agent launcher was imported and refused invocation inside an active event
loop with the fixed redacted error. This does **not** exercise actual Agent
lifespan construction, SDK credentials or signed readiness. Caddy2.11.7 only ran
version/adapt; its exact run handoff was intercepted before exec. No public
listener, certificate validation or ACME operation occurred.

The container is a Lambda AL2023 image, not an EC2 AMI or PID1 systemd host. Real
service-UID provisioning, protected installation, production Linux dependency
selection, systemd252 supervision/capabilities/signals, TLS/DNS, IAM/OAC/events,
capacity and cloud acceptance remain required. Process startup is not readiness;
Bedrock is still unqualified and disabled. No uncertain Action is replayed.

## Inventory and cost ruling

[The dated reconciliation](research/2026-10-23-cap06-inventory-reconciliation.md)
separates two Lambda functions, static/control edge traffic, and shared table/log
allowances. Primary independently recomputed the Decimal rows and sensitivity in
the evidence. The explicit continuous 60-day example totals USD68.360270
infrastructure, or USD79.390270 including the unapproved USD11 future-model
planning allocation and separate existing USD0.03 diagnostic hold. At 120 EC2
running hours the combined example is USD50.878270; 30-second average non-tick
Lambda duration instead of two seconds makes the continuous example USD102.723650.

These are unmeasured scenarios, not spending caps or evidence of a current credit
balance. The old USD78.50 sum does not establish an USD80 fit. Conditional
Scheduler/metric/alarm additions remain unadopted and inactive. No new inference
authorization, inventory selection, credit eligibility, account check or apply
approval follows from this arithmetic. Preserve Free plan/Stockholm/USD0 cash;
the exact resource/cost/rollback package and account/model gates remain open.
