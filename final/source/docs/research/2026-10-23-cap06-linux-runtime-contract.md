# CAP-06 local Linux runtime contract

Researched 23 October 2026 against primary documentation and the installed
Uvicorn source. This records a test contract, not execution evidence. This
research did not run Docker, invoke an account API/SDK/model, install software,
or change resources, credentials, Docker settings or runtime endpoints.

## Image and retained identity

AWS documents `public.ecr.aws/lambda/python:3.12` as its Python 3.12 base image,
based on Amazon Linux 2023. Its example selects `linux/amd64`; ARM64 requires a
separate `linux/arm64` selection. AL2023 local execution needs Docker 20.10.10 or
newer. The image includes the runtime interface client and emulator.
[AWS Python images](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html)

Use the approved `linux/amd64` target explicitly. Separate public acquisition
from offline execution: retain the actual pull's repository digest, image ID,
OS/architecture and Docker version; run the digest reference with `--pull=never`.
Do not invent a digest or treat the moving `:3.12` tag as a frozen artifact.
Docker documents digest pulls as immutable image selection and `image inspect`
as the local metadata inspection command. Newer APIs additionally support
platform-specific inspection.
[Docker digest pulls](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier),
[Docker image inspect](https://docs.docker.com/reference/cli/docker/image/inspect/)

Inspect the selected image and execute a small interpreter/version/platform
probe before accepting `/var/lang/bin/python3.12`. AWS's published Dockerfile
places `/var/lang/bin` first in PATH; its Dockerfile alone does not prove the
contents of a particular pulled digest.
[AWS Python 3.12 Dockerfile](https://github.com/aws/aws-lambda-base-images/blob/python3.12/Dockerfile.python3.12)

## Offline import smoke boundary

`-I` removes the script/current directory and user site paths and ignores
`PYTHON*` variables; `-S` suppresses `site` initialization; `-B` suppresses `.pyc`
writes. The harness must explicitly add only its verified extracted ZIP root
to `sys.path`, then check module provenance and pinned dependency versions.
These interpreter flags do not themselves prevent application network access.
[Python 3.12 command line](https://docs.python.org/3.12/using/cmdline.html)

Candidate PowerShell invocation, after independently retaining the image and
archive digests and preparing a self-contained, standard-library smoke harness:

```powershell
docker run --rm --pull=never --platform linux/amd64 `
  --network none --read-only --cap-drop ALL `
  --security-opt no-new-privileges=true --pids-limit 64 `
  --memory 256m --memory-swap 256m --cpus 1 `
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777 `
  --mount "type=bind,source=$ArtifactZip,target=/input/artifact.zip,readonly" `
  --mount "type=bind,source=$SmokeScript,target=/input/smoke.py,readonly" `
  --entrypoint /var/lang/bin/python3.12 $PinnedImage `
  -I -S -B /input/smoke.py /input/artifact.zip $ArchiveSha256
```

This is a proposed bounded local test, not Lambda's resource configuration.
Docker defines these root filesystem, privilege, PID/CPU/memory and pull controls.
Explicit swap equality also avoids the default additional swap allowance.
Read-only bind mounts protect host inputs; tmpfs extraction consumes the same
container memory budget and disappears when the container stops. Failures at
these bounds must be reported, not silently relaxed.
[Docker run controls](https://docs.docker.com/reference/cli/docker/container/run/),
[memory constraints](https://docs.docker.com/engine/containers/run/#user-memory-constraints),
[bind mounts](https://docs.docker.com/engine/storage/bind-mounts/),
[tmpfs mounts](https://docs.docker.com/engine/storage/tmpfs/)

Mount only the exact ZIP and harness: no checkout, home, `.aws`, Docker socket,
credential/config/key directory, or environment file. Forward no credentials or
ambient host environment. Inside the harness, clear environment settings and
block SDK client creation and socket/DNS calls before importing the artifact.
No real account SDK request or model request is part of this check. `none`
network provides only container-local loopback, independently blocking external
network routes.
[Docker none network](https://docs.docker.com/engine/network/drivers/none/)

## Invocation evidence is a separate level

An isolated interpreter import and injected handler delegation check bypasses
the Runtime Interface Client/Emulator and is not an actual Lambda handler
invocation. Optional RIE testing must retain all offline guards: run an internal
HTTP client and emulator in the same `--network none` container, addressing only
its loopback invocation endpoint, with no published port. A blanket socket
guard needs a narrow reviewed loopback exception for that test. The official
RIE documentation establishes HTTP invocation, not a Unix-socket interface; do
not assume UDS support. Even a successful RIE invocation does not emulate
Lambda orchestration, security/authentication, IAM, event delivery or cloud
integrations.
[AWS RIE contract and limitations](https://github.com/aws/aws-lambda-runtime-interface-emulator)

## Host startup ordering

The installed `D:/agent depi/.venv/Lib/site-packages/uvicorn` is version 0.35.0.
Read-only inspection found `server.py:65–78`: `Server.run()` enters
`asyncio.run(self.serve(...))`; async `_serve()` calls `config.load()`.
`config.py:442` then calls the loaded app factory. Thus ordinary `--factory`
startup invokes a wrapper around `create_host_app` inside a running loop,
conflicting with `deploy/host_bootstrap.py:138–143`, which explicitly refuses
that state before SDK creation. This conclusion is from the installed source,
not an inference that factory loading is pre-loop.

The future explicit host CLI must load validated settings and construct
`app = create_host_app(settings)` synchronously, then call `uvicorn.run(app, ...)`
from its main guard. Uvicorn officially supports passing a preconstructed app
when reload/multiprocessing are disabled. Preserve a single process and run the
app lifespan; this note does not activate the launcher or qualify the provider.
[Uvicorn programmatic startup](https://uvicorn.dev/deployment/#running-programmatically)

## Docker Desktop startup failure reported during preparation

Docker's issue tracker contains the same `dockerInference` remove failure and
misleading listener path-syntax suffix. Reporter observations describe inaccessible
Windows AF_UNIX entries after shutdown; `Archive, ReparsePoint` alone does not
establish a tag or root cause on this machine. Docker's 4.89.0 and 4.90.0 release
notes acknowledge a stuck-socket startup fix, but tracker reports include later
recurrence. A fixed-version or universally supported exact-endpoint cleanup
remedy is not established by these sources.
[Docker release notes](https://docs.docker.com/desktop/release-notes/),
[Docker issue 460](https://github.com/docker/desktop-feedback/issues/460),
[Docker issue 625](https://github.com/docker/desktop-feedback/issues/625)

Tracker workarounds (Windows Restart, recoverable parent-directory quarantine,
in-place update, settings changes) have mixed results and are user reports,
not a Docker-supported repair procedure. Disabling inference flags can still
leave listener initialization active. Do not prescribe reset/purge, recursive
deletion, ACL/tag manipulation, feature changes or persistent-data operations
from this research. Preserve local evidence and treat unavailable Linux-engine
access as an execution blocker until a separately justified recovery succeeds.
