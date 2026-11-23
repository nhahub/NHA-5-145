from eval.milestone_report import summarize_run


def row(i, **overrides):
    return {
        "case_id": str(i),
        "passed": True,
        "safety": False,
        "kind": "navigation",
        "steps": 2,
        "action_ms": [100, 300],
        "model_calls": [],
        **overrides,
    }


def test_gate_rejects_safety_failure_even_above_overall_threshold():
    rows = [row(i) for i in range(44)]
    rows[0].update(passed=False, safety=True)
    report = summarize_run(rows, expected_ids=[str(i) for i in range(44)])
    assert report["passed_cases"] == 43
    assert report["gate_passed"] is False
    assert "safety" in report["failed_gates"]


def test_missing_duplicate_and_slow_results_cannot_pass():
    rows = [row(i, action_ms=[3000]) for i in range(43)] + [row(0)]
    report = summarize_run(rows, expected_ids=[str(i) for i in range(44)])
    assert report["gate_passed"] is False
    assert set(report["failed_gates"]) >= {"coverage", "action_latency"}


def test_failed_filters_count_against_efficiency_and_missing_cost_stays_unknown():
    rows = [row(i, kind="filter", steps=1) for i in range(44)]
    for item in rows[:10]:
        item.update(passed=False, steps=0)
    rows[0]["model_calls"] = [{"usage": None}]
    report = summarize_run(rows, expected_ids=[str(i) for i in range(44)])
    assert report["one_action_filter_fraction"] == 34 / 44
    assert report["estimated_cost_usd"] is None
    assert "filter_efficiency" in report["failed_gates"]


def test_missing_measurements_cannot_pass_even_when_every_task_passes():
    rows = [row(i) for i in range(44)]
    report = summarize_run(rows, expected_ids=[str(i) for i in range(44)])
    assert "measurement_completeness" in report["failed_gates"]
    assert report["gate_passed"] is False


def test_complete_evidence_reports_real_percentiles_and_all_gates():
    rows = [row(i, kind="filter", steps=1) for i in range(44)]
    rows[0]["phase_samples"] = [
        {"phase": p, "elapsed_ms": 5}
        for p in (
            "snapshot_build",
            "snapshot_serialization",
            "settle",
            "action_execute_excluding_settle",
        )
    ]
    for item in rows:
        item["action_ms"] = [200]
        item["model_calls"] = [
            {
                "elapsed_ms": 1500,
                "ttft_ms": 900,
                "usage": {"cost": 0.001, "prompt_tokens": 200, "completion_tokens": 50},
            }
        ]
    report = summarize_run(rows, expected_ids=[str(i) for i in range(44)])
    assert report["gate_passed"]
    assert report["action_latency_ms"] == {"p50": 200, "p95": 200}
    assert report["tokens"] == {"prompt_tokens": 8800, "completion_tokens": 2200}
    assert round(report["estimated_cost_usd"], 6) == 0.044
    rows[1]["model_calls"] = []
    assert not summarize_run(rows, expected_ids=[str(i) for i in range(44)])["gate_passed"]
