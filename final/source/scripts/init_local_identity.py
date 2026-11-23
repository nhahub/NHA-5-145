"""Create a local, ignored service credential without displaying it."""

import json
import os
import secrets
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    directory = root / "work"
    directory.mkdir(exist_ok=True)
    path = directory / "local-identity.json"
    if path.exists():
        print("Local identity configuration already exists; left unchanged.")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        try:
            if os.name == "nt":
                identity = subprocess.check_output(["whoami"], text=True).strip()
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{identity}:(F)"],
                    check=True,
                    capture_output=True,
                )
            json.dump({"secret": secrets.token_hex(32)}, stream)
        except Exception:
            stream.close()
            path.unlink()
            raise
    print("Created restricted local identity configuration under ignored work/.")


if __name__ == "__main__":
    main()
