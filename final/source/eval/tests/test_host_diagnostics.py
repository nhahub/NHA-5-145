import importlib
from pathlib import Path

import pytest


@pytest.fixture
def diagnostic():
    return importlib.import_module("deploy.host_diagnostics")


def test_fixed_lifecycle_payload_never_serializes_arbitrary_service_result(diagnostic):
    assert diagnostic.payload("store", "starting", "private", now=1) == {
        "time": 1,
        "service": "store",
        "event": "starting",
        "outcome": None,
    }
    assert diagnostic.payload("proxy", "stopped", "success", now=2)["outcome"] == "success"
    assert diagnostic.payload("agent", "stopped", "private key/path", now=2)["outcome"] == "failed"
    for service, event in (("private", "starting"), ("store", "private")):
        with pytest.raises(ValueError):
            diagnostic.payload(service, event, now=2)


def test_diagnostic_cli_has_only_fixed_paths_and_redacts_failure(diagnostic, monkeypatch, capsys):
    calls = []

    def write(path, service, event, **kwargs):
        calls.append((path, service, event))
        raise OSError("private key/path")

    monkeypatch.setattr(diagnostic, "write_event", write)
    assert diagnostic.main(["--service", "store", "--event", "starting"]) == 1
    assert calls == [(Path("/var/log/shopping-copilot/store"), "store", "starting")]
    assert capsys.readouterr().err == "Host diagnostics refused\n"
    calls.clear()
    assert diagnostic.main(["--service", "store", "--event", "starting", "--path", "/private"]) == 1
    assert calls == []
    assert capsys.readouterr().err == "Host diagnostics refused\n"
