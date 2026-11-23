"""Role-specific factories, durable wake and stubbed asynchronous queue acceptance."""

import json
from dataclasses import replace

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ReadTimeoutError
from botocore.stub import Stubber

from agent.lifecycle.lambda_runtime import (
    ControlSettings,
    create_controller_runtime,
    create_startup_runtime,
)
from agent.tests.test_control_worker import described
from agent.tests.test_lifecycle_dynamodb import world as _world
from agent.tests.test_lifecycle_executor import INSTANCE, reply
from agent.tests.test_lifecycle_executor import ec2 as _ec2
from agent.tests.test_readiness import RELEASE, SECRET
from agent.tests.test_startup import ORIGIN, event

world, ec2 = _world, _ec2
TARGET = "arn:aws:lambda:eu-north-1:123456789012:function:copilot-controller"


def settings(world, role="startup"):
    _, store, _, _, life, _ = world
    common = dict(
        role=role,
        table=store.table,
        namespace=store.namespace,
        invitation_identity=store.identity,
        lifecycle_identity=life.identity,
    )
    if role == "startup":
        return ControlSettings(**common, origin=ORIGIN, controller_arn=TARGET)
    return ControlSettings(**common, instance=INSTANCE, release=RELEASE, readiness_secret=SECRET)


@pytest.fixture
def queue():
    client = boto3.client(
        "lambda",
        region_name="eu-north-1",
        aws_access_key_id="offline-dummy",
        aws_secret_access_key="offline-dummy",
        config=Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1}),
    )
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()
    client.close()


def startup(world, queue):
    clients, created = {"dynamodb": world[5], "lambda": queue[0]}, []

    def sdk(name):
        created.append(name)
        return clients[name]

    return create_startup_runtime(
        settings(world), sdk_factory=sdk, clock=lambda: world[0][0]
    ), created


def enqueue(stub, kind="dispatch"):
    stub.add_response(
        "invoke",
        {"StatusCode": 202, "ResponseMetadata": {"HTTPStatusCode": 202}},
        {
            "FunctionName": TARGET,
            "InvocationType": "Event",
            "Payload": json.dumps({"kind": kind, "generation": 1}, separators=(",", ":")).encode(),
        },
    )


def test_startup_factory_has_no_ec2_client_and_queue_payload_has_no_code(world, queue):
    handler, created = startup(world, queue)
    assert created == ["dynamodb", "lambda"]
    assert handler(event(), None)["statusCode"] == 200
    assert handler(event("/status"), None)["statusCode"] == 200
    enqueue(queue[1])
    response = handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)
    assert response["statusCode"] == 202
    assert json.loads(response["body"])["state"] == "starting"
    enqueue(queue[1], "observe")
    assert handler(event("/status"), None)["statusCode"] == 200


def test_invalid_requests_never_enqueue(world, queue):
    handler, _ = startup(world, queue)
    for request in (
        event("/no"),
        event("/wake", "POST", '{"code":"bad"}'),
        event("/wake", "POST", json.dumps({"code": world[3]}), headers={}),
    ):
        assert handler(request, None)["statusCode"] in {403, 404}
    assert world[4].status()["generation"] == 0


def test_lost_queue_ack_retains_intent_and_retry_coalesces_generation(world, queue, monkeypatch):
    handler, _ = startup(world, queue)
    calls = []
    original = queue[0].invoke

    def lost(**request):
        calls.append(request)
        raise ReadTimeoutError(endpoint_url="https://lambda.eu-north-1.amazonaws.com")

    monkeypatch.setattr(queue[0], "invoke", lost)
    request = event("/wake", "POST", json.dumps({"code": world[3]}))
    assert handler(request, None)["statusCode"] == 503
    assert len(calls) == 1
    assert world[4].status()["generation"] == 1
    monkeypatch.setattr(queue[0], "invoke", original)
    enqueue(queue[1])
    assert handler(request, None)["statusCode"] == 202
    assert world[4].status()["generation"] == 1


def test_controller_factory_has_no_queue_client_and_ordinary_health_never_ready(world, ec2):
    import httpx

    clients, created = {"dynamodb": world[5], "ec2": ec2[0]}, []

    def sdk(name):
        created.append(name)
        return clients[name]

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ok"}))
    handler = create_controller_runtime(
        settings(world, "controller"),
        sdk_factory=sdk,
        clock=lambda: world[0][0],
        http_transport=transport,
    )
    assert created == ["dynamodb", "ec2"]
    world[4].wake(world[3])
    ec2[1].add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    assert handler({"kind": "dispatch", "generation": 1}, None)["state"] == "starting"
    assert handler({"kind": "dispatch", "generation": True}, None) == {"state": "unavailable"}


