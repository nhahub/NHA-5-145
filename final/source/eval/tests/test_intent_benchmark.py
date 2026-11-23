import asyncio
import json

from agent.llm import LLMChunk, ScriptedLLMClient
from agent.storefront import load_storefront_definition
from eval.intent_benchmark import (
    CandidateSummary,
    IntentBenchmarkCase,
    IntentCorpus,
    benchmark_report,
    configured_model_candidates,
    evaluate_candidate,
    load_intent_corpus,
    passes_selection_gate,
    score_case,
)


def test_intent_benchmark_corpus_is_versioned_and_has_sixty_cases() -> None:
    corpus = load_intent_corpus()

    assert corpus.version == "intent-corpus-v1"
    assert len(corpus.cases) >= 60
    assert {case.kind for case in corpus.cases} >= {
        "egyptian_arabic",
        "english",
        "franco_arabic",
        "mixed",
        "ambiguous",
        "unsupported_currency",
        "malformed_budget",
        "off_topic",
        "adversarial",
    }


def test_score_case_counts_an_exact_scripted_intent_as_a_pass() -> None:
    case = IntentBenchmarkCase(
        case_id="exact-case",
        kind="english",
        message="Show me black running shoes under 2500 EGP",
        expected={
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {
                "category": "shoes",
                "product_type": "running",
                "color": "black",
                "max_price": {"amount": "2500", "currency": "EGP"},
            },
            "needs_clarification": False,
            "missing_fields": [],
            "conflicting_fields": [],
        },
        critical_safety=False,
    )
    payload = {
        "v": 8,
        "language": "en",
        "dialect": "english",
        **case.expected,
    }

    result = asyncio.run(
        score_case(
            case,
            ScriptedLLMClient(responses=[[LLMChunk(text=json.dumps(payload))]]),
            load_storefront_definition(),
        )
    )

    assert result.schema_valid is True
    assert result.exact is True
    assert result.safety_passed is True


def test_score_case_reports_safe_critical_output_separately_from_exact_accuracy() -> None:
    case = IntentBenchmarkCase(
        case_id="foreign-budget",
        kind="unsupported_currency",
        message="Show shoes under $100",
        expected={
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "shoes"},
            "missing_fields": ["max_price"],
            "conflicting_fields": [],
            "needs_clarification": True,
        },
        critical_safety=True,
    )
    safe_but_inexact = {
        "v": 8,
        "language": "en",
        "dialect": "english",
        "intent": "find_products",
        "constraints": {},
        "missing_fields": ["max_price"],
        "conflicting_fields": [],
        "needs_clarification": True,
    }

    result = asyncio.run(
        score_case(
            case,
            ScriptedLLMClient(responses=[[LLMChunk(text=json.dumps(safe_but_inexact))]]),
            load_storefront_definition(),
        )
    )

    assert result.schema_valid is True
    assert result.exact is False
    assert result.safety_passed is True


def test_selection_gate_rejects_perfect_accuracy_when_a_critical_safety_repeat_fails() -> None:
    summary = CandidateSummary(
        model="candidate-model",
        total_runs=64,
        schema_valid_runs=64,
        exact_runs=64,
        safety_passed_runs=63,
        critical_safety_runs=12,
        critical_safety_passed_runs=11,
        latency_ms=(100, 120),
        token_usage={},
        estimated_cost_usd=None,
    )

    assert passes_selection_gate(summary) is False


def test_candidate_evaluation_repeats_critical_cases_three_times() -> None:
    expected = {
        "language": "en",
        "dialect": "english",
        "intent": "off_topic",
        "constraints": {},
        "missing_fields": [],
        "conflicting_fields": [],
        "needs_clarification": False,
    }
    corpus = IntentCorpus(
        version="test-v1",
        cases=(
            IntentBenchmarkCase("normal", "english", "hello", expected, False),
            IntentBenchmarkCase("critical", "off_topic", "joke", expected, True),
        ),
    )

    def client_factory(model: str) -> ScriptedLLMClient:
        assert model == "candidate-model"
        return ScriptedLLMClient(responses=[[LLMChunk(text=json.dumps({"v": 8, **expected}))]])

    summary = asyncio.run(
        evaluate_candidate(
            corpus,
            "candidate-model",
            client_factory,
            load_storefront_definition(),
        )
    )

    assert summary.total_runs == 4
    assert summary.critical_safety_runs == 3
    assert summary.kind_outcomes["off_topic"] == {
        "runs": 3,
        "schema_valid_runs": 3,
        "exact_runs": 3,
        "safety_passed_runs": 3,
    }
    assert passes_selection_gate(summary) is True


def test_benchmark_report_includes_gate_and_latency_evidence() -> None:
    summary = CandidateSummary(
        model="candidate-model",
        total_runs=10,
        schema_valid_runs=10,
        exact_runs=10,
        safety_passed_runs=10,
        critical_safety_runs=3,
        critical_safety_passed_runs=3,
        latency_ms=(10, 20, 30, 40),
        token_usage={"total_tokens": 100},
        estimated_cost_usd=0.02,
    )

    report = benchmark_report("intent-corpus-v1", [summary])

    assert report["corpus_version"] == "intent-corpus-v1"
    assert report["candidates"][0]["passes_gate"] is True
    assert report["candidates"][0]["latency_ms"] == {"p50": 25, "p95": 40}
    assert report["candidates"][0]["by_kind"] == {}


def test_candidate_evaluation_reports_redacted_failure_categories() -> None:
    case = IntentBenchmarkCase(
        "invalid-response",
        "english",
        "Show shoes under 2500 EGP",
        {
            "language": "en",
            "dialect": "english",
            "intent": "find_products",
            "constraints": {"category": "shoes"},
            "missing_fields": [],
            "conflicting_fields": [],
            "needs_clarification": False,
        },
        False,
    )
    corpus = IntentCorpus(version="test-v1", cases=(case,))

    summary = asyncio.run(
        evaluate_candidate(
            corpus,
            "candidate-model",
            lambda _model: ScriptedLLMClient(
                responses=[[LLMChunk(text="not structured intent json")]]
            ),
            load_storefront_definition(),
        )
    )
    report = benchmark_report(corpus.version, [summary])

    assert report["candidates"][0]["failure_counts"] == {"StructuredIntentDraftError": 1}


def test_configured_candidates_default_to_the_selected_provider_model() -> None:
    assert configured_model_candidates({}, "qwen/qwen3.8-27b") == ("qwen/qwen3.8-27b",)


def test_configured_candidates_accept_provider_neutral_model_overrides() -> None:
    assert configured_model_candidates(
        {"LLM_BENCHMARK_MODELS": "model-a, model-b"},
        "configured-model",
    ) == ("model-a", "model-b")
