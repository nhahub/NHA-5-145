"""Offline, narrow pure-wheel Lambda assembly. Never installs or contacts AWS."""

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import parse_tag
from packaging.utils import canonicalize_name, parse_wheel_filename

SOURCES = (
    "agent/__init__.py",
    "agent/admission/__init__.py",
    "agent/admission/store.py",
    "agent/admission/dynamodb.py",
    "agent/lifecycle/__init__.py",
    "agent/lifecycle/store.py",
    "agent/lifecycle/dynamodb.py",
    "agent/lifecycle/executor.py",
    "agent/lifecycle/controller.py",
    "agent/lifecycle/readiness.py",
    "agent/lifecycle/startup.py",
    "agent/lifecycle/lambda_runtime.py",
    "agent/lifecycle/lambda_entry.py",
    "agent/lifecycle/operating.py",
    "agent/lifecycle/operating_guard.py",
    "agent/lifecycle/operating_dns.py",
    "agent/lifecycle/waiting.html",
    "deploy/__init__.py",
    "deploy/cloud_access.py",
    "deploy/operating.py",
    "deploy/guard_runtime.py",
)
DISTRIBUTIONS = {
    "anyio",
    "boto3",
    "botocore",
    "certifi",
    "h11",
    "httpcore",
    "httpx",
    "idna",
    "jmespath",
    "python-dateutil",
    "s3transfer",
    "six",
    "typing-extensions",
    "urllib3",
}
MANIFEST = "lambda-manifest.json"
MAX_ZIP, MAX_EXTRACTED, MAX_MEMBERS = 50 * 1024**2, 250 * 1024**2, 10000
STAMP = (1980, 1, 1, 0, 0, 0)


def _refuse():
    raise ValueError("Restricted Lambda package contract required")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _refuse()
        value[key] = item
    return value


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"


def _path(name, *, allow_data=False):
    if type(name) is not str or not name or len(name) > 512:
        _refuse()
    for part in name.split("/"):
        if (
            re.fullmatch(r"[A-Za-z0-9_.@+\-]+", part) is None
            or part in {".", "..", "__pycache__"}
            or part.endswith((".", " "))
            or part.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{x}" for x in range(10)),
                *(f"LPT{x}" for x in range(10)),
            }
            or (part.endswith(".data") and not allow_data)
        ):
            _refuse()
    if re.search(r"\.(so(?:\.[0-9.]+)?|pyd|dll|dylib|exe|a|lib|pyc|pyo)$", name, re.I):
        _refuse()
    return name


def _file(root, name, maximum):
    path = root
    for part in name.split("/"):
        path /= part
        if path.is_symlink() or path.is_junction():
            _refuse()
    if not path.is_file() or path.stat().st_size > maximum:
        _refuse()
    data = path.read_bytes()
    if len(data) > maximum:
        _refuse()
    return data


def _locked_wheels(lock):
    if (
        type(lock) is not dict
        or set(lock) != {"version", "python", "wheels"}
        or type(lock["version"]) is not int
        or lock["version"] != 1
        or lock["python"] != "3.12"
    ):
        _refuse()
    wheels = lock["wheels"]
    if type(wheels) is not list or len(wheels) != 14:
        _refuse()
    seen, filenames = set(), set()
    for item in wheels:
        if (
            type(item) is not dict
            or set(item) != {"name", "version", "filename", "sha256"}
            or any(type(v) is not str for v in item.values())
        ):
            _refuse()
        name, version, build, tags = parse_wheel_filename(item["filename"])
        normalized = canonicalize_name(item["name"])
        if (
            _path(item["filename"]) != item["filename"]
            or "/" in item["filename"]
            or name != normalized
            or str(version) != item["version"]
            or build
            or not any(t.interpreter == "py3" for t in tags)
            or any(
                t.interpreter not in {"py2", "py3"} or t.abi != "none" or t.platform != "any"
                for t in tags
            )
            or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
            or normalized in seen
            or item["filename"].casefold() in filenames
        ):
            _refuse()
        seen.add(normalized)
        filenames.add(item["filename"].casefold())
    if seen != DISTRIBUTIONS:
        _refuse()
    return wheels


def _inventory(source):
    lock = json.loads(_file(source, "deploy/lambda-wheels.json", 65536), object_pairs_hook=_pairs)
    wheels = _locked_wheels(lock)
    required = "".join(
        f"{w['name']}=={w['version']} --hash=sha256:{w['sha256']}\n" for w in wheels
    ).encode("ascii")
    if _file(source, "deploy/lambda-requirements.lock", 65536) != required:
        _refuse()
    return wheels


