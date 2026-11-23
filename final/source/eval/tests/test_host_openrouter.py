"""Explicit protected fallback selection without provider or account access."""

import hashlib
import json
import os
import stat
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.inference.config import configured_guard
from agent.inference.ledger import AllowanceLedger
from agent.llm.config import load_llm_settings
from deploy import host_files
from deploy.artifact import files
from deploy.host_config import load_host_settings

PROVIDER_KEY = "synthetic-openrouter-key-" + "x" * 64


def fixture_reader(path, limit):
    """Synthetic inputs only; protected-reader metadata has a separate test below."""
    return path.read_bytes()


@pytest.fixture
def openrouter_config(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    (release / "app.py").write_text("# synthetic host fixture\n")
    manifest = {
        "format": 1,
        "catalogue_schema": 1,
        "files": files(release),
        "local_rehearsal": False,
        "public_origins": {
            "panel": "https://app.scpilot.tech",
            "store": "https://store.scpilot.tech",
            "agent": "https://app.scpilot.tech",
        },
    }
    (release / "release.json").write_text(json.dumps(manifest))
    catalogue = tmp_path / "catalogue.sqlite"
    catalogue.write_bytes(b"synthetic catalogue; not opened by host configuration")
    ledger_path = tmp_path / "ledger.sqlite"
    identity = AllowanceLedger.initialize(ledger_path, Decimal("0.73"))
    ledger = AllowanceLedger(ledger_path, identity)
    ledger.reserve("retained-uncertain", Decimal("0.04"))
    for name, value in (
        ("service.key", b"s" * 32),
        ("readiness.key", b"r" * 32),
        ("provider.key", PROVIDER_KEY.encode("ascii")),
    ):
        (tmp_path / name).write_bytes(value)
    data = {
        "version": 2,
        "provider": "openrouter",
        "model": "google/gemini-3.5-flash-lite",
        "provider_key_file": str(tmp_path / "provider.key"),
        "release": str(release),
        "fingerprint": hashlib.sha256((release / "release.json").read_bytes()).hexdigest(),
        "catalogue": str(catalogue),
        "table": "synthetic-host-table",
        "namespace": "synthetic-host",
        "invitation_identity": "11111111-1111-4111-8111-111111111111",
        "lifecycle_identity": "22222222-2222-4222-8222-222222222222",
        "service_secret_file": str(tmp_path / "service.key"),
        "readiness_secret_file": str(tmp_path / "readiness.key"),
        "inference": {
            "INFERENCE_LEDGER_PATH": str(ledger_path),
            "INFERENCE_LEDGER_ID": identity,
            "INFERENCE_PROVIDER": "openrouter",
            "INFERENCE_MODEL": "google/gemini-3.5-flash-lite",
            "INFERENCE_INPUT_USD_PER_MILLION": "0.3",
            "INFERENCE_OUTPUT_USD_PER_MILLION": "2.5",
            "INFERENCE_MAX_ACTIVE": "1",
            "INFERENCE_MAX_WAITING": "2",
            "INFERENCE_WAIT_SECONDS": "1",
            "INFERENCE_MAXIMUM_PAGES": "1024",
        },
        "admission_limits": {
            "maximum_bytes": 2621440,
            "global_rate": 1000,
            "browser_rate": 120,
            "maximum_requests": 16,
            "maximum_streams": 16,
            "maximum_sessions": 20,
            "browser_sessions": 2,
        },
    }
    path = tmp_path / "host.json"
    path.write_text(json.dumps(data))
    return path, data, ledger


def assert_refused(path, *, reader=fixture_reader):
    with pytest.raises(ValueError, match="^Host configuration refused$") as caught:
        load_host_settings(path, read_private=reader)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert PROVIDER_KEY not in str(caught.value) and str(path) not in str(caught.value)


def test_explicit_fallback_binds_model_key_cap_and_existing_allowance(
    openrouter_config, monkeypatch
):
    path, data, ledger = openrouter_config
    before = ledger.status()
    monkeypatch.setattr(
        AllowanceLedger, "initialize", lambda *args: pytest.fail("Host reset allowance")
    )
    for provider in ("bedrock.BedrockClient", "openrouter.OpenRouterClient"):
        monkeypatch.setattr(
            f"agent.llm.{provider}.__init__",
            lambda *args, **kwargs: pytest.fail("Constructed model"),
        )
    settings = load_host_settings(path, read_private=fixture_reader)
    values = settings.environment()
    llm = load_llm_settings(values)
    assert llm.provider == "openrouter" and llm.model == "google/gemini-3.5-flash-lite"
    assert llm.api_key.get_secret_value() == PROVIDER_KEY
    assert values["OPENROUTER_TOTAL_CAP_DOLLARS"] == "2.00"
    assert llm.openrouter_total_limit == 2.0
    assert Path(data["provider_key_file"]).resolve() in settings.private_files
    guard = configured_guard(object(), llm, values)
    assert guard.ledger.status() == before == ledger.status()
    assert before["remaining_usd"] == "0.690000000" and before["uncertain"] == 1
    assert guard.prices.input_per_million == Decimal("0.3")
    assert guard.prices.output_per_million == Decimal("2.5")


def test_fallback_selection_is_immutable_and_secret_free_in_repr(openrouter_config):
    path, data, _ = openrouter_config
    settings = load_host_settings(path, read_private=fixture_reader)
    assert all(secret not in repr(settings) for secret in (PROVIDER_KEY, "s" * 32, "r" * 32))
    with pytest.raises(FrozenInstanceError):
        settings.provider = "bedrock"
    with pytest.raises(FrozenInstanceError):
        settings.model = "arbitrary-model"
    with pytest.raises(TypeError):
        settings.inference["INFERENCE_PROVIDER"] = "bedrock"
    data["inference"]["INFERENCE_MODEL"] = "arbitrary-model"
    values = settings.environment()
    values["OPENROUTER_API_KEY"] = "changed"
    assert settings.environment()["OPENROUTER_API_KEY"] == PROVIDER_KEY
    assert settings.environment()["INFERENCE_MODEL"] == "google/gemini-3.5-flash-lite"
    for change in (
        {"provider": "bedrock"},
        {"model": "arbitrary-model"},
        {"provider_key": ""},
        {"provider_key": "x" * 257},
    ):
        with pytest.raises(ValueError, match="^Host configuration refused$") as caught:
            replace(settings, **change)
        assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2.0),
        ("version", "2"),
        ("version", 3),
        ("provider", "bedrock"),
        ("provider", "scripted"),
        ("provider", None),
        ("provider", ["openrouter"]),
        ("provider", " openrouter"),
        ("model", "google/gemini-2.5-flash"),
        ("model", "openai.gpt-oss-20b-1:0"),
        ("model", None),
        ("model", ["google/gemini-3.5-flash-lite"]),
        ("provider_key_file", "provider.key"),
        ("provider_key_file", None),
        ("provider_key_file", 123),
        ("provider_key_file", ["provider.key"]),
        ("OPENROUTER_TOTAL_CAP_DOLLARS", "3"),
        ("provider_key", PROVIDER_KEY),
    ],
)
def test_fallback_schema_refuses_other_routes_types_or_inline_secrets(
    openrouter_config, field, value
):
    path, data, _ = openrouter_config
    data[field] = value
    path.write_text(json.dumps(data))
    assert_refused(path)


