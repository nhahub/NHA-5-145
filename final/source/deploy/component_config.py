"""Least-input native service configuration; no Agent state or SDK imports."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from deploy.host_files import _pairs, _read_private, production_release


def _paths(release, paths):
    if any(not isinstance(path, Path) or not path.is_absolute() for path in paths):
        raise ValueError()
    resolved = [path.resolve(strict=True) for path in paths]
    if len(set(resolved)) != len(paths) or any(
        not path.is_file() or path.is_relative_to(release) for path in resolved
    ):
        raise ValueError()
    return tuple(resolved)


@dataclass(frozen=True)
class ProxySettings:
    release: Path
    fingerprint: str
    private_files: tuple[Path, ...] = field(default=(), repr=False)

    def __post_init__(self):
        self._validate()

    def _validate(self):
        release = production_release(self.release, self.fingerprint)
        private = _paths(release, self.private_files)
        object.__setattr__(self, "release", release)
        object.__setattr__(self, "private_files", private)


@dataclass(frozen=True)
class StoreSettings:
    release: Path
    fingerprint: str
    catalogue: Path
    service_secret: str = field(repr=False)
    private_files: tuple[Path, ...] = field(default=(), repr=False)

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if (
            type(self.service_secret) is not str
            or re.fullmatch(r"[!-~]{32,128}", self.service_secret) is None
        ):
            raise ValueError("Component configuration refused")
        release = production_release(self.release, self.fingerprint)
        paths = _paths(release, (self.catalogue, *self.private_files))
        object.__setattr__(self, "release", release)
        object.__setattr__(self, "catalogue", paths[0])
        object.__setattr__(self, "private_files", paths[1:])


def load_component_settings(config_path, component, *, read_private=_read_private):
    try:
        if component not in {"store", "proxy"} or type(component) is not str:
            raise ValueError()
        path = Path(config_path)
        raw = read_private(path, 16384)
        if not path.is_absolute() or type(raw) is not bytes or len(raw) > 16384:
            raise ValueError()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        names = {"version", "release", "fingerprint"}
        if component == "store":
            names |= {"catalogue", "service_secret_file"}
        if (
            type(data) is not dict
            or set(data) != names
            or type(data["version"]) is not int
            or data["version"] != 1
        ):
            raise ValueError()
        values = {"release": Path(data["release"]), "fingerprint": data["fingerprint"]}
        if component == "proxy":
            return ProxySettings(**values, private_files=(path,))
        secret_path = Path(data["service_secret_file"])
        if not secret_path.is_absolute():
            raise ValueError()
        raw_secret = read_private(secret_path, 128)
        if type(raw_secret) is not bytes:
            raise ValueError()
        return StoreSettings(
            **values,
            catalogue=Path(data["catalogue"]),
            service_secret=raw_secret.decode("ascii"),
            private_files=(path, secret_path),
        )
    except Exception:
        pass
    raise ValueError("Component configuration refused")
