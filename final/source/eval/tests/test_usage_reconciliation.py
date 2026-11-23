import copy
import json

import httpx
import pytest

from eval.reconcile_usage import reconcile_report


def report():
    return {
        "configuration": {"provider": "openrouter", "model": "google/gemini-2.5-flash"},
        "cases": [
            {
                "case_id": "orders-login",
                "model_calls": [
                    {
                        "attempt_id": "local-attempt",
                        "generation_id": "gen-failed",
                        "usage": None,
                    }
                ],
            }
        ],
    }


def test_reconciles_only_exact_generation_and_keeps_original_evidence():
    original = report()
    before = copy.deepcopy(original)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.params["id"] == "gen-failed"
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "gen-failed",
                    "model": "google/gemini-2.5-flash",
                    "native_tokens_prompt": 12,
                    "native_tokens_completion": 2,
                    "total_cost": 0.0001,
                    "tokens_prompt": 999,
                    "private": "must not be retained",
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        reconciled = reconcile_report(original, client)
    assert original == before
    call = reconciled["cases"][0]["model_calls"][0]
    assert call["usage"] == {"prompt_tokens": 12, "completion_tokens": 2, "cost": 0.0001}
    assert call["usage_evidence"]["generation_id"] == "gen-failed"
    assert "must not be retained" not in json.dumps(reconciled)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"id": "gen-unrelated"},
        {"model": "different/model"},
        {"native_tokens_prompt": None},
        {"total_cost": -1},
        {"native_tokens_completion": True},
    ],
)
def test_unattributable_or_invalid_accounting_leaves_usage_unknown(override):
    data = {
        "id": "gen-failed",
        "model": "google/gemini-2.5-flash",
        "native_tokens_prompt": 12,
        "native_tokens_completion": 2,
        "total_cost": 0.0001,
        **override,
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": data}))
    ) as client:
        result = reconcile_report(report(), client)
    assert result["cases"][0]["model_calls"][0]["usage"] is None


def test_historical_missing_id_cannot_trigger_guessed_provider_lookup():
    original = report()
    original["cases"][0]["model_calls"][0].pop("generation_id")

    def handler(_):
        pytest.fail("No lookup is allowed without a saved generation identity")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = reconcile_report(original, client)
    assert result["cases"][0]["model_calls"][0]["usage"] is None


def test_duplicate_generation_id_cannot_be_attributed_to_two_attempts():
    original = report()
    original["cases"][0]["model_calls"].append(
        {"attempt_id": "second", "generation_id": "gen-failed", "usage": None}
    )

    def handler(_):
        pytest.fail("Duplicate generation identity must not be reconciled")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = reconcile_report(original, client)
    assert all(c["usage"] is None for c in result["cases"][0]["model_calls"])


def test_conflicting_partial_usage_is_not_overwritten():
    original = report()
    original["cases"][0]["model_calls"][0]["usage"] = {"cost": 0.002}
    data = {
        "id": "gen-failed",
        "model": "google/gemini-2.5-flash",
        "native_tokens_prompt": 12,
        "native_tokens_completion": 2,
        "total_cost": 0.0001,
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": data}))
    ) as client:
        result = reconcile_report(original, client)
    assert result["cases"][0]["model_calls"][0]["usage"] == {"cost": 0.002}


def test_unavailable_accounting_is_not_retried_or_counted_as_zero():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(404, json={"error": "private error"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = reconcile_report(report(), client)
    assert len(requests) == 1
    assert result["cases"][0]["model_calls"][0]["usage"] is None
