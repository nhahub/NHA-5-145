"""Redacted diagnostics for the unchanged owner 07E intent cases."""

import asyncio
import json
import os

import httpx
from pydantic import ValidationError

from agent.llm import build_llm_client, interpret_message, load_llm_settings
from agent.storefront import load_storefront_definition
from eval.cases import OWNER_07E_CASES, STYLING_07E_CASE


async def main() -> None:
    if os.environ.get("LLM_SMOKE_TEST") != "1":
        raise SystemExit("Set LLM_SMOKE_TEST=1 for the credentialed intent probe.")
    settings = load_llm_settings()
    client = build_llm_client(settings)
    storefront = load_storefront_definition()
    selected = os.environ.get("OWNER_07E_ONLY")
    for case in (*OWNER_07E_CASES, STYLING_07E_CASE):
        if selected is not None and case.case_id != selected:
            continue
        try:
            intent = await interpret_message(
                client,
                case.message,
                storefront=storefront,
                resolved_state={},
                pending_clarification=None,
            )
            outcome = {
                "case_id": case.case_id,
                "intent": intent.intent,
                "constraints": intent.constraints.model_dump(exclude_none=True),
                "requirements": [
                    {"kind": item.kind, "value": item.value}
                    for item in intent.catalogue_requirements
                ],
                "price_preference": (
                    intent.price_preference.value if intent.price_preference else None
                ),
                "owned_item": (
                    intent.owned_item.model_dump(exclude_none=True) if intent.owned_item else None
                ),
                "desired_wear_position": intent.desired_wear_position,
                "needs_clarification": intent.needs_clarification,
                "missing_fields": intent.missing_fields,
            }
        except Exception as error:
            outcome = {"case_id": case.case_id, "error_type": type(error).__name__}
            if isinstance(error, httpx.HTTPStatusError):
                outcome["http_status"] = error.response.status_code
                outcome["retry_after"] = error.response.headers.get("retry-after")
                outcome["token_reset"] = error.response.headers.get("x-ratelimit-reset-tokens")
            if isinstance(error, ValidationError):
                outcome["validation_fields"] = [
                    ".".join(str(part) for part in item["loc"])
                    for item in error.errors(include_input=False)
                ]
            elif isinstance(error, ValueError):
                known = (
                    "Catalogue requirement source does not support its value",
                    "Catalogue requirement lacks a valid Shopper source span",
                    "Price preference source does not support its value",
                    "Price preference lacks a valid Shopper source span",
                    "Product request was not interpreted as discovery",
                )
                outcome["boundary_failure"] = (
                    str(error)
                    if any(str(error).startswith(message) for message in known)
                    else "unclassified_value_error"
                )
        metadata = getattr(client, "call_metadata", [])
        if metadata:
            outcome["usage"] = metadata[-1].usage
        print(json.dumps(outcome, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
