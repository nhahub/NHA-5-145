"""Opt-in replacement qualification; frozen milestone plus read-only advice flows."""

import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from agent.inference.ledger import AllowanceLedger
from agent.llm import load_llm_settings
from eval.milestone import BASE, Flow
from eval.milestone_cases import CASES, Case
from eval.milestone_report import summarize_run
from eval.qualification_claim import claim_qualification
from eval.services import local_services

# Synthetic/exposed qualification cases, never unseen-evaluation evidence or runtime rules.
ADVICE_CASES = (
    (
        "advice-egyptian",
        (
            "عندي بنطلون اسود ومش عارفه اختار قميص.. عايزه حاجه هاديه مش فاقعه، تنصحني بايه؟",
            "طب ليه ده احسن ليا؟ مش عايزه مجرد قايمه اسماء",
        ),
    ),
    (
        "advice-franco",
        (
            "3andi pantalon eswed w 3ayez shirt simple msh flashy .. tensa7ni be eh?",
            "tab leh da? ana msh 3ayez 7aga formal awi",
        ),
    ),
    (
        "advice-mixed",
        (
            "عايز كوتشي running size 43 تحت 2000 egp بس مش leather.. انصحني باللي موجود",
            "طب هينفع للشغل والمشي كمان ولا ايه اللي مش متأكد منه؟",
        ),
    ),
    (
        "advice-comparison",
        (
            "قارنلي قميص رسمي وقميص قطني.. مش فاهم فرقهم، انا محتاجه للشغل والخروجات",
            "طب رشحلي واحد وليه، مش لازم تقول انك متأكد من حاجه مش مكتوبه",
        ),
    ),
    (
        "advice-unknown",
        ("قبل ما اشتري ماراثون القاهرة، عايز رأيك وهل عليه ضمان سنتين وتقييمات ناس حقيقيه؟",),
    ),
    (
        "advice-exact-reason",
        ("عايز كوتشي جري size 44 لون اسود تحت 2000 جنيه.. قوللي ليه اللي لقيته مناسب",),
    ),
)


def check_advice(flow, messages):
    initial = flow.cart()
    for message in messages:
        turn = flow.done(message)
        summary = next(e["data"]["summary"] for e in turn["events"] if e["event"] == "done")
        assert len(summary.strip()) >= 30, "Advice must include an explanation"
        assert not any(e["event"] == "action" for e in turn["events"]), (
            "Read-only advice emitted Action"
        )
        assert flow.cart() == initial, "Advice changed authoritative cart state"
    calls = flow.metrics()[flow.metrics_before :]
    advice_calls = [c for c in calls if c["prompt_version"] == "advice-v4" and not c["failure"]]
    assert len(advice_calls) >= len(messages), "No validated advice response for each turn"
    assert not flow.mutations
    assert flow.cart()["lines"] == BASE


