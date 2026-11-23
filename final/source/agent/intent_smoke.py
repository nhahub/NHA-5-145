"""Explicit real-provider smoke test for multilingual intent extraction."""

import asyncio
import os

from agent.llm import build_llm_client, interpret_message, load_llm_settings
from agent.storefront import load_storefront_definition


async def main() -> None:
    if os.environ.get("LLM_SMOKE_TEST") != "1":
        raise SystemExit("Set LLM_SMOKE_TEST=1 to make a real provider request.")
    settings = load_llm_settings()
    if settings.provider == "scripted":
        raise SystemExit("Select a real LLM provider before running this smoke test.")
    intent = await interpret_message(
        build_llm_client(settings),
        "عاوز black running shoes مقاس 42 تحت 2500 EGP والأرخص",
        storefront=load_storefront_definition(),
        resolved_state={},
        pending_clarification=None,
    )
    print(intent.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
