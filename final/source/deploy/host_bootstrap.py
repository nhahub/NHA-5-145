"""Explicit pre-loop host assembly. No import-time or environment-selected activation."""

import asyncio
from contextlib import suppress
from inspect import iscoroutinefunction
from pathlib import Path
from time import time

from agent.admission.async_runtime import AsyncAdmissionPolicy
from agent.admission.dynamodb import DynamoInvitationStore
from agent.app import create_app
from agent.catalogue_client import CatalogueClient
from agent.event_log import DebugSwitch
from agent.lifecycle.async_work import AsyncLifecycleWork
from agent.lifecycle.dynamodb import DynamoLifecycle
from agent.lifecycle.host_health import HostReadiness
from agent.lifecycle.lambda_runtime import _sdk
from agent.lifecycle.store import LifecycleUnavailable
from agent.storefront_service import StorefrontService, identity_config
from deploy.host_checks import HostChecks, unqualified_provider
from deploy.host_config import HostSettings
from deploy.host_event_log import DEBUG_MARKER, HostFileSink
from deploy.host_log_shipper import Shipper, logs_client
from deploy.provider_binding import ProviderBinding
from deploy.provider_qualification import ProviderQualification, QualificationProof


class _OwnedAdmission(AsyncAdmissionPolicy):
    def __init__(self, store, **limits):
        super().__init__(store, **limits)
        self._sdk, self._sdk_closed = store.client, False
        self._closing = None
        self._work = None

    async def _drain(self):
        while True:
            try:
                if self._work is not None:
                    await self._work.close()
                await super().close()
                break
            except asyncio.CancelledError:
                # Even cancellation during loop shutdown cannot advance SDK close.
                continue
        if not self._sdk_closed:
            self._sdk_closed = True
            with suppress(Exception):
                await asyncio.to_thread(self._sdk.close)

    async def close(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._drain())
            self._closing.add_done_callback(_ProviderGate._done)
        await asyncio.shield(self._closing)


class _ProviderGate:
    def __init__(self, verify):
        self._verify, self._flight, self._closed = verify, None, False
        self._qualified, self._closing = None, None

    def attach(self, qualified):
        if (
            type(qualified) is not ProviderQualification
            or self._qualified is not None
            or self._verify is not unqualified_provider
            or self._flight is not None
            or self._closed
        ):
            raise ValueError("Host startup refused")
        self._qualified = qualified

    @staticmethod
    def _done(task):
        if not task.cancelled():
            task.exception()

    async def _call(self, action):
        if self._closed or self._flight is not None and not self._flight.done():
            return None
        task = self._flight = asyncio.create_task(action())
        task.add_done_callback(self._done)
        try:
            done, _ = await asyncio.wait({task}, timeout=1)
            return (
                task.result()
                if task in done and not task.cancelled() and not self._closed
                else None
            )
        except Exception:
            return None
        finally:
            if not task.done():
                task.cancel()

    async def observe(self):
        if self._qualified is not None:
            if self._closed:
                return None
            # Captured verification is in-memory and does not suspend for I/O.
            # It must not consume the legacy callback's single-flight slot.
            result = await self._qualified.observe()
            return result if type(result) is QualificationProof and not self._closed else None
        result = await self._call(self._verify)
        return True if result is True else None

    async def ready(self):
        return await self.observe() is not None

    async def recheck(self, proof):
        if self._qualified is None:
            return proof is True and not self._closed
        return (
            not self._closed and await self._qualified.recheck(proof) is True and not self._closed
        )

    async def _drain(self):
        try:
            if self._flight is not None:
                if not self._flight.done():
                    self._flight.cancel()
                await asyncio.gather(self._flight, return_exceptions=True)
        finally:
            if self._qualified is not None:
                await self._qualified.close()

    async def close(self):
        self._closed = True
        if self._closing is None:
            self._closing = asyncio.create_task(self._drain())
            self._closing.add_done_callback(self._done)
        await asyncio.shield(self._closing)


class _QualifiedWork(AsyncLifecycleWork):
    def __init__(self, lifecycle, sessions, provider):
        super().__init__(lifecycle, sessions)
        self._provider = provider

    async def check(self):
        generation = self.generation
        proof = await self._provider.observe()
        if proof is None:
            raise LifecycleUnavailable()
        # Qualification is outside the actor lock. Pending renewal never waits on it.
        await super().check()
        if not await self._provider.recheck(proof):
            raise LifecycleUnavailable()
        if self.failed or self.generation != generation or self._provider._closed:
            raise LifecycleUnavailable()

    async def begin(self):
        generation = self.generation
        proof = await self._provider.observe()
        if proof is None:
            raise LifecycleUnavailable()
        token = await super().begin()
        try:
            if (
                not await self._provider.recheck(proof)
                or self.failed
                or self.generation != generation
                or self._provider._closed
            ):
                raise LifecycleUnavailable()
            return token
        except BaseException:
            cleanup = asyncio.create_task(self._release_refused(token))
            self._cleanup.add(cleanup)
            cleanup.add_done_callback(self._cleanup.discard)
            await asyncio.shield(cleanup)
            raise

    async def _release_refused(self, token):
        try:
            await self.finish(token)
        except Exception:
            self.failed = True

    async def close(self):
        try:
            await self._provider.close()
        finally:
            await super().close()


