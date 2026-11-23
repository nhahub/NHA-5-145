"""Isolated Python 3.12 import/delegation proof; not a Linux runtime test."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from deploy.lambda_package import verify

SCRIPT = r"""
import importlib
import importlib.metadata
import json
import os
import socket
import sys
from pathlib import Path

assert sys.version_info[:2] == (3, 12)
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
assert not any("site-packages" in p for p in sys.path)
os.environ.clear()
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
def forbidden(*args, **kwargs):
    raise AssertionError("External access forbidden in artifact smoke")
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden

import boto3
boto3.client = forbidden
import handler
import agent.lifecycle.lambda_entry as entry
manifest = json.loads((root / "lambda-manifest.json").read_bytes())
role = manifest["role"]
result = handler.handler({}, None)
assert result == {"state": "unavailable"} if role == "controller" else result["statusCode"] == 503
assert handler.handler({}, None) == result
if role == "controller":
    try:
        handler.handler({"kind": "tick"}, None)
        raise AssertionError("Uninitialized scheduled failure was hidden")
    except RuntimeError as error:
        assert str(error) == "Scheduled observation unavailable"

config = {
    "version": 1, "table": "demo-table", "namespace": "demo",
    "invitation_identity": "00000000-0000-4000-8000-000000000001",
    "lifecycle_identity": "00000000-0000-4000-8000-000000000002",
}
if role == "startup":
    config.update(
        origin="https://example.cloudfront.net",
        controller_arn="arn:aws:lambda:eu-north-1:123456789012:function:controller",
    )
else:
    config.update(instance="i-0123456789abcdef0", release="a" * 64)
    os.environ["COPILOT_READINESS_KEY_HEX"] = "ab" * 32
os.environ["COPILOT_CONTROL_CONFIG"] = json.dumps(config)
seen = []
def factory(settings):
    seen.append(settings.role)
    assert settings.role == role
    return lambda event, context: {"delegated": role, "payload": event, "context": context}
entry.create_startup_runtime = factory
entry.create_controller_runtime = factory
handler = importlib.reload(handler)
for _ in range(2):
    assert handler.handler({"role": "different"}, "context") == {
        "delegated": role, "payload": {"role": "different"}, "context": "context",
    }
assert seen == [role]

import certifi
import botocore.session
assert Path(certifi.where()).is_relative_to(root)
assert Path(certifi.where()).stat().st_size > 100000
session = botocore.session.get_session()
for name in ("dynamodb", "ec2", "lambda"):
    assert session.get_service_model(name).service_name == name
versions = {}
for item in manifest["wheels"]:
    versions[item["name"]] = importlib.metadata.version(item["name"])
    assert versions[item["name"]] == item["version"]
packages = {
    "handler", "agent", "boto3", "botocore", "httpx", "httpcore", "anyio", "certifi",
    "idna", "jmespath", "dateutil", "s3transfer", "six", "typing_extensions", "urllib3", "h11",
}
for name, module in list(sys.modules.items()):
    if name.split(".")[0] in packages:
        if getattr(module, "__file__", None):
            assert Path(module.__file__).is_relative_to(root), name
assert (root / "agent/lifecycle/waiting.html").read_bytes()
assert not list(root.rglob("*.pyc"))
print(json.dumps({
    "role": role, "python": sys.version.split()[0], "platform": sys.platform,
    "isolated_import": True, "fixed_role_delegation": True,
    "sdk_creation_and_network_blocked": True, "service_models_and_ca_present": True,
    "versions": versions,
}, sort_keys=True))
"""


def smoke(path, *, expected_sha256):
    verify(path, expected_sha256=expected_sha256)
    with TemporaryDirectory(prefix="copilot-lambda-smoke-") as temporary:
        with ZipFile(path) as archive:
            archive.extractall(temporary)
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", SCRIPT, temporary],
            cwd=temporary,
            capture_output=True,
            encoding="utf-8",
            timeout=45,
            check=True,
        )
        return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.archive, expected_sha256=args.sha256), sort_keys=True))


if __name__ == "__main__":
    main()
