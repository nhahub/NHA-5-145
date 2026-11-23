"""Offline package validation with synthetic wheels; real artifact proof is separate."""

import base64
import csv
import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from deploy.lambda_package import SOURCES, build, verify

ROOT = Path(__file__).resolve().parents[2]


def test_package_supports_private_guard_role(inputs, tmp_path):
    source, wheels, _ = inputs
    output = tmp_path / "guard.zip"
    manifest = build(source, wheels, output, role="guard")
    assert manifest["role"] == "guard"
    with zipfile.ZipFile(output) as archive:
        assert "deploy.guard_runtime" in archive.read("handler.py").decode()


def wheel(path, name, version, *, extra=None, metadata="", wheel_text=None, bad_record=False):
    stem = f"{name.replace('-', '_')}-{version}.dist-info"
    files = {
        f"{name.replace('-', '_')}/__init__.py": b"# synthetic dependency\n",
        f"{stem}/METADATA": (
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            f"Requires-Python: >=3.9\n{metadata}\n"
        ).encode(),
        f"{stem}/WHEEL": (
            wheel_text
            or (
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n"
                + ("Tag: py2-none-any\n" if "py2.py3" in path.name else "")
                + "Tag: py3-none-any\n"
            )
        ).encode(),
        **(extra or {}),
    }
    record, data = f"{stem}/RECORD", io.StringIO(newline="")
    writer = csv.writer(data, lineterminator="\n")
    for key, value in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).decode().rstrip("=")
        writer.writerow((key, "sha256=" + ("invalid" if bad_record else digest), str(len(value))))
    writer.writerow((record, "", ""))
    files[record] = data.getvalue().encode()
    with zipfile.ZipFile(path, "w") as archive:
        for key, value in files.items():
            archive.writestr(key, value)


def relock(source, wheels, lock):
    for item in lock["wheels"]:
        item["sha256"] = hashlib.sha256((wheels / item["filename"]).read_bytes()).hexdigest()
    (source / "deploy/lambda-wheels.json").write_text(json.dumps(lock), encoding="utf-8")
    (source / "deploy/lambda-requirements.lock").write_bytes(
        "".join(
            f"{x['name']}=={x['version']} --hash=sha256:{x['sha256']}\n" for x in lock["wheels"]
        ).encode()
    )


@pytest.fixture
def inputs(tmp_path):
    source, wheels = tmp_path / "source", tmp_path / "wheels"
    source.mkdir()
    wheels.mkdir()
    (source / "deploy").mkdir()
    for name in SOURCES:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    lock = json.loads((ROOT / "deploy/lambda-wheels.json").read_text())
    for item in lock["wheels"]:
        metadata = ""
        if item["name"] == "boto3":
            metadata = "".join(
                f"Requires-Dist: {x['name']}=={x['version']}\n"
                for x in lock["wheels"]
                if x["name"] != "boto3"
            )
        wheel(wheels / item["filename"], item["name"], item["version"], metadata=metadata)
    relock(source, wheels, lock)
    return source, wheels, lock


@pytest.mark.parametrize("role", ["startup", "controller"])
def test_deterministic_fixed_role_archive_and_external_digest(inputs, tmp_path, role):
    source, wheels, _ = inputs
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    manifest = build(source, wheels, first, role=role)
    build(source, wheels, second, role=role)
    assert first.read_bytes() == second.read_bytes()
    digest = hashlib.sha256(first.read_bytes()).hexdigest()
    assert verify(first, expected_sha256=digest) == manifest
    with zipfile.ZipFile(first) as archive:
        assert archive.read("handler.py").decode().endswith(f'handler = make_entry("{role}")\n')
        assert archive.read("agent/lifecycle/waiting.html")
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist())
        assert all(
            i.create_system == 3 and i.compress_type == zipfile.ZIP_STORED
            for i in archive.infolist()
        )
        assert all(
            stat.S_IMODE(i.external_attr >> 16) == (0o755 if i.is_dir() else 0o644)
            for i in archive.infolist()
        )
        assert not any(
            x in name
            for name in archive.namelist()
            for x in (".env", "__pycache__", ".pyc", "tests/", "agent/app.py")
        )
    with pytest.raises(ValueError):
        build(source, wheels, first, role=role)
    with pytest.raises(ValueError):
        verify(first, expected_sha256="0" * 64)


@pytest.mark.parametrize("role", [None, True, "other"])
def test_invalid_role_creates_nothing(inputs, tmp_path, role):
    output = tmp_path / "out.zip"
    with pytest.raises(ValueError):
        build(*inputs[:2], output, role=role)
    assert not output.exists()


@pytest.mark.parametrize(
    "attack", ["extra-wheel", "missing-wheel", "hash", "requirements", "extra-lock", "source-link"]
)
def test_inventory_and_hash_refusal(inputs, tmp_path, attack):
    source, wheels, lock = inputs
    item = lock["wheels"][0]
    target = wheels / item["filename"]
    if attack == "extra-wheel":
        (wheels / "unexpected.whl").write_bytes(b"extra")
    elif attack == "missing-wheel":
        target.unlink()
    elif attack == "hash":
        target.write_bytes(target.read_bytes() + b"tampered")
    elif attack == "requirements":
        (source / "deploy/lambda-requirements.lock").write_text("unrelated==1\n")
    elif attack == "extra-lock":
        lock["extra"] = True
        relock(source, wheels, lock)
    else:
        original = source / SOURCES[0]
        original.unlink()
        original.symlink_to(ROOT / SOURCES[0])
    output = tmp_path / "bad.zip"
    with pytest.raises(ValueError):
        build(source, wheels, output, role="startup")
    assert not output.exists()


