"""Lazy private AWS guardian. Exact injected bindings; never performs a start."""

import json
import re
from datetime import UTC, datetime
from threading import Lock
from time import time

import boto3
from botocore.config import Config

from agent.admission.dynamodb import DynamoInvitationStore
from agent.lifecycle.dynamodb import DynamoLifecycle
from agent.lifecycle.executor import _state_name
from agent.lifecycle.lambda_entry import _pairs
from agent.lifecycle.operating import OperatingAuthority
from agent.lifecycle.operating_dns import authoritative_absence
from agent.lifecycle.operating_guard import OperatingGuard
from deploy.operating import GuardBindings, render_operating

ETAG = r'"[0-9a-f]{32}"'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def _sdk(name):
    allowed = {
        "s3",
        "ec2",
        "iam",
        "lambda",
        "cloudfront",
        "dynamodb",
        "freetier",
        "cloudwatch",
        "cloudwatch_global",
    }
    if name not in allowed:
        raise ValueError("Fixed guardian service required")
    global_service = name in {"iam", "cloudfront", "freetier", "cloudwatch_global"}
    return boto3.client(
        "cloudwatch" if name == "cloudwatch_global" else name,
        region_name="us-east-1" if global_service else "eu-north-1",
        config=Config(
            connect_timeout=1,
            read_timeout=2,
            proxies={},
            retries={"mode": "standard", "total_max_attempts": 1},
            ignore_configured_endpoint_urls=True,
        ),
        **(
            {"endpoint_url": "https://dynamodb.eu-north-1.amazonaws.com"}
            if name == "dynamodb"
            else {}
        ),
    )


