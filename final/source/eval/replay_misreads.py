"""On-demand replay of captured model requests (never run in CI).

Build the private case files once from the owner's local debug captures:

    python -m eval.replay_misreads build-cases --captures <captures.jsonl>

Print the plan and estimated cost with zero model calls:

    python -m eval.replay_misreads run --repeats 5 --dry-run

Run for real (spends money; the cap is mandatory):

    python -m eval.replay_misreads run --repeats 5 --max-spend 0.10

Two modes are compared per case. "captured" sends the captured request as it was.
"current" keeps the captured context and messages but swaps in the CURRENT prompt text
and response schema from the live builders (build_intent_request for interpreter calls,
the catalogue decision builder for decision calls). Rebuilding from the message alone is
not feasible: the capture holds the rendered context (snapshot, resolved state, history),
not the objects that produced it, so the context line/message is reused verbatim and only
the instruction text, schema, prompt/schema version and token limit come from today's code.

Case files live under work/replay-cases/ (gitignored, never committed) because they
contain Shopper text and storefront data. Expectations are data, see evaluate().
"""

import argparse
import asyncio
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.llm.contract import LLMChunk, LLMMessage, LLMRequest

CASES_DIR = Path("work/replay-cases")
MODES = ("captured", "current")
MODEL = "google/gemini-3.5-flash-lite"
# Conservative USD per million tokens: the OpenRouter price ceiling enforced by
# agent.llm.openrouter.OpenRouterClient.price_ceiling (actual flash-lite prices are lower).
PROMPT_USD_PER_M = 0.3
COMPLETION_USD_PER_M = 2.5
# Rough upper-bound characters per token for Arabic-heavy JSON text.
CHARS_PER_TOKEN = 2.5
MIN_COMPLETION_TOKENS = 300

# Expectations are data: {"all": [cond...]} or {"any": [cond...]};
# cond = {"path": "a.b", "equals" | "not_equals" | "in": value}.
# A value of "$message" means the current request text.
_REPLACE = {"all": [{"path": "intent", "equals": "replace"}]}
_CLEAR = {
    "all": [
        {"path": "intent", "equals": "mutate"},
        {"path": "mutation_kind", "equals": "clear_cart"},
    ]
}
_QUOTE = {
    "any": [
        {"path": "cart_source", "equals": "$message"},
        {"path": "intent", "not_equals": "cart_edit"},
    ]
}
_OPEN = {
    "any": [
        {"path": "intent", "equals": "open_product"},
        {"path": "request_mode", "equals": "open"},
    ]
}
_ROUTE_EXECUTE = {"all": [{"path": "kind", "equals": "execute"}]}
_SUBMIT = {
    "all": [
        {"path": "intent", "equals": "mutate"},
        {"path": "mutation_kind", "equals": "submit_checkout"},
    ]
}
# (case id, label, 1-based capture line, expectation or None = by call kind for B5).
CASE_TABLE: tuple[tuple[str, str, int, dict | None], ...] = (
    ("b2-182", "B2 later step: colour swap read as replace", 182, _REPLACE),
    ("b3-091", "B3 cart add quotes the current request", 91, _QUOTE),
    ("b3-046", "B3 later step quotes the current request", 46, _QUOTE),
    ("b4-151", "B4 empty the cart after an Undo is clear_cart", 151, _CLEAR),
    *(
        (f"b5-{n}", f"B5 open-by-name in a fresh session (capture {n})", n, None)
        for n in range(100, 108)
    ),
    ("b7-180", "B7 place the order is the guarded submission", 180, _SUBMIT),
    ("b8-162", "B8 colour swap is replace, not unsupported", 162, _REPLACE),
    ("sticky-057", "Sticky topic: empty the cart is clear_cart", 57, _CLEAR),
)


