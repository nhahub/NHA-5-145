"""Real AWS request shapes at the guardian seam, using Stubber and fake keys."""

import importlib
import importlib.util
import io
import json

import boto3
import pytest
from botocore.config import Config
from botocore.response import StreamingBody
from botocore.stub import Stubber

from agent.tests.test_lifecycle_executor import reply
from deploy.operating import GuardBindings, render_operating
from eval.tests.test_operating_deploy import fixture


def module():
    if importlib.util.find_spec("deploy.guard_runtime") is None:
        pytest.fail("Private AWS guardian runtime is not implemented")
    return importlib.import_module("deploy.guard_runtime")


@pytest.fixture
def backend():
    m = module()
    bindings = GuardBindings(**fixture())
    clients, stubs = {}, {}
    for service in ("s3", "ec2", "iam"):
        clients[service] = boto3.client(
            service,
            region_name="eu-north-1",
            aws_access_key_id="offline-dummy",
            aws_secret_access_key="offline-dummy",
            config=Config(connect_timeout=1, read_timeout=2, retries={"total_max_attempts": 1}),
        )
        stubs[service] = Stubber(clients[service])
        stubs[service].activate()
    now = [bindings.policy.opens + 10]
    runtime = m.AWSGuardBackend(bindings, sdk_factory=clients.__getitem__, clock=lambda: now[0])
    yield runtime, bindings, now, stubs
    for service, stub in stubs.items():
        stub.assert_no_pending_responses()
        stub.deactivate()
        clients[service].close()


def state(bindings, now):
    return {
        "observed": now,
        "closed_at": None,
        "reason": None,
        "credit_checked": now,
        "credits": bindings.baseline_credits,
        "dns_absent": None,
        "dns_since": None,
        "dns_checked": None,
        "released": False,
        "shutdown": dict.fromkeys(("fence", "authority", "delivery", "ingress"), False),
    }


def test_backend_stop_and_start_fence_use_only_pinned_instance_role_and_policy(backend):
    runtime, bindings, _, stubs = backend
    stubs["ec2"].add_response(
        "stop_instances", reply("stop"), {"InstanceIds": [bindings.policy.instance]}
    )
    runtime.stop()
    policy = render_operating(bindings)["stop_policy"]
    stubs["iam"].add_response(
        "put_role_policy",
        {"ResponseMetadata": {"HTTPStatusCode": 200}},
        {
            "RoleName": bindings.controller,
            "PolicyName": "PublicOperation",
            "PolicyDocument": json.dumps(policy, sort_keys=True, separators=(",", ":")),
        },
    )
    runtime.fence()
    assert "ec2:StartInstances" not in json.dumps(policy)


def test_guard_receipt_is_manifest_bound_and_conditionally_updated(backend):
    runtime, bindings, now, stubs = backend
    record = state(bindings, now[0])
    envelope = {
        "version": 1,
        "operation": bindings.policy.operation,
        "manifest_sha256": bindings.policy.manifest_sha256,
        "state": record,
    }
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    etag = '"' + "a" * 32 + '"'
    stubs["s3"].add_response(
        "get_object",
        {
            "Body": StreamingBody(io.BytesIO(raw), len(raw)),
            "ETag": etag,
            "ResponseMetadata": {"HTTPStatusCode": 200},
        },
        {"Bucket": bindings.bucket, "Key": "guard/state.json"},
    )
    assert runtime.read() == record
    stubs["s3"].add_response(
        "put_object",
        {"ETag": '"' + "b" * 32 + '"', "ResponseMetadata": {"HTTPStatusCode": 200}},
        {
            "Bucket": bindings.bucket,
            "Key": "guard/state.json",
            "Body": raw,
            "ContentType": "application/json",
            "ServerSideEncryption": "AES256",
            "IfMatch": etag,
        },
    )
    runtime.write(record)


def test_guard_does_not_create_missing_receipt_or_ignore_wrong_manifest(backend):
    runtime, bindings, now, stubs = backend
    record = state(bindings, now[0])
    raw = json.dumps(
        {
            "version": 1,
            "operation": bindings.policy.operation,
            "manifest_sha256": "b" * 64,
            "state": record,
        }
    ).encode()
    stubs["s3"].add_response(
        "get_object",
        {
            "Body": StreamingBody(io.BytesIO(raw), len(raw)),
            "ETag": '"' + "a" * 32 + '"',
            "ResponseMetadata": {"HTTPStatusCode": 200},
        },
        {"Bucket": bindings.bucket, "Key": "guard/state.json"},
    )
    with pytest.raises(ValueError):
        runtime.read()
    with pytest.raises(ValueError):
        runtime.write(record)


def test_backend_refuses_operations_after_absolute_cleanup_deadline(backend):
    runtime, bindings, now, _ = backend
    now[0] = bindings.policy.closes + 48 * 3600 + 1
    with pytest.raises(ValueError):
        runtime.stop()