class _OwnedReadiness(HostReadiness):
    def __init__(self, work, settings, checks, provider):
        super().__init__(
            work, settings.readiness_secret, settings.fingerprint, checks.checks(provider.ready)
        )
        self.checks_owner = checks
        self._provider = provider

    async def _aggregate(self, generation):
        proof = await self._provider.observe()
        if proof is None or not await super()._aggregate(generation):
            return False
        return (
            await self._provider.recheck(proof)
            and not self._closed
            and not self.work.failed
            and self.work.generation == generation
        )

    async def close(self):
        try:
            await super().close()
        finally:
            await self.checks_owner.close()


def _runtime_root():
    return Path(__file__).resolve().parents[1]


def create_host_app(
    settings,
    *,
    sdk_factory=_sdk,
    logs_factory=logs_client,
    provider_ready=unqualified_provider,
    model_client=None,
    http_transport=None,
    clock=time,
    qualification=None,
    maximum_attempts=None,
):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise ValueError("Host startup refused")
    sdk, admission, service, work, checks, readiness, provider = (None,) * 7
    shipper = None

    async def cleanup():
        if shipper is not None:
            with suppress(Exception):
                await asyncio.to_thread(shipper.stop)
        for resource in (readiness, checks, work, provider, admission):
            if resource is not None:
                with suppress(Exception):
                    await resource.close()
        if admission is None and sdk is not None:
            with suppress(Exception):
                await asyncio.to_thread(sdk.close)
        if service is not None:
            with suppress(Exception):
                await service.aclose()

    try:
        if type(settings) is not HostSettings or not iscoroutinefunction(provider_ready):
            raise ValueError()
        settings._validate()
        if settings.operating is not None:
            if maximum_attempts is None:
                maximum_attempts = settings.operating_attempt_ceiling
            elif maximum_attempts != settings.operating_attempt_ceiling:
                raise ValueError()
        if qualification is not None:
            if (
                type(qualification) is not ProviderBinding
                or qualification.settings is not settings
                or provider_ready is not unqualified_provider
            ):
                raise ValueError()
            qualification.snapshot()
        if _runtime_root() != settings.release:
            raise ValueError()
        sdk = sdk_factory("dynamodb")
        store = DynamoInvitationStore(
            sdk,
            settings.table,
            settings.namespace,
            settings.invitation_identity,
            clock=clock,
            operating=settings.operating,
        )
        lifecycle = DynamoLifecycle(store, settings.lifecycle_identity, clock=clock)
        admission = _OwnedAdmission(store, **settings.admission_limits)
        values = settings.environment()
        service = StorefrontService(identity_config(values), environment=values)
        provider = _ProviderGate(provider_ready)

        def work_factory(lifecycle, sessions):
            nonlocal work
            work = _QualifiedWork(lifecycle, sessions, provider)
            admission._work = work
            return work

        def readiness_factory(app, work):
            nonlocal checks, readiness
            if qualification is not None:
                provider.attach(ProviderQualification(qualification, app.state.llm_client))
            checks = HostChecks(
                release=settings.release,
                fingerprint=settings.fingerprint,
                catalogue=settings.catalogue,
                admission=admission,
                guard=app.state.llm_client,
                service=service,
                transport=http_transport,
            )
            readiness = _OwnedReadiness(work, settings, checks, provider)
            return readiness

        app = create_app(
            environment=values,
            inference_maximum_attempts=maximum_attempts,
            llm_client=model_client,
            admission=admission,
            lifecycle=lifecycle,
            lifecycle_work_factory=work_factory,
            readiness_factory=readiness_factory,
            storefront_service=service,
            catalogue_client=CatalogueClient(
                secret=settings.service_secret, transport=http_transport
            ),
            catalogue_retrieval_enabled=True,
            event_sink=HostFileSink(),
            debug_switch=DebugSwitch(DEBUG_MARKER, owner=0),
            release=settings.fingerprint[:12],
        )
        # Ordinary event records go from the private file to CloudWatch, per release.
        shipper = Shipper(client=logs_factory(), stream=f"agent-{settings.fingerprint[:12]}")
        shipper.start()
        app.state.log_shipper = shipper
        app.state.host_cleanup = cleanup
        return app
    except Exception:
        pass

    asyncio.run(cleanup())
    raise ValueError("Host startup refused")
