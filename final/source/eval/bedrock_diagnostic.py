"""Prepare by default; one separately approved Bedrock diagnostic, never a full set."""

import argparse
import asyncio
import hashlib
import json
import re
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from agent.inference.ledger import AllowanceLedger
from agent.llm.bedrock import BedrockClient
from agent.llm.config import load_llm_settings
from agent.llm.contract import ScriptedLLMClient
from agent.llm.intent_pipeline import PROMPT_VERSION, build_intent_request
from agent.storefront import load_storefront_definition
from eval.intent_benchmark import load_intent_corpus, score_case

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs/cap05-bedrock-diagnostic-001"
RESERVATION = Decimal("0.015")
MAXIMUM_COST = Decimal("0.02")
MODEL = "openai.gpt-oss-20b-1:0"
PROFILE = "cap05-stockholm"


def _request():
    case = load_intent_corpus().cases[0]
    if case.case_id != "ar-01":
        raise ValueError("The diagnostic case changed")
    request = build_intent_request(
        case.message,
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )
    return case, replace(request, provider_attempt_limit=1, attempt_id="bedrock-diagnostic-001")


def request_hash(request):
    payload = {
        "system": request.system,
        "messages": [asdict(m) for m in request.messages],
        "response_schema": request.response_schema,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_plan():
    case, request = _request()
    source = hashlib.sha256()
    for path in sorted(
        [
            *ROOT.joinpath("agent").rglob("*.py"),
            Path(__file__).resolve(),
            ROOT / "eval/intent_benchmark.py",
        ]
    ):
        source.update(path.relative_to(ROOT).as_posix().encode())
        source.update(path.read_bytes())
    return {
        "v": 1,
        "model": MODEL,
        "region": "eu-north-1",
        "profile": PROFILE,
        "case_id": case.case_id,
        "message": case.message,
        "prompt_version": PROMPT_VERSION,
        "schema_version": 9,
        "max_tokens": request.max_tokens,
        "temperature": 0,
        "maximum_calls": 1,
        "maximum_cost_usd": str(MAXIMUM_COST),
        "reservation_usd": str(RESERVATION),
        "sdk_retries": 0,
        "request_sha256": request_hash(request),
        "corpus_sha256": hashlib.sha256(
            ROOT.joinpath("eval/intent-corpus.json").read_bytes()
        ).hexdigest(),
        "source_sha256": source.hexdigest(),
    }


def prepare(folder):
    plan = build_plan()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "plan.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != plan:
            raise ValueError("The reviewed diagnostic plan no longer matches source")
    else:
        with path.open("x", encoding="utf-8") as file:
            json.dump(plan, file, ensure_ascii=False, indent=2)
    return plan


@contextmanager
def live_client():
    import boto3
    from botocore.config import Config

    settings = load_llm_settings(
        {"LLM_PROVIDER": "bedrock", "LLM_MODEL": MODEL, "AWS_REGION": "eu-north-1"}
    )
    session = boto3.Session(profile_name=PROFILE, region_name="eu-north-1")
    with closing(
        session.client(
            "bedrock-runtime",
            config=Config(
                connect_timeout=5,
                read_timeout=20,
                retries={"total_max_attempts": 1, "mode": "standard"},
                ignore_configured_endpoint_urls=True,
            ),
        )
    ) as sdk:
        yield BedrockClient(settings, sdk_client=sdk)


async def run_once(folder, approval_reference, *, client_factory=None):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", approval_reference):
        raise ValueError("Explicit owner approval reference is required")
    plan = prepare(folder)
    claim = {
        "approval_reference": approval_reference,
        "plan": plan,
        "created_at": datetime.now(UTC).isoformat(),
    }
    # The exclusive claim survives errors, cancellation and process restart.
    with (folder / "claim.json").open("x", encoding="utf-8") as file:
        json.dump(claim, file, ensure_ascii=False, indent=2)
    identity = AllowanceLedger.initialize(folder / "allowance.sqlite", MAXIMUM_COST)
    claim["ledger_identity"] = identity
    (folder / "claim.json").write_text(json.dumps(claim, indent=2), encoding="utf-8")
    ledger = AllowanceLedger(folder / "allowance.sqlite", identity)
    ledger.reserve("bedrock-diagnostic-001", RESERVATION)
    report = {
        "plan": plan,
        "state": "reserved",
        "cost_usd": None,
        "estimated_cost_usd": None,
        "failure": None,
        "semantic_check": None,
        "metadata": None,
        "ledger": ledger.status(),
    }
    result_path = folder / "result.json"
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    client = None
    try:
        with (client_factory or live_client)() as client:
            case, request = _request()
            if request_hash(request) != plan["request_sha256"]:
                raise ValueError("The request changed after diagnostic preparation")
            chunks = [chunk async for chunk in client.complete(request)]
            # Reuse corpus scoring locally; even a repair can only enter this
            # scripted double, never the credentialed provider a second time.
            checked = await score_case(
                case, ScriptedLLMClient([chunks]), load_storefront_definition()
            )
            report["semantic_check"] = asdict(checked)
            report["state"] = "completed"
    except BaseException as error:
        report["failure"] = type(error).__name__
        report["state"] = "canceled" if isinstance(error, asyncio.CancelledError) else "failed"
        if not isinstance(error, Exception):
            raise
    finally:
        ledger.ensure_accounted("bedrock-diagnostic-001")
        metadata = getattr(client, "call_metadata", ())
        if metadata:
            report["metadata"] = asdict(metadata[-1])
            usage = metadata[-1].usage
            if usage:
                report["estimated_cost_usd"] = str(
                    (
                        Decimal(usage["prompt_tokens"]) * Decimal("0.07")
                        + Decimal(usage["completion_tokens"]) * Decimal("0.30")
                    )
                    / Decimal(1_000_000)
                )
        report["ledger"] = ledger.status()
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("prepare", "run"), default="prepare")
    parser.add_argument("--approval-reference", default="")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        print(json.dumps(prepare(OUTPUT_ROOT), ensure_ascii=False, indent=2))
        return 0
    if not args.approval_reference:
        parser.error("Explicit owner approval reference is required before run")
    report = asyncio.run(run_once(OUTPUT_ROOT, args.approval_reference))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["semantic_check"] and report["semantic_check"]["exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