def _get(data: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(data, Mapping):
            return None
        data = data.get(part)
    return data


def _condition(output: Mapping, cond: Mapping, message: str) -> bool:
    actual = _get(output, cond["path"])
    for op in ("equals", "not_equals", "in"):
        if op in cond:
            want = message if cond[op] == "$message" else cond[op]
            if op == "equals":
                return actual == want
            if op == "not_equals":
                return actual != want
            return actual in want
    raise ValueError(f"Unknown expectation condition: {dict(cond)}")


def evaluate(expect: Mapping, output: Mapping | None, message: str) -> bool:
    """True when the parsed model output satisfies the data expectation."""
    if not isinstance(output, Mapping):
        return False
    if "all" in expect:
        return all(_condition(output, c, message) for c in expect["all"])
    if "any" in expect:
        return any(_condition(output, c, message) for c in expect["any"])
    raise ValueError("Expectation needs 'all' or 'any'")


def parse_output(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        value = json.loads(match.group(0)) if match else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


@dataclass(frozen=True)
class Case:
    case_id: str
    label: str
    kind: str  # "intent" | "decision"
    message: str
    expect: dict
    captured: dict


def _case_kind(capture: Mapping) -> str:
    version = str(capture["prompt_version"])
    return "decision" if version.startswith("catalogue-decision") else "intent"


def _message_of(capture: Mapping, kind: str) -> str:
    last = capture["messages"][-1]["content"]
    return json.loads(last)["message"] if kind == "decision" else last


def build_case_files(captures: Path, out_dir: Path) -> list[Path]:
    lines = captures.read_text(encoding="utf-8").splitlines()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for case_id, label, line, expect in CASE_TABLE:
        capture = json.loads(lines[line - 1])
        kind = _case_kind(capture)
        if expect is None:
            expect = _OPEN if kind == "intent" else _ROUTE_EXECUTE
        case = {
            "case_id": case_id,
            "label": label,
            "kind": kind,
            "source_line": line,
            "message": _message_of(capture, kind),
            "expect": expect,
            "captured": capture,
        }
        path = out_dir / f"{case_id}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def load_cases(directory: Path) -> list[Case]:
    cases = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            Case(
                raw["case_id"],
                raw["label"],
                raw["kind"],
                raw["message"],
                raw["expect"],
                raw["captured"],
            )
        )
    if not cases:
        raise FileNotFoundError(f"No case files in {directory}; run build-cases first")
    return cases


def _request_from(capture: Mapping, **overrides: Any) -> LLMRequest:
    values = {
        "system": capture["system"],
        "messages": tuple(
            LLMMessage(role=m["role"], content=m["content"]) for m in capture["messages"]
        ),
        "response_schema": capture["response_schema"],
        "prompt_version": capture["prompt_version"],
        "schema_version": capture["schema_version"],
        "max_tokens": capture["max_tokens"],
        "temperature": capture["temperature"],
        "provider_attempt_limit": 1,
    }
    return LLMRequest(**{**values, **overrides})


def captured_request(case: Case) -> LLMRequest:
    return _request_from(case.captured)


def current_request(case: Case) -> LLMRequest:
    """Captured context/messages with today's prompt text, schema and versions."""
    from agent.catalogue_retrieval import RetrievalBudget, _request
    from agent.llm import build_intent_request
    from agent.storefront import load_storefront_definition

    storefront = load_storefront_definition()
    if case.kind == "intent":
        fresh = build_intent_request(
            case.message, storefront=storefront, resolved_state={}, pending_clarification=None
        )
        context_line = case.captured["system"].split("\n", 1)[0]
        system = context_line + "\n" + fresh.system.split("\n", 1)[1]
    else:
        fresh = _request(case.message, {}, None, storefront, [], None, RetrievalBudget())
        system = fresh.system
    return _request_from(
        case.captured,
        system=system,
        response_schema=fresh.response_schema,
        prompt_version=fresh.prompt_version,
        schema_version=fresh.schema_version,
        max_tokens=fresh.max_tokens,
    )


def estimate_call_cost(request: LLMRequest, expected_output: str = "") -> float:
    chars = len(request.system) + sum(len(m.content) for m in request.messages)
    chars += len(json.dumps(request.response_schema or {}))
    completion = min(
        request.max_tokens, max(MIN_COMPLETION_TOKENS, len(expected_output) / CHARS_PER_TOKEN)
    )
    prompt_tokens = chars / CHARS_PER_TOKEN
    return (prompt_tokens * PROMPT_USD_PER_M + completion * COMPLETION_USD_PER_M) / 1_000_000


def plan(cases: list[Case], repeats: int, builder: Callable[[Case], LLMRequest]) -> dict:
    total = 0.0
    for case in cases:
        for mode in MODES:
            request = captured_request(case) if mode == "captured" else builder(case)
            total += repeats * estimate_call_cost(request, str(case.captured.get("output", "")))
    return {
        "cases": len(cases),
        "repeats": repeats,
        "calls": len(cases) * len(MODES) * repeats,
        "estimated_cost_usd": total,
    }


def format_plan(summary: Mapping) -> str:
    return (
        f"{summary['cases']} cases x {len(MODES)} modes x {summary['repeats']} repeats = "
        f"{summary['calls']} calls; estimated cost ${summary['estimated_cost_usd']:.4f} "
        f"(model {MODEL}, conservative ${PROMPT_USD_PER_M}/${COMPLETION_USD_PER_M} per M tokens)"
    )


async def _call(client: Any, request: LLMRequest) -> str:
    parts = []
    async for chunk in client.complete(request):
        if isinstance(chunk, LLMChunk) and chunk.text:
            parts.append(chunk.text)
    return "".join(parts)


def _actual_cost(client: Any, before: int, fallback: float) -> float:
    metadata = list(getattr(client, "call_metadata", ()))[before:]
    costs = [
        m.usage["cost"]
        for m in metadata
        if isinstance(getattr(m, "usage", None), dict) and "cost" in m.usage
    ]
    return float(sum(costs)) if costs else fallback


async def run_replay(
    cases: list[Case],
    client: Any,
    *,
    repeats: int,
    max_spend: float,
    builder: Callable[[Case], LLMRequest] = current_request,
) -> dict:
    """Run repeats x cases x modes, stopping before the spend would exceed max_spend."""
    results = {c.case_id: {m: [0, 0] for m in MODES} for c in cases}  # [passed, total]
    spent = 0.0
    calls = 0
    stopped = False
    for _ in range(repeats):
        for case in cases:
            for mode in MODES:
                request = captured_request(case) if mode == "captured" else builder(case)
                estimate = estimate_call_cost(request, str(case.captured.get("output", "")))
                if spent + estimate > max_spend:
                    stopped = True
                    break
                before = len(getattr(client, "call_metadata", ()))
                try:
                    text = await _call(client, request)
                except Exception:  # a provider failure is a failed run, never a crash
                    text = ""
                calls += 1
                spent += _actual_cost(client, before, estimate)
                passed = evaluate(case.expect, parse_output(text), case.message)
                results[case.case_id][mode][0] += int(passed)
                results[case.case_id][mode][1] += 1
            if stopped:
                break
        if stopped:
            break
    return {"results": results, "spent_usd": spent, "calls": calls, "stopped_on_cap": stopped}


def format_table(cases: list[Case], report: Mapping) -> str:
    rows = [f"{'case':<12}{'captured':>10}{'current':>10}  label"]
    for case in cases:
        cells = ["{}/{}".format(*report["results"][case.case_id][mode]) for mode in MODES]
        rows.append(f"{case.case_id:<12}{cells[0]:>10}{cells[1]:>10}  {case.label}")
    rows.append(
        f"calls={report['calls']} actual spend=${report['spent_usd']:.4f}"
        + (" (STOPPED at spend cap)" if report["stopped_on_cap"] else "")
    )
    return "\n".join(rows)


def _real_client() -> Any:
    from dotenv import dotenv_values

    from agent.llm import build_llm_client, load_llm_settings

    values = {**dotenv_values(".env"), "LLM_PROVIDER": "openrouter", "LLM_MODEL": MODEL}
    return build_llm_client(load_llm_settings(values))


def main(argv: list[str] | None = None, *, client_factory: Callable[[], Any] = _real_client) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-cases", help="extract case files from captures.jsonl")
    build.add_argument("--captures", type=Path, required=True)
    build.add_argument("--out", type=Path, default=CASES_DIR)
    run = sub.add_parser("run", help="replay the cases")
    run.add_argument("--cases", type=Path, default=CASES_DIR)
    run.add_argument("--repeats", type=int, default=5)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--max-spend", type=float, help="USD cap; required for real runs")
    args = parser.parse_args(argv)

    if args.command == "build-cases":
        for path in build_case_files(args.captures, args.out):
            print(path)
        return 0
    if not args.dry_run and (args.max_spend is None or args.max_spend <= 0):
        parser.error("--max-spend (positive) is required for a real run")
    cases = load_cases(args.cases)
    print(format_plan(plan(cases, args.repeats, current_request)))
    if args.dry_run:
        print("Dry run: zero model calls made.")
        return 0
    report = asyncio.run(
        run_replay(cases, client_factory(), repeats=args.repeats, max_spend=args.max_spend)
    )
    print(format_table(cases, report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
