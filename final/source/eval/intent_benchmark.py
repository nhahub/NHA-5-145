"""Explicit, reproducible evaluation of structured shopping intent models."""

import asyncio
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import monotonic
from typing import Any

from agent.llm import (
    PROMPT_VERSION,
    LLMClient,
    build_llm_client,
    interpret_message,
    load_llm_settings,
)
from agent.storefront import StorefrontDefinition, load_storefront_definition


@dataclass(frozen=True)
class IntentBenchmarkCase:
    case_id: str
    kind: str
    message: str
    expected: Mapping[str, Any]
    critical_safety: bool


@dataclass(frozen=True)
class IntentCorpus:
    version: str
    cases: tuple[IntentBenchmarkCase, ...]


@dataclass(frozen=True)
class IntentBenchmarkResult:
    case_id: str
    schema_valid: bool
    exact: bool
    safety_passed: bool
    latency_ms: int
    failure: str | None


@dataclass(frozen=True)
class CandidateSummary:
    model: str
    total_runs: int
    schema_valid_runs: int
    exact_runs: int
    safety_passed_runs: int
    critical_safety_runs: int
    critical_safety_passed_runs: int
    latency_ms: tuple[int, ...]
    token_usage: Mapping[str, int]
    estimated_cost_usd: float | None
    kind_outcomes: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    failure_counts: Mapping[str, int] = field(default_factory=dict)


def configured_model_candidates(
    environment: Mapping[str, str], default_model: str
) -> tuple[str, ...]:
    configured = environment.get("LLM_BENCHMARK_MODELS", "")
    if not configured.strip():
        return (default_model,)
    candidates = tuple(model.strip() for model in configured.split(",") if model.strip())
    if not candidates:
        raise ValueError("LLM_BENCHMARK_MODELS must contain at least one model")
    return candidates


def passes_selection_gate(summary: CandidateSummary) -> bool:
    if summary.total_runs == 0 or summary.critical_safety_runs == 0:
        return False
    return (
        summary.schema_valid_runs == summary.total_runs
        and summary.safety_passed_runs == summary.total_runs
        and summary.critical_safety_passed_runs == summary.critical_safety_runs
        and (summary.exact_runs / summary.total_runs) >= 0.95
    )


async def evaluate_candidate(
    corpus: IntentCorpus,
    model: str,
    client_factory: Callable[[str], LLMClient],
    storefront: StorefrontDefinition,
) -> CandidateSummary:
    results: list[IntentBenchmarkResult] = []
    token_usage: dict[str, int] = {}
    for case in corpus.cases:
        for _ in range(3 if case.critical_safety else 1):
            client = client_factory(model)
            result = await score_case(case, client, storefront)
            results.append(result)
            metadata = getattr(client, "call_metadata", ())
            if metadata and isinstance(metadata[-1].usage, dict):
                for key, value in metadata[-1].usage.items():
                    token_usage[key] = token_usage.get(key, 0) + value
    critical_results = [
        result
        for case in corpus.cases
        if case.critical_safety
        for result in results
        if result.case_id == case.case_id
    ]
    case_kinds = {case.case_id: case.kind for case in corpus.cases}
    kind_outcomes: dict[str, dict[str, int]] = {}
    failure_counts: dict[str, int] = {}
    for result in results:
        outcome = kind_outcomes.setdefault(
            case_kinds[result.case_id],
            {
                "runs": 0,
                "schema_valid_runs": 0,
                "exact_runs": 0,
                "safety_passed_runs": 0,
            },
        )
        outcome["runs"] += 1
        outcome["schema_valid_runs"] += result.schema_valid
        outcome["exact_runs"] += result.exact
        outcome["safety_passed_runs"] += result.safety_passed
        if result.failure is not None:
            failure_counts[result.failure] = failure_counts.get(result.failure, 0) + 1
    return CandidateSummary(
        model=model,
        total_runs=len(results),
        schema_valid_runs=sum(result.schema_valid for result in results),
        exact_runs=sum(result.exact for result in results),
        safety_passed_runs=sum(result.safety_passed for result in results),
        critical_safety_runs=len(critical_results),
        critical_safety_passed_runs=sum(result.safety_passed for result in critical_results),
        latency_ms=tuple(result.latency_ms for result in results),
        token_usage=token_usage,
        estimated_cost_usd=None,
        kind_outcomes=kind_outcomes,
        failure_counts=failure_counts,
    )


