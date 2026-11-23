import configparser
import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from deploy.artifact import files
from deploy.component_config import ProxySettings, load_component_settings
from deploy.host_config import load_host_settings
from eval.tests.test_host_checks import catalogue_source as _catalogue_source
from eval.tests.test_host_checks import prepared as _prepared
from eval.tests.test_host_checks import world as _world
from eval.tests.test_host_config import config_file as _config_file
from eval.tests.test_host_config import fixture_reader
from eval.tests.test_release import command as release_command

catalogue_source, prepared, world, config_file = _catalogue_source, _prepared, _world, _config_file
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def module():
    from deploy import host_component

    return host_component


@pytest.fixture
def settings(module, config_file, monkeypatch):
    path, data = config_file
    release = Path(data["release"])
    for name in ("store/src/server.js", "panel/dist/index.html", "deploy/Caddyfile.public"):
        target = release / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic fixture, never executed")
    manifest_path = release / "release.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"] = files(release)
    manifest_path.write_text(json.dumps(manifest))
    data["fingerprint"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    minimal = {
        name: data[name]
        for name in ("version", "release", "fingerprint", "catalogue", "service_secret_file")
    }
    component_path = path.with_name("store.json")
    component_path.write_text(json.dumps(minimal))
    value = load_component_settings(component_path, "store", read_private=fixture_reader)
    monkeypatch.setattr(module, "_runtime_root", lambda: release)
    return value


@pytest.fixture
def proxy_settings(settings):
    return ProxySettings(settings.release, settings.fingerprint)


def test_agent_configuration_and_wrong_component_type_are_not_native_inputs(
    module, settings, config_file
):
    full = load_host_settings(config_file[0], read_private=fixture_reader)
    for value, component in ((full, "store"), (full, "proxy"), (settings, "proxy")):
        with pytest.raises(ValueError, match="Host component startup refused"):
            module.command(value, component)


def test_fixed_store_environment_excludes_ambient_authority(module, settings, monkeypatch):
    for name in (
        "AWS_ACCESS_KEY_ID",
        "NODE_OPTIONS",
        "LD_PRELOAD",
        "COPILOT_EVALUATION",
        "HTTP_PROXY",
    ):
        monkeypatch.setenv(name, "ambient-private-value")
    before = dict(os.environ)
    argv, environment = module.command(settings, "store")
    assert argv == ["/usr/bin/node", str(settings.release / "store/src/server.js")]
    assert environment == {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "COPILOT_ENV": "production",
        "COPILOT_SERVICE_SECRET": settings.service_secret,
        "COPILOT_PANEL_ORIGIN": "https://app.scpilot.tech",
        "COPILOT_STORE_ORIGIN": "https://store.scpilot.tech",
        "COPILOT_CATALOGUE_DB": str(settings.catalogue),
        "COPILOT_STATE_DB": "/var/lib/shopping-copilot/store/storefront-state.sqlite",
        "CATALOGUE_RANKING": "lexical",
        "COPILOT_RELEASE": settings.fingerprint[:12],
    }
    assert dict(os.environ) == before


def test_fixed_proxy_environment_has_no_secrets(module, settings, proxy_settings, monkeypatch):
    checked = []
    monkeypatch.setattr(module, "_storage", checked.append)
    argv, environment = module.command(proxy_settings, "proxy")
    assert argv == [
        "/usr/bin/caddy",
        "run",
        "--config",
        str(settings.release / "deploy/Caddyfile.public"),
        "--adapter",
        "caddyfile",
    ]
    assert environment == {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "COPILOT_PANEL_ROOT": (settings.release / "panel/dist").as_posix(),
        "COPILOT_CADDY_STORAGE": "/var/lib/shopping-copilot/caddy",
    }
    assert checked == [Path("/var/lib/shopping-copilot/caddy")]
    assert settings.service_secret not in repr(environment)


@pytest.mark.parametrize("character", ['"', "\\", "\n", "\r", "\t", "\x00", "\x7f"])
def test_proxy_paths_cannot_change_caddyfile_syntax(module, character):
    with pytest.raises(ValueError):
        module._caddy_path("/opt/release" + character + "name/panel/dist")
    assert module._caddy_path("/opt/release with spaces/panel/dist") == (
        "/opt/release with spaces/panel/dist"
    )


def test_proxy_command_validates_interpolated_path(module, proxy_settings, monkeypatch):
    checked = []

    def refuse(path):
        checked.append(path)
        raise ValueError("unsafe interpolation")

    monkeypatch.setattr(module, "_storage", lambda _: None)
    monkeypatch.setattr(module, "_caddy_path", refuse, raising=False)
    with pytest.raises(ValueError, match="^Host component startup refused$"):
        module.command(proxy_settings, "proxy")
    assert checked == [proxy_settings.release / "panel/dist"]


@pytest.mark.parametrize("kind", ["other-release", "tampered", "catalogue", "component", "storage"])
def test_preflight_refuses_before_exec(module, settings, proxy_settings, monkeypatch, kind):
    component = "store"
    if kind == "other-release":
        monkeypatch.setattr(module, "_runtime_root", lambda: settings.release.parent)
    elif kind == "tampered":
        (settings.release / "store/src/server.js").write_text("modified")
    elif kind == "catalogue":
        settings.catalogue.write_bytes(b"not a database")
    elif kind == "component":
        component = "arbitrary"
    else:
        component = "proxy"
        settings = proxy_settings

        def unsafe(_):
            raise ValueError("unsafe storage")

        monkeypatch.setattr(module, "_storage", unsafe)
    with pytest.raises((ValueError, OSError)):
        module.command(settings, component)


@pytest.mark.parametrize("kind", ["good", "public", "wrong-owner", "symlink", "no-write", "parent"])
def test_storage_metadata_checks(module, monkeypatch, kind):
    uid, mode = 1000, stat.S_IFDIR | 0o700
    if kind == "public":
        mode = stat.S_IFDIR | 0o755
    elif kind == "wrong-owner":
        uid = 1001
    elif kind == "symlink":
        mode = stat.S_IFLNK | 0o700
    elif kind == "no-write":
        mode = stat.S_IFDIR | 0o500
    info = SimpleNamespace(st_mode=mode, st_uid=uid)
    parent = SimpleNamespace(
        st_mode=stat.S_IFDIR | (0o777 if kind == "parent" else 0o755), st_uid=0
    )
    path = SimpleNamespace(
        is_absolute=lambda: True,
        lstat=lambda: info,
        parents=[SimpleNamespace(lstat=lambda: parent)],
    )
    monkeypatch.setattr(module, "os", SimpleNamespace(name="posix", geteuid=lambda: 1000))
    if kind == "good":
        module._storage(path)
    else:
        with pytest.raises(ValueError):
            module._storage(path)


@pytest.mark.parametrize(
    "binary,version,accepted",
    [
        ("/usr/bin/node", "v24.13.0\n", True),
        ("/usr/bin/node", "v24.25.3\n", True),
        ("/usr/bin/node", "v24.12.9\n", False),
        ("/usr/bin/node", "v25.0.0\n", False),
        ("/usr/bin/caddy", "v2.11.7 h1:fixture\n", True),
        ("/usr/bin/caddy", "v2.11.70\n", False),
        ("/usr/bin/caddy", "v2.11.6\n", False),
    ],
)
def test_bounded_fixed_version_check(module, monkeypatch, binary, version, accepted):
    environment = {"PATH": "/usr/bin:/bin"}

    def run(argv, **kwargs):
        assert argv == [binary, "--version" if binary.endswith("node") else "version"]
        assert kwargs["timeout"] == 5 and kwargs["env"] is environment
        return SimpleNamespace(returncode=0, stdout=version)

    monkeypatch.setattr(module.subprocess, "run", run)
    if accepted:
        module._version(binary, environment)
    else:
        with pytest.raises(ValueError):
            module._version(binary, environment)


@pytest.mark.parametrize("stage", ["load", "version", "exec", "timeout", "cli"])
def test_main_refuses_generically(module, settings, monkeypatch, capsys, stage):
    def fail(*_, **__):
        raise ValueError("private key/path")

    def timed_out(*_, **__):
        raise subprocess.TimeoutExpired("private key/path", 5)

    monkeypatch.setattr(
        module, "load_component_settings", fail if stage == "load" else lambda *_: settings
    )
    monkeypatch.setattr(
        module,
        "_version",
        timed_out if stage == "timeout" else fail if stage == "version" else lambda *_: None,
    )
    executed = []

    def execute(*_):
        executed.append(True)
        fail()

    monkeypatch.setattr(module.os, "execve", execute)
    arguments = ["--config", "/protected/host.json", "--component", "store"]
    if stage == "cli":
        arguments += ["--binary", "private key/path"]
    assert module.main(arguments) == 1
    output = capsys.readouterr()
    assert output.err == "Host component startup refused\n" and output.out == ""
    assert executed == ([True] if stage == "exec" else [])


def test_main_exec_replaces_process_with_exact_command(module, settings, monkeypatch):
    class Executed(BaseException):
        pass

    monkeypatch.setattr(module, "load_component_settings", lambda *_: settings)
    monkeypatch.setattr(module, "_version", lambda *_: None)
    expected = module.command(settings, "store")

    def execute(binary, argv, environment):
        assert binary == "/usr/bin/node" and (argv, environment) == expected
        raise Executed()

    monkeypatch.setattr(module.os, "execve", execute)
    with pytest.raises(Executed):
        module.main(["--config", "/protected/host.json", "--component", "store"])


def test_unit_bundle_order_conflicts_caps_and_explicit_target():
    names = {f"shopping-copilot-{name}.service" for name in ("store", "agent", "proxy")}
    target = configparser.ConfigParser()
    target.read(ROOT / "deploy/shopping-copilot-host.target")
    assert set(target["Unit"]["Wants"].split()) == names
    assert target["Install"]["WantedBy"] == "multi-user.target"
    for name in names:
        unit = configparser.ConfigParser()
        unit.read(ROOT / "deploy" / name)
        assert unit["Unit"]["PartOf"] == "shopping-copilot-host.target"
        assert "shopping-copilot.service" in unit["Unit"]["Conflicts"].split()
        after = unit["Unit"]["After"].split()
        assert "shopping-copilot.service" in after and "shopping-copilot-host.target" not in after
        component = name.removeprefix("shopping-copilot-").removesuffix(".service")
        assert unit["Service"]["User"] == (
            "copilot" if component == "agent" else "copilot-" + component
        )
        assert unit["Service"]["Group"] == unit["Service"]["User"]
        assert "shopping-copilot-metadata.service" in after
        assert (
            unit["Unit"]["BindsTo"]
            == unit["Unit"]["Requires"]
            == "shopping-copilot-metadata.service"
        )
        assert unit["Service"]["ProtectProc"] == "invisible"
        assert unit["Service"]["RestrictNamespaces"] == unit["Service"]["RestrictSUIDSGID"] == "yes"
        assert unit["Service"]["LogsDirectory"] == "shopping-copilot/" + component
        assert unit["Service"]["LogsDirectoryMode"] == "0700"
        assert "--service " + component + " --event starting" in unit["Service"]["ExecStartPre"]
        assert "--service " + component + " --event stopped" in unit["Service"]["ExecStopPost"]
        assert "/etc/shopping-copilot/" + component + "/" in unit["Service"]["ExecStart"]
        assert unit["Service"]["NoNewPrivileges"] == "yes"
        assert unit["Service"]["ProtectSystem"] == "strict"
        if "proxy" in name:
            assert {"shopping-copilot-store.service", "shopping-copilot-agent.service"} <= set(
                after
            )
            assert unit["Service"]["AmbientCapabilities"] == "CAP_NET_BIND_SERVICE"
            assert unit["Service"]["CapabilityBoundingSet"] == "CAP_NET_BIND_SERVICE"
            assert (
                unit["Service"]["ReadWritePaths"]
                == "/var/lib/shopping-copilot/caddy /var/log/shopping-copilot/proxy"
            )
        else:
            assert not unit["Service"].get("AmbientCapabilities", "")
        if "agent" in name:
            assert "shopping-copilot-store.service" in after
            assert unit["Service"]["SupplementaryGroups"] == "copilot-catalogue"
            assert "/var/lib/shopping-copilot/store" in unit["Service"]["ReadOnlyPaths"]
        if component != "proxy":
            assert (
                unit["Service"]["ReadWritePaths"]
                == f"/var/lib/shopping-copilot/{component} /var/log/shopping-copilot/{component}"
            )
    barrier = configparser.ConfigParser()
    barrier.read(ROOT / "deploy/shopping-copilot-metadata.service")
    service = barrier["Service"]
    assert service["User"] == "root" and service["Type"] == "oneshot"
    assert service["RemainAfterExit"] == "yes" and "ExecStop" not in service
    assert service["CapabilityBoundingSet"] == "CAP_NET_ADMIN"
    assert service["RestrictAddressFamilies"] == "AF_NETLINK"
    assert service.get("PrivateNetwork", "no") == "no"


def test_packaged_production_store_uses_generated_environment(
    module, config_file, tmp_path, monkeypatch
):
    from agent.catalogue_contract import SearchQuery
    from deploy.catalogue import catalogue_status

    for name, value in (
        ("COPILOT_PANEL_ORIGIN", "https://app.scpilot.tech"),
        ("COPILOT_STORE_ORIGIN", "https://store.scpilot.tech"),
        ("COPILOT_AGENT_ORIGIN", "https://app.scpilot.tech"),
    ):
        monkeypatch.setenv(name, value)
    release = tmp_path / "production-release"
    assert release_command("build", "--output", release).returncode == 0
    path, data = config_file
    data["release"] = str(release)
    data["fingerprint"] = hashlib.sha256((release / "release.json").read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    minimal = {
        name: data[name]
        for name in ("version", "release", "fingerprint", "catalogue", "service_secret_file")
    }
    component_path = path.with_name("store.json")
    component_path.write_text(json.dumps(minimal))
    settings = load_component_settings(component_path, "store", read_private=fixture_reader)
    monkeypatch.setattr(module, "_runtime_root", lambda: release)
    argv, environment = module.command(settings, "store")
    # Production keeps Storefront state in the host's state folder; the test process
    # cannot create that folder, so it runs against its own file.
    assert environment["COPILOT_STATE_DB"] == module.STORE_STATE_FILE
    environment["COPILOT_STATE_DB"] = str(tmp_path / "storefront-state.sqlite")
    before = catalogue_status(settings.catalogue)
    node = shutil.which("node")
    assert node is not None
    # Windows harness selects the installed binary; production still pins /usr/bin/node.
    if os.name == "nt":
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    for _ in range(2):
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", 4000)) != 0, "Test port4000 is occupied"
        process = subprocess.Popen(
            [node, *argv[1:]],
            cwd=release,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 15
            with httpx.Client(
                base_url="http://127.0.0.1:4000", timeout=2, trust_env=False
            ) as client:
                while True:
                    assert process.poll() is None, "Packaged Storefront exited"
                    try:
                        if client.get("/__catalogue/v1/products").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, "Packaged Storefront did not start"
                    time.sleep(0.05)
                assert client.post("/__test/reset").status_code == 404
                payload = SearchQuery(query="").model_dump(mode="json")
                assert client.post("/__internal/catalogue/search", json=payload).status_code in {
                    401,
                    403,
                }
                assert (
                    client.post(
                        "/__internal/catalogue/search",
                        json=payload,
                        headers={"x-service-secret": settings.service_secret},
                    ).status_code
                    == 200
                )
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        assert catalogue_status(settings.catalogue) == before