def _members(archive, *, directories=False, allowed_data=()):
    entries, folded, total = {}, set(), 0
    if len(archive.infolist()) > MAX_MEMBERS:
        _refuse()
    for info in archive.infolist():
        name = info.filename
        if info.is_dir():
            if not directories:
                _refuse()
            _path(name[:-1])
        else:
            _path(name, allow_data=name in allowed_data)
        mode = info.external_attr >> 16
        if (
            name.casefold() in folded
            or stat.S_IFMT(mode) not in {0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG}
            or info.flag_bits & 1
            or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            or info.file_size < 0
        ):
            _refuse()
        folded.add(name.casefold())
        total += info.file_size
        if total > MAX_EXTRACTED:
            _refuse()
        entries[name] = info
    # A path cannot be both a file and a directory, including on Windows.
    files = {n.casefold() for n in entries if not n.endswith("/")}
    for name in entries:
        parts = name.rstrip("/").split("/")
        if any("/".join(parts[:i]).casefold() in files for i in range(1, len(parts))):
            _refuse()
    return entries


def _one(metadata, key):
    values = metadata.get_all(key, [])
    if len(values) != 1:
        _refuse()
    return values[0]


def _wheel(data, item):
    if _sha(data) != item["sha256"]:
        _refuse()
    script = f"jmespath-{item['version']}.data/scripts/jp.py"
    allowed = {script} if canonicalize_name(item["name"]) == "jmespath" else set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = _members(archive, allowed_data=allowed)
        files = {name: archive.read(info) for name, info in entries.items()}
    roots = {n.split("/")[0] for n in files if ".dist-info/" in n}
    if len(roots) != 1:
        _refuse()
    root = roots.pop()
    if root != f"{item['name'].replace('-', '_')}-{item['version']}.dist-info":
        _refuse()
    metadata = BytesParser().parsebytes(files[root + "/METADATA"])
    wheel = BytesParser().parsebytes(files[root + "/WHEEL"])
    expected_tags = parse_wheel_filename(item["filename"])[3]
    actual_tags = set().union(*(parse_tag(t) for t in wheel.get_all("Tag", [])))
    if (
        canonicalize_name(_one(metadata, "Name")) != canonicalize_name(item["name"])
        or _one(metadata, "Version") != item["version"]
        or "3.12.0" not in SpecifierSet(_one(metadata, "Requires-Python"))
        or _one(wheel, "Wheel-Version") != "1.0"
        or _one(wheel, "Root-Is-Purelib") != "true"
        or actual_tags != expected_tags
    ):
        _refuse()
    record = root + "/RECORD"
    recorded = set()
    for row in csv.reader(io.StringIO(files[record].decode("utf-8"), newline="")):
        if len(row) != 3 or row[0] not in files or row[0] in recorded:
            _refuse()
        name, digest, size = row
        recorded.add(name)
        if name == record:
            if digest or size:
                _refuse()
        else:
            expected = (
                base64.urlsafe_b64encode(hashlib.sha256(files[name]).digest()).decode().rstrip("=")
            )
            if digest != "sha256=" + expected or size != str(len(files[name])):
                _refuse()
    if recorded != set(files):
        _refuse()
    omitted = sorted(allowed & set(files))
    for name in omitted:
        del files[name]
    return files, [Requirement(value) for value in metadata.get_all("Requires-Dist", [])], omitted


def _closure(inventory, requirements):
    versions = {canonicalize_name(x["name"]): x["version"] for x in inventory}
    environment = {
        **default_environment(),
        "implementation_name": "cpython",
        "implementation_version": "3.12.0",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": "3.12.0",
        "python_version": "3.12",
        "sys_platform": "linux",
        "extra": "",
    }
    reached, pending = set(), ["boto3", "httpx"]
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        for requirement in requirements[name]:
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            target = canonicalize_name(requirement.name)
            if (
                requirement.extras
                or requirement.url
                or target not in versions
                or versions[target] not in requirement.specifier
            ):
                _refuse()
            pending.append(target)
    if reached != set(versions):
        _refuse()


def _entry(role):
    if role == "guard":
        return (
            b"from deploy.guard_runtime import make_guard_entry\n\nhandler = make_guard_entry()\n"
        )
    return (
        f'from agent.lifecycle.lambda_entry import make_entry\n\nhandler = make_entry("{role}")\n'
    ).encode("ascii")


def _directories(files):
    return {
        "/".join(name.split("/")[:i]) + "/"
        for name in files
        for i in range(1, len(name.split("/")))
    }


