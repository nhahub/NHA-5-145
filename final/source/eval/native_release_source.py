"""Capture reviewed local Git objects for an offline native release checkout.

Consumers extract the allowlisted files and create an empty .git/refs directory
before invoking real Git. No owner references or configuration are exported.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile, ZipInfo

_MAX_BYTES = 64 * 1024**2
_MAX_MEMBERS = 20000
_OBJECT = re.compile(
    r"objects/(?:[a-f0-9]{2}/[a-f0-9]{38}|pack/pack-[a-f0-9]{40}\.(?:pack|idx|rev))"
)
_CONFIG = (
    b"[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
    b"\tfilemode = true\n\tautocrlf = false\n"
)


def _directory(path):
    path = Path(path).absolute()
    if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)):
        raise ValueError
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError
    return resolved


def _prepare(source, output, revision):
    if not isinstance(revision, str) or re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        raise ValueError
    source = _directory(source)
    output = Path(output).absolute()
    parent = _directory(output.parent)
    output = parent / output.name
    if (
        output.exists()
        or output.is_symlink()
        or output.is_junction()
        or output.is_relative_to(source)
        or source.is_relative_to(output)
    ):
        raise ValueError
    executable = shutil.which("git")
    if executable is None:
        raise ValueError
    with TemporaryDirectory(prefix="copilot-native-source-", dir=parent) as temporary:
        temporary = Path(temporary)
        home = temporary / "home"
        home.mkdir()
        environment = {
            key: os.environ[key]
            for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR")
            if key in os.environ
        }
        environment.update(
            HOME=str(home),
            XDG_CONFIG_HOME=str(home),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_OPTIONAL_LOCKS="0",
            GIT_NO_REPLACE_OBJECTS="1",
            LC_ALL="C",
        )

        def git(cwd, *arguments):
            return subprocess.run(
                [
                    executable,
                    "-c",
                    f"core.hooksPath={home}",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "credential.helper=",
                    "-c",
                    "protocol.allow=never",
                    "-c",
                    "protocol.file.allow=always",
                    "-c",
                    "gc.auto=0",
                    "-c",
                    "maintenance.auto=false",
                    "-c",
                    "pack.threads=1",
                    "-c",
                    "index.threads=1",
                    "-C",
                    str(cwd),
                    *arguments,
                ],
                env=environment,
                check=True,
                capture_output=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ).stdout

        def reviewed():
            if (
                git(source, "rev-parse", "HEAD").strip().decode("ascii") != revision
                or Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve()
                != source
                or git(source, "rev-parse", "--show-object-format").strip() != b"sha1"
                or git(source, "status", "--porcelain=v1", "-z", "--untracked-files=all")
            ):
                raise ValueError

        reviewed()
        tree = git(source, "rev-parse", f"{revision}^{{tree}}").strip().decode("ascii")
        if re.fullmatch(r"[a-f0-9]{40}", tree) is None:
            raise ValueError
        tracked = git(source, "ls-tree", "-r", "-l", "-z", revision).split(b"\0")[:-1]
        total = 0
        for entry in tracked:
            metadata, _ = entry.split(b"\t", 1)
            mode, kind, _, size = metadata.split()
            if mode not in {b"100644", b"100755"} or kind != b"blob":
                raise ValueError
            total += int(size)
        if total > _MAX_BYTES or len(tracked) > _MAX_MEMBERS:
            raise ValueError
        repository = temporary / "repository"
        git(source, "init", "--quiet", "--bare", "--template=", str(repository))
        git(
            repository,
            "fetch",
            "--quiet",
            "--depth=1",
            "--no-tags",
            "--no-write-fetch-head",
            "--no-recurse-submodules",
            "--",
            str(source),
            revision,
        )
        git(repository, "update-ref", "--no-deref", "HEAD", revision)
        git(repository, "fsck", "--full", "--strict")
        if (
            git(repository, "rev-parse", "HEAD").strip().decode("ascii") != revision
            or git(repository, "rev-parse", "HEAD^{tree}").strip().decode("ascii") != tree
            or (repository / "shallow").read_bytes() != f"{revision}\n".encode()
        ):
            raise ValueError
        entries = {
            ".git/HEAD": f"{revision}\n".encode(),
            ".git/config": _CONFIG,
            ".git/shallow": f"{revision}\n".encode(),
        }
        object_bytes = sum(map(len, entries.values()))
        for path in sorted((repository / "objects").rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise ValueError
            if path.is_dir():
                continue
            name = path.relative_to(repository).as_posix()
            if not path.is_file() or _OBJECT.fullmatch(name) is None:
                raise ValueError
            object_bytes += path.stat().st_size
            if object_bytes > _MAX_BYTES:
                raise ValueError
            entries[".git/" + name] = path.read_bytes()
        if len(entries) + 1 > _MAX_MEMBERS or len(entries) == 3:
            raise ValueError
        manifest = {
            "format": 1,
            "commit": revision,
            "tree": tree,
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
        }
        entries["source-snapshot.json"] = (
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        ).encode()
        archive = temporary / "source.zip"
        with ZipFile(archive, "x", compression=ZIP_STORED) as package:
            for name, data in sorted(entries.items()):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                package.writestr(info, data)
        if archive.stat().st_size > _MAX_BYTES:
            raise ValueError
        reviewed()
        if _directory(parent) != parent:
            raise ValueError
        with archive.open("r+b") as ready:
            os.fsync(ready.fileno())
        data = archive.read_bytes()
        report = {
            "commit": revision,
            "tree": tree,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "files": len(manifest["files"]),
        }
        # Linking publishes a complete file atomically and refuses a racing existing name.
        os.link(archive, output)
    return report


def prepare(source: Path, output: Path, *, revision: str) -> dict:
    """Export only exact original Git objects from a clean current local revision."""
    try:
        return _prepare(source, output, revision)
    except Exception:
        raise ValueError("Native source snapshot refused") from None
