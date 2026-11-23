"""Disposable AL2023 rehearsal only. No account, provider, systemd or public TLS operation."""

import asyncio
import copy
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from decimal import Decimal
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

INPUT, WORK = Path("/input"), Path("/rehearsal")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(expected):
    assert len(expected) == 64 and sha(INPUT / "runtime-profile.json") == expected
    return json.loads((INPUT / "runtime-profile.json").read_bytes())


def paths():
    assert sys.version_info[:2] == (3, 12) and sys.platform == "linux"
    assert not any("site-packages" in item for item in sys.path)
    sys.path[:0] = [str(WORK / "site"), str(WORK / "release")]
    os.environ.clear()
    os.environ.update(PATH="/usr/bin:/bin", AWS_EC2_METADATA_DISABLED="true")
    os.umask(0o077)


def block_external():
    def forbidden(*_, **__):
        raise AssertionError("SDK or external connection forbidden in rehearsal")

    import boto3
    import botocore.session

    boto3.client = forbidden
    botocore.session.Session.create_client = forbidden
    connect, resolve = socket.socket.connect, socket.getaddrinfo

    def loopback(self, address):
        if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", 4000):
            forbidden()
        return connect(self, address)

    def lookup(host, port, *args, **kwargs):
        if (host, port) != ("127.0.0.1", 4000):
            forbidden()
        return resolve(host, port, *args, **kwargs)

    socket.socket.connect, socket.getaddrinfo = loopback, lookup


def closure(inventory):
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    selected = {item["name"]: item["version"] for item in inventory["wheels"]}
    reached, pending = set(), [Requirement(value) for value in inventory["roots"]]
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        key = (name, tuple(sorted(requirement.extras)))
        if key in reached:
            continue
        reached.add(key)
        distribution = importlib.metadata.distribution(name)
        assert Path(distribution.locate_file("")).resolve() == WORK / "site"
        assert distribution.version == selected[name]
        assert distribution.version in requirement.specifier
        for value in distribution.requires or ():
            dependency = Requirement(value)
            if dependency.marker is None or any(
                dependency.marker.evaluate({**default_environment(), "extra": extra})
                for extra in {"", *requirement.extras}
            ):
                assert dependency.url is None
                pending.append(dependency)
    assert {name for name, _ in reached} == set(selected)
    return selected


def unpack(inventory):
    archive = INPUT / "release.zip"
    assert sha(archive) == inventory["fixture"]["sha256"]
    release = WORK / "release"
    release.mkdir(mode=0o700)
    with ZipFile(archive) as package:
        entries = package.infolist()
        assert len(entries) <= 20001 and sum(item.file_size for item in entries) <= 129 * 1024**2
        proof = json.loads(package.read("fixture.json"))
        assert proof["upstream_manifest_sha256"] == inventory["fixture"]["upstream_manifest_sha256"]
        expected = {"fixture.json", *("release/" + name for name in proof["files"])}
        assert len(entries) == len(expected) and {item.filename for item in entries} == expected
        for item in entries:
            name = PurePosixPath(item.filename)
            assert not name.is_absolute() and ".." not in name.parts and "\\" not in item.filename
            assert (item.external_attr >> 16) & 0o170000 in {0, 0o100000}
            if item.filename == "fixture.json":
                continue
            relative = item.filename.removeprefix("release/")
            content = package.read(item)
            assert hashlib.sha256(content).hexdigest() == proof["files"][relative]
            destination = release / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(content)
        for name, target in proof["links"].items():
            for value in (name, target):
                parts = PurePosixPath(value)
                assert not parts.is_absolute() and ".." not in parts.parts and "\\" not in value
                assert value not in {"", "."}
            destination = release / name
            resolved = release / target
            assert resolved.exists() and not resolved.is_symlink()
            assert not destination.exists() and not destination.is_symlink()
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.symlink_to(os.path.relpath(resolved, destination.parent))
    return proof