@pytest.mark.parametrize("field", ["provider", "model", "provider_key_file"])
def test_fallback_requires_every_explicit_selection_field(openrouter_config, field):
    path, data, _ = openrouter_config
    del data[field]
    path.write_text(json.dumps(data))
    assert_refused(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("INFERENCE_PROVIDER", "bedrock"),
        ("INFERENCE_MODEL", "google/gemini-2.5-flash"),
        ("INFERENCE_INPUT_USD_PER_MILLION", "0.299"),
        ("INFERENCE_OUTPUT_USD_PER_MILLION", "2.49"),
        ("INFERENCE_MAX_ACTIVE", "0"),
        ("INFERENCE_MAX_WAITING", "65"),
        ("INFERENCE_WAIT_SECONDS", "31"),
        ("OPENROUTER_TOTAL_CAP_DOLLARS", "3"),
        ("OPENROUTER_API_KEY", PROVIDER_KEY),
    ],
)
def test_fallback_preserves_inference_binding_price_and_queue_checks(
    openrouter_config, field, value
):
    path, data, _ = openrouter_config
    data["inference"][field] = value
    path.write_text(json.dumps(data))
    assert_refused(path)


@pytest.mark.parametrize(
    "value", [b"", b"x" * 31, b"x" * 257, b"x" * 32 + b"\n", b"x " * 32, b"\xff" * 32]
)
def test_fallback_requires_bounded_ascii_non_whitespace_key(openrouter_config, value):
    path, data, _ = openrouter_config
    Path(data["provider_key_file"]).write_bytes(value)
    assert_refused(path)


@pytest.mark.parametrize("length", [32, 256])
def test_fallback_accepts_key_length_boundaries(openrouter_config, length):
    path, data, _ = openrouter_config
    Path(data["provider_key_file"]).write_bytes(b"x" * length)
    settings = load_host_settings(path, read_private=fixture_reader)
    assert settings.environment()["OPENROUTER_API_KEY"] == "x" * length


