"""Opt-in live check for resolving a named recommendation without product search."""

import asyncio

from agent.llm import build_llm_client, interpret_message, load_llm_settings
from agent.storefront import load_storefront_definition


async def main() -> None:
    settings = load_llm_settings()
    if settings.provider != "groq":
        raise SystemExit("This check requires the configured local Groq model")
    intent = await interpret_message(
        build_llm_client(settings),
        "طب ينفع توريني صفحة كوتشي ممشى النيل ده",
        storefront=load_storefront_definition(),
        resolved_state={
            "_previous_suggestions": [
                {"id": "shoe-09", "name": "ممشى النيل"},
                {"id": "shoe-02", "name": "عدّاء النيل"},
            ]
        },
        pending_clarification=None,
    )
    print(f"intent={intent.intent} product_id={intent.product_id}")
    if intent.intent != "open_product" or intent.product_id != "shoe-09":
        raise SystemExit("Live model did not select the named recommended product")


if __name__ == "__main__":
    asyncio.run(main())
