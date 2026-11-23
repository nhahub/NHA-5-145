import asyncio
import os
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from time import monotonic, time
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response, StreamingResponse

from agent.admission.runtime import AdmissionClient, AdmissionPolicy, configured_admission
from agent.admission.store import AdmissionDenied
from agent.advice import build_advice_request, compose_advice, prepare_advice
from agent.async_boundary import invoke
from agent.catalogue import CatalogueReader, HttpCatalogueReader, evaluate_catalogue
from agent.catalogue_client import CatalogueReadError
from agent.catalogue_contract import DetailsQuery
from agent.catalogue_turn import CatalogueTurnInterrupted, configured_client, prepare_turn
from agent.conditions import evaluate as evaluate_condition
from agent.conditions import not_met_text
from agent.event_log import (
    EventLog,
    RequestLog,
    StreamSink,
    bind,
    record_error,
    shopper_tag,
)
from agent.inference.client import GuardedClient
from agent.inference.config import configured_guard
from agent.inference.ledger import InferenceRefused
from agent.inference.recorded import RecordedClient
from agent.lifecycle.work import LifecycleWork, configured_lifecycle
from agent.llm import LLMClient, LLMSettings, build_llm_client, interpret_message, load_llm_settings
from agent.llm.bedrock import BedrockProviderError
from agent.llm.gemini import GeminiRateLimitError
from agent.llm.groq import GroqRateLimitError
from agent.llm.openrouter import OpenRouterBudgetError
from agent.named_product import (
    QUESTION as NAMED_QUESTION,
)
from agent.named_product import (
    check_chosen_product,
    choice_intent,
    from_catalogue_product,
    is_open_by_name,
    needs_name_check,
    resolve_named_product,
    shopper_words,
)
from agent.planner import ActionIdentity, ScriptedPlanner, UnsupportedShoppingTask
from agent.plans import RETRIEVAL_EXHAUSTED
from agent.product_confirmation import NAMED_KEY
from agent.schemas import ActionResult, Snapshot, to_wire
from agent.session_stream import encode_sse as encode_sse
from agent.session_stream import session_event_response
from agent.sessions import (
    ActionResultMismatch,
    InterpretationPauseReason,
    LeaseConflict,
    SessionExpired,
    SessionNotFound,
    SessionStore,
    StateSaveFailed,
    TaskConflict,
)
from agent.shopper_access import ShopperBinding
from agent.shopper_http import install_shopper_http
from agent.speech import MAX_AUDIO_BYTES, OpenRouterSpeechTranscriber, SpeechTranscriber
from agent.state_store import configured_state_store
from agent.storefront_service import StorefrontService, identity_config
from agent.swap import SwapDecision, read_line
from agent.swap import decide as decide_swap


class StepRequest(BaseModel):
    message: str
    snapshot: Snapshot


class SessionMessage(BaseModel):
    text: str
    snapshot: Snapshot
    replace_active: bool = False


class SessionAnswer(BaseModel):
    question_id: str
    text: str
    snapshot: Snapshot


class SessionCreate(BaseModel):
    tab_id: str | None = None


class ReconcileRequest(BaseModel):
    snapshot: Snapshot


class RetryRequest(BaseModel):
    snapshot: Snapshot


class TakeoverRequest(BaseModel):
    tab_id: str


class AdvanceTestTime(BaseModel):
    seconds: float


# Interpretation runs inside the HTTP request. Keep this below the proxy's
# response_header_timeout for interpretation routes (deploy/Caddyfile*).
INTERPRETATION_DEADLINE_SECONDS = 90


def interpretation_pause_reason(error: Exception) -> InterpretationPauseReason:
    if isinstance(error, BedrockProviderError):
        return {"throttled": "throttled", "timeout": "timeout", "network": "network"}.get(
            error.category, "provider_http"
        )
    if isinstance(error, InferenceRefused):
        return {
            "budget": "budget",
            "busy": "inference_busy",
            "disabled": "inference_disabled",
        }.get(error.reason, "inference_unavailable")
    if isinstance(error, OpenRouterBudgetError):
        return "budget"
    if isinstance(error, GroqRateLimitError | GeminiRateLimitError):
        return "throttled"
    if isinstance(error, httpx.HTTPStatusError):
        return "throttled" if error.response.status_code == 429 else "provider_http"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "network"
    if isinstance(error, ValueError):
        return "invalid_response"
    return "unexpected"


