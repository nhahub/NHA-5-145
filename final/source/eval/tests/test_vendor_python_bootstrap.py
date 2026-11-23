"""Public vendor input extraction cannot leave the disposable private prefix."""

import hashlib
import io
import tarfile

import pytest

from eval.vendor_python_bootstrap import unpack


def archive(tmp_path, entries):
    path = tmp_path / "python.tar"
    with tarfile.open(path, "w") as output:
        for name, value in entries:
            item = tarfile.TarInfo(name)
            item.size = len(value)
            output.addfile(item, io.BytesIO(value))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_verified_prefix_extracts_original_regular_bytes(tmp_path):
    source, digest = archive(tmp_path, [("usr/bin/python3.12", b"verified fixture")])
    target = tmp_path / "prefix"
    assert unpack(source, digest, target) == target / "usr/bin/python3.12"
    assert (target / "usr/bin/python3.12").read_bytes() == b"verified fixture"


@pytest.mark.parametrize("attack", ["digest", "escape", "absolute", "duplicate", "device"])
def test_prefix_refuses_bad_identity_or_archive_members(tmp_path, attack):
    entries = [("usr/bin/python3.12", b"fixture")]
    if attack == "escape":
        entries.append(("../outside", b"forbidden"))
    elif attack == "absolute":
        entries.append(("/outside", b"forbidden"))
    elif attack == "duplicate":
        entries.append(entries[0])
    source, digest = archive(tmp_path, entries)
    if attack == "digest":
        digest = "0" * 64
    elif attack == "device":
        with tarfile.open(source, "a") as output:
            item = tarfile.TarInfo("usr/device")
            item.type = tarfile.FIFOTYPE
            output.addfile(item)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        unpack(source, digest, tmp_path / "prefix")
    assert not (tmp_path / "outside").exists()


def test_existing_prefix_is_never_overwritten(tmp_path):
    source, digest = archive(tmp_path, [("usr/bin/python3.12", b"fixture")])
    target = tmp_path / "prefix"
    target.mkdir()
    (target / "preserved").write_bytes(b"existing")
    with pytest.raises(ValueError):
        unpack(source, digest, target)
    assert (target / "preserved").read_bytes() == b"existing"
