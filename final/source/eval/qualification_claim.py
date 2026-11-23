"""A qualification set cannot renew its allowance by restarting the launcher."""

import json
from pathlib import Path


def claim_qualification(marker: Path, report: Path, *, maximum_cost: float = 0.25) -> None:
    if not 0 < maximum_cost <= 0.25:
        raise ValueError("Qualification claim exceeds its supported allowance")
    marker.parent.mkdir(parents=True, exist_ok=True)
    with marker.open("x", encoding="utf-8") as file:
        json.dump(
            {"report": report.as_posix(), "maximum_runs": 1, "maximum_cost_usd": maximum_cost},
            file,
        )
