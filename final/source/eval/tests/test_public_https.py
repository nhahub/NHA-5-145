"""Real Caddy parsing only: never provision modules, issue certificates or listen."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOSTS = {"app.scpilot.tech", "store.scpilot.tech"}


@pytest.fixture(scope="module")
def caddy_binary():
    candidate = os.environ.get("CADDY_BINARY") or shutil.which("caddy")
    if not candidate:
        local = ROOT / ".scratch/cap04-cloud-readiness/tools/caddy.exe"
        if os.name == "nt" and local.is_file():
            candidate = str(local)
    if not candidate:
        pytest.skip("Offline public HTTPS checks require the pinned Caddy 2.11.7 binary")
    result = subprocess.run(
        [candidate, "version"], capture_output=True, text=True, check=True, timeout=10
    )
    assert result.stdout.startswith("v2.11.7 "), "Use the pinned Caddy 2.11.7 executable"
    return candidate


def adapt(binary, profile, tmp_path, *, overrides=None):
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    }
    environment.update(
        COPILOT_PANEL_ORIGIN="https://app.scpilot.tech",
        COPILOT_STORE_ORIGIN="https://store.scpilot.tech",
        COPILOT_PANEL_ROOT=(tmp_path / "panel").as_posix(),
        COPILOT_CADDY_STORAGE=(tmp_path / "certificate-state").as_posix(),
        COPILOT_TLS_CERT=(tmp_path / "absent-test.pem").as_posix(),
        COPILOT_TLS_KEY=(tmp_path / "absent-test.key").as_posix(),
    )
    environment.update(overrides or {})
    result = subprocess.run(
        [binary, "adapt", "--config", str(ROOT / "deploy" / profile), "--adapter", "caddyfile"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "certificate-state").exists(), "Adapt must not provision TLS storage"
    return json.loads(result.stdout)


def servers(config):
    return list(config["apps"]["http"]["servers"].values())


def test_public_profile_automates_only_approved_hosts_without_static_certificates(
    caddy_binary, tmp_path
):
    config = adapt(caddy_binary, "Caddyfile.public", tmp_path)
    assert config["admin"] == {"disabled": True, "config": {"persist": False}}
    assert config["storage"] == {
        "module": "file_system",
        "root": (tmp_path / "certificate-state").as_posix(),
    }
    tls = config["apps"]["tls"]
    assert not tls.get("certificates")
    subjects = set()
    for policy in tls["automation"]["policies"]:
        subjects.update(policy["subjects"])
        assert policy["issuers"] == [
            {
                "module": "acme",
                "ca": "https://acme-v02.api.letsencrypt.org/directory",
                "challenges": {"bind_host": "0.0.0.0"},
            }
        ]
        assert not policy.get("on_demand")
    assert subjects == HOSTS
    for server in servers(config):
        assert server["listen"] == ["0.0.0.0:443"]
        assert server["strict_sni_host"] is True
        assert server.get("protocols") == ["h1", "h2"]
        assert not server.get("automatic_https", {}).get("disable")
        assert not server.get("automatic_https", {}).get("disable_redirects")


def test_public_profile_ignores_rehearsal_host_bind_upstream_and_certificate_overrides(
    caddy_binary, tmp_path
):
    baseline = adapt(caddy_binary, "Caddyfile.public", tmp_path)
    changed = adapt(
        caddy_binary,
        "Caddyfile.public",
        tmp_path,
        overrides={
            "COPILOT_PANEL_ORIGIN": "https://panel.copilot.test:4443",
            "COPILOT_STORE_ORIGIN": "https://store.merchant.test:4443",
            "COPILOT_PROXY_BIND": "127.0.0.2",
            "COPILOT_AGENT_UPSTREAM": "192.0.2.1:9999",
            "COPILOT_TLS_CERT": "do-not-load.pem",
            "COPILOT_TLS_KEY": "do-not-load.key",
        },
    )
    assert changed == baseline


def normalized_routes(routes):
    groups = {}

    def normalize(value):
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: normalize(item) for key, item in value.items()}
        if "group" in result:
            result["group"] = groups.setdefault(result["group"], len(groups))
        if result.get("handler") == "file_server":
            # The adapter hides its own source filename, outside the Panel root.
            assert len(result["hide"]) == 1
            assert Path(result["hide"][0]).name in {"Caddyfile", "Caddyfile.public"}
            result["hide"] = ["<profile source>"]
        return result

    return normalize(routes)


def test_public_profile_preserves_rehearsal_routes_and_redacted_diagnostics(caddy_binary, tmp_path):
    public = adapt(caddy_binary, "Caddyfile.public", tmp_path)
    rehearsal = adapt(caddy_binary, "Caddyfile", tmp_path)
    assert len(servers(public)) == len(servers(rehearsal)) == 1
    assert normalized_routes(servers(public)[0]["routes"]) == normalized_routes(
        servers(rehearsal)[0]["routes"]
    )
    assert public["logging"] == rehearsal["logging"]
    assert servers(rehearsal)[0]["listen"] == ["127.0.0.1:443"]
    assert servers(rehearsal)[0]["automatic_https"]["disable"] is True
