"""Injected DynamoDB invitation authority; not selected by runtime configuration."""

import re
import secrets
from decimal import Decimal
from threading import Lock
from time import time
from uuid import UUID, uuid4

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from agent.admission.store import AdmissionDenied, digest

SERIALIZER, DESERIALIZER = TypeSerializer(), TypeDeserializer()


def _encode(values):
    return {name: SERIALIZER.serialize(value) for name, value in values.items()}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        raise ValueError("Finite numeric authority required")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Finite nonnegative authority required")
    return result


def _count(value, maximum, *, minimum=0):
    result = _number(value)
    if result != result.to_integral_value() or not minimum <= result <= maximum:
        raise ValueError("Bounded integer authority required")
    return int(result)


def _identifier(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("Canonical authority identity required")
    return value


class DynamoInvitationStore:
    @staticmethod
    def _configuration(client, table, namespace):
        if (
            not isinstance(table, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", table) is None
            or not isinstance(namespace, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", namespace) is None
        ):
            raise ValueError("Explicit bounded table and namespace required")
        config = client.meta.config
        attempts = (config.retries or {}).get("total_max_attempts")
        if (
            client.meta.region_name != "eu-north-1"
            or client.meta.endpoint_url != "https://dynamodb.eu-north-1.amazonaws.com"
            or type(attempts) is not int
            or attempts != 1
            or type(config.connect_timeout) not in {int, float}
            or type(config.read_timeout) not in {int, float}
            or not 0 < config.connect_timeout <= 5
            or not 0 < config.read_timeout <= 15
        ):
            raise ValueError("Stockholm client with bounded timeouts and zero retries required")

    @classmethod
    def initialize(cls, client, table, namespace):
        cls._configuration(client, table, namespace)
        identity = str(uuid4())
        try:
            existing = client.query(
                TableName=table,
                KeyConditionExpression="pk=:namespace",
                ExpressionAttributeValues={":namespace": {"S": namespace}},
                ConsistentRead=True,
                Limit=1,
            )
            if existing.get("Items") or existing.get("LastEvaluatedKey"):
                raise ValueError("Authority namespace already contains state")
            client.put_item(
                TableName=table,
                Item=_encode(
                    {"pk": namespace, "sk": "meta", "schema": 1, "identity": identity, "issued": 0}
                ),
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ValueError:
            raise
        except Exception:
            raise AdmissionDenied("access_unavailable") from None
        return identity

    def __init__(
        self,
        client,
        table,
        namespace,
        identity,
        *,
        clock=time,
        operating=None,
        operating_control=False,
    ):
        self._configuration(client, table, namespace)
        self.identity = _identifier(identity)
        self.client, self.table, self.namespace, self.clock = client, table, namespace, clock
        if type(operating_control) is not bool:
            raise ValueError("Explicit operating observation mode required")
        self.operating, self.operating_control = operating, operating_control
        self._operating_lock, self._operating_seen = Lock(), 0
        self._metadata()

    def _key(self, sk):
        return _encode({"pk": self.namespace, "sk": sk})

    def check(self):
        """Read bound metadata only; never allocates access or allowance."""
        self._configuration(self.client, self.table, self.namespace)
        self._metadata()

    def _read(self, sk):
        try:
            response = self.client.get_item(
                TableName=self.table, Key=self._key(sk), ConsistentRead=True
            )
            if "Item" not in response:
                return None
            row = {key: DESERIALIZER.deserialize(value) for key, value in response["Item"].items()}
            if row["pk"] != self.namespace or row["sk"] != sk:
                raise ValueError("Mismatched authority row")
            return row
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _metadata(self):
        try:
            row = self._read("meta")
            if row is None or row["identity"] != self.identity:
                raise ValueError("Missing or mismatched authority")
            _count(row["schema"], 1, minimum=1)
            _count(row["issued"], 1000)
            if self.operating is not None or any(name.startswith("operating_") for name in row):
                from agent.lifecycle.operating import OperatingAuthority

                OperatingAuthority(self, self.operating).check(allow_closed=self.operating_control)
            elif self._read("operating#window") is not None:
                raise ValueError("Existing finite operation requires explicit configuration")
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _now(self):
        try:
            return _number(self.clock())
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _condition(self, sk, expression, values, *, update=None):
        text = expression + " " + (update or "")
        operation = {
            "TableName": self.table,
            "Key": self._key(sk),
            "ConditionExpression": expression,
            "ExpressionAttributeNames": {name: name[1:] for name in set(re.findall(r"#\w+", text))},
            "ExpressionAttributeValues": _encode(values),
        }
        if update:
            operation["UpdateExpression"] = update
        return {"Update" if update else "ConditionCheck": operation}

    def _meta_condition(self, *, issuing=False):
        expression = "#schema=:schema AND #identity=:identity"
        values = {":schema": 1, ":identity": self.identity}
        if self.operating is None:
            expression += (
                " AND attribute_not_exists(#operating_operation)"
                " AND attribute_not_exists(#operating_manifest)"
            )
        if issuing:
            expression += " AND #issued<:maximum"
            values.update({":maximum": 1000, ":one": 1})
        return self._condition(
            "meta", expression, values, update="ADD #issued :one" if issuing else None
        )

    def _put(self, sk, values):
        return {
            "Put": {
                "TableName": self.table,
                "Item": _encode({"pk": self.namespace, "sk": sk, **values}),
                "ConditionExpression": "attribute_not_exists(pk)",
            }
        }

    def _write(self, operations, *, refusal="access_required"):
        try:
            if self.operating is None:
                operating_key = self._key("operating#window")
                initializes_operation = any(
                    operation.get("Put", {}).get("Item", {}).get("sk") == operating_key["sk"]
                    for operation in operations
                )
                if not initializes_operation:
                    operations = [
                        *operations,
                        {
                            "ConditionCheck": {
                                "TableName": self.table,
                                "Key": operating_key,
                                "ConditionExpression": "attribute_not_exists(pk)",
                            }
                        },
                    ]
            if self.operating is not None and not self.operating_control:
                from agent.lifecycle.operating import KEY, OperatingAuthority

                # An operating-record update supplies its own compare-and-swap.
                # Other admission/lifecycle writes must atomically race closure.
                own_key = self._key(KEY)
                owns_record = any(
                    body.get("Key", {k: body.get("Item", {}).get(k) for k in ("pk", "sk")})
                    == own_key
                    for operation in operations
                    for body in operation.values()
                )
                if not owns_record:
                    OperatingAuthority(self, self.operating).check()
                    operations = [
                        *operations,
                        self._condition(
                            KEY,
                            "#schema=:schema AND #policy=:policy AND #closed=:no",
                            {":schema": 1, ":policy": self.operating.values(), ":no": False},
                        ),
                    ]
            self.client.transact_write_items(
                TransactItems=operations, ClientRequestToken=uuid4().hex
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                raise AdmissionDenied(refusal) from None
            raise AdmissionDenied("access_unavailable") from None
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _invitation(self, invitation):
        try:
            invitation = _identifier(invitation)
            row = self._read("invitation#" + invitation)
            return self._invitation_row(row, invitation)
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _invitation_row(self, row, invitation):
        try:
            if row is None:
                return None
            if (
                row["pk"] != self.namespace
                or row["sk"] != "invitation#" + _identifier(invitation)
                or set(row)
                != {
                    "pk",
                    "sk",
                    "id",
                    "hash",
                    "starts",
                    "ends",
                    "redemptions",
                    "sessions",
                    "used_redemptions",
                    "created_sessions",
                    "revoked",
                }
            ):
                raise ValueError("Invalid invitation record")
            if row["id"] != invitation or re.fullmatch(r"[0-9a-f]{64}", row["hash"]) is None:
                raise ValueError("Invalid invitation identity")
            start, end = _number(row["starts"]), _number(row["ends"])
            if not start < end or end - start > 31 * 86400 or type(row["revoked"]) is not bool:
                raise ValueError("Invalid invitation window")
            redemptions = _count(row["redemptions"], 20, minimum=1)
            sessions = _count(row["sessions"], 100, minimum=1)
            _count(row["used_redemptions"], redemptions)
            _count(row["created_sessions"], sessions)
            return row
        except Exception:
            raise AdmissionDenied("access_unavailable") from None

    def _active(self, row):
        return row is not None and not row["revoked"] and row["starts"] <= self._now() < row["ends"]

    def _code(self, code):
        if not isinstance(code, str) or not 16 <= len(code) <= 128:
            raise AdmissionDenied()
        row = self._read("code#" + digest(code))
        if row is None:
            raise AdmissionDenied()
        invitation = self._invitation(row.get("invitation"))
        if invitation is None or invitation["hash"] != digest(code) or not self._active(invitation):
            raise AdmissionDenied()
        return invitation

    @staticmethod
    def _subject(subject):
        if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
            raise AdmissionDenied()
        return digest(subject)

    def _active_condition(self, row, *, counter=None):
        expression = (
            "#revoked=:false AND #starts<=:now AND #ends>:now AND #id=:id AND #hash=:hash "
            "AND #starts=:starts AND #ends=:ends AND #redemptions=:redemptions "
            "AND #sessions=:sessions AND #used_redemptions>=:zero "
            "AND #used_redemptions<=#redemptions AND #created_sessions>=:zero "
            "AND #created_sessions<=#sessions"
        )
        values = {":false": False, ":now": self._now(), ":zero": 0}
        values.update(
            {
                ":" + name: row[name]
                for name in ("id", "hash", "starts", "ends", "redemptions", "sessions")
            }
        )
        update = None
        if counter:
            limit = "redemptions" if counter == "used_redemptions" else "sessions"
            expression += f" AND #{counter}<#{limit}"
            values[":one"] = 1
            update = f"ADD #{counter} :one"
        return self._condition("invitation#" + row["id"], expression, values, update=update)

    def issue(self, starts, ends, *, redemptions, sessions):
        start, end = _number(starts), _number(ends)
        if not start < end or end - start > 31 * 86400:
            raise ValueError("Explicit bounded invitation window required")
        if type(redemptions) is not int or type(sessions) is not int:
            raise ValueError("Explicit integer quotas required")
        _count(redemptions, 20, minimum=1)
        _count(sessions, 100, minimum=1)
        self._metadata()
        invitation, code = str(uuid4()), secrets.token_urlsafe(24)
        if self.operating is not None:
            from agent.lifecycle.operating import OperatingAuthority

            if not self.operating.opens <= start < end <= self.operating.closes or redemptions > 2:
                raise ValueError("Invitation exceeds the finite operating grant")
            OperatingAuthority(self, self.operating).reserve_invitation(invitation)
        self._write(
            [
                self._meta_condition(issuing=True),
                self._put(
                    "invitation#" + invitation,
                    {
                        "id": invitation,
                        "hash": digest(code),
                        "starts": start,
                        "ends": end,
                        "redemptions": redemptions,
                        "sessions": sessions,
                        "used_redemptions": 0,
                        "created_sessions": 0,
                        "revoked": False,
                    },
                ),
                self._put("code#" + digest(code), {"invitation": invitation}),
            ],
            refusal="access_capacity",
        )
        return invitation, code

    def redeem(self, code, subject):
        key = "grant#" + self._subject(subject)
        self._metadata()
        invitation = self._code(code)
        existing = self._read(key)
        conditions = [self._meta_condition()]
        if existing:
            old = self._invitation(existing.get("invitation"))
            if old is None:
                raise AdmissionDenied("access_unavailable")
            if old["id"] == invitation["id"]:
                self._write(
                    [
                        *conditions,
                        self._active_condition(invitation),
                        self._condition(key, "#invitation=:old", {":old": old["id"]}),
                    ]
                )
                if not self.valid_invitation(invitation["id"]):
                    raise AdmissionDenied()
                return
            if not old["revoked"] and old["ends"] > self._now():
                raise AdmissionDenied()
            conditions.append(
                self._condition(
                    "invitation#" + old["id"],
                    "#revoked=:true OR #ends<=:now",
                    {":true": True, ":now": self._now()},
                )
            )
            binding = self._condition(
                key,
                "#invitation=:old",
                {":old": old["id"], ":new": invitation["id"]},
                update="SET #invitation=:new",
            )
        else:
            binding = self._put(key, {"invitation": invitation["id"]})
        self._write(
            [*conditions, self._active_condition(invitation, counter="used_redemptions"), binding]
        )
        if not self.valid_invitation(invitation["id"]):
            raise AdmissionDenied()

    def wake_invitation(self, code):
        self._metadata()
        return self._code(code)["id"]

    def valid_invitation(self, invitation):
        try:
            self._metadata()
            return self._active(self._invitation(invitation))
        except AdmissionDenied:
            return False

    def allowed(self, subject):
        try:
            self._metadata()
            grant = self._read("grant#" + self._subject(subject))
            return grant is not None and self._active(self._invitation(grant.get("invitation")))
        except AdmissionDenied:
            return False

    def allocate_session(self, subject):
        key = "grant#" + self._subject(subject)
        self._metadata()
        grant = self._read(key)
        invitation = self._invitation(grant.get("invitation")) if grant else None
        if not self._active(invitation):
            raise AdmissionDenied()
        self._write(
            [
                self._meta_condition(),
                self._active_condition(invitation, counter="created_sessions"),
                self._condition(key, "#invitation=:old", {":old": invitation["id"]}),
            ],
            refusal="access_sessions",
        )
        if not self.valid_invitation(invitation["id"]):
            raise AdmissionDenied()
        return invitation["id"]

    def revoke(self, invitation):
        self._metadata()
        row = self._invitation(invitation)
        if row is None:
            raise ValueError("Invitation not found")
        self._write(
            [
                self._meta_condition(),
                self._condition(
                    "invitation#" + row["id"],
                    "attribute_exists(pk)",
                    {":true": True},
                    update="SET #revoked=:true",
                ),
            ]
        )

    def status(self):
        self._metadata()
        result, page_key = [], None
        for _ in range(11):
            request = {
                "TableName": self.table,
                "ConsistentRead": True,
                "Limit": 100,
                "KeyConditionExpression": "pk=:namespace AND begins_with(sk,:prefix)",
                "ExpressionAttributeValues": _encode(
                    {":namespace": self.namespace, ":prefix": "invitation#"}
                ),
            }
            if page_key:
                request["ExclusiveStartKey"] = page_key
            try:
                response = self.client.query(**request)
                for item in response.get("Items", []):
                    decoded = {key: DESERIALIZER.deserialize(value) for key, value in item.items()}
                    row = self._invitation_row(decoded, decoded["id"])
                    result.append(
                        {
                            "id": row["id"],
                            "starts": float(row["starts"]),
                            "ends": float(row["ends"]),
                            "redemptions": int(row["redemptions"]),
                            "sessions": int(row["sessions"]),
                            "used_sessions": int(row["created_sessions"]),
                            "revoked": int(row["revoked"]),
                            "used_redemptions": int(row["used_redemptions"]),
                        }
                    )
                if len(result) > 1000:
                    raise ValueError("Authority capacity exceeded")
                page_key = response.get("LastEvaluatedKey")
                if not page_key:
                    return result
            except Exception:
                raise AdmissionDenied("access_unavailable") from None
        raise AdmissionDenied("access_unavailable")
