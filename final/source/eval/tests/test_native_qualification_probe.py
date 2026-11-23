"""Native synthetic binding preparation is exclusive and never prints custody."""

import hashlib
import json

import pytest

from eval.tests.test_host_openrouter import PROVIDER_KEY
from eval.tests.test_host_openrouter import openrouter_config as _host
from eval.tests.test_provider_binding import binding_world as _binding


def test_native_binding_arguments_pin_exclusive_private_candidate_bytes(tmp_path, monkeypatch):
    from eval.native_qualification_probe import qualification_arguments

    world = _binding.__wrapped__(_host.__wrapped__(tmp_path), monkeypatch)
    settings = world[1]
    path = tmp_path / "native-binding.json"
    arguments = qualification_arguments(settings, path, issued_at=100, expires_at=200)
    raw = path.read_bytes()
    assert arguments == [
        "--qualification",
        str(path),
        "--qualification-sha256",
        hashlib.sha256(raw).hexdigest(),
    ]
    assert json.loads(raw)["provider"] == "openrouter"
    assert PROVIDER_KEY not in " ".join(arguments)
    assert hashlib.sha256(PROVIDER_KEY.encode()).hexdigest() not in " ".join(arguments)
    with pytest.raises(FileExistsError):
        qualification_arguments(settings, path, issued_at=100, expires_at=200)
    assert path.read_bytes() == raw
