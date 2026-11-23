"""Bounded disposable native build proof. No provider, host install or public TLS."""

import asyncio
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import redirect_stderr
from decimal import Decimal
from pathlib import Path

INPUT, WORK = Path("/input"), Path("/rehearsal")
IMAGE = "25aee9bac65f131c5d090d3e3a36ccf232d65cf3e6c1dbd0bffd43ca7ce34406"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args, cwd=None, timeout=60, env=None):
    result = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError("Native proof command refused")
    return result.stdout.decode().strip()


def directory_digest(root):
    records = []
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        assert not path.is_symlink()
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
            )
    raw = json.dumps(records, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    return hashlib.sha256(raw).hexdigest(), len(records)


def profile():
    assert len(sys.argv) >= 2 and sha(INPUT / "profile.json") == sys.argv[1]
    value = json.loads((INPUT / "profile.json").read_bytes())
    assert value["version"] == 1 and value["image_sha256"] == IMAGE
    assert sha(Path("/usr/bin/git")) == value["git_sha256"]
    assert sha(Path("/usr/bin/node")) == value["node_sha256"]
    assert sha(Path("/usr/bin/caddy")) == value["caddy_sha256"]
    return value


def initialize():
    assert sys.platform == "linux" and sys.version_info[:2] == (3, 12) and os.geteuid() == 10001
    os.environ.clear()
    os.environ.update(
        PATH="/rehearsal/bin:/usr/bin:/bin",
        HOME="/rehearsal/home",
        LANG="C.UTF-8",
        CI="true",
        AWS_EC2_METADATA_DISABLED="true",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_TERMINAL_PROMPT="0",
        GIT_NO_REPLACE_OBJECTS="1",
    )
    if sys.executable == "/rehearsal/vendor-python/usr/bin/python3.12":
        os.environ["LD_LIBRARY_PATH"] = "/rehearsal/vendor-python/usr/lib64"
    os.umask(0o077)


def unpack_source(expected):
    archive = INPUT / "source.zip"
    assert sha(archive) == expected["sha256"] and archive.stat().st_size == expected["bytes"]
    source = WORK / "source"
    source.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        assert len(entries) <= 20001 and sum(entry.file_size for entry in entries) <= 128 * 1024**2
        assert len({entry.filename for entry in entries}) == len(entries)
        manifest = json.loads(package.read("source-snapshot.json"))
        assert manifest["format"] == 1
        assert (manifest["commit"], manifest["tree"]) == (expected["commit"], expected["tree"])
        assert {entry.filename for entry in entries} == {"source-snapshot.json", *manifest["files"]}
        for entry in entries:
            name = entry.filename
            if name == "source-snapshot.json":
                continue
            assert entry.orig_filename == name and name.startswith(".git/") and "\\" not in name
            assert entry.compress_type == zipfile.ZIP_STORED and not entry.flag_bits & 1
            assert all(part not in {"", ".", ".."} for part in name.split("/"))
            assert name in {".git/HEAD", ".git/config", ".git/shallow"} or re.fullmatch(
                r"\.git/objects/(?:[a-f0-9]{2}/[a-f0-9]{38}|pack/pack-[a-f0-9]{40}\.(?:pack|idx|rev))",
                name,
            )
            assert stat.S_IFMT(entry.external_attr >> 16) in {0, stat.S_IFREG}
            content = package.read(entry)
            assert hashlib.sha256(content).hexdigest() == manifest["files"][name]
            destination = source / name
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            destination.write_bytes(content)
    (source / ".git/refs").mkdir()
    assert (source / ".git/config").read_bytes() == (
        b"[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
        b"\tfilemode = true\n\tautocrlf = false\n"
    )
    assert command("git", "--version") == "git version 2.50.1"
    command("git", "fsck", "--strict", cwd=source)
    command("git", "checkout", "--detach", expected["commit"], cwd=source)
    assert command("git", "rev-parse", "HEAD", cwd=source) == expected["commit"]
    assert command("git", "rev-parse", "HEAD^{tree}", cwd=source) == expected["tree"]
    assert command("git", "rev-list", "--count", "HEAD", cwd=source) == "1"
    assert not command("git", "status", "--porcelain", cwd=source)
    return source


def runtime_paths():
    assert not any("site-packages" in path for path in sys.path)
    sys.path[:0] = [str(WORK / "site"), str(WORK / "release")]


def runtime(expected):
    runtime_paths()
    import boto3
    import botocore.session

    def forbidden(*_, **__):
        raise AssertionError("Account/provider creation forbidden")

    boto3.client = forbidden
    botocore.session.Session.create_client = forbidden
    connect, lookup = socket.socket.connect, socket.getaddrinfo

    def local_connect(self, address):
        assert isinstance(address, tuple) and address[:2] == ("127.0.0.1", 4000)
        return connect(self, address)

    def local_lookup(host, port, *args, **kwargs):
        assert (host, port) == ("127.0.0.1", 4000)
        return lookup(host, port, *args, **kwargs)

    socket.socket.connect, socket.getaddrinfo = local_connect, local_lookup
    from agent.catalogue_contract import SearchQuery
    from agent.inference.ledger import AllowanceLedger
    from deploy import host_agent, host_component
    from deploy.artifact import verify
    from deploy.catalogue import catalogue_status
    from deploy.component_config import load_component_settings
    from deploy.host_config import load_host_settings

    release = WORK / "release"
    manifest = verify(release)
    assert (
        manifest["source_commit"] == expected["source"]["commit"]
        and manifest["source_dirty"] is False
    )
    fingerprint = sha(release / "release.json")
    runtime_profile = json.loads((release / "deploy/linux-runtime.json").read_bytes())
    selected = {row["name"]: row["version"] for row in runtime_profile["wheels"]}
    installed = {
        item.metadata["Name"].lower().replace("_", "-"): item.version
        for item in importlib.metadata.distributions(path=[str(WORK / "site")])
    }
    assert installed == selected and len(installed) == 28
    native_imports = []
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
        native_imports.append(name)
    state = WORK / "state"
    state.mkdir(mode=0o700)
    catalogue = state / "catalogue.sqlite"
    assert sha(INPUT / "catalogue.sqlite") == expected["catalogue_sha256"]
    catalogue.write_bytes((INPUT / "catalogue.sqlite").read_bytes())
    ledger_path = state / "ledger.sqlite"
    identity = AllowanceLedger.initialize(ledger_path, Decimal("0.73"))
    ledger = AllowanceLedger(ledger_path, identity)
    ledger.reserve("retained-synthetic-uncertainty", Decimal("0.04"))
    ledger.set_enabled(False)
    before = ledger.status()
    for name, content in (
        ("service.key", b"s" * 32),
        ("readiness.key", b"r" * 32),
        ("provider.key", b"synthetic-openrouter-key-" + b"x" * 64),
    ):
        (state / name).write_bytes(content)
    data = {
        "version": 2,
        "provider": "openrouter",
        "model": "google/gemini-3.5-flash-lite",
        "provider_key_file": str(state / "provider.key"),
        "release": str(release),
        "fingerprint": fingerprint,
        "catalogue": str(catalogue),
        "table": "offline-control",
        "namespace": "offline",
        "invitation_identity": "00000000-0000-4000-8000-000000000001",
        "lifecycle_identity": "00000000-0000-4000-8000-000000000002",
        "service_secret_file": str(state / "service.key"),
        "readiness_secret_file": str(state / "readiness.key"),
        "inference": {
            "INFERENCE_LEDGER_PATH": str(ledger_path),
            "INFERENCE_LEDGER_ID": identity,
            "INFERENCE_PROVIDER": "openrouter",
            "INFERENCE_MODEL": "google/gemini-3.5-flash-lite",
            "INFERENCE_INPUT_USD_PER_MILLION": "0.3",
            "INFERENCE_OUTPUT_USD_PER_MILLION": "2.5",
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
    config = state / "host.json"
    config.write_text(json.dumps(data))
    settings = load_host_settings(config)
    assert settings.environment()["OPENROUTER_TOTAL_CAP_DOLLARS"] == "2.00"
    assert settings.provider_key not in repr(settings)
    refusals = []
    provider_key = state / "provider.key"
    provider_key.chmod(0o640)
    try:
        load_host_settings(config)
        raise AssertionError("Group-readable provider key accepted")
    except ValueError:
        refusals.append("group-readable-provider-key")
    provider_key.chmod(0o600)
    link = state / "provider-link"
    link.symlink_to(provider_key)
    changed = dict(data, provider_key_file=str(link))
    config.write_text(json.dumps(changed))
    try:
        load_host_settings(config)
        raise AssertionError("Symlink provider key accepted")
    except ValueError:
        refusals.append("symlink-provider-key")
    config.write_text(json.dumps(data))
    errors = io.StringIO()

    async def early():
        with redirect_stderr(errors):
            assert host_agent.main(["--config", str(config)]) == 1

    asyncio.run(early())
    assert errors.getvalue() == "Host startup refused\n"
    minimal = {
        key: data[key] for key in ("release", "fingerprint", "catalogue", "service_secret_file")
    }
    store_config = state / "store.json"
    store_config.write_text(json.dumps({"version": 1, **minimal}))
    proxy_config = state / "proxy.json"
    proxy_config.write_text(
        json.dumps({"version": 1, "release": str(release), "fingerprint": fingerprint})
    )
    catalogue_before = catalogue_status(catalogue)
    for _ in range(2):
        child = subprocess.Popen(
            [sys.executable, "-I", "-S", "-B", __file__, sys.argv[1], "store"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                assert child.poll() is None, "Native Storefront refused"
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:4000/__catalogue/v1/products", timeout=2
                    ) as response:
                        assert response.status == 200
                    break
                except (urllib.error.URLError, TimeoutError):
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
            environment = Path(f"/proc/{child.pid}/environ").read_bytes()
            assert (
                b"OPENROUTER_API_KEY" not in environment
                and settings.provider_key.encode() not in environment
            )
            for secret, expected_status in ((None, 403), (settings.service_secret, 200)):
                headers = {"Content-Type": "application/json"}
                if secret:
                    headers["x-service-secret"] = secret
                request = urllib.request.Request(
                    "http://127.0.0.1:4000/__internal/catalogue/search",
                    data=json.dumps(SearchQuery(query="").model_dump(mode="json")).encode(),
                    headers=headers,
                )
                try:
                    with urllib.request.urlopen(request, timeout=2) as response:
                        assert response.status == expected_status
                except urllib.error.HTTPError as error:
                    assert error.code in ({401, 403} if secret is None else {200})
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stderr.close()
        assert catalogue_status(catalogue) == catalogue_before
    storage = Path("/var/lib/shopping-copilot/caddy")
    storage.mkdir(mode=0o700)
    args, env = host_component.command(load_component_settings(proxy_config, "proxy"), "proxy")
    host_component._version(args[0], env)
    adapted = json.loads(
        command(
            args[0], "adapt", "--config", args[3], "--adapter", "caddyfile", env=env, timeout=15
        )
    )
    assert adapted["admin"]["disabled"] and not list(storage.iterdir())
    assert ledger.status() == before and sha(release / "release.json") == fingerprint
    result = {
        "default_posix_v2_load": True,
        "key_refusals": refusals,
        "agent_running_loop_refusal_only": True,
        "agent_full_startup_verified": False,
        "native_storefront_restarts": 2,
        "storefront_key_environment_isolation": True,
        "catalogue_preserved": True,
        "uncertain_allowance_preserved": True,
        "caddy_adapt_only": True,
        "provider_calls": 0,
        "sdk_calls": 0,
        "manifest_unchanged": True,
        "runtime_distributions": 28,
        "native_imports": native_imports,
    }
    print(json.dumps(result, sort_keys=True))


def restore_policy(source, expected):
    """Restore pnpm's genuine policy successes only for the sealed lock and cache."""
    cache = INPUT / "lockfile-verified.jsonl"
    assert sha(source / "pnpm-lock.yaml") == expected["policy_lock_sha256"]
    assert sha(cache) == expected["policy_cache_sha256"] and cache.stat().st_size <= 1024**2
    destination = WORK / "home/.cache/pnpm/lockfile-verified.jsonl"
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(cache.read_bytes())


def build(expected):
    assert sys.version_info[:3] == (3, 12, 14)
    assert sys.executable == "/rehearsal/vendor-python/usr/bin/python3.12"
    for name in ("home", "bin"):
        (WORK / name).mkdir(mode=0o700)
    assert directory_digest(Path("/store")) == (expected["store_manifest_sha256"], 6334)
    assert directory_digest(Path("/pnpm"))[0] == expected["pnpm_manifest_sha256"]
    store = WORK / "home/.local/share/pnpm/store"
    shutil.copytree("/store", store / "v11")
    wrapper = WORK / "bin/pnpm"
    wrapper.write_text('#!/bin/sh\nexec /usr/bin/node /pnpm/bin/pnpm.cjs "$@"\n')
    wrapper.chmod(0o755)
    assert command("pnpm", "--version") == "11.19.0"
    assert command("node", "--version") == "v24.22.1"
    source = unpack_source(expected["source"])
    restore_policy(source, expected)
    assert command("pnpm", "store", "path", cwd=source) == str(store / "v11")
    command(
        "pnpm",
        "install",
        "--frozen-lockfile",
        "--offline",
        "--store-dir",
        str(store),
        cwd=source,
        timeout=180,
    )
    assert not command("git", "status", "--porcelain", cwd=source)
    command(
        sys.executable,
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "install",
        "--no-index",
        "--require-hashes",
        "--no-deps",
        "--only-binary=:all:",
        "--no-compile",
        "--no-cache-dir",
        "--target",
        str(WORK / "site"),
        "--find-links",
        "/wheels",
        "-r",
        str(source / "deploy/requirements-linux.lock"),
        timeout=90,
    )
    sys.path[:0] = [str(WORK / "site"), str(source), str(INPUT / "packaging.whl")]
    assert sha(INPUT / "packaging.whl") == expected["packaging_sha256"]
    os.environ.update(
        COPILOT_ENV="production",
        COPILOT_PANEL_ORIGIN="https://app.scpilot.tech",
        COPILOT_STORE_ORIGIN="https://store.scpilot.tech",
        COPILOT_AGENT_ORIGIN="https://app.scpilot.tech",
    )
    from deploy.artifact import build as build_release
    from deploy.artifact import verify

    manifest = build_release(source, WORK / "release")
    assert manifest["source_commit"] == expected["source"]["commit"]
    assert manifest["source_dirty"] is False and manifest["local_rehearsal"] is False
    assert not command("git", "status", "--porcelain", cwd=source)
    runtime_result = json.loads(
        command(sys.executable, "-I", "-S", "-B", __file__, sys.argv[1], "runtime", timeout=90)
    )
    release = WORK / "release"
    verify(release)
    output = Path("/output/release.tar")
    assert not output.exists()
    with tarfile.open(output, "x", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(release.rglob("*")):
            assert path.is_dir() or path.is_file() or path.is_symlink()
            item = archive.gettarinfo(str(path), arcname=path.relative_to(release).as_posix())
            item.uid = item.gid = item.mtime = 0
            item.uname = item.gname = ""
            item.mode = 0o755 if item.isdir() or item.mode & 0o111 else 0o644
            if path.is_symlink():
                assert not Path(os.readlink(path)).is_absolute() and path.resolve().is_relative_to(
                    release
                )
            if item.isfile():
                with path.open("rb") as content:
                    archive.addfile(item, content)
            else:
                archive.addfile(item)
    result = {
        "source_commit": manifest["source_commit"],
        "source_tree": expected["source"]["tree"],
        "source_clean": True,
        "genuine_git": True,
        "offline_native_build": True,
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "python_prefix": sys.prefix,
        "node_version": command("node", "--version"),
        "policy_cache_sha256": expected["policy_cache_sha256"],
        "policy_lock_sha256": expected["policy_lock_sha256"],
        "manifest_sha256": sha(release / "release.json"),
        "archive_sha256": sha(output),
        "archive_bytes": output.stat().st_size,
        "runtime": runtime_result,
    }
    (Path("/output") / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    initialize()
    expected = profile()
    mode = sys.argv[2] if len(sys.argv) == 3 else "build"
    if mode == "build":
        build(expected)
    elif mode == "runtime":
        runtime(expected)
    else:
        assert mode == "store"
        runtime_paths()
        from deploy.host_component import main

        raise SystemExit(main(["--config", str(WORK / "state/store.json"), "--component", "store"]))
