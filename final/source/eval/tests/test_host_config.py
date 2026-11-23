import json
import os
import stat
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agent.inference.config import REQUIRED
from deploy.host_config import _file_metadata, _parent_metadata, _read_private, load_host_settings
from eval.tests.test_host_checks import catalogue_source as _catalogue_source
from eval.tests.test_host_checks import prepared as _prepared
from eval.tests.test_host_checks import world as _world

catalogue_source, prepared, world = _catalogue_source, _prepared, _world


def fixture_reader(path, limit):
    """Trusted test seam only; this does not assert Windows/POSIX permissions."""
    return path.read_bytes()


@pytest.fixture
def config_file(prepared, tmp_path, world):
    service, key = tmp_path / "service.key", tmp_path / "readiness.key"
    service.write_bytes(b"s" * 32)
    key.write_bytes(b"k" * 32)
    ledger = prepared["guard"].ledger
    inference = dict(
        zip(
            REQUIRED,
            [
                str(ledger.path),
                ledger.identity,
                "bedrock",
                "openai.gpt-oss-20b-1:0",
                "1",
                "1",
                "1",
                "2",
                "1",
                "1024",
            ],
            strict=True,
        )
    )
    data = {
        "version": 1,
        "release": str(prepared["release"]),
        "fingerprint": prepared["fingerprint"],
        "catalogue": str(prepared["catalogue"]),
        "table": prepared["admission"].store.table,
        "namespace": prepared["admission"].store.namespace,
        "invitation_identity": prepared["admission"].store.identity,
        "lifecycle_identity": world[4].identity,
        "service_secret_file": str(service),
        "readiness_secret_file": str(key),
        "inference": inference,
        "admission_limits": {
            name: getattr(prepared["admission"], name)
            for name in (
                "maximum_bytes",
                "global_rate",
                "browser_rate",
                "maximum_requests",
                "maximum_streams",
                "maximum_sessions",
                "browser_sessions",
            )
        },
    }
    path = tmp_path / "host.json"
    path.write_text(json.dumps(data))
    return path, data


def test_settings_are_validated_immutable_and_do_not_expose_keys(config_file):
    path, data = config_file
    settings = load_host_settings(path, read_private=fixture_reader)
    assert settings.service_secret == "s" * 32 and settings.readiness_secret == b"k" * 32
    assert "s" * 32 not in repr(settings) and "k" * 32 not in repr(settings)
    assert settings.environment()["COPILOT_ENV"] == "production"
    assert settings.environment()["AWS_REGION"] == "eu-north-1"
    with pytest.raises(TypeError):
        settings.inference["INFERENCE_PROVIDER"] = "scripted"
    data["inference"]["INFERENCE_PROVIDER"] = "scripted"
    assert settings.inference["INFERENCE_PROVIDER"] == "bedrock"
    with pytest.raises(ValueError):
        replace(settings, inference={})


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "version-bool",
        "relative",
        "bad-uuid",
        "alias",
        "missing-state",
        "extra-inference",
        "wrong-provider",
        "bad-limit",
        "wrong-fingerprint",
    ],
)
def test_invalid_settings_refuse_generically(config_file, change):
    path, data = config_file
    if change == "extra":
        data["AWS_SECRET_ACCESS_KEY"] = "private-value"
    elif change == "version-bool":
        data["version"] = True
    elif change == "relative":
        data["catalogue"] = "relative.sqlite"
    elif change == "bad-uuid":
        data["invitation_identity"] = "private-value"
    elif change == "alias":
        data["catalogue"] = data["inference"]["INFERENCE_LEDGER_PATH"]
    elif change == "missing-state":
        data["catalogue"] += ".missing"
    elif change == "extra-inference":
        data["inference"]["AWS_PROFILE"] = "private-value"
    elif change == "wrong-provider":
        data["inference"]["INFERENCE_PROVIDER"] = "openrouter"
    elif change == "bad-limit":
        data["admission_limits"]["maximum_requests"] = True
    else:
        data["fingerprint"] = "0" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="^Host configuration refused$") as caught:
        load_host_settings(path, read_private=fixture_reader)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize(
    "kind", ["duplicate", "oversize", "key-short", "service-whitespace", "inside-release"]
)
def test_raw_file_limits_and_secret_separation(config_file, kind):
    path, data = config_file
    if kind == "duplicate":
        path.write_text(path.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    elif kind == "oversize":
        path.write_bytes(b" " * 16385)
    elif kind == "key-short":
        path.with_name("readiness.key").write_bytes(b"short")
    elif kind == "service-whitespace":
        path.with_name("service.key").write_bytes(b"s" * 31 + b"\n")
    else:
        data["service_secret_file"] = str(path.parent / "release" / "key")
        (path.parent / "release" / "key").write_bytes(b"s" * 32)
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="^Host configuration refused$"):
        load_host_settings(path, read_private=fixture_reader)


@pytest.mark.parametrize(
    "mode,owner,links",
    [
        (0o644, 1000, 1),
        (0o600, 1001, 1),
        (0o600, 1000, 2),
        (0o000, 1000, 1),
        (stat.S_IFLNK | 0o600, 1000, 1),
    ],
)
def test_private_file_metadata_refuses_insecure_owner_mode_or_links(mode, owner, links):
    info = SimpleNamespace(
        st_mode=(stat.S_IFREG | mode) if not mode & stat.S_IFLNK else mode,
        st_uid=owner,
        st_nlink=links,
    )
    with pytest.raises(ValueError):
        _file_metadata(info, 1000)


def test_private_metadata_accepts_owner_only_files_and_safe_parents():
    _file_metadata(SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=1000, st_nlink=1), 1000)
    _parent_metadata(SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0), 1000)
    with pytest.raises(ValueError):
        _parent_metadata(SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=0), 1000)


def test_default_reader_does_not_claim_windows_permission_enforcement(config_file):
    if os.name != "posix":
        with pytest.raises(ValueError):
            _read_private(config_file[0], 16384)
