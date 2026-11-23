"""Opt-in, bounded live evaluation: python -m eval.gemini_cart --repeats 2."""

import argparse
import asyncio
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from pydantic import ValidationError

from agent.llm import build_intent_request, build_llm_client, interpret_message, load_llm_settings
from agent.llm.contract import LLMChunk, ScriptedLLMClient
from agent.llm.intent import StructuredIntent
from agent.storefront import load_storefront_definition

CASES = (
    ("add_selected", "ضيفلي المنتج ده للسلة", {"intent": "cart_edit", "cart_operation": "add"}),
    (
        "add_variant",
        "ضيف صانع اللعب للسلة مقاس 43 لون اسود",
        {
            "intent": "cart_edit",
            "cart_operation": "add",
            "cart_target": "صانع اللعب",
            "constraints": {"size": "43", "color": "black"},
        },
    ),
    (
        "increase_owner",
        "عايزك تضيف اتنين كمان من كوتشي صانع اللعب",
        {
            "intent": "cart_edit",
            "cart_operation": "quantity",
            "cart_target": "صانع اللعب",
            "cart_quantity": 2,
            "cart_quantity_mode": "increase",
        },
    ),
    (
        "set_quantity",
        "خلي كمية صانع اللعب 3",
        {
            "intent": "cart_edit",
            "cart_operation": "quantity",
            "cart_target": "صانع اللعب",
            "cart_quantity": 3,
            "cart_quantity_mode": "set",
        },
    ),
    (
        "decrease_quantity",
        "قلل كمية صانع اللعب بواحد",
        {
            "intent": "cart_edit",
            "cart_operation": "quantity",
            "cart_target": "صانع اللعب",
            "cart_quantity": 1,
            "cart_quantity_mode": "decrease",
        },
    ),
    (
        "remove_named",
        "شيل صانع اللعب من السلة",
        {"intent": "cart_edit", "cart_operation": "remove", "cart_target": "صانع اللعب"},
    ),
    (
        "clear_owner",
        "شيل الحاجة اللي فالسلة كلها",
        {"intent": "mutate", "mutation_kind": "clear_cart"},
    ),
    ("clear_standard", "فضي السلة", {"intent": "mutate", "mutation_kind": "clear_cart"}),
)


def matches(actual, expected):
    return isinstance(actual, dict) and all(
        matches(actual.get(key), value) if isinstance(value, dict) else actual.get(key) == value
        for key, value in expected.items()
    )


def acceptable_intent(actual, expected):
    return (
        matches(actual, expected)
        and not actual.get("needs_clarification")
        and not actual.get("missing_fields")
        and not actual.get("conflicting_fields")
    )


async def run(repeats: int, model: str, output: Path, provider: str = "gemini"):
    values = {**dotenv_values(".env"), "LLM_PROVIDER": provider, "LLM_MODEL": model}
    client = build_llm_client(load_llm_settings(values))
    storefront = load_storefront_definition()
    rows = []
    for repeat in range(repeats):
        for case_id, message, expected in CASES:
            row = {
                "case": case_id,
                "repeat": repeat + 1,
                "message": message,
                "expected": expected,
                "passed": False,
            }
            request = build_intent_request(
                message, storefront=storefront, resolved_state={}, pending_clarification=None
            )
            stage = "provider"
            try:
                # Capture output before local validation so failures are attributable.
                text = "".join(
                    [
                        c.text or ""
                        async for c in client.complete(replace(request, response_validator=None))
                    ]
                )
                stage = "schema"
                raw = StructuredIntent.model_validate_json(text)
                row["raw_intent"] = raw.model_dump(exclude_none=True)
                stage = "boundary"
                intent = await interpret_message(
                    ScriptedLLMClient([[LLMChunk(text=text)]]),
                    message,
                    storefront=storefront,
                    resolved_state={},
                    pending_clarification=None,
                )
                row["validated_intent"] = intent.model_dump(exclude_none=True)
                row["passed"] = acceptable_intent(row["validated_intent"], expected)
                stage = "passed" if row["passed"] else "semantic_mismatch"
            except ValidationError as error:
                row["error"] = [
                    {"location": list(e["loc"]), "type": e["type"], "message": e["msg"]}
                    for e in error.errors()
                ]
            except Exception as error:
                # Never persist HTTP bodies, request headers or credentials.
                row["error"] = type(error).__name__
                if isinstance(error, ValueError):
                    row["validation_message"] = str(error)[:500]
            row["stage"] = stage
            row["metadata"] = asdict(client.call_metadata[-1])
            rows.append(row)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps({"model": model, "rows": rows}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"{case_id} [{repeat + 1}]: {stage}", flush=True)
            if row["metadata"]["failure_category"] in {"throttled", "http", "budget"}:
                print("Stopping live calls after provider rejection.", flush=True)
                return
            await asyncio.sleep(15 if provider == "gemini" else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, choices=range(1, 4), default=2)
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--provider", choices=["gemini", "openrouter"], default="gemini")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"eval/reports/gemini-cart-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"),
    )
    args = parser.parse_args()
    asyncio.run(run(args.repeats, args.model, args.output, args.provider))


if __name__ == "__main__":
    main()
