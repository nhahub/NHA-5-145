"""Per-attempt evaluation telemetry, separate from the application entrypoint."""

import asyncio
import json
import os
from contextlib import aclosing
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from agent.advice import AdviceResponse
from agent.cart import CART_ROUTES
from agent.llm.intent import StructuredIntent


def pipeline_error_diagnostic(error):
    """Keep categories only; exception messages can contain rejected model text."""
    return {"category": type(error).__name__}


class MeasuredClient:
    def __init__(self, client, *, journal: Path):
        self.client = client
        self.journal = journal
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        # Never reuse a previous service's journal.
        self.journal.touch(exist_ok=False)
        self.calls = []
        self.release = asyncio.Event()
        self.release.set()

    async def complete(self, request):
        start = perf_counter()
        attempt_id = str(uuid4())
        failure = None
        diagnostic = {}
        validator = request.response_validator

        def validate(text):
            try:
                intent = validator(text) if validator else None
            except Exception as error:
                if hasattr(error, "errors"):
                    errors = error.errors(include_input=False, include_context=False)
                    properties = (request.response_schema or {}).get("properties", {})
                    diagnostic["schema_error_count"] = len(errors)
                    diagnostic["schema_fields"] = sorted(
                        {
                            item["loc"][0]
                            for item in errors
                            if item["loc"] and item["loc"][0] in properties
                        }
                    )
                raise
            if isinstance(intent, StructuredIntent):
                # Numeric IDs and operation enums only, never rejected text or page values.
                diagnostic.update(
                    intent=intent.intent,
                    operation=intent.cart_operation,
                    quantity=intent.cart_quantity,
                    mode=intent.cart_quantity_mode,
                    target_id=intent.cart_target_id,
                    request_mode=intent.request_mode,
                    needs_clarification=intent.needs_clarification,
                    query_present=intent.constraints.query is not None,
                    catalogue_requirement_count=len(intent.catalogue_requirements),
                    catalogue_discovery=intent.catalogue_discovery,
                )
                context_text = request.system.split("Shopping Copilot intent context: ", 1)[-1]
                context, _ = json.JSONDecoder().raw_decode(context_text)
                diagnostic["observed_operation_targets"] = [
                    {"id": e["id"], "operation": e.get("form_action")}
                    for e in (context.get("current_snapshot") or {}).get("elements", [])
                    if e.get("role") == "button" and e.get("form_action") in CART_ROUTES.values()
                ]
            elif isinstance(intent, AdviceResponse):
                diagnostic["advice_product_ids"] = intent.product_ids
                diagnostic["advice_length"] = len(intent.message)
            return intent

        try:
            async with aclosing(
                self.client.complete(
                    replace(request, response_validator=validate, attempt_id=attempt_id)
                )
            ) as completion:
                async for chunk in completion:
                    await self.release.wait()
                    yield chunk
        except (Exception, asyncio.CancelledError) as error:
            failure = type(error).__name__
            raise
        finally:
            metadata = [
                m for m in getattr(self.client, "call_metadata", []) if m.attempt_id == attempt_id
            ]
            self.calls.append(
                {
                    "attempt_id": attempt_id,
                    "generation_id": metadata[-1].generation_id if metadata else None,
                    "started_at": metadata[-1].started_at if metadata else None,
                    "failure_category": metadata[-1].failure_category if metadata else None,
                    "elapsed_ms": metadata[-1].latency_ms
                    if metadata
                    else (perf_counter() - start) * 1000,
                    "ttft_ms": getattr(metadata[-1], "ttft_ms", None) if metadata else None,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "prompt_version": request.prompt_version,
                    "schema_version": request.schema_version,
                    "failure": failure,
                    "diagnostic": diagnostic,
                    "usage": asdict(metadata[-1])["usage"] if metadata else None,
                }
            )
            with self.journal.open("a", encoding="utf-8") as file:
                file.write(json.dumps(self.calls[-1], ensure_ascii=False) + "\n")
                file.flush()
                os.fsync(file.fileno())
