"""Owner release operations. Output is fixed metadata, never raw configuration/errors."""

import argparse
import json
import signal
import threading
from pathlib import Path

from deploy.artifact import build, install, verify
from deploy.catalogue import copy_catalogue
from deploy.configuration import preflight
from deploy.runtime import ReleaseRuntime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("build")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--local-rehearsal", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("--release", type=Path, required=True)
    copy_release = commands.add_parser("install")
    copy_release.add_argument("--release", type=Path, required=True)
    copy_release.add_argument("--output", type=Path, required=True)
    for name in ("backup", "restore"):
        copy = commands.add_parser(name)
        copy.add_argument("--catalogue", type=Path, required=True)
        copy.add_argument("--output", type=Path, required=True)
    check_state = commands.add_parser("check")
    check_state.add_argument("--release", type=Path, required=True)
    check_state.add_argument("--config", type=Path, required=True)
    check_state.add_argument("--local-rehearsal", action="store_true")
    check_state.add_argument("--minimum-free-bytes", type=int, default=64 * 1024 * 1024)
    run = commands.add_parser("run")
    run.add_argument("--release", type=Path, required=True)
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--logs", type=Path, required=True)
    run.add_argument("--local-rehearsal", action="store_true")
    run.add_argument("--service", choices=["all", "agent", "store", "panel"], default="all")
    args = parser.parse_args()
    try:
        if args.operation == "build":
            build(Path(__file__).resolve().parents[1], args.output, local=args.local_rehearsal)
        elif args.operation == "verify":
            verify(args.release)
        elif args.operation == "install":
            install(args.release, args.output)
        elif args.operation == "check":
            preflight(
                args.release,
                args.config,
                local=args.local_rehearsal,
                minimum_free_bytes=args.minimum_free_bytes,
            )
        elif args.operation == "run":
            stop = threading.Event()
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            with ReleaseRuntime(
                args.release,
                args.config,
                args.logs,
                local=args.local_rehearsal,
                service=args.service,
            ) as runtime:
                while not stop.wait(2):
                    runtime.check_health()
        else:
            result = copy_catalogue(args.catalogue, args.output)
            print(json.dumps({"status": "ok", "operation": args.operation, **result}))
            return 0
    except Exception:
        print(json.dumps({"status": "refused", "operation": args.operation}))
        return 1
    print(json.dumps({"status": "ok", "operation": args.operation}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
