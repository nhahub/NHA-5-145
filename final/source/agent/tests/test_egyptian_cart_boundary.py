import asyncio
import json

from agent.llm import interpret_message
from agent.llm.contract import LLMChunk, ScriptedLLMClient
from agent.storefront import load_storefront_definition


def interpret(message, fields):
    payload = {
        "v": 8,
        "language": "ar",
        "dialect": "egyptian_arabic",
        "constraints": {},
        "missing_fields": [],
        "needs_clarification": False,
        **fields,
    }
    return asyncio.run(
        interpret_message(
            ScriptedLLMClient([[LLMChunk(text=json.dumps(payload))]]),
            message,
            storefront=load_storefront_definition(),
            resolved_state={},
            pending_clarification=None,
        )
    )


def test_owner_bulk_clear_wording_reaches_guarded_intent_boundary():
    message = "شيل الحاجة اللي فالسلة كلها"
    result = interpret(
        message, {"intent": "mutate", "mutation_kind": "clear_cart", "mutation_source": message}
    )
    assert result.mutation_kind == "clear_cart"
