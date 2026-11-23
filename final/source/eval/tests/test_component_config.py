import hashlib
import json
from dataclasses import replace

import pytest

from deploy.artifact import files


@pytest.fixture
def component_files(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    for name in ("store/src/server.js", "panel/dist/index.html", "deploy/Caddyfile.public"):
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    manifest = release / "release.json"
    manifest.write_text(
        json.dumps(
            {
                "format": 1,
                "catalogue_schema": 1,
                "local_rehearsal": False,
                "public_origins": {
                    "panel": "https://app.scpilot.tech",
                    "store": "https://store.scpilot.tech",
                    "agent": "https://app.scpilot.tech",
                },
                "files": files(release),
            }
        )
    )
    catalogue = tmp_path / "catalogue.sqlite"
    catalogue.write_bytes(b"not inspected during minimal config load")
    secret = tmp_path / "store.key"
    secret.write_bytes(b"s" * 32)
    basic = {
        "version": 1,
        "release": str(release),
        "fingerprint": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }
    return tmp_path, basic, catalogue, secret


@pytest.mark.parametrize("component", ["store", "proxy"])
def test_minimal_component_load_reads_only_its_own_inputs(component_files, component):
    from deploy.component_config import ProxySettings, StoreSettings, load_component_settings

    directory, data, catalogue, secret = component_files
    if component == "store":
        data.update(catalogue=str(catalogue), service_secret_file=str(secret))
    config = directory / (component + ".json")
    config.write_text(json.dumps(data))
    reads = []

    def reader(path, limit):
        reads.append(path)
        return path.read_bytes()

    settings = load_component_settings(config, component, read_private=reader)
    assert type(settings) is (StoreSettings if component == "store" else ProxySettings)
    assert reads == ([config, secret] if component == "store" else [config])
    assert settings.release == directory / "release"
    assert "s" * 32 not in repr(settings)
    assert not hasattr(settings, "readiness_secret") and not hasattr(settings, "inference")
    with pytest.raises(ValueError):
        replace(settings, fingerprint="0" * 64)


@pytest.mark.parametrize(
    "case",
    [
        "agent-fields",
        "duplicate",
        "version-bool",
        "unknown-component",
        "secret-in-proxy",
        "relative",
        "changed",
        "missing",
        "bad-secret",
        "alias",
    ],
)
def test_unsafe_or_overprivileged_component_config_refuses(component_files, case):
    from deploy.component_config import load_component_settings

    directory, data, catalogue, secret = component_files
    component = "store"
    data.update(catalogue=str(catalogue), service_secret_file=str(secret))
    if case == "agent-fields":
        data["inference"] = {"AWS_SECRET_ACCESS_KEY": "private"}
    elif case == "version-bool":
        data["version"] = True
    elif case == "unknown-component":
        component = "arbitrary"
    elif case == "secret-in-proxy":
        component = "proxy"
    elif case == "relative":
        data["catalogue"] = "relative.sqlite"
    elif case == "changed":
        (directory / "release/store/src/server.js").write_text("changed")
    elif case == "missing":
        data["catalogue"] += ".missing"
    elif case == "bad-secret":
        secret.write_bytes(b"s" * 31 + b"\n")
    elif case == "alias":
        data["catalogue"] = str(secret)
    config = directory / "component.json"
    config.write_text(json.dumps(data))
    if case == "duplicate":
        config.write_text(config.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    with pytest.raises(ValueError, match="^Component configuration refused$") as error:
        load_component_settings(
            config, component, read_private=lambda path, limit: path.read_bytes()
        )
    assert error.value.__cause__ is None and error.value.__context__ is None
