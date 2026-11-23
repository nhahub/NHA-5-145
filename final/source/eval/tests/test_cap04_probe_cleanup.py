"""Probe cleanup failures must not strand trust or private test keys."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from eval.probes import cap04_cross_site as probe


@pytest.mark.parametrize("failure", ["process", "certificate"])
def test_probe_cleanup_attempts_all_resources_and_records_failure(tmp_path, monkeypatch, failure):
    tls = tmp_path / "tls"
    tls.mkdir()
    for name in ("ca.key", "leaf.key"):
        (tls / name).write_text("test-only placeholder")
    process = Mock()
    if failure == "process":
        process.terminate.side_effect = PermissionError("simulated process failure")
    remove = Mock()
    if failure == "certificate":
        remove.side_effect = subprocess.CalledProcessError(1, ["certutil"])
    monkeypatch.setattr(probe, "command", remove)
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=0 if failure == "certificate" else 1)),
    )
    report = tmp_path / "result.json"
    result = {"outcome": "failed"}

    with pytest.raises(RuntimeError, match="cleanup"):
        probe.cleanup([process], "test-thumbprint", tls, report, result)

    remove.assert_called_once_with(["certutil", "-user", "-delstore", "Root", "test-thumbprint"])
    assert not (tls / "ca.key").exists()
    assert not (tls / "leaf.key").exists()
    saved = json.loads(report.read_text())
    assert saved["cleanup_errors"]
    assert saved["temporary_ca_removed"] is (failure != "certificate")
