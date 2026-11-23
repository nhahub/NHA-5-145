"""Prepare a retrieval turn; publishing remains owned by the active Session task."""

import asyncio
import os
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path

from agent.advice import (
    AdviceEvidence,
    build_advice_request,
    compose_advice,
    prepare_retrieved_advice,
)
from agent.catalogue import DiscoveryResult
from agent.catalogue_client import CatalogueClient
from agent.catalogue_retrieval import (
    RetrievalBudget,
    RetrievalExhausted,
    RetrievalOutcome,
    retrieve_products,
)
from agent.event_log import record
from agent.llm.intent import StructuredIntent
from agent.plans import PlanSteps


@lru_cache(maxsize=1)
def _encoder(cache):
    from agent.catalogue_embedding import CatalogueEncoder

    return CatalogueEncoder(Path(cache))


async def configured_client(config, environment=None):
    values = os.environ if environment is None else environment
    ranking = values.get("CATALOGUE_RANKING", "lexical")
    if ranking not in {"lexical", "hybrid"}:
        raise ValueError("Invalid catalogue ranking")
    encoder = None
    if ranking == "hybrid":
        cache = values.get("CATALOGUE_MODEL_CACHE")
        if not cache:
            raise ValueError("Hybrid requires a pre-populated local model cache")
        encoder = await asyncio.to_thread(_encoder, cache)
    return CatalogueClient(secret=config["secret"], origin=config["private_url"], encoder=encoder)


class CatalogueTurnInterrupted(Exception):
    pass


@dataclass
class PreparedTurn:
    intent: StructuredIntent
    evidence: AdviceEvidence | None
    summary: str | None
    references: list[dict[str, str]]
    # The Shopper's words for later parts of the message; empty for a one-part message.
    steps: PlanSteps = field(default_factory=PlanSteps)
    # The turn ended in the exhausted fallback: the task completes, but did not do its step.
    exhausted: bool = False
    # Verified (category, product type) of the products the turn read; the Session derives size
    # kinds from these, never from the model or a name.
    facts: dict[str, tuple[str, str]] = field(default_factory=dict)
    beneficiary: str | None = None
    size_hint: str | None = None
    # The turn is a real question for the Shopper (the clarify outcome), never the exhausted
    # fallback: its summary is the question.
    question: bool = False
    # Choices for "which product?": their names, and the product code chose from an exact name.
    options: list[str] = field(default_factory=list)
    named_product: str | None = None


def _size_hint(requirements) -> str | None:
    """The one size the Shopper asked for as a search predicate, when the model left the
    constraint empty."""
    values = {
        p.value
        for p in requirements
        if getattr(p, "field", None) == "size" and getattr(p, "op", None) == "eq"
    }
    return next(iter(values)) if len(values) == 1 else None


