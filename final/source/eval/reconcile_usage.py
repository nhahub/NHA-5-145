"""Read-only provider accounting lookup; originals and unknown measurements stay intact."""

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

import httpx

from agent.llm import load_llm_settings
from agent.llm.openrouter import generation_id
from eval.milestone_report import summarize_run

ENDPOINT = "https://openrouter.ai/api/v1/generation"
USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "cost")


def complete_usage(usage):
    return isinstance(usage, dict) and all(usage.get(k) is not None for k in USAGE_FIELDS)


def reconcile_report(original, client):
    report = copy.deepcopy(original)
    configuration = report["configuration"]
    if configuration["provider"] != "openrouter":
        raise ValueError("Only OpenRouter accounting can be reconciled here")
    ids = [c.get("generation_id") for row in report["cases"] for c in row["model_calls"]]
    for row in report["cases"]:
        for call in row["model_calls"]:
            if complete_usage(call.get("usage")):
                continue
            identity = generation_id(call.get("generation_id"))
            if identity is None or ids.count(identity) != 1:
                continue
            try:
                response = client.get(ENDPOINT, params={"id": identity})
                response.raise_for_status()
                data = response.json()["data"]
                if data["id"] != identity or data["model"] != configuration["model"]:
                    continue
                usage = {
                    "prompt_tokens": data["native_tokens_prompt"],
                    "completion_tokens": data["native_tokens_completion"],
                    "cost": data["total_cost"],
                }
                if any(
                    isinstance(v, bool)
                    or not isinstance(v, int | float)
                    or not isfinite(v)
                    or v < 0
                    or (k != "cost" and not isinstance(v, int))
                    for k, v in usage.items()
                ):
                    continue
                # Disagreement with any observed field needs investigation, not replacement.
                if any(
                    k in (call.get("usage") or {}) and call["usage"][k] != v
                    for k, v in usage.items()
                ):
                    continue
                call["usage_evidence"] = {
                    "source": ENDPOINT,
                    "generation_id": identity,
                    "model": data["model"],
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "original_usage": call.get("usage"),
                    "token_basis": "native_tokens_prompt/native_tokens_completion",
                    "response_sha256": hashlib.sha256(response.content).hexdigest(),
                    "verified_usage": usage,
                }
                call["usage"] = usage
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                # Accounting is sometimes delayed. No retries, guesses, or provider errors saved.
                continue
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.report.resolve() or args.output.exists():
        raise SystemExit("Use a new output path; existing evidence cannot be overwritten")
    raw = args.report.read_bytes()
    settings = load_llm_settings()
    if settings.provider != "openrouter" or settings.api_key is None:
        raise SystemExit("Configured OpenRouter credentials are required for accounting lookup")
    with httpx.Client(
        timeout=10, headers={"Authorization": f"Bearer {settings.api_key.get_secret_value()}"}
    ) as client:
        report = reconcile_report(json.loads(raw), client)
    report["reconciliation"] = {
        "original_sha256": hashlib.sha256(raw).hexdigest(),
        "created_at": datetime.now(UTC).isoformat(),
        "method": "exact_generation_id_accounting",
    }
    report["summary"] = summarize_run(
        report["cases"], expected_ids=[c["case_id"] for c in report["configuration"]["cases"]]
    )
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print(json.dumps(report["summary"]))
    return 0 if report["summary"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