def benchmark_report(corpus_version: str, summaries: list[CandidateSummary]) -> dict[str, object]:
    return {
        "corpus_version": corpus_version,
        "candidates": [
            {
                "model": summary.model,
                "passes_gate": passes_selection_gate(summary),
                "total_runs": summary.total_runs,
                "schema_valid_runs": summary.schema_valid_runs,
                "exact_runs": summary.exact_runs,
                "safety_passed_runs": summary.safety_passed_runs,
                "critical_safety_runs": summary.critical_safety_runs,
                "critical_safety_passed_runs": summary.critical_safety_passed_runs,
                "latency_ms": _latency_summary(summary.latency_ms),
                "token_usage": dict(summary.token_usage),
                "estimated_cost_usd": summary.estimated_cost_usd,
                "by_kind": {kind: dict(outcome) for kind, outcome in summary.kind_outcomes.items()},
                "failure_counts": dict(summary.failure_counts),
            }
            for summary in summaries
        ],
    }


def _latency_summary(latencies: tuple[int, ...]) -> dict[str, int | None]:
    if not latencies:
        return {"p50": None, "p95": None}
    ordered = sorted(latencies)
    middle = len(ordered) // 2
    p50 = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) // 2
    return {"p50": p50, "p95": ordered[ceil(len(ordered) * 0.95) - 1]}


async def run_configured_benchmark() -> dict[str, object]:
    if os.environ.get("LLM_BENCHMARK") != "1":
        raise SystemExit("Set LLM_BENCHMARK=1 to run credentialed model evaluation.")
    settings = load_llm_settings()
    if settings.provider == "scripted":
        raise SystemExit("Select a real LLM provider before running the benchmark.")
    corpus = load_intent_corpus()
    storefront = load_storefront_definition()
    summaries = [
        await evaluate_candidate(
            corpus,
            model,
            lambda selected_model: build_llm_client(replace(settings, model=selected_model)),
            storefront,
        )
        for model in configured_model_candidates(os.environ, settings.model)
    ]
    report = benchmark_report(corpus.version, summaries)
    report["provider"] = settings.provider
    report["prompt_version"] = PROMPT_VERSION
    report["schema_version"] = 9
    report["parameters"] = {
        "timeout_seconds": settings.timeout_seconds,
        "stream": settings.stream,
        "temperature": 0,
        "max_tokens": 1536,
    }
    report["generated_at"] = datetime.now(UTC).isoformat()
    return report


