"""Opt-in live acceptance for semantic recommendations and original 07E requests."""

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent.llm import load_llm_settings
from agent.llm.intent_pipeline import PROMPT_VERSION
from eval.cases import OWNER_07E_CASES, STYLING_07E_CASE, EvaluationAssertion, EvaluationCase
from eval.runner import run_evaluation
from eval.services import local_services

REPAIR_CASES = (
    EvaluationCase(
        case_id="owner-green-brown-outfit",
        message="عندي طقم جامد تيشيرت اخضر وبنطلون بني رملي كده عايز كوتشي ليه تقترح ايه",
        language="ar",
        timeout_ms=60_000,
        assertions=(
            EvaluationAssertion("panel_count", ".suggestion-styling_suggestion", "3"),
            EvaluationAssertion("panel_count", ".suggestion-alternative", "0"),
            EvaluationAssertion("url_matches", r"^http://localhost:4000/$"),
        ),
    ),
    EvaluationCase(
        case_id="heldout-outfit-size-budget",
        message="لابس جينز ازرق وقميص ابيض، رشحلي جزمة تكمل اللبس مقاس 43 تحت 2500 جنيه",
        language="ar",
        timeout_ms=60_000,
        assertions=(
            EvaluationAssertion("panel_count", ".suggestion-styling_suggestion", "3"),
            EvaluationAssertion("panel_count", ".suggestion-alternative", "0"),
        ),
    ),
    EvaluationCase(
        case_id="semantic-open-account",
        message="وديني عالحساب",
        language="ar",
        timeout_ms=60_000,
        assertions=(EvaluationAssertion("url_matches", r"/account$"),),
    ),
    STYLING_07E_CASE,
    *OWNER_07E_CASES,
)


def main() -> int:
    if os.environ.get("LLM_BROWSER_SMOKE") != "1":
        raise SystemExit("Set LLM_BROWSER_SMOKE=1 to run credentialed browser acceptance.")
    settings = load_llm_settings()
    if settings.provider != "groq" or settings.model != "openai/gpt-oss-120b":
        raise SystemExit("This acceptance run uses the pinned local Groq baseline.")
    selected = os.environ.get("SEMANTIC_CASE")
    cases = [case for case in REPAIR_CASES if selected in {None, case.case_id}]
    if not cases:
        raise SystemExit("Unknown SEMANTIC_CASE")
    results = []
    with local_services(real_model=True), sync_playwright() as playwright:
        for index, case in enumerate(cases):
            if index:
                time.sleep(45)
            result = run_evaluation(playwright.chromium, (case,))[0]
            results.append(result)
            print(
                json.dumps(
                    {"case": case.case_id, "passed": result.passed, "failure": result.failure}
                ),
                flush=True,
            )
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "provider": settings.provider,
        "model": settings.model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": 3,
        "results": [result.as_dict() for result in results],
    }
    reports = Path(__file__).resolve().parent / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"semantic-repair-browser-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "passed": all(result.passed for result in results)}))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
