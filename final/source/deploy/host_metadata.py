"""Install only the fixed host metadata boundary; no SDK or import-time effects."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from deploy.host_files import _pairs, _read_private, production_release


def render_metadata(agent_uid):
    if type(agent_uid) is not int or not 0 < agent_uid < 4294967295:
        raise ValueError("Agent UID required")
    return (
        "add table inet scpilot_metadata\n"
        "add chain inet scpilot_metadata output { type filter hook output priority 0; "
        "policy accept; }\n"
        "flush chain inet scpilot_metadata output\n"
        f"add rule inet scpilot_metadata output meta skuid {{ 0, {agent_uid} }} return\n"
        "add rule inet scpilot_metadata output ip daddr 169.254.169.254 reject\n"
        "add rule inet scpilot_metadata output ip6 daddr fd00:ec2::254 reject\n"
    )


def _root():
    return os.name == "posix" and os.geteuid() == 0


def _identity():
    import pwd

    return pwd.getpwnam("copilot").pw_uid


def _runtime_root():
    return Path(__file__).resolve().parents[1]


def configure(path, *, read_private=_read_private):
    try:
        if not _root() or not isinstance(path, Path) or not path.is_absolute():
            raise ValueError()
        raw = read_private(path, 4096)
        if len(raw) > 4096:
            raise ValueError()
        data = json.loads(raw, object_pairs_hook=_pairs)
        if (
            type(data) is not dict
            or set(data) != {"version", "release", "fingerprint", "agent_uid"}
            or type(data["version"]) is not int
            or data["version"] != 1
        ):
            raise ValueError()
        batch = render_metadata(data["agent_uid"])
        if data["agent_uid"] != _identity():
            raise ValueError()
        release = production_release(Path(data["release"]), data["fingerprint"])
        if release != _runtime_root():
            raise ValueError()
        subprocess.run(
            ["/usr/sbin/nft", "--file", "-"],
            input=batch,
            text=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
            timeout=5,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    except Exception:
        pass
    raise ValueError("Metadata protection refused")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError()


def main(argv=None):
    try:
        parser = _Parser(description="Configure the fixed metadata boundary", allow_abbrev=False)
        parser.add_argument("--config", type=Path, required=True)
        configure(parser.parse_args(argv).config)
        return 0
    except (Exception, SystemExit):
        print("Metadata protection refused", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
