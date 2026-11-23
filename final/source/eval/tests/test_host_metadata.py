import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval.tests.test_component_config import component_files as _component_files

component_files = _component_files


@pytest.fixture
def metadata():
    return importlib.import_module("deploy.host_metadata")


@pytest.mark.parametrize("uid", [True, 0, -1, 4294967295, "1001", None])
def test_metadata_uid_cannot_be_root_text_or_unbounded(metadata, uid):
    with pytest.raises(ValueError):
        metadata.render_metadata(uid)


def test_metadata_batch_is_fixed_and_scoped_to_own_chain(metadata):
    text = metadata.render_metadata(10001)
    assert "169.254.169.254" in text and "fd00:ec2::254" in text
    assert "meta skuid { 0, 10001 } return" in text
    assert "flush chain inet scpilot_metadata output" in text
    assert "flush ruleset" not in text and "delete table" not in text
    assert len(text) < 1024


@pytest.mark.parametrize(
    "case",
    ["ok", "uid-mismatch", "not-root", "extra", "duplicate", "release", "nft-failed", "timeout"],
)
def test_metadata_cli_verifies_root_identity_release_before_one_bounded_nft(
    metadata, component_files, monkeypatch, capsys, case
):
    directory, basic, _, _ = component_files
    data = {**basic, "agent_uid": 10001}
    if case == "extra":
        data["rules"] = "private injected rule"
    if case == "release":
        data["fingerprint"] = "0" * 64
    config = directory / "metadata.json"
    config.write_text(json.dumps(data))
    if case == "duplicate":
        config.write_text(config.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    monkeypatch.setattr(metadata, "_runtime_root", lambda: directory / "release")
    monkeypatch.setattr(metadata, "_identity", lambda: 10002 if case == "uid-mismatch" else 10001)
    monkeypatch.setattr(metadata, "_root", lambda: case != "not-root")
    calls = []

    def run(argv, **values):
        calls.append(argv)
        assert argv == ["/usr/sbin/nft", "--file", "-"]
        assert values["input"] == metadata.render_metadata(10001)
        assert values["timeout"] == 5 and values["check"] is True
        assert values["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        assert values["stdout"] == values["stderr"] == subprocess.DEVNULL
        if case == "nft-failed":
            raise subprocess.CalledProcessError(1, argv, stderr="private")
        if case == "timeout":
            raise subprocess.TimeoutExpired(argv, 5)

    monkeypatch.setattr(metadata.subprocess, "run", run)
    if case == "ok":
        metadata.configure(config, read_private=lambda path, limit: path.read_bytes())
        assert len(calls) == 1
    else:
        with pytest.raises(ValueError, match="^Metadata protection refused$"):
            metadata.configure(config, read_private=lambda path, limit: path.read_bytes())
        assert len(calls) == (1 if case in {"nft-failed", "timeout"} else 0)
    assert capsys.readouterr().out == ""


def test_metadata_import_has_no_sdk_or_third_party_boundary():
    root = Path(__file__).resolve().parents[2]
    source = (
        "import sys;sys.path.insert(0,sys.argv[1]);import deploy.host_metadata;"
        "assert not any(x in sys.modules for x in ('boto3','httpx','pydantic','agent.app'));"
        "print('pure')"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", source, str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "pure\n"
