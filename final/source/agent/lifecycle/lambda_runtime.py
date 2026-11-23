"""Explicit injected factories; no environment-selected or import-time activation."""

import json
import re
from dataclasses import dataclass, field
from time import time

import boto3
from botocore.config import Config

from agent.admission.dynamodb import DynamoInvitationStore, _identifier
from agent.lifecycle.controller import ControlObserver, ControlWorker, is_tick
from agent.lifecycle.dynamodb import DynamoLifecycle
from agent.lifecycle.executor import EC2CommandExecutor
from agent.lifecycle.operating import OperatingAuthority, OperatingPolicy
from agent.lifecycle.readiness import HTTPSReadinessProbe
from agent.lifecycle.startup import DynamoStartupRates, create_startup_handler
from agent.lifecycle.store import LifecycleUnavailable

TARGET = r"arn:aws:lambda:eu-north-1:[0-9]{12}:function:[A-Za-z0-9_-]{1,64}"


@dataclass(frozen=True)
class ControlSettings:
    role: str
    table: str
    namespace: str
    invitation_identity: str
    lifecycle_identity: str
    origin: str | None = None
    controller_arn: str | None = None
    instance: str | None = None
    release: str | None = None
    readiness_secret: bytes | None = field(default=None, repr=False)
    operating: OperatingPolicy | None = None

    def __post_init__(self):
        try:
            if self.operating is not None:
                if type(self.operating) is not OperatingPolicy:
                    raise ValueError()
                self.operating.__post_init__()
            if type(self.role) is not str or self.role not in {"startup", "controller"}:
                raise ValueError()
            for value, pattern in (
                (self.table, r"[A-Za-z0-9_.-]{3,255}"),
                (self.namespace, r"[A-Za-z0-9_-]{1,64}"),
            ):
                if type(value) is not str or re.fullmatch(pattern, value) is None:
                    raise ValueError()
            _identifier(self.invitation_identity)
            _identifier(self.lifecycle_identity)
            if self.role == "startup":
                if (
                    type(self.origin) is not str
                    or re.fullmatch(r"https://[a-z0-9]{1,63}\.cloudfront\.net", self.origin) is None
                    or type(self.controller_arn) is not str
                    or re.fullmatch(TARGET, self.controller_arn) is None
                    or any(
                        value is not None
                        for value in (self.instance, self.release, self.readiness_secret)
                    )
                ):
                    raise ValueError()
            else:
                if (
                    self.origin is not None
                    or self.controller_arn is not None
                    or type(self.instance) is not str
                    or re.fullmatch(r"i-[0-9a-f]{17}", self.instance) is None
                ):
                    raise ValueError()
                HTTPSReadinessProbe(self.readiness_secret, self.release)
                if self.operating is not None and self.operating.instance != self.instance:
                    raise ValueError()
        except Exception:
            raise ValueError("Exact restricted role configuration required") from None


def _sdk(service):
    if service not in {"dynamodb", "lambda", "ec2"}:
        raise ValueError("Fixed control service required")
    return boto3.client(
        service,
        region_name="eu-north-1",
        endpoint_url=f"https://{service}.eu-north-1.amazonaws.com",
        use_ssl=True,
        verify=True,
        config=Config(
            connect_timeout=5,
            read_timeout=15,
            proxies={},
            retries={"mode": "standard", "total_max_attempts": 1},
            ignore_configured_endpoint_urls=True,
        ),
    )