def build(source, wheels, output, *, role):
    """Validate everything before exclusively publishing one local ZIP."""
    try:
        if type(role) is not str or role not in {"startup", "controller", "guard"}:
            _refuse()
        source, wheels, output = (
            Path(source).resolve(strict=True),
            Path(wheels).resolve(strict=True),
            Path(output).absolute(),
        )
        if output.exists() or output.is_symlink() or not output.parent.is_dir():
            _refuse()
        inventory = _inventory(source)
        if {p.name for p in wheels.iterdir()} != {i["filename"] for i in inventory}:
            _refuse()
        files, requirements, omitted = {}, {}, []
        for item in inventory:
            payload, deps, excluded = _wheel(_file(wheels, item["filename"], MAX_ZIP), item)
            if {n.casefold() for n in payload} & {n.casefold() for n in files}:
                _refuse()
            files.update(payload)
            requirements[canonicalize_name(item["name"])] = deps
            omitted.extend(excluded)
        _closure(inventory, requirements)
        for name in SOURCES:
            if name.casefold() in {n.casefold() for n in files}:
                _refuse()
            files[name] = _file(source, name, 1024**2)
        if {"handler.py", MANIFEST} & set(files):
            _refuse()
        files["handler.py"] = _entry(role)
        manifest = {
            "version": 1,
            "python": "3.12",
            "role": role,
            "wheels": inventory,
            "omitted": sorted(omitted),
            "files": {n: _sha(data) for n, data in files.items()},
        }
        files[MANIFEST] = _json(manifest)
        if sum(map(len, files.values())) > MAX_EXTRACTED:
            _refuse()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(set(files) | _directories(files)):
                info = zipfile.ZipInfo(name, STAMP)
                info.create_system = 3
                info.external_attr = (
                    (stat.S_IFDIR | 0o755) if name.endswith("/") else (stat.S_IFREG | 0o644)
                ) << 16
                archive.writestr(info, b"" if name.endswith("/") else files[name])
        data = buffer.getvalue()
        if len(data) > MAX_ZIP:
            _refuse()
        # Verify assembled bytes, including cross-wheel directory collisions.
        _verify(data)
        with output.open("xb") as target:
            target.write(data)
        return manifest
    except Exception:
        raise ValueError("Restricted Lambda package contract required") from None


def _verify(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = _members(archive, directories=True)
        if MANIFEST not in members or members[MANIFEST].file_size > 2 * 1024**2:
            _refuse()
        manifest = json.loads(archive.read(MANIFEST), object_pairs_hook=_pairs)
        if (
            type(manifest) is not dict
            or set(manifest) != {"version", "python", "role", "wheels", "omitted", "files"}
            or type(manifest["version"]) is not int
            or manifest["version"] != 1
            or manifest["python"] != "3.12"
            or manifest["role"] not in {"startup", "controller", "guard"}
            or type(manifest["files"]) is not dict
        ):
            _refuse()
        files = manifest["files"]
        inventory = _locked_wheels({"version": 1, "python": "3.12", "wheels": manifest["wheels"]})
        jmespath = next(x for x in inventory if canonicalize_name(x["name"]) == "jmespath")
        omitted = [f"jmespath-{jmespath['version']}.data/scripts/jp.py"]
        if manifest["omitted"] not in ([], omitted):
            _refuse()
        if (
            not set(SOURCES).issubset(files)
            or "handler.py" not in files
            or MANIFEST in files
            or set(members) != set(files) | {MANIFEST} | _directories(files)
        ):
            _refuse()
        for name, digest in files.items():
            if type(digest) is not str or digest != _sha(archive.read(name)):
                _refuse()
        if archive.read("handler.py") != _entry(manifest["role"]):
            _refuse()
        for info in members.values():
            if (
                info.date_time != STAMP
                or info.create_system != 3
                or info.compress_type != zipfile.ZIP_STORED
                or info.external_attr >> 16
                != ((stat.S_IFDIR | 0o755) if info.is_dir() else (stat.S_IFREG | 0o644))
            ):
                _refuse()
        return manifest


def verify(path, *, expected_sha256):
    """Require independently retained digest; an editable manifest is not trust."""
    try:
        path = Path(path)
        if (
            type(expected_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or path.stat().st_size > MAX_ZIP
            or path.is_symlink()
        ):
            _refuse()
        data = path.read_bytes()
        if len(data) > MAX_ZIP or _sha(data) != expected_sha256:
            _refuse()
        return _verify(data)
    except Exception:
        raise ValueError("Restricted Lambda package contract required") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = commands.add_parser("build")
    package.add_argument("--source", required=True)
    package.add_argument("--wheels", required=True)
    package.add_argument("--output", required=True)
    package.add_argument("--role", required=True, choices=("startup", "controller", "guard"))
    check = commands.add_parser("verify")
    check.add_argument("--archive", required=True)
    check.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args.source, args.wheels, args.output, role=args.role)
    else:
        verify(args.archive, expected_sha256=args.sha256)


if __name__ == "__main__":
    main()
