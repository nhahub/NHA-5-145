"""Production-input preparation checks use synthetic wheels, never installs or SDKs."""

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[2]
REFUSAL = "Linux runtime inputs refused"
TARGET = {
    "implementation": "cpython",
    "python_version": "3.12",
    "sys_platform": "linux",
    "platform_machine": "x86_64",
    "libc": "glibc",
    "libc_version": "2.34",
    "marker_python_full_version": "3.12.14",
}
ROOTS = [
    "boto3==1.43.115",
    "fastapi==0.116.1",
    "httpx==0.28.1",
    "python-dotenv==1.2.3",
    "uvicorn[standard]==0.35.0",
]


def candidate():
    tested = json.loads((ROOT / "eval/linux-host-runtime.json").read_bytes())
    return {
        "version": 1,
        "purpose": "linux-host-runtime-preparation",
        "production_interpreter_approved": False,
        "target": copy.deepcopy(TARGET),
        "roots": list(ROOTS),
        "wheels": [
            {key: item[key] for key in ("name", "version", "filename", "sha256", "bytes")}
            for item in tested["wheels"]
            if item["purpose"] == "runtime"
        ],
    }


def save(source, profile):
    (source / "deploy/linux-runtime.json").write_text(json.dumps(profile), encoding="utf-8")
    (source / "deploy/requirements-linux.lock").write_bytes(
        "".join(
            f"{item['name']}{'[standard]' if item['name'] == 'uvicorn' else ''}"
            f"=={item['version']} --hash=sha256:{item['sha256']}\n"
            for item in profile["wheels"]
        ).encode("ascii")
    )


def synthetic_wheel(path, item, *, requirements=(), provides=(), overrides=None, extra=None):
    stem = f"{item['name'].replace('-', '_')}-{item['version']}.dist-info"
    headers = {
        "Name": item["name"],
        "Version": item["version"],
        "Requires-Python": ">=3.9",
        **(overrides or {}),
    }
    metadata = "Metadata-Version: 2.4\n" + "".join(
        f"{key}: {value}\n" for key, value in headers.items() if value is not None
    )
    metadata += "".join(f"Provides-Extra: {value}\n" for value in provides)
    metadata += "".join(f"Requires-Dist: {value}\n" for value in requirements)
    tags = parse_wheel_filename(item["filename"])[3]
    wheel = "Wheel-Version: 1.0\nRoot-Is-Purelib: "
    wheel += "true\n" if all(tag.platform == "any" for tag in tags) else "false\n"
    wheel += "".join(f"Tag: {tag}\n" for tag in sorted(tags, key=str))
    files = {
        f"{stem}/METADATA": (metadata + "\n").encode(),
        f"{stem}/WHEEL": wheel.encode(),
        f"{stem}/RECORD": b"",
        f"{item['name'].replace('-', '_')}/__init__.py": b"# synthetic, never imported\n",
        **(extra or {}),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name)
            # ZipInfo normally rewrites Windows separators; preserve hostile test bytes.
            info.filename = name
            archive.writestr(info, content)


def relock(source, wheels, profile):
    for item in profile["wheels"]:
        data = (wheels / item["filename"]).read_bytes()
        item["sha256"] = hashlib.sha256(data).hexdigest()
        item["bytes"] = len(data)
    save(source, profile)


def replace_wheel(inputs, name, **options):
    source, wheels, profile = inputs
    item = next(value for value in profile["wheels"] if value["name"] == name)
    synthetic_wheel(wheels / item["filename"], item, **options)
    relock(source, wheels, profile)


@pytest.fixture
def inputs(tmp_path):
    source, wheels = tmp_path / "source", tmp_path / "wheels"
    (source / "deploy").mkdir(parents=True)
    wheels.mkdir()
    (source / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes())
    profile = candidate()
    direct = {"boto3", "fastapi", "httpx", "python-dotenv", "uvicorn"}
    for item in profile["wheels"]:
        requirements, provides = [], []
        if item["name"] == "boto3":
            requirements = [
                f"{other['name']}=={other['version']}"
                for other in profile["wheels"]
                if other["name"] not in direct | {"uvloop"}
            ]
        elif item["name"] == "uvicorn":
            provides = ["standard"]
            requirements = [
                'uvloop==0.22.1; extra == "standard" and sys_platform == "linux"',
                'colorama==0.4.6; extra == "standard" and sys_platform == "win32"',
                'absent==1; python_full_version > "3.12.15"',
            ]
        synthetic_wheel(
            wheels / item["filename"], item, requirements=requirements, provides=provides
        )
    relock(source, wheels, profile)
    return source, wheels, profile


