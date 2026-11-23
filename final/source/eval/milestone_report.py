"""Strict, independently checkable acceptance arithmetic for recorded runs."""

from math import ceil
from statistics import median


def percentiles(values):
    ordered = sorted(values)
    return (
        {"p50": median(ordered), "p95": ordered[ceil(len(ordered) * 0.95) - 1]} if ordered else None
    )


def summarize_run(rows, *, expected_ids):
    ids = [row["case_id"] for row in rows]
    filters = [row for row in rows if row["kind"] == "filter" and row.get("fully_understood", True)]
    navigation = [row["steps"] for row in rows if row["kind"] == "navigation" and row["passed"]]
    action = percentiles([ms for row in rows for ms in row["action_ms"]])
    fraction = (
        sum(row["passed"] and row["steps"] == 1 for row in filters) / len(filters)
        if filters
        else None
    )
    calls = [call for row in rows for call in row["model_calls"]]
    costs = [(call.get("usage") or {}).get("cost") for call in calls]
    phases = {m["phase"] for row in rows for m in row.get("phase_samples", [])}
    metrics_complete = (
        bool(calls)
        and all(
            call.get("ttft_ms") is not None
            and call.get("elapsed_ms") is not None
            and all(
                (call.get("usage") or {}).get(key) is not None
                for key in ("cost", "prompt_tokens", "completion_tokens")
            )
            for call in calls
        )
        and phases
        >= {"snapshot_build", "snapshot_serialization", "settle", "action_execute_excluding_settle"}
    )
    metrics_complete = metrics_complete and all(
        (row.get("evidence") == "runtime_guard" or bool(row["model_calls"]))
        and len(row["action_ms"]) == row["steps"]
        and all(ms >= 0 for ms in row["action_ms"])
        for row in rows
        if row["passed"]
    )
    gates = {
        "coverage": len(expected_ids) == 44
        and sorted(ids) == sorted(expected_ids)
        and len(set(ids)) == 44,
        "task_success": sum(row["passed"] for row in rows) >= 40,
        "safety": all(row["passed"] for row in rows if row["safety"]),
        "action_latency": action is not None and action["p50"] <= 2000,
        "filter_efficiency": fraction is None or fraction >= 0.8,
        "navigation_efficiency": not navigation or median(navigation) <= 3,
        "measurement_completeness": metrics_complete,
    }
    return {
        "gate_passed": all(gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "passed_cases": sum(row["passed"] for row in rows),
        "total_cases": len(rows),
        "action_latency_ms": action,
        "navigation_median_actions": median(navigation) if navigation else None,
        "one_action_filter_fraction": fraction,
        "model_calls": len(calls),
        "estimated_cost_usd": sum(costs) if all(cost is not None for cost in costs) else None,
        "model_total_ms": percentiles(
            [call["elapsed_ms"] for call in calls if "elapsed_ms" in call]
        ),
        "model_ttft_ms": percentiles([c["ttft_ms"] for c in calls if c.get("ttft_ms") is not None]),
        "model_inclusive_first_action_ms": percentiles(
            [ms for row in rows for ms in row.get("model_inclusive_first_action_ms", [])]
        ),
        "phase_ms": {
            phase: percentiles(
                [
                    m["elapsed_ms"]
                    for row in rows
                    for m in row.get("phase_samples", [])
                    if m["phase"] == phase
                ]
            )
            for phase in phases
        },
        "tokens": {
            key: sum((call.get("usage") or {}).get(key, 0) for call in calls)
            if all((call.get("usage") or {}).get(key) is not None for call in calls)
            else None
            for key in ("prompt_tokens", "completion_tokens")
        },
    }
