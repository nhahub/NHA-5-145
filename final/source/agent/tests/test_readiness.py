"""Authenticated readiness under intercepted HTTPS only; never a live probe."""

import copy

import httpx
import pytest

from agent.lifecycle.readiness import HTTPSReadinessProbe, readiness_reply

SECRET, RELEASE = b"offline-test-key-32-bytes-exact!!!", "a" * 64


def probe_for(callback, **options):
    def streaming(request):
        response = callback(request)
        if response.is_stream_consumed:
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                stream=httpx.ByteStream(response.content),
                request=request,
            )
        return response

    return HTTPSReadinessProbe(SECRET, RELEASE, transport=httpx.MockTransport(streaming), **options)


def reply(request, *, ready=True):
    return readiness_reply(
        request.headers, secret=SECRET, release=RELEASE, generation=1, ready=ready
    )


def test_readiness_proof_binds_fixed_url_release_generation_and_nonce():
    seen = []

    def serve(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=reply(request))

    assert probe_for(serve).check(1) is True
    assert seen == ["https://app.scpilot.tech/health"]


@pytest.mark.parametrize(
    "field,bad",
    [
        ("generation", True),
        ("generation", 2),
        ("release", "b" * 64),
        ("nonce", "f" * 64),
        ("ready", "true"),
        ("mac", "0" * 64),
    ],
)
def test_readiness_tampered_fields_never_ready(field, bad):
    def serve(request):
        value = reply(request)
        value[field] = bad
        return httpx.Response(200, json=value)

    assert probe_for(serve).check(1) is False


def test_readiness_old_response_cannot_be_replayed():
    previous = []

    def serve(request):
        if not previous:
            previous.append(reply(request))
        return httpx.Response(200, json=copy.deepcopy(previous[0]))

    probe = probe_for(serve)
    assert probe.check(1) is True
    assert probe.check(1) is False


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"status": "ok", "service": "agent"}),
        httpx.Response(302, headers={"Location": "https://evil.example/"}),
        httpx.Response(503, text="private details"),
        httpx.Response(200, content=b"\xff"),
        httpx.Response(200, text="x" * 1025),
        httpx.Response(200, text='{"ready":true,"ready":true}'),
    ],
)
def test_readiness_bad_or_ordinary_health_reply_is_unhealthy(response):
    calls = []

    def serve(request):
        calls.append(request)
        return response

    assert probe_for(serve).check(1) is False
    assert len(calls) == 1


def test_readiness_transport_failure_and_signed_not_ready():
    def timeout(request):
        raise httpx.ReadTimeout("offline", request=request)

    assert probe_for(timeout).check(1) is False
    assert probe_for(lambda r: httpx.Response(200, json=reply(r, ready=False))).check(1) is False


def test_readiness_host_refuses_unauthenticated_request_and_wrong_host_generation():
    def serve(request):
        with pytest.raises(ValueError):
            readiness_reply({}, secret=SECRET, release=RELEASE, generation=1, ready=True)
        with pytest.raises(ValueError):
            readiness_reply(
                request.headers, secret=SECRET, release=RELEASE, generation=2, ready=True
            )
        return httpx.Response(200, json=reply(request))

    assert probe_for(serve).check(1)


@pytest.mark.parametrize(
    "secret,release", [(b"short", RELEASE), ("x" * 32, RELEASE), (SECRET, "*")]
)
def test_readiness_configuration_refuses(secret, release):
    with pytest.raises(ValueError):
        HTTPSReadinessProbe(secret, release)


def test_readiness_http_policy_is_verified_bounded_and_ignores_environment(monkeypatch):
    original = httpx.Client
    captured = []

    def client(**options):
        captured.append(options)
        return original(**options)

    monkeypatch.setattr(httpx, "Client", client)
    assert probe_for(lambda r: httpx.Response(200, json=reply(r))).check(1)
    assert captured[0]["verify"] is True
    assert captured[0]["trust_env"] is False
    assert captured[0]["follow_redirects"] is False
    assert captured[0]["timeout"] == 2


def test_readiness_mac_binds_false_to_true_transition_and_direction():
    def flipped(request):
        value = reply(request, ready=False)
        value["ready"] = True
        return httpx.Response(200, json=value)

    def reflected(request):
        value = reply(request)
        value["mac"] = request.headers["x-copilot-proof"]
        return httpx.Response(200, json=value)

    assert probe_for(flipped).check(1) is False
    assert probe_for(reflected).check(1) is False


@pytest.mark.parametrize("generation", [None, True, 0, -1, 1.0, 2**53])
def test_readiness_invalid_generation_never_contacts_host(generation):
    def forbidden(request):
        pytest.fail("Invalid generation reached HTTPS transport")

    assert probe_for(forbidden).check(generation) is False


def test_readiness_slow_subchunks_stop_at_deadline_before_rebuffering(monkeypatch):
    from agent.lifecycle import readiness

    clock, consumed = [0], []

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(1025):
                clock[0] += 1
                consumed.append(1)
                yield b" "

    monkeypatch.setattr(readiness, "monotonic", lambda: clock[0])
    probe = probe_for(lambda request: httpx.Response(200, stream=Drip()))
    assert probe.check(1) is False
    assert len(consumed) <= 3