def test_repository_inventory_is_separate_complete_runtime_input():
    from deploy.linux_runtime import inventory

    before = (ROOT / "requirements.lock").read_bytes()
    profile = inventory(ROOT)
    assert profile == candidate()
    assert len(profile["wheels"]) == 28
    assert profile["production_interpreter_approved"] is False
    assert (ROOT / "requirements.lock").read_bytes() == before
    assert (
        b"uvicorn[standard]==0.35.0 --hash=sha256:"
        in (ROOT / "deploy/requirements-linux.lock").read_bytes()
    )


def test_verified_inputs_use_linux_markers_and_return_no_paths_or_secrets(inputs):
    from deploy.linux_runtime import verify_inputs

    source, wheels, _ = inputs
    before = {path.name: path.read_bytes() for path in wheels.iterdir()}
    report = verify_inputs(source, wheels)
    assert report["runtime_wheels"] == 28
    assert report["target"] == TARGET
    assert report["production_interpreter_approved"] is False
    assert str(source) not in json.dumps(report)
    assert {path.name: path.read_bytes() for path in wheels.iterdir()} == before


@pytest.mark.parametrize(
    "attack",
    [
        "unknown-field",
        "production-approved",
        "target-os",
        "target-arch",
        "target-libc",
        "target-patch",
        "missing-wheel",
        "duplicate-name",
        "diagnostic-wheel",
        "bad-size",
        "bad-digest",
        "filename-traversal",
        "filename-identity",
        "requirements",
        "roots",
        "project-pins",
        "duplicate-json",
    ],
)
def test_inventory_refuses_unbound_or_incomplete_inputs(inputs, attack):
    from deploy.linux_runtime import inventory

    source, _, profile = inputs
    if attack == "unknown-field":
        profile["unexpected"] = "private-path-must-not-leak"
    elif attack == "production-approved":
        profile["production_interpreter_approved"] = True
    elif attack.startswith("target-"):
        key, value = {
            "target-os": ("sys_platform", "win32"),
            "target-arch": ("platform_machine", "aarch64"),
            "target-libc": ("libc_version", "2.35"),
            "target-patch": ("marker_python_full_version", "3.12.16"),
        }[attack]
        profile["target"][key] = value
    elif attack == "missing-wheel":
        profile["wheels"].pop()
    elif attack == "duplicate-name":
        profile["wheels"][-1] = dict(profile["wheels"][0])
    elif attack == "diagnostic-wheel":
        profile["wheels"][0].update(name="packaging", filename="packaging-0.8.0-py3-none-any.whl")
    elif attack == "bad-size":
        profile["wheels"][0]["bytes"] = True
    elif attack == "bad-digest":
        profile["wheels"][0]["sha256"] = "not-a-digest-private-value"
    elif attack == "filename-traversal":
        profile["wheels"][0]["filename"] = "../" + profile["wheels"][0]["filename"]
    elif attack == "filename-identity":
        profile["wheels"][0]["filename"] = "different-0.8.0-py3-none-any.whl"
    elif attack == "roots":
        profile["roots"][-1] = "uvicorn==0.35.0"
    save(source, profile)
    if attack == "requirements":
        (source / "deploy/requirements-linux.lock").write_text("-e .\n", encoding="utf-8")
    elif attack == "project-pins":
        project = source / "pyproject.toml"
        project.write_text(project.read_text().replace("boto3==1.43.115", "boto3==1.43.114"))
    elif attack == "duplicate-json":
        target = source / "deploy/linux-runtime.json"
        target.write_text(target.read_text().replace('"version": 1', '"version": 1, "version": 1'))
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        inventory(source)


@pytest.mark.parametrize("attack", ["missing", "extra", "length", "digest", "invalid-zip"])
def test_wheelhouse_bytes_are_exact_and_missing_or_extra_inputs_refuse(inputs, attack):
    from deploy.linux_runtime import verify_inputs

    source, wheels, profile = inputs
    item = profile["wheels"][0]
    path = wheels / item["filename"]
    if attack == "missing":
        path.unlink()
    elif attack == "extra":
        (wheels / "packaging-26.3-py3-none-any.whl").write_bytes(b"diagnostic only")
    elif attack == "length":
        path.write_bytes(path.read_bytes() + b"changed")
    elif attack == "digest":
        path.write_bytes(b"x" * path.stat().st_size)
    else:
        path.write_bytes(b"not a wheel")
        relock(source, wheels, profile)
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(source, wheels)