def catalogue_facts(catalogue, only: str | None = None) -> dict[str, tuple[str, str]]:
    """(category, product type) of the catalogue's products: verified facts for size kinds."""
    return {
        p.id: (p.category, p.product_type)
        for p in catalogue.products
        if only is None or p.id == only
    }


def create_app(
    session_store: SessionStore | None = None,
    llm_settings: LLMSettings | None = None,
    llm_client: LLMClient | None = None,
    catalogue_reader: CatalogueReader | None = None,
    catalogue_client=None,
    catalogue_retrieval_enabled: bool | None = None,
    confirmation_registrar: Callable[[ShopperBinding | None, str, str, str, str, int], bool]
    | None = None,
    speech_transcriber: SpeechTranscriber | None = None,
    storefront_service: StorefrontService | None = None,
    evaluation: bool = False,
    admission: AdmissionPolicy | None = None,
    lifecycle=None,
    inference_queue_observer=None,
    inference_maximum_attempts=None,
    lifecycle_work_factory=None,
    readiness_factory=None,
    environment=None,
    event_sink=None,
    release: str = "local",
    debug_switch=None,
) -> FastAPI:
    environment = None if environment is None else dict(environment)
    events = EventLog(
        event_sink if event_sink is not None else StreamSink(),
        release=release,
        debug=debug_switch,
    )
    settings = llm_settings or load_llm_settings(environment)
    values = dict(os.environ) if environment is None else environment
    llm_client = configured_guard(
        llm_client or build_llm_client(settings),
        settings,
        environment,
        queue_observer=inference_queue_observer,
        maximum_attempts=inference_maximum_attempts,
    )
    # Recording wraps only the calls a turn makes; the guard itself stays as configured,
    # because readiness and the speech switch check its exact type.
    recorded_llm = RecordedClient(
        llm_client,
        provider=settings.provider,
        model=settings.model,
        classify=interpretation_pause_reason,
    )
    admission = admission or configured_admission(environment)
    lifecycle = lifecycle or configured_lifecycle(values, admission)
    if lifecycle is None and (lifecycle_work_factory is not None or readiness_factory is not None):
        raise ValueError("Host factories require explicit lifecycle authority")
    identity_settings = identity_config(environment)
    service = storefront_service or StorefrontService(identity_settings, environment=environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        work = app.state.lifecycle_work
        maintenance = None
        try:
            app.state.storefront_service.validate_configuration()
            if work is not None:
                if hasattr(work, "initialize"):
                    await invoke(work, "initialize")
                maintenance = asyncio.create_task(work.maintain())
            yield
        finally:
            try:
                if maintenance is not None:
                    maintenance.cancel()
                    with suppress(asyncio.CancelledError):
                        await maintenance
            finally:
                try:
                    try:
                        if app.state.host_readiness is not None:
                            await invoke(app.state.host_readiness, "close")
                    finally:
                        if work is not None:
                            await invoke(work, "close")
                finally:
                    try:
                        if admission is not None and hasattr(admission, "close"):
                            await invoke(admission, "close")
                    finally:
                        close = getattr(app.state.storefront_service, "aclose", None)
                        if close is not None:
                            await close()

    app = FastAPI(title="Shopping Copilot Agent", lifespan=lifespan)
    app.state.llm_settings = settings
    app.state.llm_client = llm_client
    app.state.admission = admission
    planner = ScriptedPlanner()
    test_clock_enabled = settings.provider == "scripted" and values.get("EVAL_TEST_CLOCK") == "1"
    clock_offset = [0.0]

    def session_clock() -> float:
        return monotonic() + clock_offset[0]

    def wall_clock() -> float:
        return time() + clock_offset[0]

    sessions = session_store or SessionStore(
        planner,
        clock=session_clock,
        capacity=admission.maximum_sessions if admission else 800,
        confirmation_registrar=confirmation_registrar or service.register_confirmation,
        store=configured_state_store(values),
        wall_clock=wall_clock,
    )
    install_shopper_http(
        app,
        sessions,
        service,
        admission=admission,
        panel_origin=identity_settings["panel_origin"],
        evaluation=values.get("COPILOT_ENV") != "production"
        and settings.provider == "scripted"
        and (evaluation or values.get("COPILOT_EVALUATION") == "1"),
        lifecycle_work=(lifecycle_work_factory or LifecycleWork)(lifecycle, sessions)
        if lifecycle
        else None,
    )
    app.state.host_readiness = (
        readiness_factory(app, app.state.lifecycle_work) if readiness_factory is not None else None
    )
    catalogue_reader = catalogue_reader or HttpCatalogueReader()

    retrieval_enabled = (
        values.get("CATALOGUE_RETRIEVAL_ENABLED") == "1"
        if catalogue_retrieval_enabled is None
        else catalogue_retrieval_enabled
    )

    active_interpretations: set[tuple[str, str, str]] = set()

    async def verify_owner(session_id: str) -> None:
        if lifecycle:
            await invoke(app.state.lifecycle_work, "check")
        owner = sessions.get(session_id).shopper
        if (
            owner is None
            or not await app.state.storefront_service.validate(owner)
            or not await app.state.shopper_access.owns_session_async(
                session_id,
                owner,
                (lambda record: invoke(admission, "allowed", record)) if admission else None,
            )
        ):
            raise SessionNotFound(session_id)
        if lifecycle:
            await invoke(app.state.lifecycle_work, "check")
        if sessions.get(session_id).shopper != owner or not app.state.shopper_access.owns_session(
            session_id, owner
        ):
            raise SessionNotFound(session_id)

    async def run_interpretation(session_id: str, task_id: str, call_id: str) -> None:
        # Save what the request changed so far before any model call: if that fails the
        # request has no effect (the change is rolled back) and nothing is interpreted.
        sessions.flush(checkpoint=True)
        try:
            async with asyncio.timeout(INTERPRETATION_DEADLINE_SECONDS):
                await _interpret(session_id, task_id, call_id)
        except TimeoutError:
            sessions.fail_interpretation(session_id, task_id, call_id, "timeout")
        except asyncio.CancelledError:
            sessions.fail_interpretation(session_id, task_id, call_id, "interrupted")
            raise

    async def drive_plan(session_id: str) -> None:
        """Interpret each plan step that a task end has just started.

        The shared task end starts the next step synchronously; interpreting it is model work,
        so the request handler that caused the end (message, answer, retry or Action Result)
        does it here. A step that ends at once starts the next, so this loops.
        """
        while True:
            sessions.settle_plan(session_id)
            session = sessions.get(session_id)
            task = session.active_task
            if session.start_pending is None:
                return
            pending, session.start_pending = session.start_pending, None
            if task is None or task.task_id != pending or task.status != "interpreting":
                return
            await run_interpretation(session_id, task.task_id, task.model_call_id or "")

    async def _interpret(session_id: str, task_id: str, call_id: str) -> None:
        session = sessions.get(session_id)
        with bind(
            events,
            session_id=session_id,
            task_id=task_id,
            shopper=shopper_tag(session.shopper),
            invitation_id=session.invitation_id,
        ):
            await _interpret_task(session_id, task_id, call_id)

    async def prepare_add(session_id: str, intent, fetch) -> tuple[bool | None, str | None]:
        """Verified facts about the product an add names, read from the catalogue.

        Learns the size kind (once per product) and, when the add carries a condition, reads
        the product fresh and evaluates the condition in code. Returns (verdict, reason): the
        verdict is None when the fact cannot be read; the reason is the code-built text for a
        condition that is not met. A failed read just leaves everything unknown.
        """
        session = sessions.get(session_id)
        if (
            intent.intent != "cart_edit"
            or intent.cart_operation != "add"
            or not intent.product_id
            or intent.needs_clarification
        ):
            return None, None
        conditional = intent.condition is not None
        if not conditional and intent.product_id in session.product_kinds:
            return None, None
        try:
            product = await fetch(intent.product_id)
        except (CatalogueReadError, httpx.HTTPError, ValueError, OSError):
            return None, None
        if product is None:
            return None, None
        if intent.product_id not in session.product_kinds:
            kind = (product.category, getattr(product, "type", None) or product.product_type)
            sessions.note_product_facts(session_id, {product.id: kind})
        if not conditional:
            return None, None
        storefront = planner.storefront
        verdict = evaluate_condition(intent.condition, product, storefront)
        reason = (
            not_met_text(intent.condition, product, intent.language, storefront)
            if verdict is False
            else None
        )
        return verdict, reason

    async def prepare_swap(session_id: str, intent, observed, fetch) -> SwapDecision | None:
        """The catalogue check before a colour change of a cart line, decided in code.

        Reads the old line from the cart Snapshot; returns None when the intent is not a swap
        on a readable cart line (the task then says which item it could not identify). A failed
        or empty catalogue read leaves the product unknown, so the Copilot asks.
        """
        if (
            intent.intent != "cart_edit"
            or intent.cart_operation != "replace"
            or intent.needs_clarification
        ):
            return None
        storefront = planner.storefront
        color = intent.constraints.color
        line = read_line(
            observed, intent.cart_target_id, intent.constraints.size, storefront.product_route
        )
        if line is None:
            return None
        try:
            product = await fetch(line.product_id)
        except (CatalogueReadError, httpx.HTTPError, ValueError, OSError):
            product = None
        return decide_swap(line, color, product, intent.language, storefront)

    async def _interpret_task(session_id: str, task_id: str, call_id: str) -> None:
        task = sessions.get(session_id).active_task
        if task is None or task.task_id != task_id or task.model_call_id != call_id:
            return
        identity = (session_id, task_id, call_id)
        if identity in active_interpretations:
            return
        active_interpretations.add(identity)
        model = (
            AdmissionClient(recorded_llm, lambda: verify_owner(session_id))
            if admission
            else recorded_llm
        )
        observed = sessions.get(session_id).last_snapshot
        observed = observed.model_copy(deep=True) if observed is not None else None
        phase = "intent"
        try:
            await verify_owner(session_id)
            if retrieval_enabled:
                phase = "catalogue"

                async def ensure_active():
                    current = sessions.get(session_id)
                    if (
                        current.active_task is not task
                        or task.model_call_id != call_id
                        or task.status != "interpreting"
                        or current.requires_reconciliation
                        or current.last_snapshot != observed
                    ):
                        raise CatalogueTurnInterrupted()
                    await verify_owner(session_id)
                    # Ownership validation awaits external I/O; recheck task identity afterwards.
                    current = sessions.get(session_id)
                    if (
                        current.active_task is not task
                        or task.model_call_id != call_id
                        or task.status != "interpreting"
                        or current.requires_reconciliation
                        or current.last_snapshot != observed
                    ):
                        raise CatalogueTurnInterrupted()

                await ensure_active()
                reader = catalogue_client or (
                    await configured_client(identity_settings)
                    if environment is None
                    else await configured_client(identity_settings, environment=environment)
                )
                await ensure_active()
                phase = "intent"
                prepared = await prepare_turn(
                    task, observed, planner.storefront, model, reader, ensure_active
                )
                await ensure_active()
                sessions.get(session_id).product_context.remember_catalogue(prepared.references)
                # Remember verified identities only, never DOM targets or mutation authority.
                task.resolved_state["_known_products"] = [
                    *task.resolved_state.get("_known_products", []),
                    *prepared.references,
                ][-24:]
                if prepared.evidence is not None:
                    sessions.finish_catalogue_interpretation(
                        session_id,
                        task_id,
                        call_id,
                        prepared.intent,
                        prepared.evidence.discovery,
                        advice_text=prepared.summary,
                        plan_steps=prepared.steps,
                        end_reason=RETRIEVAL_EXHAUSTED if prepared.exhausted else None,
                        clarify=prepared.question,
                        options=prepared.options,
                        facts=prepared.facts,
                        beneficiary=prepared.beneficiary,
                        size_hint=prepared.size_hint,
                    )
                    session = sessions.get(session_id)
                    session.advice_context["retrieval_requirements"] = list(
                        prepared.evidence.requirements
                    )
                    session.advice_context["unverified_requirements"] = list(
                        prepared.evidence.unverified_requirements
                    )
                else:
                    if prepared.named_product is not None:
                        # Code chose this product from the Shopper's exact words (ticket 06).
                        task.resolved_state[NAMED_KEY] = prepared.named_product

                    async def fetch_details(product_id):
                        found = await reader.details(DetailsQuery(ids=[product_id]))
                        return next(
                            (p.product for p in found.products if p.product.id == product_id),
                            None,
                        )

                    verdict, reason = await prepare_add(session_id, prepared.intent, fetch_details)
                    swap_check = await prepare_swap(
                        session_id, prepared.intent, observed, fetch_details
                    )
                    await ensure_active()
                    sessions.finish_interpretation(
                        session_id,
                        task_id,
                        call_id,
                        prepared.intent,
                        plan_steps=prepared.steps,
                        condition_result=verdict,
                        condition_reason=reason,
                        swap_check=swap_check,
                    )
                return
            intent = await interpret_message(
                model,
                task.message,
                storefront=planner.storefront,
                resolved_state=task.resolved_state,
                pending_clarification=task.pending_clarification,
                snapshot=observed,
            )
            await verify_owner(session_id)
            if sessions.get(session_id).last_snapshot != observed:
                sessions.fail_interpretation(session_id, task_id, call_id, "interrupted")
                return
            read_once: list = []

            async def read_catalogue():
                # One read per interpretation: the name check and the add facts share it.
                if not read_once:
                    read_once.append(await catalogue_reader.read())
                return read_once[0]

            if is_open_by_name(intent) or needs_name_check(intent, task.resolved_state):
                phase = "catalogue"

                async def look_up(text):
                    catalogue = await read_catalogue()
                    return [from_catalogue_product(p) for p in catalogue.validated_products()]

                words = shopper_words(task.message, task.resolved_state)
                if task.resolved_state.get("_plan_step"):
                    words = [task.message]
                if is_open_by_name(intent):
                    resolution = await resolve_named_product(
                        intent, words, look_up, category_missing=True
                    )
                else:
                    try:
                        resolution = await check_chosen_product(
                            intent,
                            words,
                            task.resolved_state,
                            observed,
                            planner.storefront,
                            look_up,
                        )
                    except (CatalogueReadError, httpx.HTTPError, ValueError, OSError):
                        resolution = None  # cannot verify: the existing name guard still applies
                phase = "intent"
                await verify_owner(session_id)
                if sessions.get(session_id).last_snapshot != observed:
                    sessions.fail_interpretation(session_id, task_id, call_id, "interrupted")
                    return
            else:
                resolution = None
            if resolution is not None:
                if resolution.kind == "several":
                    sessions.finish_catalogue_interpretation(
                        session_id,
                        task_id,
                        call_id,
                        choice_intent(intent.language),
                        resolution.choices,
                        advice_text=NAMED_QUESTION["ar" if intent.language == "ar" else "en"],
                        clarify=True,
                        options=[c.name for c in resolution.choices.suggestions],
                    )
                    return
                if resolution.kind == "one":
                    product = resolution.products[0]
                    known = task.resolved_state.setdefault("_known_products", [])
                    known.append(
                        {
                            "id": product.id,
                            "name": product.name_ar if intent.language == "ar" else product.name_en,
                        }
                    )
                    task.resolved_state[NAMED_KEY] = product.id
                intent = resolution.intent
            catalogue_discovery = intent.catalogue_discovery
            if intent.v >= 9 and (intent.intent == "advice" or catalogue_discovery):
                phase = "catalogue"
                catalogue = await catalogue_reader.read()
                evidence = prepare_advice(catalogue, intent)
                current = sessions.get(session_id)
                if current.active_task is not task or task.model_call_id != call_id:
                    return
                if (
                    intent.intent != "advice"
                    and intent.request_mode == "browse"
                    and not evidence.discovery.exact_count
                ):
                    await verify_owner(session_id)
                    sessions.finish_catalogue_interpretation(
                        session_id,
                        task_id,
                        call_id,
                        intent,
                        evidence.discovery,
                        facts=catalogue_facts(catalogue),
                    )
                    return
                phase = "advice"
                await verify_owner(session_id)
                try:
                    summary = await compose_advice(
                        model,
                        build_advice_request(
                            task.message, intent, evidence, task.resolved_state, observed
                        ),
                        evidence,
                    )
                except (
                    ValueError,
                    httpx.HTTPError,
                    OpenRouterBudgetError,
                    GroqRateLimitError,
                    GeminiRateLimitError,
                ):
                    summary = (
                        "مش قادر أقدّم نصيحة موثوقة دلوقتي. "
                        "أي منتجات ظاهرة مبنية على بيانات المتجر؛ "
                        "ما غيّرتش حاجة في السلة."
                        if intent.language == "ar"
                        else "I couldn't prepare reliable advice right now. Any products shown use "
                        "verified catalogue data; your cart has not changed."
                    )
                await verify_owner(session_id)
                if sessions.get(session_id).last_snapshot != observed:
                    sessions.fail_interpretation(session_id, task_id, call_id, "interrupted")
                    return
                await verify_owner(session_id)
                sessions.finish_catalogue_interpretation(
                    session_id,
                    task_id,
                    call_id,
                    intent,
                    evidence.discovery,
                    advice_text=summary,
                    facts=catalogue_facts(catalogue),
                )
                return
            if catalogue_discovery:
                phase = "catalogue"
                catalogue = await catalogue_reader.read()
                result = evaluate_catalogue(catalogue, intent)
                await verify_owner(session_id)
                sessions.finish_catalogue_interpretation(
                    session_id,
                    task_id,
                    call_id,
                    intent,
                    result,
                    facts=catalogue_facts(catalogue),
                )
                return

            async def read_product(product_id):
                found = await read_catalogue()
                return next((p for p in found.products if p.id == product_id), None)

            verdict, reason = await prepare_add(session_id, intent, read_product)
            swap_check = await prepare_swap(session_id, intent, observed, read_product)
            await verify_owner(session_id)
            sessions.finish_interpretation(
                session_id,
                task_id,
                call_id,
                intent,
                condition_result=verdict,
                condition_reason=reason,
                swap_check=swap_check,
            )
        except CatalogueTurnInterrupted:
            sessions.fail_interpretation(session_id, task_id, call_id, "interrupted")
            return
        except SessionNotFound:
            return
        except Exception as error:
            record_error(error)
            reason = (
                "catalogue_unavailable"
                if phase == "catalogue" or isinstance(error, CatalogueReadError)
                else interpretation_pause_reason(error)
            )
            sessions.fail_interpretation(
                session_id,
                task_id,
                call_id,
                reason,
                retry_after_seconds=getattr(error, "retry_after_seconds", None),
            )
        finally:
            active_interpretations.discard(identity)

    @app.get("/health")
    async def health(request: Request):
        if any(name.startswith("x-copilot-") for name in request.headers):
            if app.state.host_readiness is None:
                raise HTTPException(
                    status_code=503,
                    detail="Readiness unavailable",
                    headers={"Cache-Control": "no-store"},
                )
            return await app.state.host_readiness.response(request.headers)
        return {"status": "ok", "service": "agent"}

    @app.get("/speech/availability")
    async def speech_availability() -> dict[str, bool]:
        if isinstance(llm_client, GuardedClient) or admission is not None:
            return {"available": False}
        if settings.provider != "openrouter" and speech_transcriber is None:
            return {"available": False}
        transcriber = speech_transcriber or OpenRouterSpeechTranscriber(settings)
        try:
            return {"available": await transcriber.available()}
        except (httpx.HTTPError, ValueError):
            return {"available": False}

    @app.post("/speech/transcribe")
    async def transcribe_speech(request: Request, language: Literal["ar", "en"]) -> dict[str, str]:
        if isinstance(llm_client, GuardedClient) or admission is not None:
            raise HTTPException(
                status_code=503,
                detail="Server transcription is unavailable; use typing or browser speech",
            )
        if request.headers.get("content-type", "").split(";", 1)[0] != "audio/webm":
            raise HTTPException(status_code=415, detail="WebM audio is required")
        content_length = request.headers.get("content-length", "0")
        if not content_length.isdecimal():
            raise HTTPException(status_code=400, detail="Invalid recording length")
        if int(content_length) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio recording is too large")
        audio = await request.body()
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio recording is too large")
        if not audio.startswith(b"\x1a\x45\xdf\xa3"):
            raise HTTPException(status_code=400, detail="Invalid WebM recording")
        if settings.provider != "openrouter" and speech_transcriber is None:
            raise HTTPException(status_code=503, detail="Speech transcription is unavailable")
        transcriber = speech_transcriber or OpenRouterSpeechTranscriber(settings)
        try:
            return {"text": await transcriber.transcribe(audio, language)}
        except OpenRouterBudgetError as error:
            raise HTTPException(status_code=429, detail="Speech budget is unavailable") from error
        except (httpx.HTTPError, ValueError) as error:
            raise HTTPException(status_code=502, detail="Speech transcription failed") from error

    if test_clock_enabled:

        @app.post("/__test/advance-time", status_code=204)
        async def advance_test_time(request: AdvanceTestTime) -> None:
            if not 0 < request.seconds <= 120:
                raise HTTPException(status_code=400, detail="Invalid test clock advance")
            clock_offset[0] += request.seconds

    @app.post("/step")
    async def step(request: StepRequest) -> dict[str, object]:
        if settings.provider != "scripted":
            raise HTTPException(status_code=404, detail="Use the live session API")
        try:
            action = planner.plan(
                request.message,
                request.snapshot,
                ActionIdentity(
                    task_id=f"task-{uuid4().hex}",
                    action_id=f"action-{uuid4().hex}",
                    sequence_number=1,
                ),
            )
        except UnsupportedShoppingTask as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return to_wire(action)

    @app.post("/shopper/activity", status_code=204)
    async def shopper_activity():
        return Response(status_code=204)

    @app.post("/sessions", status_code=201)
    async def create_session(
        http_request: Request, request: SessionCreate | None = None
    ) -> dict[str, str]:
        authority = http_request.state.browser_authority
        for existing in list(authority.sessions):
            try:
                sessions.get(existing)
            except SessionNotFound:
                authority.sessions.discard(existing)
        if len(authority.sessions) >= (admission.browser_sessions if admission else 8):
            raise HTTPException(status_code=429, detail="Too many active sessions")
        invitation_id = None
        if admission is not None:
            if not sessions.has_capacity():
                raise HTTPException(status_code=503, detail="Session capacity reached")
            try:
                invitation_id = await invoke(admission, "allocate_session", authority)
            except AdmissionDenied as error:
                raise HTTPException(
                    status_code=429, detail="Demo session allowance exhausted"
                ) from error
        if authority.shopper != http_request.state.shopper:
            raise HTTPException(status_code=409, detail="Shopper identity changed")
        if len(authority.sessions) >= (admission.browser_sessions if admission else 8):
            raise HTTPException(status_code=429, detail="Too many active sessions")
        try:
            session = sessions.create(request.tab_id if request is not None else None)
        except OverflowError as error:
            raise HTTPException(status_code=503, detail="Session capacity reached") from error
        session.shopper = http_request.state.shopper
        session.invitation_id = invitation_id
        authority.sessions.add(session.session_id)
        return {"session_id": session.session_id}

    @app.post("/sessions/{session_id}/messages", status_code=202)
    async def submit_message(
        session_id: str,
        message: SessionMessage,
        x_tab_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        try:
            if settings.provider == "scripted":
                task = sessions.submit_message(
                    session_id,
                    message.text,
                    message.snapshot,
                    replace_active=message.replace_active,
                    tab_id=x_tab_id,
                )
            else:
                task = sessions.begin_interpretation(
                    session_id,
                    message.text,
                    message.snapshot,
                    replace_active=message.replace_active,
                    tab_id=x_tab_id,
                )
                await run_interpretation(session_id, task.task_id, task.model_call_id or "")
                await drive_plan(session_id)
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except TaskConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except LeaseConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except UnsupportedShoppingTask as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"task_id": task.task_id}

    @app.post("/sessions/{session_id}/tasks/{task_id}/retry", status_code=202)
    async def retry_task(
        session_id: str,
        task_id: str,
        request: RetryRequest,
        x_tab_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        try:
            task = sessions.retry_interpretation(session_id, task_id, x_tab_id, request.snapshot)
            await run_interpretation(session_id, task_id, task.model_call_id or "")
            await drive_plan(session_id)
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except (TaskConflict, LeaseConflict) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"task_id": task_id, "status": "retried"}

    @app.post("/sessions/{session_id}/tasks/{task_id}/answers", status_code=202)
    async def answer_question(
        session_id: str,
        task_id: str,
        answer: SessionAnswer,
        x_tab_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        try:
            if (
                settings.provider == "scripted"
                or sessions.is_auth_handoff(session_id, task_id, answer.question_id)
                or sessions.is_guarded_confirmation(session_id, task_id, answer.question_id)
                or sessions.is_stop_only_question(session_id, task_id, answer.question_id)
            ):
                task = sessions.answer(
                    session_id,
                    task_id,
                    answer.question_id,
                    answer.text,
                    answer.snapshot,
                    x_tab_id,
                )
            else:
                task = sessions.begin_answer_interpretation(
                    session_id,
                    task_id,
                    answer.question_id,
                    answer.text,
                    answer.snapshot,
                    x_tab_id,
                )
                await run_interpretation(session_id, task_id, task.model_call_id or "")
            await drive_plan(session_id)
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except (
            ActionResultMismatch,
            UnsupportedShoppingTask,
            TaskConflict,
            LeaseConflict,
        ) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "task_id": task.task_id,
            "status": (
                "awaiting_login"
                if task.auth_handoff
                and task.action is not None
                and task.action.action_id == answer.question_id
                else "resumed"
            ),
        }

    @app.get("/sessions/{session_id}/events")
    async def stream_events(
        session_id: str,
        request: Request,
        after: int = 0,
        once: bool = False,
        tab_id: str | None = None,
    ) -> StreamingResponse:
        return await session_event_response(sessions, session_id, request, after, once, tab_id)

    @app.post("/sessions/{session_id}/action-results", status_code=202)
    async def accept_action_result(
        session_id: str,
        action_result: ActionResult,
        x_tab_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        try:
            task = sessions.accept_result(session_id, action_result, x_tab_id)
            if task.status == "interpreting" and task.model_call_id:
                await run_interpretation(session_id, task.task_id, task.model_call_id)
            await drive_plan(session_id)
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except (ActionResultMismatch, LeaseConflict) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"task_id": task.task_id, "status": "accepted"}

    @app.post("/sessions/{session_id}/stop", status_code=202)
    async def stop_task(
        session_id: str, x_tab_id: str | None = Header(default=None)
    ) -> dict[str, str]:
        try:
            task = sessions.stop(session_id, x_tab_id)
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except (TaskConflict, LeaseConflict) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"task_id": task.task_id, "status": "cancelled"}

    @app.get("/sessions/{session_id}/state")
    async def session_state(session_id: str, tab_id: str) -> dict[str, object]:
        try:
            return sessions.state(session_id, tab_id)
        except SessionExpired as error:
            raise HTTPException(status_code=410, detail="Session expired") from error
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error

    @app.post("/sessions/{session_id}/reconcile")
    async def reconcile_session(
        session_id: str,
        request: ReconcileRequest,
        x_tab_id: str = Header(),
    ) -> dict[str, object]:
        try:
            return sessions.reconcile(session_id, x_tab_id, request.snapshot)
        except SessionExpired as error:
            raise HTTPException(status_code=410, detail="Session expired") from error
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error
        except LeaseConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/sessions/{session_id}/takeover")
    async def takeover_session(session_id: str, request: TakeoverRequest) -> dict[str, object]:
        try:
            sessions.takeover(session_id, request.tab_id)
            return sessions.state(session_id, request.tab_id)
        except SessionExpired as error:
            raise HTTPException(status_code=410, detail="Session expired") from error
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Session not found") from error

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[identity_settings["panel_origin"]],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def save_session_state(request: Request, call_next):
        """Write-through: every change is saved before the response is sent; a failed save
        fails the request instead of letting the Shopper see a change that will vanish."""
        try:
            response = await call_next(request)
            sessions.flush()
        except StateSaveFailed:
            return JSONResponse({"detail": "State could not be saved"}, status_code=503)
        return response

    app.state.events = events
    sessions.attach_event_log(events)
    app.add_middleware(RequestLog, events=events, routes=app.router.routes)
    return app


def __getattr__(name):
    if name != "app":
        raise AttributeError(name)
    default = create_app()
    globals()["app"] = default
    return default
