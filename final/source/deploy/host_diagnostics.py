"""Private bounded process lifecycle records, never application output."""

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

from deploy.host_files import _parent_metadata

_NAMES = ("lifecycle.jsonl", "lifecycle.jsonl.1", "lifecycle.jsonl.2")
_RETENTION = 7 * 24 * 60 * 60


def payload(service, event, result=None, *, now):
    if service not in {"agent", "store", "proxy"} or event not in {"starting", "stopped"}:
        raise ValueError("Fixed lifecycle event required")
    if type(now) is not int or now < 0:
        raise ValueError("Integer lifecycle time required")
    return {
        "time": now,
        "service": service,
        "event": event,
        "outcome": None if event == "starting" else "success" if result == "success" else "failed",
    }


def _directory(path):
    if os.name != "posix" or not path.is_absolute():
        raise ValueError("Private POSIX log directory required")
    uid = os.geteuid()
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC
    descriptor = os.open("/", flags)
    try:
        _parent_metadata(os.fstat(descriptor), uid)
        for part in path.parts[1:]:
            if part in {".", ".."}:
                raise ValueError()
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            _parent_metadata(os.fstat(descriptor), uid)
        info = os.fstat(descriptor)
        if info.st_uid != uid or info.st_mode & 0o077 or info.st_mode & 0o700 != 0o700:
            raise ValueError("Private log directory required")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _file(directory, name, maximum_bytes, *, create=False):
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    descriptor = os.open(name, flags, 0o600, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
            or info.st_size > maximum_bytes
        ):
            raise ValueError("Private bounded log file required")
        return descriptor, info
    except BaseException:
        os.close(descriptor)
        raise


def write_event(directory, service, event, *, result=None, now=None, maximum_bytes=65536):
    if type(maximum_bytes) is not int or not 256 <= maximum_bytes <= 65536:
        raise ValueError("Bounded log size required")
    now = int(time.time()) if now is None else now
    encoded = (
        json.dumps(payload(service, event, result, now=now), separators=(",", ":")) + "\n"
    ).encode("ascii")
    append_line(Path(directory), _NAMES, encoded, maximum_bytes=maximum_bytes, now=now)


def append_line(directory, names, encoded, *, maximum_bytes, now, sync=True):
    """Append one line to a private, bounded file that rotates through ``names``.

    Shared by the lifecycle records and the Agent's event records. The directory and
    every managed file are validated through descriptors before anything changes:
    symlinks, foreign owners, loose modes, extra hard links and oversize files are
    refused, and a directory lock serialises writers across processes.
    """
    import fcntl

    if len(encoded) > maximum_bytes:
        raise ValueError("Record larger than the log file limit")
    descriptor = _directory(Path(directory))
    try:
        deadline = time.monotonic() + 1
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Log lock unavailable") from None
                time.sleep(0.01)
        # Validate every managed name before changing any. Never traverse or scan others.
        existing = {}
        for name in names:
            try:
                file, info = _file(descriptor, name, maximum_bytes)
            except FileNotFoundError:
                continue
            os.close(file)
            existing[name] = info
        for name, info in tuple(existing.items()):
            if now - info.st_mtime > _RETENTION:
                os.unlink(name, dir_fd=descriptor)
                del existing[name]
        current = existing.get(names[0])
        if current is not None and current.st_size + len(encoded) > maximum_bytes:
            if names[2] in existing:
                os.unlink(names[2], dir_fd=descriptor)
            if names[1] in existing:
                os.rename(names[1], names[2], src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.rename(names[0], names[1], src_dir_fd=descriptor, dst_dir_fd=descriptor)
            existing.pop(names[0])
        file, _ = _file(descriptor, names[0], maximum_bytes, create=names[0] not in existing)
        try:
            if os.write(file, encoded) != len(encoded):
                raise OSError("Incomplete log write")
            if sync:
                os.fsync(file)
        finally:
            os.close(file)
        if sync:
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def record(service, event):
    # Validate before deriving the fixed path; raw SERVICE_RESULT is never serialized.
    payload(service, event, now=0)
    write_event(
        Path("/var/log/shopping-copilot") / service,
        service,
        event,
        result=os.environ.get("SERVICE_RESULT"),
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


def main(argv=None):
    try:
        parser = _Parser(description="Record a fixed process lifecycle event", allow_abbrev=False)
        parser.add_argument("--service", choices=("agent", "store", "proxy"), required=True)
        parser.add_argument("--event", choices=("starting", "stopped"), required=True)
        args = parser.parse_args(argv)
        record(args.service, args.event)
        return 0
    except (Exception, SystemExit):
        print("Host diagnostics refused", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