@pytest.mark.parametrize(
    "field,bad",
    [
        ("controller_arn", TARGET.replace("eu-north-1", "us-east-1")),
        ("controller_arn", TARGET + ":*"),
        ("origin", ORIGIN + ".evil"),
        ("table", "*"),
        ("namespace", "demo*"),
        ("role", "anything"),
        ("lifecycle_identity", "reset"),
        ("instance", INSTANCE),
    ],
)
def test_runtime_settings_reject_unsafe_or_cross_role_values(world, field, bad):
    with pytest.raises(ValueError):
        replace(settings(world), **{field: bad})


def test_runtime_secret_is_not_in_settings_repr_and_wrong_role_has_no_sdk_entry(world):
    config = settings(world, "controller")
    assert SECRET.decode() not in repr(config)

    def forbidden(name):
        pytest.fail("SDK factory reached for wrong role")

    with pytest.raises(ValueError):
        create_startup_runtime(config, sdk_factory=forbidden)


def test_queue_bad_client_policy_refuses_without_losing_wake(world, queue, monkeypatch):
    handler, _ = startup(world, queue)
    monkeypatch.setattr(queue[0].meta.config, "retries", {"total_max_attempts": 2})
    assert (
        handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)["statusCode"] == 503
    )
    assert world[4].status()["state"] == "starting"


def test_factories_connect_wake_to_signed_readiness_without_duplicate_start(world, queue, ec2):
    import httpx

    from agent.lifecycle.readiness import readiness_reply

    startup_handler, _ = startup(world, queue)

    def health(request):
        value = readiness_reply(
            request.headers, secret=SECRET, release=RELEASE, generation=1, ready=True
        )
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(value).encode()))

    controller = create_controller_runtime(
        settings(world, "controller"),
        sdk_factory=lambda name: {"dynamodb": world[5], "ec2": ec2[0]}[name],
        clock=lambda: world[0][0],
        http_transport=httpx.MockTransport(health),
    )
    enqueue(queue[1])
    assert (
        startup_handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)["statusCode"]
        == 202
    )
    ec2[1].add_response("start_instances", reply(), {"InstanceIds": [INSTANCE]})
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    assert controller({"kind": "dispatch", "generation": 1}, None)["state"] == "ready"
    enqueue(queue[1], "observe")
    response = startup_handler(event("/status"), None)
    assert json.loads(response["body"])["state"] == "ready"
    ec2[1].add_response("describe_instances", described(), {"InstanceIds": [INSTANCE]})
    assert controller({"kind": "observe", "generation": 1}, None)["state"] == "ready"


def test_default_sdk_builder_is_explicit_bounded_and_lazy(monkeypatch):
    from agent.lifecycle.lambda_runtime import _sdk

    calls = []
    sentinel = object()

    def capture(service, **options):
        calls.append((service, options))
        return sentinel

    monkeypatch.setattr(boto3, "client", capture)
    assert not calls
    assert _sdk("lambda") is sentinel
    service, options = calls[0]
    assert service == "lambda"
    assert options["region_name"] == "eu-north-1"
    assert options["endpoint_url"] == "https://lambda.eu-north-1.amazonaws.com"
    assert options["verify"] is True and options["use_ssl"] is True
    assert options["config"].retries == {"mode": "standard", "total_max_attempts": 1}
    assert options["config"].connect_timeout == 5 and options["config"].read_timeout == 15
    assert options["config"].proxies == {}


@pytest.mark.parametrize(
    "response",
    [
        {"StatusCode": 200, "ResponseMetadata": {"HTTPStatusCode": 200}},
        {"StatusCode": 202, "ResponseMetadata": {"HTTPStatusCode": 200}},
        {
            "StatusCode": 202,
            "ResponseMetadata": {"HTTPStatusCode": 202},
            "FunctionError": "private",
        },
    ],
)
def test_queue_malformed_acceptance_is_unavailable_without_retry(world, queue, response):
    handler, _ = startup(world, queue)
    queue[1].add_response("invoke", response)
    result = handler(event("/wake", "POST", json.dumps({"code": world[3]})), None)
    assert result["statusCode"] == 503
    assert result["body"] == '{"state":"unavailable"}'
    assert world[4].status()["generation"] == 1
