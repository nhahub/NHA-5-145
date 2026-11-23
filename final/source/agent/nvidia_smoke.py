"""Explicit opt-in smoke test for the configured NVIDIA NIM model."""

import asyncio
import os

from agent.llm import LLMMessage, LLMRequest, build_llm_client, load_llm_settings


async def main() -> None:
    if os.environ.get("NVIDIA_SMOKE_TEST") != "1":
        raise SystemExit("Set NVIDIA_SMOKE_TEST=1 to make a real NVIDIA request.")
    settings = load_llm_settings()
    if settings.provider != "nvidia":
        raise SystemExit("Set LLM_PROVIDER=nvidia before running this smoke test.")
    client = build_llm_client(settings)
    request = LLMRequest(
        system="Reply with exactly: ready",
        messages=(LLMMessage(role="shopper", content="Confirm the connection."),),
    )
    response_parts = [chunk.text or "" async for chunk in client.complete(request)]
    response = "".join(response_parts)
    if not response.strip():
        raise SystemExit("NVIDIA returned an empty response.")
    print(f"NVIDIA connection succeeded for model: {settings.model}")


if __name__ == "__main__":
    asyncio.run(main())