def main():
    if os.environ.get("MODEL_QUALIFICATION") != "1":
        raise SystemExit("Explicit MODEL_QUALIFICATION=1 is required")
    settings = load_llm_settings()
    if settings.provider != "openrouter" or settings.model != "google/gemini-3.5-flash-lite":
        raise SystemExit("This frozen qualification selects only Gemini 3.5 Flash-Lite")
    approved_set = os.environ.get("MODEL_QUALIFICATION_APPROVED_SET", "1")
    if approved_set not in {"1", "2", "3", "4"}:
        raise SystemExit("No further qualification set is authorized")
    maximum_cost, maximum_calls = 0.25, 120
    if approved_set == "4":
        # Explicit owner-approved extra allowance, never a reset of prior spending.
        from agent.llm.intent_pipeline import PROMPT_VERSION

        if PROMPT_VERSION != "intent-v32":
            raise SystemExit("The approved final set requires the reviewed intent-v32 prompt")
        maximum_cost = 0.12
    if approved_set in {"2", "3"}:
        diagnostic = json.loads(
            Path("eval/reports/gemini-3.5-diagnostic-approved-2.json").read_text(encoding="utf-8")
        )
        assert diagnostic["budget"]["posts"] == 1
        assert 0 <= diagnostic["budget"]["accounted_cost"] <= 0.02
        maximum_cost -= diagnostic["budget"]["accounted_cost"]
        maximum_calls -= 1
    suffix = "" if approved_set == "1" else "-approved-" + approved_set
    marker = Path(f"eval/reports/gemini-3.5-flash-lite-qualification-claim{suffix}.json")
    continuation = os.environ.get("MODEL_QUALIFICATION_CONTINUE") == "1"
    if approved_set == "3":
        if continuation:
            raise SystemExit("The final protocol is one new set, not a continuation")
        prior_marker = Path(
            "eval/reports/gemini-3.5-flash-lite-qualification-claim-approved-2.json"
        )
        prior_folder = Path(
            json.loads(prior_marker.read_text(encoding="utf-8"))["report"]
        ).resolve()
        if prior_folder.parent != Path("eval/reports").resolve():
            raise SystemExit("Prior accounting must remain in the owned report path")
        ledger_policy = json.loads(
            (prior_folder / "continuation-ledger.json").read_text(encoding="utf-8")
        )
        ledger_path = (prior_folder / "continuation.sqlite").resolve()
        ledger = AllowanceLedger(ledger_path, ledger_policy["identity"])
        maximum_calls = ledger.status()["attempts"] + 120
        if maximum_calls > 200:
            raise SystemExit("Final protocol exceeds the fixed global POST bound")
        os.environ["MODEL_QUALIFICATION_CONTINUE"] = "1"
        os.environ["MODEL_QUALIFICATION_LEDGER_PATH"] = str(ledger_path)
        os.environ["MODEL_QUALIFICATION_LEDGER_ID"] = ledger_policy["identity"]
        folder = Path("eval/reports") / (
            "model-qualification-final-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        folder.mkdir(parents=True, exist_ok=False)
        claim_qualification(marker, folder, maximum_cost=maximum_cost)
        (folder / "budget.jsonl").touch(exist_ok=False)
    elif continuation:
        if approved_set not in {"2", "4"}:
            raise SystemExit("Only an explicitly resumed interrupted set may continue")
        folder = Path(json.loads(marker.read_text(encoding="utf-8"))["report"]).resolve()
        if folder.parent != Path("eval/reports").resolve():
            raise SystemExit("Qualification report must remain in the owned collection path")
        ledger_policy = json.loads(
            (folder / "continuation-ledger.json").read_text(encoding="utf-8")
        )
        os.environ["MODEL_QUALIFICATION_LEDGER_PATH"] = str(
            (folder / "continuation.sqlite").resolve()
        )
        os.environ["MODEL_QUALIFICATION_LEDGER_ID"] = ledger_policy["identity"]
    else:
        folder = Path("eval/reports") / (
            "model-qualification-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        folder.mkdir(parents=True, exist_ok=False)
        claim_qualification(marker, folder, maximum_cost=maximum_cost)
    os.environ["MILESTONE_EVAL"] = "1"
    os.environ["MODEL_QUALIFICATION_JOURNAL"] = str((folder / "budget.jsonl").resolve())
    os.environ["MODEL_QUALIFICATION_MAXIMUM_COST"] = str(maximum_cost)
    os.environ["MODEL_QUALIFICATION_MAXIMUM_CALLS"] = str(maximum_calls)
    report = {
        "model": settings.model,
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "approved_set": approved_set,
        "maximum_cost_usd": maximum_cost,
        "maximum_model_calls": maximum_calls,
        "maximum_runs": 1,
        "cases_sha256": hashlib.sha256(
            json.dumps([asdict(c) for c in CASES], sort_keys=True).encode()
        ).hexdigest(),
        "supplemental_cases": ADVICE_CASES,
        "source_sha256": {
            path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for root in ("agent", "bridge/src", "panel/src", "store/src", "eval")
            for path in sorted(Path(root).rglob("*"))
            if path.suffix in {".py", ".ts"} and "reports" not in path.parts
        },
        "milestone": [],
        "advice": [],
        "advice_manual_review": "pending",
    }
    if approved_set == "3":
        report["prior_report"] = str(prior_folder / "results.json")
        report["accounting_at_start"] = ledger.status()
        report["protocol_revision"] = (
            "Fresh full verification after general advice-boundary and harness fixes. "
            "Prior failures retained; same cumulative allowance, no refill. "
            "Owner reprioritized mandatory replacement."
        )
    elif approved_set == "4":
        report["protocol_revision"] = (
            "Owner approved one additional set capped at $0.12 inside the unchanged $2 key "
            "limit. Reviewed intent-v32 clarifies literal search text versus type filters "
            "and preserves explicit features/exclusions. Prior failed cohorts are retained; "
            "this is post-fix verification, not an initial-pass or unseen-evaluation claim."
        )
    result_file = folder / "results.json"
    if continuation:
        current_sources = report["source_sha256"]
        report = json.loads(result_file.read_text(encoding="utf-8"))
        assert report["approved_set"] == approved_set and report["model"] == settings.model
        assert (
            report["maximum_cost_usd"] == maximum_cost
            and report["maximum_model_calls"] == maximum_calls
        )
        for path in (
            "agent/llm/intent.py",
            "agent/llm/intent_pipeline.py",
            "agent/llm/intent_wire.py",
            "agent/llm/provider_schema.py",
            "agent/advice.py",
            "agent/catalogue_retrieval.py",
        ):
            assert report["source_sha256"][path] == current_sources[path], (
                "Frozen interpretation/advice inputs changed"
            )
        report.setdefault("continuations", []).append(
            {
                "reason": "Interrupted telemetry GET; retain rows and every prior charge",
                "source_sha256": current_sources,
                "reasoning": {"effort": "minimal", "exclude": True},
            }
        )
        if approved_set == "4":
            report["continuations"][-1]["reason"] = (
                "Browser page setup interrupted before the next case/model call. "
                "Owner notified: continue only unexecuted cases in the same set; retain "
                "all prior rows, failures and charges within the original $0.12/120 POSTs."
            )
            report.setdefault("setup_interruptions", []).append(report.pop("setup_failure"))
        report["automated_passed"] = False
    report["reasoning"] = {"effort": "minimal", "exclude": True}

    def save():
        result_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    with (
        local_services(real_model=True, agent_app="eval.milestone_server:app"),
        sync_playwright() as pw,
    ):
        browser = pw.chromium.launch(headless=True)
        try:
            selected = [(c, None) for c in CASES] + [
                (Case(name, "advice", messages[0]), messages) for name, messages in ADVICE_CASES
            ]
            if approved_set in {"3", "4"}:
                exact = (
                    "عايز رأيك في كوتشي جري اسود مقاس 42 لحد 2000 جنيه.. قوللي ليه اللي لقيته مناسب"
                )
                selected.append((Case("advice-verified-exact", "advice", exact), (exact,)))
            for case, messages in selected:
                if any(
                    row["case_id"] == case.case_id for row in report["milestone"] + report["advice"]
                ):
                    continue
                flow, failure = None, None
                try:
                    flow = Flow(browser, case)
                    if "catalogue_snapshot" not in report:
                        catalogue = flow.api.get("http://localhost:4000/__catalogue/v1/products")
                        assert catalogue.status == 200
                        report["catalogue_snapshot"] = catalogue.json()
                        save()
                    if messages:
                        check_advice(flow, messages)
                    else:
                        flow.check()
                except Exception as error:
                    failure = {
                        "category": type(error).__name__,
                        "detail": str(error).split("\n", 1)[0][:300],
                    }
                if flow is None:
                    report["setup_failure"] = failure
                    save()
                    raise RuntimeError("Qualification setup failed; partial evidence retained")
                row = flow.finish(failure)
                report["advice" if messages else "milestone"].append(row)
                save()
                print(
                    case.case_id,
                    "PASS" if failure is None else "FAIL " + failure["detail"],
                    flush=True,
                )
                if any(
                    c["failure"] in {"OpenRouterBudgetError", "HTTPStatusError"}
                    for c in row["model_calls"]
                ):
                    report["automated_passed"] = False
                    report["budget"] = flow.budget_summary
                    report["stop_reason"] = "Provider rejection or allowance exhaustion"
                    save()
                    raise RuntimeError("Qualification stopped; no automatic new set")
            report["milestone_summary"] = summarize_run(
                report["milestone"], expected_ids=[c.case_id for c in CASES]
            )
            report["budget"] = flow.budget_summary
            report["automated_passed"] = report["milestone_summary"]["gate_passed"] and all(
                r["passed"] for r in report["advice"]
            )
            save()
        finally:
            browser.close()
    print(
        json.dumps(
            {
                "report": str(result_file),
                "summary": report.get("milestone_summary"),
                "budget": report.get("budget"),
                "automated_passed": report.get("automated_passed"),
            }
        ),
        flush=True,
    )
    return 0 if report.get("automated_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
