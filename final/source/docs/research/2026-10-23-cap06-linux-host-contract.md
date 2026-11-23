# CAP-06 protected Linux host rehearsal contract

Researched 23 October 2026. This is a proposed local, offline test contract,
not execution evidence or deployment authorization. Research read repository
sources and public upstream documentation/release metadata only. No binary or
wheel was downloaded, installed or executed; no Docker command, account API,
credential, model, unit activation or public Caddy operation was used.

## Scope and existing contracts

Use the already retained official Python 3.12 Amazon Linux 2023 image, explicitly
`linux/amd64`, without pulling or changing it:

```text
public.ecr.aws/lambda/python@sha256:25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406
```

AWS documents Python 3.12 images as AL2023 based; this identifies the distribution
family, not an EC2 host or systemd environment. Retain local image ID,
repository digest, architecture, interpreter and libc observations for the exact
run. [AWS Python base images](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html)

Repository inputs inspected: `pyproject.toml`, `requirements.lock`,
`deploy/host_config.py`, `deploy/host_component.py`, `deploy/host_agent.py`,
`deploy/host_bootstrap.py`, `deploy/lambda_package.py`, `deploy/lambda-wheels.json`,
`deploy/artifact.py`, the public Caddyfile and prepared service units. The
checkpoint distinguishes the existing eleven AST-extracted Linux filesystem
checks from full-module configuration acceptance. The worktree used for this
research did not contain `docs/graduation-scope.md` or `store/src/server.js`;
graduation scope was read from the primary `D:/agent depi` checkout. A later
rehearsal must acquire a complete verified immutable release rather than assuming
this research checkout itself is runnable.

`load_host_settings` must run with its default real POSIX reader; injecting a
reader would skip the required protected-file checks. Its paths require
non-writable protected ancestors, private owner/root-owned single-link regular
files, no symlink/FIFO substitution, bounded reads, a valid immutable release
manifest/fingerprint, separate catalogue/ledger/private paths, and validated
inference/admission configuration. `host_component.command` additionally requires
the actual importing release root to equal `settings.release`; a monkeypatched
`_runtime_root` is only a unit test. Caddy storage is fixed at
`/var/lib/shopping-copilot/caddy` and must already satisfy its owner-only directory
contract. Use disposable synthetic state only; retain no real keys or ledgers.

## Portable executable acquisition and identity

