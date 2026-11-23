"""Offline Linux host input preparation; never installs, imports wheels or activates services.

The packaging library belongs to the preparation environment, not the host runtime lock.
The tested marker patch does not approve a production interpreter or provisioning method.
"""

import hashlib
import io
import json
import re
import stat
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import compatible_tags, cpython_tags, parse_tag
from packaging.utils import canonicalize_name, parse_wheel_filename

TARGET = {
    "implementation": "cpython",
    "python_version": "3.12",
    "sys_platform": "linux",
    "platform_machine": "x86_64",
    "libc": "glibc",
    "libc_version": "2.34",
    "marker_python_full_version": "3.12.14",
}
RUNTIME_NAMES = {
    "annotated-types",
    "anyio",
    "boto3",
    "botocore",
    "certifi",
    "click",
    "fastapi",
    "h11",
    "httpcore",
    "httptools",
    "httpx",
    "idna",
    "jmespath",
    "pydantic",
    "pydantic-core",
    "python-dateutil",
    "python-dotenv",
    "pyyaml",
    "s3transfer",
    "six",
    "starlette",
    "typing-extensions",
    "typing-inspection",
    "urllib3",
    "uvicorn",
    "uvloop",
    "watchfiles",
    "websockets",
}
MAX_WHEEL = 64 * 1024**2
MAX_MEMBERS, MAX_EXPANDED, MAX_METADATA = 20000, 256 * 1024**2, 2 * 1024**2


def _refuse():
    raise ValueError("Linux runtime inputs refused")


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            _refuse()
        result[name] = value
    return result


def _read(root, name, maximum):
    path = root
    for part in name.split("/"):
        path /= part
        if path.is_symlink() or path.is_junction():
            _refuse()
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
        _refuse()
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    after = path.stat()
    if len(data) != before.st_size or any(
        getattr(before, key) != getattr(after, key)
        for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    ):
        _refuse()
    return data


def _root(value):
    value = Path(value).absolute()
    if value.is_symlink() or value.is_junction() or not value.is_dir():
        _refuse()
    return value


def _tags():
    # Explicit target platforms: never use sys_tags(), uname or Windows host markers.
    platforms = []
    for minor in range(34, 4, -1):
        platforms.append(f"manylinux_2_{minor}_x86_64")
        if minor in {17, 12, 5}:
            platforms.append(
                {17: "manylinux2014", 12: "manylinux2010", 5: "manylinux1"}[minor] + "_x86_64"
            )
    return set(cpython_tags((3, 12), abis=["cp312"], platforms=platforms)) | set(
        compatible_tags((3, 12), interpreter="cp312", platforms=platforms)
    )


def _roots(profile, project):
    roots = profile["roots"]
    if type(roots) is not list or roots != project["project"]["dependencies"] or not roots:
        _refuse()
    if TARGET["marker_python_full_version"] not in SpecifierSet(
        project["project"]["requires-python"]
    ):
        _refuse()
    result = {}
    for text in roots:
        if type(text) is not str:
            _refuse()
        requirement = Requirement(text)
        specs = list(requirement.specifier)
        name = canonicalize_name(requirement.name)
        if (
            requirement.url
            or requirement.marker
            or len(specs) != 1
            or specs[0].operator != "=="
            or "*" in specs[0].version
            or name in result
        ):
            _refuse()
        result[name] = requirement
    return result


def _inventory(source):
    profile = json.loads(
        _read(source, "deploy/linux-runtime.json", 65536), object_pairs_hook=_pairs
    )
    if (
        type(profile) is not dict
        or set(profile)
        != {"version", "purpose", "production_interpreter_approved", "target", "roots", "wheels"}
        or type(profile["version"]) is not int
        or profile["version"] != 1
        or profile["purpose"] != "linux-host-runtime-preparation"
        or profile["production_interpreter_approved"] is not False
        or profile["target"] != TARGET
    ):
        _refuse()
    roots = _roots(profile, tomllib.loads(_read(source, "pyproject.toml", 256 * 1024).decode()))
    wheels, names, filenames, lines = profile["wheels"], set(), set(), []
    supported = _tags()
    if type(wheels) is not list or len(wheels) != len(RUNTIME_NAMES):
        _refuse()
    for item in wheels:
        if (
            type(item) is not dict
            or set(item) != {"name", "version", "filename", "sha256", "bytes"}
            or any(type(item[key]) is not str for key in ("name", "version", "filename", "sha256"))
            or type(item["bytes"]) is not int
            or not 0 < item["bytes"] <= MAX_WHEEL
            or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
            or re.fullmatch(r"[A-Za-z0-9_.+\-]+\.whl", item["filename"]) is None
        ):
            _refuse()
        name, version, build, tags = parse_wheel_filename(item["filename"])
        if (
            item["name"] != canonicalize_name(item["name"])
            or name != item["name"]
            or str(version) != item["version"]
            or build
            or not tags & supported
            or name in names
            or item["filename"].casefold() in filenames
        ):
            _refuse()
        names.add(name)
        filenames.add(item["filename"].casefold())
        extras = ""
        if name in roots:
            if version not in roots[name].specifier:
                _refuse()
            if roots[name].extras:
                extras = "[" + ",".join(sorted(roots[name].extras)) + "]"
        lines.append(f"{name}{extras}=={version} --hash=sha256:{item['sha256']}\n")
    if names != RUNTIME_NAMES or not set(roots) <= names:
        _refuse()
    if _read(source, "deploy/requirements-linux.lock", 65536) != "".join(lines).encode("ascii"):
        _refuse()
    return profile


