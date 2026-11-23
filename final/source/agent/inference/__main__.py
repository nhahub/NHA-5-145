"""Owner-only local CLI. No HTTP route initializes or changes an allowance."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from agent.inference.ledger import AllowanceLedger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["initialize", "status", "disable", "enable"])
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--identity")
    parser.add_argument("--allowance-usd", type=Decimal)
    arguments = parser.parse_args()
    if arguments.operation == "initialize":
        if arguments.allowance_usd is None or arguments.identity is not None:
            parser.error("Initialization requires an allowance and generates a new identity")
        identity = AllowanceLedger.initialize(arguments.path, arguments.allowance_usd)
        print(json.dumps({"identity": identity, "path": str(arguments.path)}))
        return
    if not arguments.identity or arguments.allowance_usd is not None:
        parser.error("Existing ledger operations require identity and never replace its allowance")
    ledger = AllowanceLedger(arguments.path, arguments.identity)
    if arguments.operation in {"disable", "enable"}:
        ledger.set_enabled(arguments.operation == "enable")
    print(json.dumps(ledger.status()))


if __name__ == "__main__":
    main()