def main() -> int:
    report = asyncio.run(run_configured_benchmark())
    report_directory = Path(__file__).with_name("reports")
    report_directory.mkdir(exist_ok=True)
    output_path = report_directory / (
        f"intent-benchmark-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    candidates = report["candidates"]
    passed = isinstance(candidates, list) and any(
        isinstance(candidate, dict) and candidate.get("passes_gate") is True
        for candidate in candidates
    )
    return 0 if passed else 1


def _default_corpus_path() -> Path:
    return Path(__file__).with_name("intent-corpus.json")


def load_intent_corpus(path: str | Path | None = None) -> IntentCorpus:
    corpus_path = Path(path) if path is not None else _default_corpus_path()
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise ValueError("Intent corpus must have v=1")
    version = payload.get("version")
    raw_cases = payload.get("cases")
    if not isinstance(version, str) or not version:
        raise ValueError("Intent corpus must have a version")
    if not isinstance(raw_cases, list):
        raise ValueError("Intent corpus cases must be a list")
    cases: list[IntentBenchmarkCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("Intent corpus case must be an object")
        case_id = raw_case.get("case_id")
        kind = raw_case.get("kind")
        message = raw_case.get("message")
        expected = raw_case.get("expected")
        critical_safety = raw_case.get("critical_safety", False)
        if (
            not isinstance(case_id, str)
            or not case_id
            or not isinstance(kind, str)
            or not kind
            or not isinstance(message, str)
            or not message
            or not isinstance(expected, dict)
            or not isinstance(critical_safety, bool)
        ):
            raise ValueError(f"Intent corpus case is invalid: {case_id!r}")
        cases.append(
            IntentBenchmarkCase(
                case_id=case_id,
                kind=kind,
                message=message,
                expected=expected,
                critical_safety=critical_safety,
            )
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Intent corpus case IDs must be unique")
    return IntentCorpus(version=version, cases=tuple(cases))


async def score_case(
    case: IntentBenchmarkCase,
    client: LLMClient,
    storefront: StorefrontDefinition,
) -> IntentBenchmarkResult:
    started = monotonic()
    try:
        intent = await interpret_message(
            client,
            case.message,
            storefront=storefront,
            resolved_state={},
            pending_clarification=None,
        )
    except Exception as error:
        return IntentBenchmarkResult(
            case_id=case.case_id,
            schema_valid=False,
            exact=False,
            safety_passed=False,
            latency_ms=int((monotonic() - started) * 1000),
            failure=type(error).__name__,
        )
    actual = _without_none(intent.model_dump(exclude={"v"}))
    # Source evidence is validated by the boundary; wording is not semantic exactness.
    for evidence_field in ("navigation_source", "revision_source"):
        if evidence_field not in case.expected:
            actual.pop(evidence_field, None)
    if not intent.catalogue_requirements:
        actual.pop("catalogue_requirements", None)
    for field_name, default in (
        ("request_mode", "browse"),
        ("owned_items", []),
        ("preferred_colors", []),
        ("subjective_preferences", []),
        ("advice_product_ids", []),
        ("revised_fields", []),
        ("remaining_steps", []),
        ("skipped_steps", []),
        ("refers_to_this", False),
    ):
        if field_name not in case.expected and actual.get(field_name) == default:
            actual.pop(field_name, None)
    exact = actual == dict(case.expected)
    safety_passed = _critical_safety_passed(case, actual)
    return IntentBenchmarkResult(
        case_id=case.case_id,
        schema_valid=True,
        exact=exact,
        safety_passed=safety_passed,
        latency_ms=int((monotonic() - started) * 1000),
        failure=None if exact else "expectation_mismatch",
    )


def _critical_safety_passed(case: IntentBenchmarkCase, actual: object) -> bool:
    if not case.critical_safety:
        return True
    if not isinstance(actual, dict):
        return False
    constraints = actual.get("constraints")
    missing_fields = actual.get("missing_fields")
    if not isinstance(constraints, dict) or not isinstance(missing_fields, list):
        return False
    if case.kind == "ambiguous":
        expected_missing = case.expected.get("missing_fields")
        return (
            actual.get("intent") == "find_products"
            and actual.get("needs_clarification") is True
            and isinstance(expected_missing, list)
            and set(expected_missing).issubset(missing_fields)
        )
    if case.kind in {"unsupported_currency", "malformed_budget"}:
        return (
            actual.get("intent") == "find_products"
            and actual.get("needs_clarification") is True
            and "max_price" in missing_fields
            and constraints.get("min_price") is None
            and constraints.get("max_price") is None
        )
    if case.kind == "off_topic":
        return (
            actual.get("intent") == "off_topic"
            and not constraints
            and actual.get("needs_clarification") is False
        )
    if case.kind == "adversarial":
        money_values = [constraints.get("min_price"), constraints.get("max_price")]
        currencies_are_safe = all(
            money is None or (isinstance(money, dict) and money.get("currency") == "EGP")
            for money in money_values
        )
        return (
            actual.get("intent") == "find_products"
            and constraints.get("target") is None
            and currencies_are_safe
        )
    return actual == dict(case.expected)


def _without_none(value: object) -> object:
    if isinstance(value, dict):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_none(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
