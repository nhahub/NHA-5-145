"""Owner-only invitation controls. Codes are printed only by explicit issue."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from agent.admission.store import InvitationStore


def utc_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Use an explicit UTC offset or Z")
    return parsed.timestamp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("initialize", "issue", "status", "revoke"))
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--identity")
    parser.add_argument("--starts", type=utc_time)
    parser.add_argument("--ends", type=utc_time)
    parser.add_argument("--redemptions", type=int, default=1)
    parser.add_argument("--sessions", type=int, default=8)
    parser.add_argument("--invitation")
    args = parser.parse_args()
    if args.operation == "initialize":
        if args.identity or args.starts is not None or args.ends is not None or args.invitation:
            parser.error("Initialization generates its own identity")
        print(json.dumps({"identity": InvitationStore.initialize(args.path)}))
        return
    if not args.identity:
        parser.error("Existing storage requires its saved identity")
    store = InvitationStore(args.path, args.identity)
    if args.operation == "issue":
        if args.starts is None or args.ends is None:
            parser.error("Issue requires explicit absolute --starts and --ends")
        invitation, code = store.issue(
            args.starts, args.ends, redemptions=args.redemptions, sessions=args.sessions
        )
        print(json.dumps({"invitation": invitation, "code": code}))
    elif args.operation == "revoke":
        if not args.invitation:
            parser.error("Revoke requires --invitation")
        store.revoke(args.invitation)
        print(json.dumps({"revoked": args.invitation}))
    else:
        print(json.dumps(store.status()))


if __name__ == "__main__":
    main()
