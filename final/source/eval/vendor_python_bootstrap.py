"""Bounded private vendor interpreter bootstrap, never a host package installer."""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(archive, expected, output):
    try:
        if (
            archive.stat().st_size > 256 * 1024**2
            or sha(archive) != expected
            or output.exists()
            or output.is_symlink()
            or not output.parent.is_dir()
            or any(parent.is_symlink() for parent in output.parents)
        ):
            raise ValueError()
        with tarfile.open(archive) as package:
            entries = package.getmembers()
            if (
                len(entries) > 20000
                or sum(entry.size for entry in entries) > 512 * 1024**2
                or len({entry.name for entry in entries}) != len(entries)
            ):
                raise ValueError()
            regular = set()
            for entry in entries:
                name = entry.name.rstrip("/") if entry.isdir() else entry.name
                if (
                    name != "usr"
                    and not name.startswith("usr/")
                    or PurePosixPath(name).is_absolute()
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                    or "\\" in name
                    or not (entry.isfile() or entry.isdir() or entry.issym() or entry.islnk())
                    or entry.issym()
                    and PurePosixPath(entry.linkname).is_absolute()
                    or entry.islnk()
                    and entry.linkname not in regular
                ):
                    raise ValueError()
                if entry.isfile():
                    regular.add(entry.name)
            output.mkdir(mode=0o700)
            package.extractall(output, filter="data")
        output = output.resolve(strict=True)
        for path in output.rglob("*"):
            if path.is_symlink() and not path.resolve(strict=True).is_relative_to(output):
                raise ValueError()
        executable = output / "usr/bin/python3.12"
        if not executable.is_file() or executable.is_symlink():
            raise ValueError()
        return executable
    except Exception:
        raise ValueError("Vendor interpreter input refused") from None


def main():
    inputs = Path("/input")
    profile = inputs / "profile.json"
    assert len(sys.argv) >= 2 and profile.stat().st_size <= 65536
    assert sha(profile) == sys.argv[1]
    expected = json.loads(profile.read_bytes())
    assert sha(Path(__file__)) == expected["python_bootstrap_sha256"]
    assert sha(inputs / "probe.py") == expected["probe_sha256"]
    prefix = Path("/rehearsal/vendor-python")
    executable = unpack(inputs / "vendor-python.tar", expected["python_prefix_sha256"], prefix)
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/rehearsal/home",
        "LANG": "C.UTF-8",
        "AWS_EC2_METADATA_DISABLED": "true",
        "LD_LIBRARY_PATH": str(prefix / "usr/lib64"),
    }
    check = """
import importlib,json,ssl,sys,sysconfig
from pathlib import Path
assert sys.version_info[:3] == (3,12,14)
assert sys.prefix == '/rehearsal/vendor-python/usr'
assert not any('site-packages' in p or '/var/lang' in p for p in sys.path)
modules={}
for name in ['_ssl','_hashlib','_sqlite3','_decimal','_bz2','_lzma','_ctypes',
             'pyexpat','_gdbm','_dbm','_crypt','_uuid','readline','zlib']:
 module=importlib.import_module(name)
 path=Path(module.__file__).resolve(strict=True)
 assert path.is_relative_to(Path(sys.prefix))
 modules[name]=str(path)
print(json.dumps({'python_version':'.'.join(map(str,sys.version_info[:3])),
                 'prefix':sys.prefix,'soabi':sysconfig.get_config_var('SOABI'),
                 'openssl':ssl.OPENSSL_VERSION,'native_stdlib_imports':modules}))
"""
    result = subprocess.run(
        [str(executable), "-I", "-S", "-B", "-c", check],
        env=environment,
        capture_output=True,
        timeout=20,
        check=False,
    )
    Path("/output/vendor-python.stdout").write_bytes(result.stdout)
    Path("/output/vendor-python.stderr").write_bytes(result.stderr)
    assert result.returncode == 0
    Path("/output/vendor-python.json").write_text(
        json.dumps(json.loads(result.stdout), indent=2) + "\n"
    )
    os.execve(
        executable,
        [str(executable), "-I", "-S", "-B", "/input/probe.py", sys.argv[1], *sys.argv[2:]],
        environment,
    )


if __name__ == "__main__":
    main()
