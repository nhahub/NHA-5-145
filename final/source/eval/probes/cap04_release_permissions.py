"""Disposable Linux DAC proof; no users, services or host permissions are changed."""

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    if os.name != "posix" or os.geteuid() != 0:
        raise SystemExit("Run this disposable probe as root in Linux/WSL")
    with TemporaryDirectory(prefix="copilot-permission-proof-") as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        release, state = root / "release", root / "state"
        release.mkdir(mode=0o755)
        state.mkdir(mode=0o700)
        os.chown(state, 65534, 65534)
        code, config = release / "entry.py", root / "runtime.env"
        code.write_text("# immutable release\n")
        code.chmod(0o444)
        config.write_text("fictional disposable configuration\n")
        os.chown(config, 0, 65534)
        config.chmod(0o640)
        script = r"""
import os, pathlib, sqlite3, sys
root = pathlib.Path(sys.argv[1])
assert os.getuid() == 65534
assert (root/'release/entry.py').read_text()
assert (root/'runtime.env').read_text()
for path in (root/'release/entry.py', root/'release/extra.py', root/'runtime.env'):
    try:
        path.write_text('forbidden')
    except PermissionError:
        continue
    raise AssertionError('runtime wrote immutable code/configuration')
with sqlite3.connect(root/'state/probe.sqlite') as db:
    db.execute('CREATE TABLE probe(value TEXT)')
    db.execute("INSERT INTO probe VALUES('state-write')")
print('service-permissions-ok')
"""

        def service_identity():
            os.setgroups([])
            os.setgid(65534)
            os.setuid(65534)

        result = subprocess.run(
            [sys.executable, "-c", script, str(root)],
            preexec_fn=service_identity,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "service-permissions-ok"

        def other_identity():
            os.setgroups([])
            os.setgid(65533)
            os.setuid(65533)

        denied = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pathlib,sys;pathlib.Path(sys.argv[1]).read_text()",
                str(config),
            ],
            preexec_fn=other_identity,
            capture_output=True,
            check=False,
        )
        assert denied.returncode != 0
        print(
            json.dumps(
                {
                    "status": "passed",
                    "runtime_uid": 65534,
                    "immutable_release": True,
                    "restricted_configuration": True,
                    "writable_state": True,
                    "other_account_denied": True,
                }
            )
        )


if __name__ == "__main__":
    main()