def inventory(source: Path) -> dict:
    """Validate the prepared target/profile, exact hash lock and project dependency pins."""
    try:
        return _inventory(_root(source))
    except Exception:
        raise ValueError("Linux runtime inputs refused") from None


def _one(metadata, name):
    values = metadata.get_all(name, [])
    if len(values) != 1:
        _refuse()
    return values[0]


def _metadata(data, item):
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        _refuse()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries, folded, total = {}, set(), 0
        if len(archive.infolist()) > MAX_MEMBERS:
            _refuse()
        for info in archive.infolist():
            name = info.orig_filename
            parts = name.rstrip("/").split("/")
            total += info.file_size
            if (
                not name
                or name != info.filename
                or "\\" in name
                or ":" in name
                or any(ord(char) < 32 or ord(char) == 127 for char in name)
                or any(part in {"", ".", ".."} for part in parts)
                or name.casefold() in folded
                or stat.S_IFMT(info.external_attr >> 16)
                not in {0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG}
                or info.flag_bits & 1
                or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or total > MAX_EXPANDED
            ):
                _refuse()
            folded.add(name.casefold())
            entries[name] = info
        stem = f"{item['name'].replace('-', '_')}-{item['version']}.dist-info"
        if {name.split("/")[0] for name in entries if ".dist-info/" in name} != {stem}:
            _refuse()
        messages = []
        for name in (stem + "/METADATA", stem + "/WHEEL"):
            if entries[name].file_size > MAX_METADATA:
                _refuse()
            messages.append(BytesParser().parsebytes(archive.read(entries[name])))
    metadata, wheel = messages
    expected = parse_wheel_filename(item["filename"])[3]
    declared = set().union(*(parse_tag(value) for value in wheel.get_all("Tag", [])))
    pure = "true" if all(tag.platform == "any" for tag in expected) else "false"
    if (
        canonicalize_name(_one(metadata, "Name")) != item["name"]
        or _one(metadata, "Version") != item["version"]
        or TARGET["marker_python_full_version"]
        not in SpecifierSet(_one(metadata, "Requires-Python"))
        or _one(wheel, "Wheel-Version") != "1.0"
        or _one(wheel, "Root-Is-Purelib") != pure
        or declared != expected
    ):
        _refuse()
    extras = metadata.get_all("Provides-Extra", [])
    if any(re.fullmatch(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*", extra) is None for extra in extras):
        _refuse()
    extras = {canonicalize_name(extra) for extra in extras}
    requirements = [Requirement(value) for value in metadata.get_all("Requires-Dist", [])]
    if any(requirement.url is not None for requirement in requirements):
        _refuse()
    return {"version": item["version"], "extras": extras, "requirements": requirements}


def _closure(profile, distributions):
    patch = TARGET["marker_python_full_version"]
    environment = {
        "implementation_name": "cpython",
        "implementation_version": patch,
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "platform_python_implementation": "CPython",
        "python_full_version": patch,
        "python_version": "3.12",
        "sys_platform": "linux",
    }
    reached, pending = set(), [Requirement(text) for text in profile["roots"]]
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        extras = frozenset(canonicalize_name(extra) for extra in requirement.extras)
        distribution = distributions[name]
        if (
            distribution["version"] not in requirement.specifier
            or not extras <= distribution["extras"]
        ):
            _refuse()
        if (name, extras) in reached:
            continue
        reached.add((name, extras))
        for dependency in distribution["requirements"]:
            if dependency.marker is None or any(
                dependency.marker.evaluate({**environment, "extra": extra})
                for extra in {"", *extras}
            ):
                pending.append(dependency)
    if {name for name, _ in reached} != set(distributions):
        _refuse()


def verify_inputs(source: Path, wheels: Path) -> dict:
    """Verify exact offline wheel bytes/metadata and complete explicit Linux extras closure.

    No wheel is extracted, installed or imported. The result approves neither the
    production interpreter nor a native release, provisioned host or model provider.
    """
    try:
        source, wheels = _root(source), _root(wheels)
        profile = _inventory(source)
        if {path.name for path in wheels.iterdir()} != {
            item["filename"] for item in profile["wheels"]
        }:
            _refuse()
        distributions = {
            item["name"]: _metadata(_read(wheels, item["filename"], MAX_WHEEL), item)
            for item in profile["wheels"]
        }
        _closure(profile, distributions)
        return {
            "version": 1,
            "runtime_wheels": len(distributions),
            "target": dict(TARGET),
            "production_interpreter_approved": False,
            "requirements_sha256": hashlib.sha256(
                _read(source, "deploy/requirements-linux.lock", 65536)
            ).hexdigest(),
        }
    except Exception:
        raise ValueError("Linux runtime inputs refused") from None