@pytest.mark.parametrize("kind", ["missing", "service-alias", "readiness-alias", "inside-release"])
def test_provider_key_is_an_existing_disjoint_external_private_file(openrouter_config, kind):
    path, data, _ = openrouter_config
    if kind == "missing":
        Path(data["provider_key_file"]).unlink()
    elif kind in {"service-alias", "readiness-alias"}:
        name = "service_secret_file" if kind == "service-alias" else "readiness_secret_file"
        data["provider_key_file"] = str(Path(data[name]).parent / "." / Path(data[name]).name)
    else:
        target = Path(data["release"]) / "provider.key"
        target.write_bytes(PROVIDER_KEY.encode("ascii"))
        data["provider_key_file"] = str(target)
        manifest_path = Path(data["release"]) / "release.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"] = files(Path(data["release"]))
        manifest_path.write_text(json.dumps(manifest))
        data["fingerprint"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    assert_refused(path)


def test_fallback_refusal_redacts_reader_exceptions(openrouter_config):
    path, data, _ = openrouter_config

    def reader(target, limit):
        if target == Path(data["provider_key_file"]):
            raise OSError(f"{target}: {PROVIDER_KEY}")
        return fixture_reader(target, limit)

    assert_refused(path, reader=reader)


def test_ambient_values_and_dotenv_cannot_select_or_override_fallback(
    openrouter_config, monkeypatch
):
    path, _, _ = openrouter_config
    for name, value in {
        "LLM_PROVIDER": "scripted",
        "LLM_MODEL": "ambient-model",
        "OPENROUTER_API_KEY": "ambient-key",
        "OPENROUTER_TOTAL_CAP_DOLLARS": "100",
        "INFERENCE_PROVIDER": "bedrock",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("agent.llm.config.load_dotenv", lambda: pytest.fail("Loaded dotenv"))
    before = dict(os.environ)
    settings = load_host_settings(path, read_private=fixture_reader)
    assert dict(os.environ) == before
    assert settings.environment()["LLM_PROVIDER"] == "openrouter"
    assert settings.environment()["LLM_MODEL"] == "google/gemini-3.5-flash-lite"
    assert settings.environment()["OPENROUTER_API_KEY"] == PROVIDER_KEY
    assert settings.environment()["OPENROUTER_TOTAL_CAP_DOLLARS"] == "2.00"


def test_version_one_stays_bedrock_and_refuses_fallback_fields(openrouter_config):
    path, data, _ = openrouter_config
    data["version"] = 1
    path.write_text(json.dumps(data))
    assert_refused(path)
    for name in ("provider", "model", "provider_key_file"):
        del data[name]
    data["inference"]["INFERENCE_PROVIDER"] = "bedrock"
    data["inference"]["INFERENCE_MODEL"] = "openai.gpt-oss-20b-1:0"
    path.write_text(json.dumps(data))
    values = load_host_settings(path, read_private=fixture_reader).environment()
    assert values["LLM_PROVIDER"] == "bedrock"
    assert values["LLM_MODEL"] == "openai.gpt-oss-20b-1:0"
    assert "OPENROUTER_API_KEY" not in values and "OPENROUTER_TOTAL_CAP_DOLLARS" not in values


@pytest.mark.parametrize(
    "kind",
    [
        "safe",
        "readable-by-group",
        "wrong-owner",
        "hardlink",
        "symlink",
        "unsafe-parent",
        "oversize",
    ],
)
def test_provider_key_uses_existing_posix_descriptor_reader(openrouter_config, monkeypatch, kind):
    path, data, _ = openrouter_config
    raw_key = PROVIDER_KEY.encode("ascii")
    file_info = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600,
        st_uid=1000,
        st_nlink=1,
        st_size=len(raw_key),
        st_dev=1,
        st_ino=2,
        st_mtime_ns=1,
        st_ctime_ns=1,
    )
    parent_info = SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=0)
    if kind == "readable-by-group":
        file_info.st_mode |= 0o040
    elif kind == "wrong-owner":
        file_info.st_uid = 1001
    elif kind == "hardlink":
        file_info.st_nlink = 2
    elif kind == "symlink":
        file_info.st_mode = stat.S_IFLNK | 0o600
    elif kind == "unsafe-parent":
        parent_info.st_mode |= 0o002
    elif kind == "oversize":
        file_info.st_size = 257
    protected_path = SimpleNamespace(
        is_absolute=lambda: True,
        parents=[SimpleNamespace(lstat=lambda: parent_info)],
    )
    chunks = iter([raw_key, b""])
    monkeypatch.setattr(
        host_files,
        "os",
        SimpleNamespace(
            name="posix",
            geteuid=lambda: 1000,
            O_RDONLY=0,
            O_NOFOLLOW=1,
            O_NONBLOCK=2,
            O_CLOEXEC=4,
            open=lambda target, flags: 5,
            fstat=lambda descriptor: file_info,
            read=lambda descriptor, limit: next(chunks),
            close=lambda descriptor: None,
        ),
    )

    def reader(target, limit):
        if target == Path(data["provider_key_file"]):
            assert limit == 256
            return host_files._read_private(protected_path, limit)
        return fixture_reader(target, limit)

    if kind == "safe":
        settings = load_host_settings(path, read_private=reader)
        assert settings.environment()["OPENROUTER_API_KEY"] == PROVIDER_KEY
    else:
        assert_refused(path, reader=reader)
