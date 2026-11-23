"""Application wiring; receipt verification remains adapter-specific."""

import os
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path

from agent.inference.client import GuardedClient, InferencePrices
from agent.inference.ledger import AllowanceLedger
from agent.llm.bedrock import BedrockClient
from agent.llm.openrouter import OpenRouterClient

REQUIRED = (
    "INFERENCE_LEDGER_PATH",
    "INFERENCE_LEDGER_ID",
    "INFERENCE_PROVIDER",
    "INFERENCE_MODEL",
    "INFERENCE_INPUT_USD_PER_MILLION",
    "INFERENCE_OUTPUT_USD_PER_MILLION",
    "INFERENCE_MAX_ACTIVE",
    "INFERENCE_MAX_WAITING",
    "INFERENCE_WAIT_SECONDS",
    "INFERENCE_MAXIMUM_PAGES",
)


def openrouter_receipt(client, attempt):
    for item in reversed(getattr(client, "call_metadata", ())):
        if item.attempt_id == attempt:
            cost = item.usage.get("cost") if item.usage else None
            if (
                isinstance(cost, int | float)
                and not isinstance(cost, bool)
                and isfinite(cost)
                and cost >= 0
            ):
                return Decimal(str(cost))
            break
    return None


def configured_guard(
    client, settings, environment=None, *, queue_observer=None, maximum_attempts=None
):
    values = os.environ if environment is None else environment
    selected = any(name in values for name in REQUIRED)
    required = values.get("COPILOT_ENV") == "production" and settings.provider != "scripted"
    if not selected and not required:
        if maximum_attempts is not None:
            raise ValueError("Attempt ceiling requires a durable inference allowance")
        return client
    if not all(values.get(name, "").strip() for name in REQUIRED):
        raise ValueError("Explicit durable inference allowance configuration is required")
    if (
        values["INFERENCE_PROVIDER"] != settings.provider
        or values["INFERENCE_MODEL"] != settings.model
    ):
        raise ValueError("Inference prices must be bound to the selected provider and model")
    try:
        prices = InferencePrices(
            Decimal(values["INFERENCE_INPUT_USD_PER_MILLION"]),
            Decimal(values["INFERENCE_OUTPUT_USD_PER_MILLION"]),
        )
        if settings.provider == "openrouter" and (
            prices.input_per_million < Decimal(OpenRouterClient.price_ceiling[0])
            or prices.output_per_million < Decimal(OpenRouterClient.price_ceiling[1])
        ):
            raise ValueError("Inference prices cannot under-reserve the route's price ceiling")
        if settings.provider == "bedrock" and (
            prices.input_per_million < Decimal(BedrockClient.price_floor[0])
            or prices.output_per_million < Decimal(BedrockClient.price_floor[1])
        ):
            raise ValueError("Inference prices cannot under-reserve the Bedrock candidate")
        ledger = AllowanceLedger(
            Path(values["INFERENCE_LEDGER_PATH"]),
            values["INFERENCE_LEDGER_ID"],
            maximum_pages=int(values["INFERENCE_MAXIMUM_PAGES"]),
        )
        return GuardedClient(
            client,
            ledger,
            prices,
            receipt=openrouter_receipt if settings.provider == "openrouter" else None,
            maximum_active=int(values["INFERENCE_MAX_ACTIVE"]),
            maximum_waiting=int(values["INFERENCE_MAX_WAITING"]),
            wait_seconds=float(values["INFERENCE_WAIT_SECONDS"]),
            queue_observer=queue_observer,
            maximum_attempts=maximum_attempts,
        )
    except (ValueError, InvalidOperation) as error:
        raise ValueError("Invalid durable inference allowance configuration") from error