class LambdaNotifier:
    def __init__(self, client, target):
        if type(target) is not str or re.fullmatch(TARGET, target) is None:
            raise ValueError("Fixed controller target required")
        self.client, self.target = client, target
        self._configuration()

    def _configuration(self):
        try:
            meta, config = self.client.meta, self.client.meta.config
            attempts = (config.retries or {}).get("total_max_attempts")
            if (
                meta.service_model.service_name != "lambda"
                or meta.region_name != "eu-north-1"
                or meta.endpoint_url != "https://lambda.eu-north-1.amazonaws.com"
                or type(attempts) is not int
                or attempts != 1
                or type(config.connect_timeout) not in {int, float}
                or not 0 < config.connect_timeout <= 5
                or type(config.read_timeout) not in {int, float}
                or not 0 < config.read_timeout <= 15
                or type(self.target) is not str
                or re.fullmatch(TARGET, self.target) is None
            ):
                raise ValueError()
        except Exception:
            raise LifecycleUnavailable() from None

    def __call__(self, kind, generation):
        try:
            self._configuration()
            if (
                type(kind) is not str
                or kind not in {"dispatch", "observe"}
                or type(generation) is not int
                or not 1 <= generation <= 2**53 - 1
            ):
                raise ValueError()
            response = self.client.invoke(
                FunctionName=self.target,
                InvocationType="Event",
                Payload=json.dumps(
                    {"kind": kind, "generation": generation}, separators=(",", ":")
                ).encode(),
            )
            try:
                if (
                    response.get("StatusCode") != 202
                    or response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 202
                    or response.get("FunctionError")
                ):
                    raise ValueError()
            finally:
                if response.get("Payload") is not None:
                    response["Payload"].close()
        except Exception:
            raise LifecycleUnavailable() from None


def _lifecycle(settings, role, sdk_factory, clock):
    if type(settings) is not ControlSettings or settings.role != role:
        raise ValueError("Exact control role required")
    settings.__post_init__()
    store = DynamoInvitationStore(
        sdk_factory("dynamodb"),
        settings.table,
        settings.namespace,
        settings.invitation_identity,
        clock=clock,
        operating=settings.operating,
        operating_control=role == "controller",
    )
    return DynamoLifecycle(store, settings.lifecycle_identity, clock=clock)


def create_startup_runtime(settings, *, sdk_factory=_sdk, clock=time):
    lifecycle = _lifecycle(settings, "startup", sdk_factory, clock)
    notify = LambdaNotifier(sdk_factory("lambda"), settings.controller_arn)
    rates = DynamoStartupRates(lifecycle.invitations, clock=clock)
    return create_startup_handler(lifecycle, rates, origin=settings.origin, notify=notify)


def create_controller_runtime(
    settings, *, sdk_factory=_sdk, clock=time, http_transport=None, tick_writer=print
):
    lifecycle = _lifecycle(settings, "controller", sdk_factory, clock)
    client = sdk_factory("ec2")
    probe = HTTPSReadinessProbe(
        settings.readiness_secret, settings.release, transport=http_transport
    )
    operating = (
        OperatingAuthority(lifecycle.invitations, settings.operating)
        if settings.operating is not None
        else None
    )
    worker = ControlWorker(
        lifecycle,
        EC2CommandExecutor(lifecycle, client, settings.instance, operating=operating),
        ControlObserver(lifecycle, client, settings.instance, probe, operating=operating),
    )

    def handler(event, context):
        try:
            result = worker.handle(event)
            if is_tick(event):
                timestamp = clock()
                if type(timestamp) not in {int, float} or not 0 <= timestamp < 2**43:
                    raise ValueError()
                tick_writer(
                    json.dumps(
                        {
                            "_aws": {
                                "Timestamp": int(timestamp * 1000),
                                "CloudWatchMetrics": [
                                    {
                                        "Namespace": "ShoppingCopilot/Lifecycle",
                                        "Dimensions": [["Component"]],
                                        "Metrics": [{"Name": "TickCompleted", "Unit": "Count"}],
                                    }
                                ],
                            },
                            "Component": "Controller",
                            "TickCompleted": 1,
                        },
                        separators=(",", ":"),
                    )
                )
            return result
        except Exception:
            if is_tick(event):
                raise RuntimeError("Scheduled observation unavailable") from None
            return {"state": "unavailable"}

    return handler