class AWSGuardBackend:
    def __init__(
        self,
        bindings,
        *,
        sdk_factory=_sdk,
        clock=time,
        context=None,
        dns_probe=authoritative_absence,
    ):
        if type(bindings) is not GuardBindings:
            raise ValueError("Exact guardian bindings required")
        bindings.__post_init__()
        self.b, self.sdk_factory, self.clock, self.context = bindings, sdk_factory, clock, context
        self.closes, self.cleanup_end = bindings.policy.closes, bindings.policy.closes + 48 * 3600
        self.baseline_credits = bindings.baseline_credits
        self._clients, self._store = {}, None
        self._etag, self._record, self._dns_verified = None, None, None
        self._dns_probe = dns_probe

    def _budget(self, minimum=4000):
        now = self.clock()
        if type(now) not in (int, float) or not self.b.policy.opens <= now <= self.cleanup_end:
            raise ValueError("Guardian interval refused")
        if self.context is not None and self.context.get_remaining_time_in_millis() < minimum:
            raise ValueError("Guardian invocation budget exhausted")

    def can_work(self, minimum):
        try:
            self._budget(minimum)
            return True
        except ValueError:
            return False

    def _client(self, name):
        self._budget()
        if name not in self._clients:
            self._clients[name] = self.sdk_factory(name)
        return self._clients[name]

    def _call(self, service, method, **request):
        response = getattr(self._client(service), method)(**request)
        if (
            type(response) is not dict
            or response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200
        ):
            raise ValueError("Guardian observation unavailable")
        return response

    def _envelope(self, state):
        return {
            "version": 1,
            "operation": self.b.policy.operation,
            "manifest_sha256": self.b.policy.manifest_sha256,
            "state": state,
        }

    def read(self):
        self._etag, self._record = None, None
        response = self._call("s3", "get_object", Bucket=self.b.bucket, Key="guard/state.json")
        body = response["Body"]
        try:
            raw = body.read(8193)
        finally:
            body.close()
        etag = response.get("ETag")
        value = json.loads(raw, object_pairs_hook=_pairs)
        if (
            len(raw) > 8192
            or type(value) is not dict
            or value != self._envelope(value.get("state"))
        ):
            raise ValueError("Pinned guard receipt required")
        if (
            type(etag) is not str
            or re.fullmatch(ETAG, etag) is None
            or type(value["state"]) is not dict
        ):
            raise ValueError("Conditional guard receipt required")
        self._etag, self._record = etag, dict(value["state"])
        return dict(self._record)

    def write(self, record):
        if self._etag is None or self._record is None:
            raise ValueError("No automatic guardian receipt initialization")
        raw = _json(self._envelope(record))
        if len(raw) > 8192:
            raise ValueError("Bounded guard receipt required")
        response = self._call(
            "s3",
            "put_object",
            Bucket=self.b.bucket,
            Key="guard/state.json",
            Body=raw,
            ContentType="application/json",
            ServerSideEncryption="AES256",
            IfMatch=self._etag,
        )
        etag = response.get("ETag")
        if type(etag) is not str or re.fullmatch(ETAG, etag) is None:
            raise ValueError("Guardian receipt update uncertain")
        self._etag, self._record = etag, dict(record)

    def _authority(self):
        if self._store is None:
            self._store = DynamoInvitationStore(
                self._client("dynamodb"),
                self.b.table,
                self.b.namespace,
                self.b.invitation_identity,
                clock=self.clock,
                operating=self.b.policy,
                operating_control=True,
            )
        return OperatingAuthority(self._store, self.b.policy)

    def authority_status(self):
        return self._authority().status()

    def close_authority(self, reason):
        self._authority().close(reason)

    def host_status(self):
        result = self._call("ec2", "describe_instances", InstanceIds=[self.b.policy.instance])
        reservations = result.get("Reservations")
        if type(reservations) is not list or len(reservations) != 1 or result.get("NextToken"):
            raise ValueError("Exact designated host observation required")
        rows = reservations[0].get("Instances")
        if (
            type(rows) is not list
            or len(rows) != 1
            or rows[0].get("InstanceId") != self.b.policy.instance
        ):
            raise ValueError("Designated host identity changed")
        state = _state_name(rows[0].get("State"))
        launch = rows[0].get("LaunchTime")
        if state not in {"running", "pending", "stopping", "stopped"}:
            raise ValueError("Host observation uncertain")
        if state == "running" and (type(launch) is not datetime or launch.tzinfo is None):
            raise ValueError("Host launch observation unavailable")
        return {"state": state, "launched": launch.timestamp() if type(launch) is datetime else 0}

    def stop(self):
        result = self._call("ec2", "stop_instances", InstanceIds=[self.b.policy.instance])
        rows = result.get("StoppingInstances")
        if (
            type(rows) is not list
            or len(rows) != 1
            or rows[0].get("InstanceId") != self.b.policy.instance
            or _state_name(rows[0].get("CurrentState")) not in {"stopped", "stopping"}
        ):
            raise ValueError("Stop acknowledgement uncertain")

    def cycle_stop(self):
        self._authority()
        lifecycle = DynamoLifecycle(self._store, self.b.lifecycle_identity, clock=self.clock)
        lifecycle.request_stop(generation=lifecycle.status()["generation"])
        # The controller settles its durable stop intent on subsequent ticks.
        self.stop()

    def fence(self):
        policy = render_operating(self.b)["stop_policy"]
        self._call(
            "iam",
            "put_role_policy",
            RoleName=self.b.controller,
            PolicyName="PublicOperation",
            PolicyDocument=_json(policy).decode("ascii"),
        )

    def _metric_totals(self, service, queries):
        response = self._call(
            service,
            "get_metric_data",
            MetricDataQueries=queries,
            StartTime=datetime.fromtimestamp(self.b.policy.opens, UTC),
            EndTime=datetime.fromtimestamp(self.clock(), UTC),
            MaxDatapoints=1000,
        )
        if response.get("NextToken"):
            raise ValueError("Bounded metric observation unavailable")
        rows = response.get("MetricDataResults")
        if type(rows) is not list or {x.get("Id") for x in rows} != {x["Id"] for x in queries}:
            raise ValueError("Complete metric observation required")
        result = {}
        for row in rows:
            values = row.get("Values")
            if row.get("StatusCode") != "Complete" or type(values) is not list:
                raise ValueError("Metric observation incomplete")
            if any(type(v) not in (int, float) or not 0 <= v < 2**53 for v in values):
                raise ValueError("Invalid metric observation")
            result[row["Id"]] = sum(values)
        return result

    def _traffic_ok(self):
        def query(identifier, namespace, metric, dimensions):
            return {
                "Id": identifier,
                "ReturnData": True,
                "MetricStat": {
                    "Metric": {
                        "Namespace": namespace,
                        "MetricName": metric,
                        "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()],
                    },
                    "Period": 86400,
                    "Stat": "Sum",
                },
            }

        regional = self._metric_totals(
            "cloudwatch",
            [
                *(
                    query("fn" + str(i), "AWS/Lambda", "Invocations", {"FunctionName": name})
                    for i, name in enumerate((self.b.startup, self.b.controller, self.b.guard))
                ),
                query(
                    "writes",
                    "AWS/DynamoDB",
                    "ConsumedWriteCapacityUnits",
                    {"TableName": self.b.table},
                ),
                query(
                    "reads",
                    "AWS/DynamoDB",
                    "ConsumedReadCapacityUnits",
                    {"TableName": self.b.table},
                ),
                query("out", "AWS/EC2", "NetworkOut", {"InstanceId": self.b.policy.instance}),
            ],
        )
        edge = self._metric_totals(
            "cloudwatch_global",
            [
                query(
                    "requests",
                    "AWS/CloudFront",
                    "Requests",
                    {"DistributionId": self.b.distribution, "Region": "Global"},
                ),
                query(
                    "bytes",
                    "AWS/CloudFront",
                    "BytesDownloaded",
                    {"DistributionId": self.b.distribution, "Region": "Global"},
                ),
            ],
        )
        return (
            sum(regional["fn" + str(i)] for i in range(3)) <= 77000
            and regional["fn0"] <= 20000
            and regional["writes"] <= 5_000_000
            and regional["reads"] <= 10_000_000
            and regional["out"] <= 10_000_000_000
            and edge["requests"] <= 100000
            and edge["bytes"] <= 1_000_000_000
        )

    def plan_status(self):
        response = self._call("freetier", "get_account_plan_state")
        if response.get("accountId") != self.b.account:
            raise ValueError("Wrong Free-plan account")
        credits = response.get("accountPlanRemainingCredits", {})
        if credits.get("unit") != "USD" or type(credits.get("amount")) not in (int, float):
            raise ValueError("USD credit observation required")
        return {
            "free": response.get("accountPlanType") == "FREE",
            "active": response.get("accountPlanStatus") == "ACTIVE",
            "credits": str(credits["amount"]),
            "within_traffic": self._traffic_ok(),
        }

    def close_delivery(self):
        self._call(
            "lambda",
            "put_function_concurrency",
            FunctionName=self.b.startup,
            ReservedConcurrentExecutions=0,
        )
        response = self._call("cloudfront", "get_distribution_config", Id=self.b.distribution)
        config = response["DistributionConfig"]
        if config["Enabled"]:
            self._call(
                "cloudfront",
                "update_distribution",
                Id=self.b.distribution,
                IfMatch=response["ETag"],
                DistributionConfig={**config, "Enabled": False},
            )
            return False
        actual = self._call("cloudfront", "get_distribution", Id=self.b.distribution)[
            "Distribution"
        ]
        return actual["Status"] == "Deployed" and actual["DistributionConfig"]["Enabled"] is False

    def close_ingress(self):
        response = self._call("ec2", "describe_security_groups", GroupIds=[self.b.security_group])
        rows = response.get("SecurityGroups")
        if (
            type(rows) is not list
            or len(rows) != 1
            or rows[0].get("GroupId") != self.b.security_group
        ):
            raise ValueError("Designated security group observation required")
        permissions = [
            row
            for row in rows[0].get("IpPermissions", [])
            if row.get("IpProtocol") == "tcp"
            and row.get("FromPort") == row.get("ToPort")
            and row["FromPort"] in {22, 80, 443}
        ]
        if permissions:
            self._call(
                "ec2",
                "revoke_security_group_ingress",
                GroupId=self.b.security_group,
                IpPermissions=permissions,
            )

    def dns_absent(self):
        self._budget(22000)
        result = self._dns_probe(self.b.nameservers) is True
        self._dns_verified = self.clock() if result else None
        return result

    def release(self):
        self._budget(12000)
        now = self.clock()
        record = self._record
        if (
            record is None
            or record.get("closed_at") is None
            or record.get("dns_since") is None
            or now - record["dns_since"] < 7200
            or self._dns_verified is None
            or not 0 <= now - self._dns_verified <= 30
        ):
            raise ValueError("Fresh full-TTL DNS proof required")
        if self.host_status()["state"] != "stopped":
            raise ValueError("Stopped host observation required")
        response = self._call(
            "ec2",
            "describe_addresses",
            Filters=[{"Name": "allocation-id", "Values": [self.b.allocation]}],
        )
        rows = response.get("Addresses")
        intent = {
            "version": 1,
            "operation": self.b.policy.operation,
            "manifest_sha256": self.b.policy.manifest_sha256,
            "allocation": self.b.allocation,
        }
        if rows == []:
            proof = self._call(
                "s3", "get_object", Bucket=self.b.bucket, Key="guard/release-intent.json"
            )
            body = proof["Body"]
            try:
                observed = json.loads(body.read(8193), object_pairs_hook=_pairs)
            finally:
                body.close()
            if observed != intent:
                raise ValueError("Absent address has no owned release intent")
            return True
        if type(rows) is not list or len(rows) != 1:
            raise ValueError("Exact owned EIP required")
        row = rows[0]
        if (
            row.get("AllocationId") != self.b.allocation
            or row.get("Domain") != "vpc"
            or {t["Key"]: t["Value"] for t in row.get("Tags", [])}.get("OwnerOperation")
            != self.b.policy.operation
            or row.get("InstanceId") not in {None, self.b.policy.instance}
        ):
            raise ValueError("EIP ownership mismatch")
        # Immutable intent before an uncertain release; never infer ownership of
        # a missing address from a transient DescribeAddresses response alone.
        try:
            self._call(
                "s3",
                "put_object",
                Bucket=self.b.bucket,
                Key="guard/release-intent.json",
                Body=_json(intent),
                ContentType="application/json",
                ServerSideEncryption="AES256",
                IfNoneMatch="*",
            )
        except Exception:
            proof = self._call(
                "s3", "get_object", Bucket=self.b.bucket, Key="guard/release-intent.json"
            )
            body = proof["Body"]
            try:
                if json.loads(body.read(8193), object_pairs_hook=_pairs) != intent:
                    raise ValueError("Release intent mismatch")
            finally:
                body.close()
        if row.get("AssociationId"):
            self._call("ec2", "disassociate_address", AssociationId=row["AssociationId"])
        self._call("ec2", "release_address", AllocationId=self.b.allocation)
        observed = self._call(
            "ec2",
            "describe_addresses",
            Filters=[{"Name": "allocation-id", "Values": [self.b.allocation]}],
        )
        return observed.get("Addresses") == [] and not observed.get("NextToken")


def make_guard_entry(*, environment=None, sdk_factory=_sdk):
    initialized, bindings, lock = False, None, Lock()

    def handler(event, context):
        nonlocal initialized, bindings
        try:
            with lock:
                if not initialized:
                    initialized = True
                    if environment is None:
                        import os

                        source = os.environ
                    else:
                        source = environment
                    raw = source.get("COPILOT_GUARD_CONFIG")
                    if type(raw) is not str or len(raw.encode()) > 3800:
                        raise ValueError()
                    bindings = GuardBindings.parse(json.loads(raw, object_pairs_hook=_pairs))
            if bindings is None:
                raise ValueError()
            backend = AWSGuardBackend(bindings, sdk_factory=sdk_factory, context=context)
            result = OperatingGuard(backend).handle(event)
            print(json.dumps(result, separators=(",", ":")))
            return result
        except Exception:
            return {"state": "unavailable"}

    return handler
