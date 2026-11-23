"""Disposable offline runtime proof, never a host installer or application launcher."""

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

INPUT, WHEELS, WORK = Path("/input"), Path("/wheels"), Path("/rehearsal")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert len(sys.argv) == 2 and digest(INPUT / "profile.json") == sys.argv[1]
    profile = json.loads((INPUT / "profile.json").read_bytes())
    assert profile["production_interpreter_approved"] is False
    assert sys.version_info[:2] == (3, 12) and sys.platform == "linux"
    assert platform.machine() == "x86_64" and os.geteuid() != 0
    assert platform.python_version() == profile["target"]["marker_python_full_version"]
    assert platform.libc_ver() == ("glibc", profile["target"]["libc_version"])
    assert not any("site-packages" in path for path in sys.path)
    expected = {row["name"]: row["version"] for row in profile["wheels"]}
    assert len(expected) == 28 and "packaging" not in expected
    lock = "".join(
        f"{row['name']}{'[standard]' if row['name'] == 'uvicorn' else ''}"
        f"=={row['version']} --hash=sha256:{row['sha256']}\n"
        for row in profile["wheels"]
    ).encode("ascii")
    assert (INPUT / "requirements.lock").read_bytes() == lock
    for row in profile["wheels"]:
        path = WHEELS / row["filename"]
        assert path.name == row["filename"] and path.stat().st_size == row["bytes"]
        assert digest(path) == row["sha256"]
    os.environ.clear()
    os.environ.update(PATH="/usr/bin:/bin", HOME="/tmp", AWS_EC2_METADATA_DISABLED="true")
    os.umask(0o077)
    site = WORK / "site"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "install",
            "--no-index",
            "--require-hashes",
            "--no-deps",
            "--only-binary=:all:",
            "--no-compile",
            "--no-cache-dir",
            "--no-warn-script-location",
            "--find-links",
            str(WHEELS),
            "--target",
            str(site),
            "-r",
            str(INPUT / "requirements.lock"),
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, "Offline runtime installation failed"
    installed = {
        distribution.metadata["Name"].lower().replace("_", "-"): distribution.version
        for distribution in importlib.metadata.distributions(path=[str(site)])
    }
    assert installed == expected
    sys.path.insert(0, str(site))

    def blocked(*_, **__):
        raise RuntimeError("Network forbidden in offline runtime proof")

    socket.socket.connect = blocked
    socket.getaddrinfo = blocked
    # Diagnostic tooling stays outside the installed 28-distribution runtime.
    tool = INPUT / "packaging.whl"
    assert digest(tool) == "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"
    sys.path.insert(1, str(tool))
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    pending, reached = [Requirement(root) for root in profile["roots"]], set()
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        identity = (name, tuple(sorted(requirement.extras)))
        if identity in reached:
            continue
        reached.add(identity)
        distribution = importlib.metadata.distribution(name)
        assert Path(distribution.locate_file("")).resolve() == site
        assert distribution.version == expected[name]
        assert distribution.version in requirement.specifier
        for raw in distribution.requires or ():
            dependency = Requirement(raw)
            if dependency.marker is None or any(
                dependency.marker.evaluate({**default_environment(), "extra": extra})
                for extra in {"", *requirement.extras}
            ):
                assert dependency.url is None
                pending.append(dependency)
    assert {name for name, _ in reached} == set(expected)
    native = {}
    for name in (
        "pydantic_core._pydantic_core",
        "httptools.parser.parser",
        "yaml._yaml",
        "uvloop.loop",
        "watchfiles._rust_notify",
        "websockets.speedups",
    ):
        module = importlib.import_module(name)
        assert Path(module.__file__).is_relative_to(site) and ".so" in module.__file__
        native[name] = Path(module.__file__).name
    print(
        json.dumps(
            {
                "status": "ok",
                "python": platform.python_version(),
                "libc": platform.libc_ver(),
                "runtime_distributions": installed,
                "dependency_closure": True,
                "native_imports": native,
                "production_interpreter_approved": False,
                "application_started": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