def request(path, *, body=None, secret=None):
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["x-service-secret"] = secret
    data = json.dumps(body).encode() if body is not None else None
    operation = urllib.request.Request("http://127.0.0.1:4000" + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(operation, timeout=2) as response:
            response.read(1024 * 1024)
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def probe(inventory, expected):
    paths()
    block_external()
    versions = closure(inventory)
    native = {}
    for name in (
        "pydantic_core._pydantic_core",
        "httptools.parser.parser",
        "yaml._yaml",
        "uvloop.loop",
        "watchfiles._rust_notify",
        "websockets.speedups",
    ):
        module = importlib.import_module(name)
        assert Path(module.__file__).is_relative_to(WORK / "site") and ".so" in module.__file__
        native[name] = Path(module.__file__).name

    from agent.catalogue_contract import SearchQuery
    from agent.inference.ledger import AllowanceLedger
    from deploy import host_agent, host_component
    from deploy.artifact import files, verify
    from deploy.catalogue import catalogue_status
    from deploy.host_config import load_host_settings

    release = WORK / "release"
    manifest = inventory["provenance"]["upstream_manifest"].copy()
    manifest["files"] = files(release)
    (release / "release.json").write_text(json.dumps(manifest))
    verify(release)
    state = WORK / "state"
    state.mkdir(mode=0o700)
    catalogue = state / "catalogue.sqlite"
    catalogue.write_bytes((INPUT / "catalogue.sqlite").read_bytes())
    assert sha(catalogue) == inventory["catalogue_sha256"]
    ledger_path = state / "ledger.sqlite"
    identity = AllowanceLedger.initialize(ledger_path, Decimal("1"))
    ledger = AllowanceLedger(ledger_path, identity)
    ledger.reserve("synthetic-uncertain", Decimal("0.20"))
    ledger.set_enabled(False)
    before = ledger.status()
    service, key = state / "service.key", state / "readiness.key"
    service.write_bytes(b"s" * 32)
    key.write_bytes(b"k" * 32)
    config = state / "host.json"
    data = {
        "version": 1,
        "release": str(release),
        "fingerprint": sha(release / "release.json"),
        "catalogue": str(catalogue),
        "table": "offline-control",
        "namespace": "offline",
        "invitation_identity": "00000000-0000-4000-8000-000000000001",
        "lifecycle_identity": "00000000-0000-4000-8000-000000000002",
        "service_secret_file": str(service),
        "readiness_secret_file": str(key),
        "inference": {
            "INFERENCE_LEDGER_PATH": str(ledger_path),
            "INFERENCE_LEDGER_ID": identity,
            "INFERENCE_PROVIDER": "bedrock",
            "INFERENCE_MODEL": "openai.gpt-oss-20b-1:0",
            "INFERENCE_INPUT_USD_PER_MILLION": "1",
            "INFERENCE_OUTPUT_USD_PER_MILLION": "1",
            "INFERENCE_MAX_ACTIVE": "1",
            "INFERENCE_MAX_WAITING": "1",
            "INFERENCE_WAIT_SECONDS": "1",
            "INFERENCE_MAXIMUM_PAGES": "1024",
        },
        "admission_limits": {
            "maximum_bytes": 65536,
            "global_rate": 60,
            "browser_rate": 30,
            "maximum_requests": 5,
            "maximum_streams": 5,
            "maximum_sessions": 10,
            "browser_sessions": 2,
        },
    }

    def save(value=data):
        config.write_text(json.dumps(value))
        config.chmod(0o600)

    save()
    settings = load_host_settings(config)
    store_config = state / "store.json"
    store_config.write_text(
        json.dumps(
            {
                name: data[name]
                for name in (
                    "version",
                    "release",
                    "fingerprint",
                    "catalogue",
                    "service_secret_file",
                )
            }
        )
    )
    proxy_config = state / "proxy.json"
    proxy_config.write_text(
        json.dumps({name: data[name] for name in ("version", "release", "fingerprint")})
    )
    assert settings.release == Path(host_component.__file__).resolve().parents[1]
    assert "s" * 32 not in repr(settings) and settings.readiness_secret == b"k" * 32
    refused = []

    def reject(name, path=config):
        try:
            load_host_settings(path)
        except ValueError as error:
            assert str(error) == "Host configuration refused"
            refused.append(name)
        else:
            raise AssertionError("Unsafe full configuration accepted")

    config.chmod(0o640)
    reject("group-readable configuration")
    save()
    linked = state / "linked.json"
    linked.symlink_to(config)
    reject("symlink configuration", linked)
    hard = state / "hard.json"
    os.link(config, hard)
    reject("hardlink configuration")
    hard.unlink()
    fifo = state / "fifo"
    os.mkfifo(fifo, 0o600)
    reject("FIFO configuration", fifo)
    alias = WORK / "state-alias"
    alias.symlink_to(state, target_is_directory=True)
    reject("symlink ancestor", alias / "host.json")
    for case in ("extra", "bool-version", "alias-state", "provider", "fingerprint", "relative"):
        changed = copy.deepcopy(data)
        if case == "extra":
            changed["AWS_ACCESS_KEY_ID"] = "synthetic-forbidden"
        elif case == "bool-version":
            changed["version"] = True
        elif case == "alias-state":
            changed["catalogue"] = str(ledger_path)
        elif case == "provider":
            changed["inference"]["INFERENCE_PROVIDER"] = "openrouter"
        elif case == "fingerprint":
            changed["fingerprint"] = "0" * 64
        else:
            changed["release"] = "relative"
        save(changed)
        reject(case)
    save()
    key.write_bytes(b"short")
    reject("short private key")
    key.write_bytes(b"k" * 32)
    config.write_text(config.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    reject("duplicate JSON field")
    save()
    assert load_host_settings(config).fingerprint == settings.fingerprint

    captured = io.StringIO()

    async def early_refusal():
        with redirect_stderr(captured):
            assert host_agent.main(["--config", str(config)]) == 1

    asyncio.run(early_refusal())
    assert captured.getvalue() == "Host startup refused\n"

    catalogue_before = catalogue_status(catalogue)
    for _ in range(2):
        child = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", __file__, expected, "--store"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                if child.poll() is not None:
                    raise AssertionError(
                        "Native Storefront child failed: " + child.stderr.read(4096).decode()
                    )
                try:
                    if request("/__catalogue/v1/products") == 200:
                        break
                except urllib.error.URLError:
                    pass
                assert time.monotonic() < deadline, "Native Storefront startup timeout"
                time.sleep(0.05)
            assert request("/__test/reset", body={}) == 404
            body = SearchQuery(query="").model_dump(mode="json")
            assert request("/__internal/catalogue/search", body=body) in {401, 403}
            assert (
                request("/__internal/catalogue/search", body=body, secret=settings.service_secret)
                == 200
            )
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stderr.close()
        assert catalogue_status(catalogue) == catalogue_before and ledger.status() == before

    storage = Path("/var/lib/shopping-copilot/caddy")
    storage.mkdir(mode=0o700)
    from deploy.component_config import load_component_settings

    arguments, environment = host_component.command(
        load_component_settings(proxy_config, "proxy"), "proxy"
    )
    host_component._version(arguments[0], environment)
    adapted = subprocess.run(
        [arguments[0], "adapt", "--config", arguments[3], "--adapter", "caddyfile"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert json.loads(adapted.stdout)["admin"]["disabled"] is True and not list(storage.iterdir())

    class CapturedExec(BaseException):
        pass

    original_exec = os.execve

    def capture(binary, argv, values):
        assert (argv, values) == (arguments, environment) and binary == "/usr/bin/caddy"
        raise CapturedExec()

    os.execve = capture
    try:
        try:
            host_component.main(["--config", str(proxy_config), "--component", "proxy"])
        except CapturedExec:
            pass
        else:
            raise AssertionError("Proxy handoff not captured")
    finally:
        os.execve = original_exec
    assert ledger.status() == before
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "os_release": platform.freedesktop_os_release(),
        "libc": platform.libc_ver(),
        "uid": os.geteuid(),
        "versions": versions,
        "native_extensions": native,
        "default_protected_reader": True,
        "configuration_refusals": refused,
        "native_storefront_exec_and_restart": True,
        "catalogue_preserved": True,
        "disabled_synthetic_allowance_preserved": True,
        "agent_active_loop_refused": True,
        "proxy_handoff_captured": True,
        "caddy_adapt_only": True,
        "public_caddy_run": False,
        "sdk_creation_forbidden": True,
        "upstream_manifest_sha256": inventory["fixture"]["upstream_manifest_sha256"],
        "derived_manifest_sha256": sha(release / "release.json"),
    }


def main():
    expected = sys.argv[1]
    inventory = profile(expected)
    if sys.argv[2:] == ["--store"]:
        paths()
        block_external()
        from deploy.host_component import main as store

        raise SystemExit(
            store(["--config", str(WORK / "state/store.json"), "--component", "store"])
        )
    assert not sys.argv[2:] and os.geteuid() != 0
    assert sha(Path(__file__)) == inventory["probe_sha256"]
    os.umask(0o077)
    for item in inventory["wheels"]:
        assert sha(INPUT / "wheels" / item["filename"]) == item["sha256"]
    for item in inventory["binaries"]:
        assert sha(Path("/usr/bin") / item["name"]) == item["binary_sha256"]
    assert sha(INPUT / "requirements.lock") == inventory["requirements_sha256"]
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--require-hashes",
            "--find-links=/input/wheels",
            "--target=/rehearsal/site",
            "-r",
            "/input/requirements.lock",
        ],
        env={
            "PATH": "/usr/bin:/bin",
            "PIP_CONFIG_FILE": "/dev/null",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    inventory["provenance"] = unpack(inventory)
    print(json.dumps(probe(inventory, expected), sort_keys=True))


if __name__ == "__main__":
    main()
