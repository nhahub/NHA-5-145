"""Protected, fixed Storefront/proxy exec; no cloud SDK or service activation on import."""

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

from deploy.catalogue import catalogue_status
from deploy.component_config import ProxySettings, StoreSettings, load_component_settings
from deploy.host_files import ORIGINS, _parent_metadata

CADDY_STORAGE = Path("/var/lib/shopping-copilot/caddy")
# Saved carts, orders and sign-in: the Storefront unit's own writable state folder.
STORE_STATE_FILE = "/var/lib/shopping-copilot/store/storefront-state.sqlite"


def _runtime_root():
    return Path(__file__).resolve().parents[1]


def _caddy_path(path):
    value = path.as_posix() if isinstance(path, Path) else str(path)
    if any(
        character in {'"', "\\"} or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        raise ValueError("Literal Caddy path required")
    return value


def _storage(path):
    if os.name != "posix" or not path.is_absolute():
        raise ValueError("Protected POSIX storage required")
    uid = os.geteuid()
    for parent in path.parents:
        _parent_metadata(parent.lstat(), uid)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != uid
        or info.st_mode & 0o077
        or info.st_mode & 0o700 != 0o700
    ):
        raise ValueError("Protected storage required")


def command(settings, component):
    try:
        if component not in {"store", "proxy"} or type(settings) is not (
            StoreSettings if component == "store" else ProxySettings
        ):
            raise ValueError()
        settings._validate()
        if _runtime_root() != settings.release:
            raise ValueError()
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        if component == "store":
            script = settings.release / "store/src/server.js"
            if not script.is_file():
                raise ValueError()
            catalogue_status(settings.catalogue)
            environment.update(
                {
                    "COPILOT_ENV": "production",
                    "COPILOT_SERVICE_SECRET": settings.service_secret,
                    "COPILOT_PANEL_ORIGIN": ORIGINS["panel"],
                    "COPILOT_STORE_ORIGIN": ORIGINS["store"],
                    "COPILOT_CATALOGUE_DB": str(settings.catalogue),
                    "COPILOT_STATE_DB": STORE_STATE_FILE,
                    "CATALOGUE_RANKING": "lexical",
                    "COPILOT_RELEASE": settings.fingerprint[:12],
                }
            )
            return ["/usr/bin/node", str(script)], environment
        panel, profile = (
            settings.release / "panel/dist",
            settings.release / "deploy/Caddyfile.public",
        )
        if not (panel / "index.html").is_file() or not profile.is_file():
            raise ValueError()
        if CADDY_STORAGE.is_relative_to(settings.release):
            raise ValueError()
        _storage(CADDY_STORAGE)
        environment.update(
            COPILOT_PANEL_ROOT=_caddy_path(panel), COPILOT_CADDY_STORAGE=CADDY_STORAGE.as_posix()
        )
        return [
            "/usr/bin/caddy",
            "run",
            "--config",
            str(profile),
            "--adapter",
            "caddyfile",
        ], environment
    except Exception:
        pass
    raise ValueError("Host component startup refused")


def _version(binary, environment):
    if binary not in {"/usr/bin/node", "/usr/bin/caddy"}:
        raise ValueError()
    result = subprocess.run(
        [binary, "--version" if binary == "/usr/bin/node" else "version"],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
        timeout=5,
    )
    if result.returncode != 0 or len(result.stdout) > 512:
        raise ValueError()
    if binary == "/usr/bin/node":
        match = re.fullmatch(r"v24\.(\d+)\.\d+\s*", result.stdout)
        if match is None or int(match[1]) < 13:
            raise ValueError()
    elif re.match(r"v2\.11\.7(?:\s|$)", result.stdout) is None:
        raise ValueError()


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


def main(argv=None):
    try:
        parser = _Parser(description="Run a restricted host component", allow_abbrev=False)
        parser.add_argument("--config", type=Path, required=True)
        parser.add_argument("--component", choices=("store", "proxy"), required=True)
        args = parser.parse_args(argv)
        settings = load_component_settings(args.config, args.component)
        arguments, environment = command(settings, args.component)
        _version(arguments[0], environment)
        os.execve(arguments[0], arguments, environment)
        raise RuntimeError("Exec unexpectedly returned")
    except KeyboardInterrupt:
        code = 130
    except (Exception, SystemExit) as error:
        if isinstance(error, SystemExit) and error.code == 0:
            return 0
        code = 1
    print("Host component startup refused", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
