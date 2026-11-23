import hashlib
import json
from zipfile import ZipFile

import pytest

from deploy.artifact import files


def source(tmp_path):
    root = tmp_path / "release"
    root.mkdir()
    (root / "app.py").write_text("fixture only")
    (root / "release.json").write_text(
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
                "files": files(root),
            }
        )
    )
    return root


def test_portable_archive_keeps_provenance_and_regular_bytes(tmp_path):
    from eval.linux_host_fixture import prepare

    root = source(tmp_path)
    before = (root / "release.json").read_bytes()
    output = tmp_path / "fixture.zip"
    report = prepare(root, output)
    assert report["upstream_manifest_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    with ZipFile(output) as archive:
        data = json.loads(archive.read("fixture.json"))
        assert archive.read("release/app.py") == b"fixture only"
        assert data["files"] == {"app.py": hashlib.sha256(b"fixture only").hexdigest()}
    assert (root / "release.json").read_bytes() == before
    with pytest.raises(ValueError):
        prepare(root, output)


def test_internal_package_links_keep_target_topology(tmp_path):
    from eval.linux_host_fixture import prepare

    root = source(tmp_path)
    target = root / "packages/express"
    target.mkdir(parents=True)
    (target / "index.js").write_text("require('body-parser')")
    (root / "express").symlink_to(target, target_is_directory=True)
    manifest = json.loads((root / "release.json").read_text())
    manifest["files"] = files(root)
    (root / "release.json").write_text(json.dumps(manifest))
    output = tmp_path / "fixture.zip"
    prepare(root, output)
    with ZipFile(output) as archive:
        proof = json.loads(archive.read("fixture.json"))
        assert proof["links"] == {"express": "packages/express"}
        assert "express/index.js" not in proof["files"]
        assert archive.read("release/packages/express/index.js") == b"require('body-parser')"


@pytest.mark.parametrize("kind", ["changed", "external", "cycle", "size", "count"])
def test_invalid_source_or_bounds_never_create_output(tmp_path, kind):
    from eval.linux_host_fixture import prepare

    root = source(tmp_path)
    options = {}
    if kind == "changed":
        (root / "app.py").write_text("tampered")
    elif kind in {"external", "cycle"}:
        try:
            (root / "linked").symlink_to(
                root if kind == "cycle" else root.parent, target_is_directory=True
            )
        except OSError:
            pytest.skip("Symlink creation unavailable")
        manifest = json.loads((root / "release.json").read_text())
        manifest["files"] = files(root) if kind == "cycle" else {}
        (root / "release.json").write_text(json.dumps(manifest))
    else:
        options = {"maximum_bytes": 1} if kind == "size" else {"maximum_members": 0}
    output = tmp_path / "refused.zip"
    with pytest.raises(ValueError):
        prepare(root, output, **options)
    assert not output.exists()