The repository engine range and launcher's version check require Node 24,
minimum 24.13.0 and below 25. One exact compatible rehearsal candidate is
24.13.0; this is the minimum contract example, not a claim that it is the newest
or the patch to provision later. The official release exists and links the
portable Linux x64 archive.
[Node 24.13.0 release](https://nodejs.org/en/blog/release/v24.13.0)

| Input               | Exact public URL                                                                                                                  | Retained digest                                                                      |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Node archive        | [node-v24.13.0-linux-x64.tar.xz](https://nodejs.org/dist/v24.13.0/node-v24.13.0-linux-x64.tar.xz)                                 | SHA-256 `e798599612f4bb71333a3397ab0d095fd62214e115aea45aa858a145fc72d67e`           |
| Node checksum list  | [SHASUMS256.txt](https://nodejs.org/dist/v24.13.0/SHASUMS256.txt)                                                                 | Select the exact archive basename; do not use a floating version URL                 |
| Caddy archive       | [caddy_2.11.7_linux_amd64.tar.gz](https://github.com/caddyserver/caddy/releases/download/v2.11.7/caddy_2.11.7_linux_amd64.tar.gz) | SHA-256 `727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b`           |
| Caddy checksum list | [caddy_2.11.7_checksums.txt](https://github.com/caddyserver/caddy/releases/download/v2.11.7/caddy_2.11.7_checksums.txt)           | List file SHA-256 `5d27b76b95f496638d79208c55250317b8755fd9e90005f7466aa32956944a90` |

The Caddy release API reports the archive/list SHA-256 values above. The
checksum list itself has **SHA-512**, not SHA-256, archive entries. Its exact
Linux amd64 archive entry is:

```text
a7a433a1b133efc3c8d10eb0b99d52a24b5ef5c322dc77f5282182b1c0402139ab83f3a99f0c52409df77d20123fb0b523edad8a66d8f5e49136197bf61ef0e7  caddy_2.11.7_linux_amd64.tar.gz
```

Verify both algorithms against their corresponding sources before extraction;
retain source URL, basename, retrieval time, archive length/digests and extracted
executable digest. Archive and executable digests identify different bytes.
[Official Caddy release API](https://api.github.com/repos/caddyserver/caddy/releases/tags/v2.11.7),
[Caddy release](https://github.com/caddyserver/caddy/releases/tag/v2.11.7)

Checksum comparison establishes matching bytes against retained metadata; it is
not a substitute for signature verification. Caddy documents Sigstore asset
signatures and companion certificates. A later provenance check must use its
documented identity/issuer verification and retained verification result rather
than claiming a checksum proves publisher identity. This research installed no
signature tooling. [Caddy signature verification](https://caddyserver.com/docs/signature-verification)

Node's versioned build contract says official Linux x64 binaries support glibc
2.28 or newer, libstdc++ 6.0.25/`GLIBCXX_3.4.25` or newer, and kernel 4.18 or
newer. AL2023 documents glibc 2.34. That establishes a compatible glibc floor,
not proof the minimal Lambda image contains every shared library. Record exact
loader success/failure; missing libstdc++ must fail visibly, without an implicit
package-manager install or host-library copy. Docker uses its Linux VM's kernel,
so this also does not test the eventual EC2 kernel.
[Node 24.13.0 build requirements](https://github.com/nodejs/node/blob/v24.13.0/BUILDING.md),
[AL2023 core toolchain](https://docs.aws.amazon.com/linux/al2023/ug/core-glibc.html)

## Explicit CPython 3.12 Linux dependency closure

`uvicorn[standard]==0.35.0` declares `uvloop>=0.15.1` on CPython Linux;
`colorama` is Windows-only. The existing Windows-oriented lock includes the
other standard dependencies but no uvloop. Installing only that lock with
`--no-deps` would leave the declared Linux extra incomplete; resolving the
editable project from the network would silently select an unpinned uvloop.
[Uvicorn 0.35.0 metadata](https://pypi.org/pypi/uvicorn/0.35.0/json),
[versioned upstream definition](https://github.com/encode/uvicorn/blob/0.35.0/pyproject.toml)

Proposed approach: prepare a separate, explicit host-rehearsal requirements and
wheel inventory, preserving all reached existing versions and adding the
deliberate candidate `uvloop==0.22.1`. Do not modify the Windows lock, dependency
declaration, production interpreter policy or Lambda builder as a side effect.
The candidate has an official CPython 3.12 Linux x86_64 wheel and satisfies the
declared requirement; its selection still needs to be recorded in the later
implementation/evidence. [uvloop 0.22.1 release metadata](https://pypi.org/pypi/uvloop/0.22.1/json)

Read-only research evaluated official PyPI `Requires-Dist` metadata recursively
from `boto3`, `fastapi`, `httpx`, `python-dotenv` and `uvicorn[standard]`, using
CPython 3.12.15/Linux/x86_64 markers and propagating extras. It reached exactly
28 distributions, with no unsatisfied version or missing dependency. This is a
metadata closure check; the future assembler must repeat it against the
**downloaded wheel METADATA**, including Requires-Python and wheel tags. PyPI's
release JSON endpoint supplies exact file URLs, digests and yanked status.
[PyPI JSON API](https://docs.pypi.org/api/json/)

Proposed inventory below uses native target wheels wherever published, including
the optional native websockets wheel rather than its alternative pure wheel.
All SHA-256 values were read from the corresponding official
`https://pypi.org/pypi/NAME/VERSION/json` `urls` entry; no wheel bytes were fetched.
The filename contains the exact proposed distribution/version pin.

| Exact wheel filename                                                                             | SHA-256                                                            |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| `annotated_types-0.8.0-py3-none-any.whl`                                                         | `f072f4d804ea359e4eaf198b1af7a8b0943881a87f31bb764f8bf219bb9419e0` |
| `anyio-4.15.1-py3-none-any.whl`                                                                  | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` |
| `boto3-1.43.115-py3-none-any.whl`                                                                | `6667a0c21d48dc125dbba88444bc8a601ce881a99341a0e6169f9333898e620d` |
| `botocore-1.43.115-py3-none-any.whl`                                                             | `9ceda640c868bc15f5399129e8cfdef8cbb4b350e8a99547c9b5f477cfb9619a` |
| `certifi-2026.7.22-py3-none-any.whl`                                                             | `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775` |
| `click-8.5.0-py3-none-any.whl`                                                                   | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` |
| `fastapi-0.116.1-py3-none-any.whl`                                                               | `c46ac7c312df840f0c9e220f7964bada936781bc4e2e6eb71f1c4d7553786565` |
| `h11-0.16.0-py3-none-any.whl`                                                                    | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` |
| `httpcore-1.0.9-py3-none-any.whl`                                                                | `2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55` |
| `httptools-0.8.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl`   | `b15fc622b0f869d19207c4089a501d9bcc63ca5e071ffdd2f03f922df882dcb2` |
| `httpx-0.28.1-py3-none-any.whl`                                                                  | `d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad` |
| `idna-3.19-py3-none-any.whl`                                                                     | `815e7be7a7806d54abb586dc943addc79e8b2ee16915059658cbeff4b1b43bf4` |
| `jmespath-1.1.0-py3-none-any.whl`                                                                | `a5663118de4908c91729bea0acadca56526eb2698e83de10cd116ae0f4e97c64` |
| `pydantic-2.13.5-py3-none-any.whl`                                                               | `346a034f080da3755d8e9cb5e00e8b07de1d39e4f6e2c87d8ab7cafa0b269a73` |
| `pydantic_core-2.46.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`                | `0fc5be0abd4a407e200d844b404e33639a554e7bd0d448e7b9ae181be4789ac2` |
| `python_dateutil-2.9.0.post0-py2.py3-none-any.whl`                                               | `a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427` |
| `python_dotenv-1.2.3-py3-none-any.whl`                                                           | `904552145e8bfed22162c09dab1c2b9b54fefa7b23ba780f4f26ca0316b0f0d9` |
| `pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl`  | `ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc` |
| `s3transfer-0.19.3-py3-none-any.whl`                                                             | `24eb7535804306355e31c952a90022bf5b2f9d760f9a11062c7493a217c08553` |
| `six-1.17.0-py2.py3-none-any.whl`                                                                | `4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274` |
| `starlette-0.47.3-py3-none-any.whl`                                                              | `89c0778ca62a76b826101e7c709e70680a1699ca7da6b44d38eb0a7e61fe4b51` |
| `typing_extensions-4.16.0-py3-none-any.whl`                                                      | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |
| `typing_inspection-0.4.4-py3-none-any.whl`                                                       | `65b8397ba37ccbce054456aaccddfc91e6e3083c92824df348d96ca832f3f147` |
| `urllib3-2.8.0-py3-none-any.whl`                                                                 | `0cf3cae568d36aa9576b28dfb35f11328f1cb974ca7647d9475ebb86c75ac6e3` |
| `uvicorn-0.35.0-py3-none-any.whl`                                                                | `197535216b25ff9b785e29a0b79199f55222193d47f820816e7da751e9bc8d4a` |
| `uvloop-0.22.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl` | `7b5b1ac819a3f946d3b2ee07f09149578ae76066d70b44df3fa990add49a82e4` |
| `watchfiles-1.2.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`                    | `e53a384f76b631c3ae5334ce6a52f0baa3a911eb94a4eac7f160079868b716d5` |
| `websockets-17.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl`   | `0c863507ada5805517ca6dff1c524dcd42942efe6304dacf06700878398d21a6` |

The six native wheel selections are pydantic-core, httptools, PyYAML, uvloop,
watchfiles and websockets. Their manylinux tags include a glibc baseline no
newer than AL2023's 2.34. Actual extension imports remain necessary. Pydantic
2.13.5 specifically requires pydantic-core 2.46.5, so swapping only a convenient
core wheel is invalid.
[Pydantic metadata](https://pypi.org/pypi/pydantic/2.13.5/json),
[core wheel metadata](https://pypi.org/pypi/pydantic-core/2.46.5/json),
[platform tag specification](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)

Do not apply `deploy.lambda_package` unchanged: it intentionally requires its
14-distribution pure-wheel closure, rejects `.so` files and requires
`Root-Is-Purelib: true`. Reuse its _principles_—externally retained archive
digests, bounded members, traversal/symlink/collision rejection, metadata/tag
checks, RECORD validation and explicit closure—not its incompatible allowlist.
Keep this host assembly separate from the already verified Lambda ZIPs.

## Proposed acquisition and offline assembly workflow

1. Prepare a new workspace-only acquisition directory. Retain each exact PyPI
   release JSON URL, filename, file URL, SHA-256, size and yanked flag. Refuse an
   unexpected name/version/tag, yanked file, source archive or missing wheel.
   Download only the 28 selected filenames and the pinned Node/Caddy assets
   after acquisition is authorized; compare bytes to the retained digest before
   extraction. Never install into Windows `.venv` or system directories.
2. Generate a complete hash-locked rehearsal input from that inventory, including
   the explicit `uvloop==0.22.1` decision and Uvicorn's `standard` extra. Use
   exact wheel URLs/filenames when fetching to avoid host-marker resolution.
   Pip's cross-target flags select wheel compatibility; do not assume they fully
   reproduce Linux dependency marker evaluation when invoked on Windows.
   `--only-binary=:all:`, explicit complete pins/hashes and `--no-deps` are valid
   only because closure is independently checked for the Linux environment.
   [pip download](https://pip.pypa.io/en/stable/cli/pip_download/)
3. In the pinned offline image, assemble into a fresh disposable directory from
   those wheels only. Either use pip with `--no-index --find-links /input/wheels
--require-hashes --only-binary=:all: --no-deps --no-compile --target ...`, or a
   separately reviewed wheel extractor that correctly handles native layouts
   and any `.data` directories. Do not use `-e .`, dependency resolution,
   setuptools build isolation, an sdist, package-manager fallback or base-image
   site-packages to fill gaps. Every installed distribution must be attributable
   to the 28-entry inventory. Hash-checking requires all dependencies pinned and
   hashed; it cannot repair an omitted Linux conditional dependency.
   [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/)
4. Keep dependency materialization outside the immutable release tree. Verify
   the release archive's independent digest, safe members and `release.json`
   manifest before importing. Build only synthetic protected catalogue, ledger,
   private config and secret fixtures inside the disposable Linux filesystem.
   Do not import the release from one path while claiming another as its runtime
   root, or write dependencies into the manifest-verified release afterward.
5. Run a standard-library harness using `/var/lang/bin/python3.12 -I -S -B`;
   explicitly add only verified release and dependency directories to `sys.path`,
   keeping standard library/lib-dynload paths but excluding bundled image SDK
   site-packages. Check every third-party import and distribution's provenance,
   exact versions and native extension paths. Report the effective `sys.path`.
   [Python 3.12 isolated startup](https://docs.python.org/3.12/using/cmdline.html)

Pip itself is an assembly tool, not part of the runtime closure. If using pip
from the image, record its version and keep its installation separate; the
isolated runtime must not acquire the image's boto3/botocore by accident.
If using pytest, add a separately recorded harness-only dependency closure;
pytest and the project's optional development packages are not among these
28 runtime distributions. A standard-library harness avoids that extra closure.

## Bounded Docker invocation and required checks

Proposed invocation shape, after preparing exact workspace-only inputs. This is
an example contract, not a command run by this research:

```powershell
docker run --rm --pull=never --platform linux/amd64 `
  --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges=true --pids-limit 64 `
  --memory 1g --memory-swap 1g --cpus 1 --user 10001:10001 `
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777 `
  --tmpfs /rehearsal:rw,nosuid,nodev,exec,size=512m,mode=755,uid=10001,gid=10001 `
  --tmpfs /var/lib/shopping-copilot:rw,nosuid,nodev,noexec,size=32m,mode=755,uid=10001,gid=10001 `
  --mount "type=bind,source=$RehearsalInput,target=/input,readonly" `
  --mount "type=bind,source=$VerifiedNodeBinary,target=/usr/bin/node,readonly" `
  --mount "type=bind,source=$VerifiedCaddyBinary,target=/usr/bin/caddy,readonly" `
  --entrypoint /var/lang/bin/python3.12 $PinnedImage `
  -I -S -B /input/harness.py
```

`$RehearsalInput` must be an allowlisted prepared input directory containing only
the exact release archive, wheels, inventories and harness. It is not the
checkout, home, `.aws`, Docker socket or a credential/config directory. Binaries
come from verified workspace extraction, mounted at the launcher's fixed paths;
this performs no host `/usr/bin` installation. Record mount execution mode and
actual executable behavior rather than assuming Windows ACLs establish Linux
mode/ownership. The disposable caddy subdirectory must be created with mode
0700 by the test UID before checking the unmodified storage contract.

The 1 GiB memory ceiling is a proposed test bound, not a measured requirement
or EC2 sizing result. Do not silently relax limits on failure. Temporary files
consume the same cgroup memory budget. **Native `.so` modules must be on an
executable mount**: copying them under a `noexec` tmpfs can fail executable
mapping even though the interpreter itself starts. Keep `/tmp` for inert
metadata, `/rehearsal` for verified executable runtime material, and the state
tree for synthetic state. [Docker run controls](https://docs.docker.com/reference/cli/docker/container/run/),
[tmpfs semantics](https://docs.docker.com/engine/storage/tmpfs/),
[Linux mmap permission failures](https://man7.org/linux/man-pages/man2/mmap.2.html)

The harness must clear ambient environment, refuse socket/DNS access before
release imports, and block SDK client/session construction. Docker `none`
network blocks external routes but retains loopback; it is defense in depth,
not proof no SDK call was attempted. No environment file, AWS credential,
metadata-service probe, model call or provider qualification belongs here.
[Docker none networking](https://docs.docker.com/engine/network/drivers/none/)

Required observations for the proposed check:

- Import complete original `deploy.host_config`, `host_component`, `host_agent`
  and `host_bootstrap`, with the pinned Linux Pydantic/native dependencies.
  Exercise real Pydantic validation and native imports, not AST extraction or
  mocked replacement modules. Ensure imports create no SDK/socket activity.
- Load valid synthetic settings with the unmodified POSIX reader and verify
  release/fingerprint/catalogue/ledger/environment results. Exercise symlink,
  hardlink, FIFO, mode/owner/ancestor, duplicate JSON, overlength/change-during-
  read, invalid ledger/allowance, manifest/fingerprint and wrong-root refusals.
  Put valid protected fixtures beneath `/rehearsal`, not world-writable `/tmp`.
- Execute actual `/usr/bin/node --version`, `/usr/bin/caddy version`, and the
  launcher's original bounded `_version` checks using its clean environments.
  Record stdout, exit/timeout, binary digests and loader failure if present.
- Exercise actual `command(settings, "store")` and `command(settings, "proxy")`
  against the importing release and real filesystem, asserting fixed vectors,
  clean role environments, redacted failures, and unchanged catalogue/ledger
  hashes. Intercept the final `os.execve` in launcher-boundary tests; clearly
  label that interception. Do not execute the returned public proxy command.
- Caddy may perform only bounded `adapt --config EXACT_RELEASE_PROFILE
--adapter caddyfile` with the validated Panel/storage substitutions, without
  `--validate`. No public `run`, `start`, `validate`, `reload`, `trust` or ACME
  operation. Adaptation translates configuration; validation provisions modules.
  [Caddy CLI](https://caddyserver.com/docs/command-line#caddy-adapt)
- If exercising app assembly/cleanup, call the real factory with explicit fake
  SDK/model/HTTP dependencies and preserve its default closed provider gate.
  Its default `sdk_factory=_sdk` is bound at definition: changing a module name
  afterward does not replace that default. Do not invoke an unmodified default
  Agent CLI expecting an SDK-free execution. Record fake-boundary evidence as
  such. A separate real Storefront loopback subprocess test requires an explicit
  narrow internal-loopback allowance while retaining all external/model blocks.

## Evidence levels and remaining acceptance

| Evidence                                            | What it establishes                                                                                                                                                  | What remains open                                                                                                      |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Existing source-extracted primitive checks          | Specific Linux permission/path primitives                                                                                                                            | Full imports, protected configuration, native dependencies and executable behavior                                     |
| Proposed assembled AL2023 rehearsal                 | Full original modules with pinned native Linux wheels, real protected synthetic inputs, binary/version loading, command/environment contracts, pure Caddy adaptation | Actual proxy exec, service supervision, deployment identities, readiness/TLS and cloud integration                     |
| Later authorized real AL2023/systemd/EC2 acceptance | Installed accounts/paths, systemd 252 behavior, process replacement/signals/restarts, effective capabilities and writable state boundaries                           | Only outcomes explicitly exercised; it does not establish arbitrary Storefront support or general production readiness |

The Lambda image is not systemd PID 1. `systemd-analyze verify`, inert executable
stubs or a container's root user cannot establish `User=copilot`, capability
inheritance through Python-to-Caddy exec, service ordering, restart limits,
shutdown cleanup, signed readiness, real IAM/OAC/events, public DNS/TLS/renewal,
provider qualification or safe deployed recovery. Preserve the separate cloud
approval and acceptance gates. See the existing
[host services contract](2026-10-23-cap06-host-services-contract.md) and
[Linux runtime contract](2026-10-23-cap06-linux-runtime-contract.md).
