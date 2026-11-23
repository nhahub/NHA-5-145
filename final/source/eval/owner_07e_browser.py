"""Run the three unchanged owner-written 07E requests through the real browser path."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent.llm import load_llm_settings
from agent.llm.intent_pipeline import PROMPT_VERSION
from eval.cases import OWNER_07E_CASES, STYLING_07E_CASE
from eval.runner import run_evaluation
from eval.services import local_services


def main() -> int:
    if os.environ.get("LLM_BROWSER_SMOKE") != "1":
        raise SystemExit("Set LLM_BROWSER_SMOKE=1 to run the real-model browser gate.")
    settings = load_llm_settings()
    if settings.provider != "groq" or settings.model != "openai/gpt-oss-120b":
        raise SystemExit("Select the pinned Groq GPT-OSS 120B local baseline.")
    selected = os.environ.get("OWNER_07E_ONLY")
    available = OWNER_07E_CASES + ((STYLING_07E_CASE,) if selected is not None else ())
    cases = tuple(case for case in available if selected in {None, case.case_id})
    timeout_override = os.environ.get("OWNER_07E_TIMEOUT_MS")
    if timeout_override is not None:
        cases = tuple(replace(case, timeout_ms=int(timeout_override)) for case in cases)
    with local_services(real_model=True), sync_playwright() as playwright:
        results = run_evaluation(playwright.chromium, cases, inter_case_delay_seconds=45)
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
    path = reports / f"owner-07e-browser-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "passed": all(result.passed for result in results)}))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
