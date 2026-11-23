"""Bounded portable rehearsal fixture from a verified release; never an installer."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from deploy.artifact import verify


def prepare(source, output, *, maximum_bytes=128 * 1024**2, maximum_members=20000):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    if output.exists() or not output.parent.is_dir() or output.is_relative_to(source):
        raise ValueError("New external rehearsal archive required")
    manifest = verify(source)
    if manifest.get("local_rehearsal") is not False:
        raise ValueError("Production-origin rehearsal source required")
    upstream = (source / "release.json").read_bytes()
    entries, total, links, visited = {}, 0, {}, 0

    def walk(path, relative, ancestors, collect=True):
        nonlocal total, visited
        visited += 1
        if visited > maximum_members:
            raise ValueError("Bounded release required")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(source) or resolved in ancestors:
            raise ValueError("Internal acyclic release paths required")
        if path.is_symlink() or path.is_junction():
            if collect:
                links[relative] = resolved.relative_to(source).as_posix()
            collect = False
        if path.is_dir():
            for child in sorted(path.iterdir()):
                walk(child, f"{relative}/{child.name}".lstrip("/"), ancestors | {resolved}, collect)
        elif path.is_file():
            if relative == "release.json":
                return
            if "\\" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
                raise ValueError("Portable member path required")
            total += path.stat().st_size
            if total > maximum_bytes:
                raise ValueError("Bounded release required")
            data = path.read_bytes()
            if len(data) != path.stat().st_size:
                raise ValueError("Stable release required")
            if collect:
                entries[relative] = data
        else:
            raise ValueError("Regular release inputs required")

    walk(source, "", set())
    verify(source)
    if (source / "release.json").read_bytes() != upstream:
        raise ValueError("Stable source manifest required")
    provenance = {
        "version": 1,
        "upstream_manifest_sha256": hashlib.sha256(upstream).hexdigest(),
        "upstream_manifest": manifest,
        "links": links,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
    }
    with ZipFile(output, "x", compression=ZIP_STORED) as archive:
        archive.writestr("fixture.json", json.dumps(provenance, sort_keys=True))
        for name, data in entries.items():
            archive.writestr("release/" + name, data)
    return {
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "upstream_manifest_sha256": provenance["upstream_manifest_sha256"],
        "members": len(entries),
        "bytes": sum(len(value) for value in entries.values()),
        "traversed_bytes": total,
        "normalized_links": len(links),
    }