def test_guard_eip_release_refuses_wrong_owner_even_after_fresh_dns_and_stopped_host(
    backend, monkeypatch
):
    runtime, bindings, now, stubs = backend
    now[0] += 8000
    record = state(bindings, now[0])
    record.update(
        closed_at=bindings.policy.opens,
        reason="owner",
        dns_absent=bindings.policy.opens,
        dns_since=bindings.policy.opens,
    )
    envelope = {
        "version": 1,
        "operation": bindings.policy.operation,
        "manifest_sha256": bindings.policy.manifest_sha256,
        "state": record,
    }
    raw = json.dumps(envelope).encode()
    stubs["s3"].add_response(
        "get_object",
        {
            "Body": StreamingBody(io.BytesIO(raw), len(raw)),
            "ETag": '"' + "a" * 32 + '"',
            "ResponseMetadata": {"HTTPStatusCode": 200},
        },
        {"Bucket": bindings.bucket, "Key": "guard/state.json"},
    )
    runtime.read()
    monkeypatch.setattr(runtime, "_dns_probe", lambda _: True)
    assert runtime.dns_absent() is True
    stubs["ec2"].add_response(
        "describe_instances",
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": bindings.policy.instance,
                            "State": {"Name": "stopped", "Code": 80},
                        }
                    ]
                }
            ],
            "ResponseMetadata": {"HTTPStatusCode": 200},
        },
        {"InstanceIds": [bindings.policy.instance]},
    )
    stubs["ec2"].add_response(
        "describe_addresses",
        {
            "Addresses": [
                {
                    "AllocationId": bindings.allocation,
                    "Domain": "vpc",
                    "Tags": [{"Key": "OwnerOperation", "Value": "someone-else"}],
                }
            ],
            "ResponseMetadata": {"HTTPStatusCode": 200},
        },
        {"Filters": [{"Name": "allocation-id", "Values": [bindings.allocation]}]},
    )
    with pytest.raises(ValueError, match="ownership mismatch"):
        runtime.release()


def test_guard_entry_creation_has_no_sdk_lookup_and_latches_bad_config(monkeypatch):
    m = module()
    monkeypatch.setattr(boto3, "client", lambda *a, **k: pytest.fail("Import-time SDK"))
    entry = m.make_guard_entry(environment={})
    assert entry({"kind": "guard"}, None) == {"state": "unavailable"}
    assert entry({"kind": "guard"}, None) == {"state": "unavailable"}


def test_release_acknowledgement_is_not_a_proof_of_address_absence(backend, monkeypatch):
    runtime, bindings, now, _ = backend
    now[0] += 8000
    runtime._record = {"closed_at": bindings.policy.opens, "dns_since": bindings.policy.opens}
    runtime._dns_verified = now[0]
    monkeypatch.setattr(runtime, "host_status", lambda: {"state": "stopped"})
    calls = []
    address = {
        "AllocationId": bindings.allocation,
        "Domain": "vpc",
        "Tags": [{"Key": "OwnerOperation", "Value": bindings.policy.operation}],
    }

    def acknowledged_but_present(service, action, **kwargs):
        calls.append(action)
        return {"Addresses": [address]} if action == "describe_addresses" else {}

    monkeypatch.setattr(runtime, "_call", acknowledged_but_present)
    assert runtime.release() is False
    assert calls.count("describe_addresses") == 2


def test_slow_successful_cleanup_advances_to_dns_across_bounded_lambda_invocations(monkeypatch):
    from agent.lifecycle.operating_guard import OperatingGuard

    m = module()
    bindings = GuardBindings(**fixture())
    elapsed, epoch, dns_calls = [0.0], [bindings.policy.closes], []
    record = state(bindings, epoch[0])
    requests = []

    class Context:
        def get_remaining_time_in_millis(self):
            return int(30000 - elapsed[0] * 1000)

    class Authority:
        def status(self):
            elapsed[0] += 4.5
            return {"closed": False}

        def close(self, reason):
            elapsed[0] += 5.4

    def probe(_):
        dns_calls.append(epoch[0])
        elapsed[0] += 0.9
        return True

    for _ in range(3):
        elapsed[0] = 0
        runtime = m.AWSGuardBackend(
            bindings, clock=lambda: epoch[0] + elapsed[0], context=Context(), dns_probe=probe
        )
        monkeypatch.setattr(runtime, "_authority", lambda: Authority())

        def wire(service, method, *, _runtime=runtime, **kwargs):
            nonlocal record
            _runtime._budget()
            elapsed[0] += 0.9
            requests.append(method)
            result = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            if method == "get_object":
                raw = json.dumps(_runtime._envelope(record)).encode()
                result.update(
                    Body=StreamingBody(io.BytesIO(raw), len(raw)), ETag='"' + "a" * 32 + '"'
                )
            elif method == "put_object":
                record = json.loads(kwargs["Body"])["state"]
                result["ETag"] = '"' + "a" * 32 + '"'
            elif method == "describe_instances":
                result["Reservations"] = [
                    {
                        "Instances": [
                            {
                                "InstanceId": bindings.policy.instance,
                                "State": {"Name": "stopped", "Code": 80},
                            }
                        ]
                    }
                ]
            elif method == "stop_instances":
                result = reply("stop")
                result["StoppingInstances"][0]["InstanceId"] = bindings.policy.instance
            elif method == "get_distribution_config":
                result.update(
                    DistributionConfig={
                        "CallerReference": bindings.policy.operation,
                        "Enabled": False,
                    },
                    ETag='"a"',
                )
            elif method == "get_distribution":
                result["Distribution"] = {
                    "Status": "Deployed",
                    "DistributionConfig": {"Enabled": False},
                }
            elif method == "describe_security_groups":
                result["SecurityGroups"] = [
                    {"GroupId": bindings.security_group, "IpPermissions": []}
                ]
            return result

        monkeypatch.setattr(runtime, "_call", wire)
        result = OperatingGuard(runtime, clock=lambda: epoch[0] + elapsed[0]).handle(
            {"kind": "guard"}
        )
        epoch[0] += 300
    assert dns_calls, (record, requests, result)
    assert requests.count("put_role_policy") == 1
