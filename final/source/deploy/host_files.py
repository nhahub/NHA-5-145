"""Standard-library protected host input and production-artifact checks."""

import hashlib
import os
import re
import stat
from pathlib import Path

from deploy.artifact import verify

ORIGINS = {
    "panel": "https://app.scpilot.tech",
    "store": "https://store.scpilot.tech",
    "agent": "https://app.scpilot.tech",
}


def _file_metadata(info, uid):
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid not in {0, uid}
        or info.st_nlink != 1
        or info.st_mode & 0o077
        or not info.st_mode & 0o400
    ):
        raise ValueError("Private file required")


def _parent_metadata(info, uid):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, uid} or info.st_mode & 0o022:
        raise ValueError("Protected parent required")


def _read_private(path, limit):
    if os.name != "posix" or not path.is_absolute():
        raise ValueError("POSIX private file required")
    uid = os.geteuid()
    for parent in path.parents:
        _parent_metadata(parent.lstat(), uid)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        _file_metadata(before, uid)
        if before.st_size > limit:
            raise ValueError("Bounded private file required")
        data = bytearray()
        while len(data) <= limit:
            chunk = os.read(descriptor, limit + 1 - len(data))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(descriptor)
        fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            len(data) > limit
            or len(data) != before.st_size
            or any(getattr(before, name) != getattr(after, name) for name in fields)
        ):
            raise ValueError("Private file changed")
        return bytes(data)
    finally:
        os.close(descriptor)


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("Duplicate field")
        result[name] = value
    return result


def production_release(release, fingerprint):
    if (
        not isinstance(release, Path)
        or not release.is_absolute()
        or type(fingerprint) is not str
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ValueError("Bound production release required")
    release = release.resolve(strict=True)
    manifest = verify(release)
    if (
        hashlib.sha256((release / "release.json").read_bytes()).hexdigest() != fingerprint
        or manifest.get("local_rehearsal") is not False
        or manifest.get("public_origins") != ORIGINS
    ):
        raise ValueError("Bound production release required")
    return release
