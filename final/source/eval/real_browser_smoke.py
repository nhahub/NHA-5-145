"""Opt-in browser check through the pinned real Intent Interpreter."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent.llm import load_llm_settings
from agent.llm.intent_pipeline import PROMPT_VERSION
from eval.cases import DISCOVERY_CASES
from eval.runner import run_evaluation
from eval.services import local_services


def main() -> int:
    if os.environ.get("LLM_BROWSER_SMOKE") != "1":
        raise SystemExit("Set LLM_BROWSER_SMOKE=1 to run the real-model browser check.")
    settings = load_llm_settings()
    if settings.provider != "groq" or settings.model != "openai/gpt-oss-120b":
        raise SystemExit("Select the pinned Groq GPT-OSS 120B local baseline.")
    with local_services(real_model=True), sync_playwright() as playwright:
        results = run_evaluation(playwright.chromium, (DISCOVERY_CASES[3],))
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "provider": settings.provider,
        "model": settings.model,
        "reasoning_effort": settings.reasoning_effort,
        "prompt_version": PROMPT_VERSION,
        "schema_version": 3,
        "results": [result.as_dict() for result in results],
    }
    reports = Path(__file__).resolve().parent / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"real-browser-smoke-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "passed": all(result.passed for result in results)}))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