@pytest.mark.parametrize(
    "overrides",
    [
        {"Name": "different-private-value"},
        {"Name": "fastapi\nName: fastapi"},
        {"Version": "999.0"},
        {"Requires-Python": ">=3.13"},
        {"Requires-Python": "<3.12.14"},
        {"Requires-Python": None},
    ],
)
def test_wheel_metadata_identity_and_python_contract_must_match(inputs, overrides):
    from deploy.linux_runtime import verify_inputs

    replace_wheel(inputs, "fastapi", overrides=overrides)
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(*inputs[:2])


@pytest.mark.parametrize(
    "requirement,compatible",
    [(">=3.12.15", False), (">=3.12.14,<3.12.15", True)],
)
def test_selected_vendor_patch_controls_wheel_python_compatibility(inputs, requirement, compatible):
    from deploy.linux_runtime import verify_inputs

    replace_wheel(inputs, "fastapi", overrides={"Requires-Python": requirement})
    if compatible:
        assert verify_inputs(*inputs[:2])["runtime_wheels"] == 28
    else:
        with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
            verify_inputs(*inputs[:2])


@pytest.mark.parametrize(
    "tag",
    [
        "cp313-cp313-manylinux_2_17_x86_64",
        "cp312-cp312-win_amd64",
        "cp312-cp312-manylinux_2_35_x86_64",
        "cp312-cp312-manylinux_2_17_aarch64",
        "cp312-cp312-musllinux_1_2_x86_64",
    ],
)
def test_filename_tags_are_checked_against_explicit_target_not_running_host(inputs, tag):
    from deploy.linux_runtime import verify_inputs

    source, wheels, profile = inputs
    item = next(value for value in profile["wheels"] if value["name"] == "uvloop")
    (wheels / item["filename"]).unlink()
    item["filename"] = f"uvloop-0.22.1-{tag}.whl"
    synthetic_wheel(wheels / item["filename"], item)
    relock(source, wheels, profile)
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(source, wheels)


def test_native_wheel_members_are_permitted_without_loading_them(inputs):
    from deploy.linux_runtime import verify_inputs

    replace_wheel(
        inputs, "uvloop", extra={"uvloop/loop.cpython-312-x86_64-linux-gnu.so": b"native"}
    )
    assert verify_inputs(*inputs[:2])["runtime_wheels"] == 28


@pytest.mark.parametrize(
    "requirements,provides",
    [
        (["absent==1; sys_platform == 'linux'"], ["standard"]),
        (["uvloop==0.22.0; extra == 'standard'"], ["standard"]),
        (["uvloop[missing]==0.22.1; extra == 'standard'"], ["standard"]),
        (["uvloop==0.22.1; extra == 'standard'"], []),
        (["uvloop==0.22.1; extra == 'standard' and sys_platform == 'win32'"], ["standard"]),
        (["uvloop @ https://example.invalid/private.whl"], ["standard"]),
        (["this is not a requirement"], ["standard"]),
    ],
)
def test_active_dependency_closure_versions_and_requested_extras_are_required(
    inputs, requirements, provides
):
    from deploy.linux_runtime import verify_inputs

    replace_wheel(inputs, "uvicorn", requirements=requirements, provides=provides)
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(*inputs[:2])


def test_wheel_metadata_tags_cannot_disagree_with_filename(inputs):
    from deploy.linux_runtime import verify_inputs

    source, wheels, profile = inputs
    item = next(value for value in profile["wheels"] if value["name"] == "uvloop")
    path = wheels / item["filename"]
    with zipfile.ZipFile(path) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    name = "uvloop-0.22.1.dist-info/WHEEL"
    files[name] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: cp312-cp312-win_amd64\n"
    with zipfile.ZipFile(path, "w") as archive:
        for member, content in files.items():
            archive.writestr(member, content)
    relock(source, wheels, profile)
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(source, wheels)


@pytest.mark.parametrize("member", ["../outside", "/absolute", "bad\\member"])
def test_unsafe_wheel_members_are_refused_without_extraction(inputs, member):
    from deploy.linux_runtime import verify_inputs

    replace_wheel(inputs, "fastapi", extra={member: b"never extracted"})
    with pytest.raises(ValueError, match=f"^{REFUSAL}$"):
        verify_inputs(*inputs[:2])