@pytest.mark.parametrize(
    "attack",
    [
        "traversal",
        "backslash",
        "absolute",
        "drive",
        "data",
        "native",
        "case",
        "record",
        "purelib",
        "tag",
        "python",
        "dependency",
        "unused",
    ],
)
def test_locked_malicious_wheel_refusal(inputs, tmp_path, attack):
    source, wheels, lock = inputs
    item = next(x for x in lock["wheels"] if x["name"] == "httpx")
    extra, metadata, wheel_text = {}, "", None
    names = {
        "traversal": "../escape.py",
        "backslash": "bad\\escape.py",
        "absolute": "/escape.py",
        "drive": "C:/escape.py",
        "data": "httpx-0.28.1.data/purelib/extra.py",
        "native": "httpx/native.so",
        "case": "HTTPX/__init__.py",
    }
    if attack in names:
        extra[names[attack]] = b"bad"
    elif attack in {"purelib", "tag"}:
        pure = "false" if attack == "purelib" else "true"
        tag = "cp312-cp312-win_amd64" if attack == "tag" else "py3-none-any"
        wheel_text = f"Wheel-Version: 1.0\nRoot-Is-Purelib: {pure}\nTag: {tag}\n"
    elif attack == "python":
        metadata = "Requires-Python: >=3.13\n"
    elif attack == "dependency":
        metadata = "Requires-Dist: missing-package>=1\n"
    elif attack == "unused":
        # Remove all root dependencies, leaving twelve unaccounted-for extras.
        root = next(x for x in lock["wheels"] if x["name"] == "boto3")
        wheel(wheels / root["filename"], root["name"], root["version"])
    wheel(
        wheels / item["filename"],
        item["name"],
        item["version"],
        extra=extra,
        metadata=metadata,
        wheel_text=wheel_text,
        bad_record=attack == "record",
    )
    relock(source, wheels, lock)
    output = tmp_path / "bad.zip"
    with pytest.raises(ValueError):
        build(source, wheels, output, role="controller")
    assert not output.exists()


def test_manifest_and_archive_mutation_refused(inputs, tmp_path):
    output = tmp_path / "good.zip"
    build(*inputs[:2], output, role="startup")
    with zipfile.ZipFile(output) as archive:
        content = {i.filename: archive.read(i) for i in archive.infolist() if not i.is_dir()}
    content["handler.py"] += b"# altered\n"
    changed = tmp_path / "changed.zip"
    with zipfile.ZipFile(changed, "w") as archive:
        for key, data in content.items():
            archive.writestr(key, data)
    with pytest.raises(ValueError):
        verify(changed, expected_sha256=hashlib.sha256(changed.read_bytes()).hexdigest())


def test_known_nonruntime_jmespath_script_is_verified_then_explicitly_omitted(inputs, tmp_path):
    source, wheels, lock = inputs
    item = next(x for x in lock["wheels"] if x["name"] == "jmespath")
    script = f"jmespath-{item['version']}.data/scripts/jp.py"
    wheel(wheels / item["filename"], item["name"], item["version"], extra={script: b"#!python\n"})
    relock(source, wheels, lock)
    output = tmp_path / "good.zip"
    manifest = build(source, wheels, output, role="startup")
    assert manifest["omitted"] == [script]
    with zipfile.ZipFile(output) as archive:
        assert script not in archive.namelist()
        assert archive.read("jmespath/__init__.py")


@pytest.mark.parametrize("attack", ["duplicate", "symlink", "unrecorded", "oversize"])
def test_wheel_member_metadata_and_bounds_refused(inputs, tmp_path, monkeypatch, attack):
    from deploy import lambda_package

    source, wheels, lock = inputs
    item = next(x for x in lock["wheels"] if x["name"] == "httpx")
    path = wheels / item["filename"]
    with zipfile.ZipFile(path) as archive:
        entries = [(i, archive.read(i)) for i in archive.infolist()]
    if attack == "symlink":
        entries[0][0].external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        for info, data in entries:
            archive.writestr(info, data)
        if attack == "duplicate":
            with pytest.warns(UserWarning):
                archive.writestr(entries[0][0], entries[0][1])
        elif attack == "unrecorded":
            archive.writestr("httpx/unrecorded.py", b"extra")
    if attack == "oversize":
        monkeypatch.setattr(lambda_package, "MAX_EXTRACTED", 8)
    relock(source, wheels, lock)
    with pytest.raises(ValueError):
        build(source, wheels, tmp_path / "bad.zip", role="startup")


@pytest.mark.parametrize("field,value", [("wheels", []), ("omitted", ["unknown.py"])])
def test_verify_refuses_invalid_provenance_with_valid_modes_and_new_digest(
    inputs, tmp_path, field, value
):
    original, changed = tmp_path / "original.zip", tmp_path / "changed.zip"
    build(*inputs[:2], original, role="startup")
    with zipfile.ZipFile(original) as archive:
        entries = [(i, archive.read(i)) for i in archive.infolist()]
    with zipfile.ZipFile(changed, "w") as archive:
        for info, data in entries:
            if info.filename == "lambda-manifest.json":
                manifest = json.loads(data)
                manifest[field] = value
                data = json.dumps(manifest).encode()
            archive.writestr(info, data)
    with pytest.raises(ValueError):
        verify(changed, expected_sha256=hashlib.sha256(changed.read_bytes()).hexdigest())
