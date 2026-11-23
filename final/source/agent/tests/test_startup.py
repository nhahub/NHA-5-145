"""Generated-host startup boundary with offline durable authority."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from botocore.exceptions import ReadTimeoutError

from agent.lifecycle.startup import DynamoStartupRates, create_startup_handler
from agent.lifecycle.store import LifecycleUnavailable
from agent.tests.test_lifecycle_dynamodb import make_ready
from agent.tests.test_lifecycle_dynamodb import world as _world_fixture

world = _world_fixture

ORIGIN = "https://d123example.cloudfront.net"


def event(path="/", method="GET", body=None, **changes):
    result = {
        "version": "2.0",
        "rawPath": path,
        "rawQueryString": "",
        "requestContext": {"http": {"method": method, "path": path}},
        "headers": {"origin": ORIGIN, "content-type": "application/json"},
        "isBase64Encoded": False,
        "body": body,
    }
    result.update(changes)
    return result


def handler(world):
    now, invitations, _, _, life, _ = world
    rates = DynamoStartupRates(invitations, clock=lambda: now[0])
    return create_startup_handler(life, rates, origin=ORIGIN)


def test_startup_page_status_and_wake_do_not_dispatch_or_redeem(world):
    _, invitations, _, code, life, _ = world
    serve = handler(world)
    response = serve(event(), None)
    assert response["statusCode"] == 200
    assert "https://app.scpilot.tech/" in response["body"]
    assert "localhost" not in response["body"]
    assert "NONCE" not in response["body"]
    assert "frame-ancestors 'none'" in response["headers"]["Content-Security-Policy"]
    assert life.status()["generation"] == 0
    result = serve(event("/wake", "POST", json.dumps({"code": code})), None)
    assert result["statusCode"] == 202
    assert json.loads(result["body"])["state"] == "starting"
    assert code not in str(result)
    assert invitations.status()[0]["used_redemptions"] == 0
    assert life.claim_command()["operation"] == "start"
    status = serve(event("/status"), None)
    assert json.loads(status["body"])["generation"] == 1
    for item in (response, result, status):
        assert item["headers"]["Cache-Control"] == "no-store"
        assert item["headers"]["Referrer-Policy"] == "no-referrer"
        assert item["headers"]["X-Content-Type-Options"] == "nosniff"
        assert "Access-Control-Allow-Origin" not in item["headers"]


def test_status_does_not_extend_activity_or_expose_private_authority(world):
    now, invitations, _, code, life, _ = world
    make_ready(world)
    before = invitations._read("lifecycle#host")
    serve = handler(world)
    now[0] += 10
    response = serve(event("/status"), None)
    assert set(json.loads(response["body"])) == {
        "state",
        "generation",
        "remaining_seconds",
        "retry_after",
    }
    assert invitations._read("lifecycle#host") == before
    assert code not in response["body"]


@pytest.mark.parametrize("count", [36, 39, 64])
def test_startup_accepts_bounded_cloudfront_headers_without_bypassing_invitation(world, count):
    headers = {"origin": ORIGIN, "content-type": "application/json"}
    headers.update({f"x-edge-{index}": "synthetic" for index in range(count - 2)})
    serve = handler(world)
    assert serve(event("/status", headers=headers), None)["statusCode"] == 200
    denied = serve(event("/wake", "POST", '{"code":"bad"}', headers=headers), None)
    assert denied["statusCode"] == 403
    assert world[4].status()["generation"] == 0


@pytest.mark.parametrize(
    "headers",
    [
        {f"x-edge-{index}": "a" for index in range(65)},
        {f"x-edge-{index}": "a" * 110 for index in range(39)},
    ],
)
def test_startup_rejects_excess_header_count_or_bytes_before_waking(world, headers):
    response = handler(world)(
        event("/wake", "POST", json.dumps({"code": world[3]}), headers=headers), None
    )
    assert response["statusCode"] == 400
    assert world[4].status()["generation"] == 0


@pytest.mark.parametrize(
    "body",
    [
        '{"code":"a","code":"b"}',
        '{"code":"bad"}',
        '{"code":null}',
        '{"code":[]}',
        '{"code":"bad","extra":1}',
        "[]",
        "{",
        '"x"',
    ],
)
def test_startup_bad_invitation_or_json_is_denied_without_echo(world, body):
    response = handler(world)(event("/wake", "POST", body), None)
    assert response["statusCode"] == 403
    assert response["body"] == '{"state":"denied"}'
    assert world[4].status()["generation"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"version": "1.0"},
        {"rawQueryString": "code=secret"},
        {"queryStringParameters": {"code": "secret"}},
        {"body": "x" * 2000},
        {"isBase64Encoded": 1},
        {"headers": {"origin": [ORIGIN]}},
        {"headers": {"Origin": ORIGIN}},
        {"headers": {"x": "x" * 5000}},
        {"requestContext": {"http": {"method": [], "path": "/wake"}}},
        {"requestContext": {"http": {"method": "POST", "path": "/status"}}},
        {"cookies": ["secret=value"]},
    ],
)
def test_startup_malformed_transport_is_bounded_and_never_wakes(world, change):
    request = event("/wake", "POST", json.dumps({"code": world[3]}))
    request.update(change)
    response = handler(world)(request, None)
    assert response["statusCode"] == 400
    assert "secret" not in response["body"]
    assert world[4].status()["generation"] == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://evil.example", "content-type": "application/json"},
        {"content-type": "application/json"},
        {"origin": ORIGIN, "content-type": "text/plain"},
        {"origin": ORIGIN, "content-type": "application/json, application/json"},
    ],
)
def test_startup_requires_exact_origin_and_json(world, headers):
    response = handler(world)(
        event("/wake", "POST", json.dumps({"code": world[3]}), headers=headers), None
    )
    assert response["statusCode"] == 403
    assert world[4].status()["generation"] == 0


def test_startup_base64_is_strict_and_decoded_body_is_bounded(world):
    serve = handler(world)
    good = base64.b64encode(json.dumps({"code": world[3]}).encode()).decode()
    assert serve(event("/wake", "POST", good, isBase64Encoded=True), None)["statusCode"] == 202
    for bad in (good + "!", base64.b64encode(b"\xff").decode(), "YQ==\n", "a" * 1369):
        assert serve(event("/wake", "POST", bad, isBase64Encoded=True), None)["statusCode"] == 400


@pytest.mark.parametrize("path,method", [("/admin", "GET"), ("/status", "POST"), ("/wake", "GET")])
def test_startup_unknown_route_is_closed(world, path, method):
    assert handler(world)(event(path, method), None)["statusCode"] == 404


@pytest.mark.parametrize(
    "origin",
    [
        "http://d123.cloudfront.net",
        ORIGIN + "/",
        "https://cloudfront.net",
        ORIGIN + ".evil",
        "https://app.scpilot.tech",
        "https://d123.cloudfront.net:443",
        None,
    ],
)
def test_startup_only_accepts_configured_generated_https_origin(world, origin):
    with pytest.raises(ValueError):
        create_startup_handler(world[4], object(), origin=origin)


def test_durable_rate_limits_persist_across_reopening(world):
    now, invitations, *_ = world
    first = DynamoStartupRates(invitations, clock=lambda: now[0])
    for _ in range(10):
        first.rate("wake")
    reopened = DynamoStartupRates(invitations, clock=lambda: now[0])
    with pytest.raises(LifecycleUnavailable):
        reopened.rate("wake")
    now[0] = 1020
    reopened.rate("wake")
    for lane in ("arbitrary", [], None):
        with pytest.raises(LifecycleUnavailable):
            reopened.rate(lane)


def test_durable_rate_competing_requests_cannot_over_admit(world, monkeypatch):
    now, invitations, *_ = world
    rates = DynamoStartupRates(invitations, clock=lambda: now[0])
    # Moto's backup/rollback transactions are not thread-isolated. Serialize
    # only mock server transactions, leaving concurrent strong reads/CAS intact.
    lock, original = Lock(), invitations.client.transact_write_items

    def atomic(**request):
        with lock:
            return original(**request)

    monkeypatch.setattr(invitations.client, "transact_write_items", atomic)

    def run(_):
        try:
            rates.rate("wake")
            return True
        except LifecycleUnavailable:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, range(24)))
    assert 1 <= sum(results) <= 10
    assert invitations._read("startup-rate#wake")["count"] == sum(results)


def test_durable_rate_uncertain_write_is_not_retried_and_consumption_is_retained(
    world, monkeypatch
):
    now, invitations, _, _, _, client = world
    rates = DynamoStartupRates(invitations, clock=lambda: now[0])
    original = client.transact_write_items
    calls = []

    def lost(**request):
        calls.append(request)
        original(**request)
        raise ReadTimeoutError(endpoint_url="https://dynamodb.eu-north-1.amazonaws.com")

    monkeypatch.setattr(client, "transact_write_items", lost)
    with pytest.raises(LifecycleUnavailable):
        rates.rate("wake")
    assert len(calls) == 1
    assert invitations._read("startup-rate#wake")["count"] == 1


def test_durable_rate_clock_rollback_and_corruption_fail_closed(world):
    now, invitations, _, _, _, client = world
    rates = DynamoStartupRates(invitations, clock=lambda: now[0])
    rates.rate("wake")
    now[0] -= 1
    with pytest.raises(LifecycleUnavailable):
        rates.rate("wake")
    now[0] += 1
    client.update_item(
        TableName=invitations.table,
        Key=invitations._key("startup-rate#wake"),
        UpdateExpression="SET #count=:bad",
        ExpressionAttributeNames={"#count": "count"},
        ExpressionAttributeValues={":bad": {"BOOL": True}},
    )
    assert (
        handler(world)(event("/wake", "POST", json.dumps({"code": world[3]})), None)["statusCode"]
        == 503
    )
    assert world[4].status()["generation"] == 0


def test_durable_rate_deleted_row_cannot_be_reinitialized(world):
    now, invitations, _, _, _, client = world
    DynamoStartupRates(invitations, clock=lambda: now[0]).rate("wake")
    client.delete_item(TableName=invitations.table, Key=invitations._key("startup-rate#wake"))
    with pytest.raises(LifecycleUnavailable):
        DynamoStartupRates(invitations, clock=lambda: now[0]).rate("wake")


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -1])
def test_durable_rate_bad_clock_is_closed(world, bad):
    with pytest.raises(LifecycleUnavailable):
        DynamoStartupRates(world[1], clock=lambda: bad).rate("http")


@pytest.mark.parametrize("lane,limit", [("http", 240), ("poll", 120)])
def test_each_fixed_durable_lane_enforces_its_limit(world, lane, limit):
    now, invitations, *_ = world
    rates = DynamoStartupRates(invitations, clock=lambda: now[0])
    for _ in range(limit):
        rates.rate(lane)
    with pytest.raises(LifecycleUnavailable):
        rates.rate(lane)


@pytest.mark.parametrize("invalid", ["expired", "revoked"])
def test_startup_rejects_expired_or_revoked_invitation_without_starting(world, invalid):
    now, invitations, invitation, code, life, _ = world
    if invalid == "expired":
        now[0] = 20000
    else:
        invitations.revoke(invitation)
    response = handler(world)(event("/wake", "POST", json.dumps({"code": code})), None)
    assert response["statusCode"] == 403
    assert life.status()["generation"] == 0


def test_http_rate_failure_has_no_authority_or_sdk_details(world):
    serve = handler(world)
    for _ in range(10):
        assert serve(event("/wake", "POST", '{"code":"bad"}'), None)["statusCode"] == 403
    response = handler(world)(event("/wake", "POST", json.dumps({"code": world[3]})), None)
    assert response["statusCode"] == 503
    assert response["body"] == '{"state":"unavailable"}'
    assert world[4].status()["generation"] == 0