def _exhausted_turn(task):
    intent = StructuredIntent.model_validate(
        {
            "v": 9,
            "language": task.language,
            "dialect": "unknown",
            "intent": "advice",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )
    question = (
        "ما قدرتش أكمّل البحث في المحاولة دي. إيه أهم شرط نبدأ بيه؟"
        if task.language == "ar"
        else "I couldn't finish this search. Which requirement should we start with?"
    )
    return PreparedTurn(
        intent, AdviceEvidence(DiscoveryResult(None, ()), ()), question, [], exhausted=True
    )


BEST_FOUND_TEXT = {
    "ar": "دي المنتجات اللي لقيتها لطلبك:",
    "en": "Here's what I found for your request:",
}


def _best_found_outcome(task, error):
    """The budget ran out after a read returned products: show the latest such read's
    verified products as the usual suggestion cards with a code-built line. The model made
    no selection, so no claim about them is made beyond the catalogue facts."""
    language = "ar" if task.language == "ar" else "en"
    intent = StructuredIntent.model_validate(
        {
            "v": 9,
            "language": language,
            "dialect": "unknown",
            "intent": "advice",
            "constraints": {},
            "missing_fields": [],
            "needs_clarification": False,
        }
    )
    products = error.best_found[:3]
    return RetrievalOutcome(
        intent,
        [p.product.id for p in products],
        products,
        task.retrieval_budget,
        error.requirements,
        error.unverified_requirements,
        language=language,
        advice_message=BEST_FOUND_TEXT[language],
    )


async def prepare_turn(task, snapshot, storefront, llm, catalogue, ensure_active):
    if task.retrieval_budget is None:
        task.retrieval_budget = RetrievalBudget()
    ending = "failed"
    try:
        turn, ending = await _prepare_turn(
            task, snapshot, storefront, llm, catalogue, ensure_active
        )
        return turn
    finally:
        # Also on failure, so the budget spent before a catalogue or model error shows.
        budget = task.retrieval_budget
        record(
            "retrieval_turn",
            outcome=ending,
            decisions=budget.decisions,
            reads=budget.reads,
            advice=budget.advice,
            rejections=list(budget.rejections),
        )


async def _prepare_turn(task, snapshot, storefront, llm, catalogue, ensure_active):
    """Run one catalogue turn; return the prepared turn and how it ended."""
    best_found = False
    try:
        outcome = await retrieve_products(
            task.message,
            task.resolved_state,
            llm,
            catalogue,
            ensure_active,
            storefront=storefront,
            snapshot=snapshot,
            budget=task.retrieval_budget,
            pending_clarification=task.pending_clarification,
        )
    except RetrievalExhausted as error:
        await ensure_active()
        if not error.best_found:
            return _exhausted_turn(task), "exhausted"
        outcome, best_found = _best_found_outcome(task, error), True
    await ensure_active()
    if outcome.question:
        intent = StructuredIntent.model_validate(
            {
                "v": 9,
                "language": outcome.language,
                "dialect": "unknown",
                "intent": "advice",
                "constraints": {},
                "missing_fields": [],
                "needs_clarification": False,
            }
        )
        choices = outcome.choices or DiscoveryResult(None, ())
        return PreparedTurn(
            intent,
            AdviceEvidence(choices, ()),
            outcome.question,
            [],
            PlanSteps(
                outcome.first_step,
                list(outcome.remaining_steps),
                list(outcome.skipped_steps),
                "unknown",
            ),
            question=True,
            options=[item.name for item in choices.suggestions],
        ), "clarify"
    intent = outcome.intent
    steps = PlanSteps(
        outcome.first_step,
        list(outcome.remaining_steps),
        list(outcome.skipped_steps),
        intent.dialect,
    )
    references = [
        {
            "id": p.product.id,
            "name": p.product.nameAr if intent.language == "ar" else p.product.nameEn,
        }
        for p in outcome.products
    ]
    facts = {p.product.id: (p.product.category, p.product.type) for p in outcome.products}
    if intent.intent not in {"find_products", "advice"} or intent.needs_clarification:
        return PreparedTurn(
            intent,
            None,
            None,
            references,
            steps,
            named_product=intent.product_id if outcome.named else None,
        ), "execute"
    evidence = prepare_retrieved_advice(outcome)
    who, hint = outcome.beneficiary, _size_hint(outcome.requirements)
    if outcome.advice_message is not None:
        return PreparedTurn(
            intent,
            evidence,
            outcome.advice_message,
            references,
            steps,
            facts=facts,
            beneficiary=who,
            size_hint=hint,
        ), "best_found" if best_found else "recommend"
    if outcome.budget.advice >= 1:
        return _exhausted_turn(task), "exhausted"
    await ensure_active()
    outcome.budget.advice += 1
    summary = await compose_advice(
        llm,
        replace(
            build_advice_request(task.message, intent, evidence, task.resolved_state, snapshot),
            provider_attempt_limit=1,
        ),
        evidence,
    )
    await ensure_active()
    return PreparedTurn(
        intent,
        evidence,
        summary,
        references,
        steps,
        facts=facts,
        beneficiary=who,
        size_hint=hint,
    ), "recommend"
