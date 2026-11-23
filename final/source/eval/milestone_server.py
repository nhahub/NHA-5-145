"""Evaluation-only Agent entrypoint; never enabled by normal app startup."""

import importlib
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from agent.app import create_app
from agent.inference.ledger import AllowanceLedger
from agent.llm import build_llm_client, load_llm_settings
from eval.measurement import MeasuredClient, pipeline_error_diagnostic
from eval.qualification_budget import QualificationClient

if os.environ.get("MILESTONE_EVAL") != "1":
    raise RuntimeError("This entrypoint is only for explicit local milestone evaluation")
settings = replace(load_llm_settings(), stream=True)

pipeline_errors = []
agent_module = importlib.import_module("agent.app")
original_interpret = agent_module.interpret_message


async def measured_interpret(*args, **kwargs):
    try:
        return await original_interpret(*args, **kwargs)
    except Exception as error:
        pipeline_errors.append(pipeline_error_diagnostic(error))
        raise


agent_module.interpret_message = measured_interpret

budget_path = os.environ.get("MODEL_QUALIFICATION_JOURNAL")
provider = (
    QualificationClient(
        settings,
        journal=Path(budget_path),
        maximum_cost=float(os.environ.get("MODEL_QUALIFICATION_MAXIMUM_COST", "0.25")),
        maximum_calls=int(os.environ.get("MODEL_QUALIFICATION_MAXIMUM_CALLS", "120")),
        durable_ledger=(
            AllowanceLedger(
                Path(os.environ["MODEL_QUALIFICATION_LEDGER_PATH"]),
                os.environ["MODEL_QUALIFICATION_LEDGER_ID"],
            )
            if os.environ.get("MODEL_QUALIFICATION_CONTINUE") == "1"
            else None
        ),
    )
    if budget_path
    else build_llm_client(settings)
)
client = MeasuredClient(
    provider,
    journal=Path("eval/reports") / f"attempts-{uuid4()}.jsonl",
)
app = create_app(llm_settings=settings, llm_client=client)


@app.get("/__eval/metrics")
def metrics():
    return {
        "provider": settings.provider,
        "model": settings.model,
        "calls": client.calls,
        "pipeline_errors": pipeline_errors,
        "journal": client.journal.as_posix(),
        "qualification_budget": provider.summary() if budget_path else None,
    }


@app.post("/__eval/hold")
async def hold():
    client.release.clear()
    return {"held": True}


@app.post("/__eval/release")
async def release():
    client.release.set()
    return {"held": False}
