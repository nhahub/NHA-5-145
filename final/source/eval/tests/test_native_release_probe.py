"""Cross-platform proof-tool input identity, without Docker or subprocesses."""

import hashlib
import json

import pytest

from eval import native_release_probe
from eval.native_release_probe import directory_digest


def test_tool_directory_digest_uses_case_sensitive_relative_path_order(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"lowercase path")
    (tmp_path / "Z.txt").write_bytes(b"uppercase path")
    entries = [
        {
            "path": name,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for name, content in (("Z.txt", b"uppercase path"), ("a.txt", b"lowercase path"))
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    assert directory_digest(tmp_path) == (hashlib.sha256(canonical).hexdigest(), 2)


@pytest.mark.parametrize(
    "executable,library_path",
    [
        ("/rehearsal/vendor-python/usr/bin/python3.12", "/rehearsal/vendor-python/usr/lib64"),
        ("/var/lang/bin/python3.12", None),
    ],
)
def test_vendor_child_environment_has_only_the_fixed_native_library_path(
    monkeypatch, executable, library_path
):
    environment = {"AWS_ACCESS_KEY_ID": "forbidden", "LD_LIBRARY_PATH": "/owner/private"}
    monkeypatch.setattr(native_release_probe.sys, "platform", "linux")
    monkeypatch.setattr(native_release_probe.sys, "executable", executable)
    monkeypatch.setattr(native_release_probe.os, "environ", environment)
    monkeypatch.setattr(native_release_probe.os, "geteuid", lambda: 10001, raising=False)
    monkeypatch.setattr(native_release_probe.os, "umask", lambda _: None)
    native_release_probe.initialize()
    assert "AWS_ACCESS_KEY_ID" not in environment
    assert environment.get("LD_LIBRARY_PATH") == library_path


@pytest.mark.parametrize("changed", [None, "lock", "cache"])
def test_policy_receipt_is_bound_before_private_cache_restoration(tmp_path, monkeypatch, changed):
    inputs, source, work = (tmp_path / name for name in ("input", "source", "work"))
    for path in (inputs, source, work):
        path.mkdir()
    lock = source / "pnpm-lock.yaml"
    cache = inputs / "lockfile-verified.jsonl"
    lock.write_bytes(b"fixed locked graph\n")
    cache.write_bytes(b'{"workspace":"verified"}\n{"production":"verified"}\n')
    expected = {
        "policy_lock_sha256": native_release_probe.sha(lock),
        "policy_cache_sha256": native_release_probe.sha(cache),
    }
    monkeypatch.setattr(native_release_probe, "INPUT", inputs)
    monkeypatch.setattr(native_release_probe, "WORK", work)
    if changed:
        (lock if changed == "lock" else cache).write_bytes(b"changed input\n")
        with pytest.raises(AssertionError):
            native_release_probe.restore_policy(source, expected)
        assert not (work / "home/.cache/pnpm/lockfile-verified.jsonl").exists()
    else:
        native_release_probe.restore_policy(source, expected)
        assert (
            work / "home/.cache/pnpm/lockfile-verified.jsonl"
        ).read_bytes() == cache.read_bytes()
