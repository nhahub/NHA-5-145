"""Finite, explicitly initialized operation; no cloud command or inferred renewal."""

import re
from dataclasses import asdict, dataclass

from agent.admission.dynamodb import _count, _identifier, _number
from agent.lifecycle.store import LifecycleUnavailable

KEY = "operating#window"
MAX_STARTS = 100
MAX_RUN_SECONDS = 8 * 3600
REASONS = {"expired", "budget", "runtime", "fault", "owner"}


@dataclass(frozen=True)
class OperatingPolicy:
    operation: str
    manifest_sha256: str
    instance: str
    opens: int
    closes: int

    def __post_init__(self):
        _identifier(self.operation)
        if (
            type(self.manifest_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.manifest_sha256) is None
            or type(self.instance) is not str
            or re.fullmatch(r"i-[0-9a-f]{17}", self.instance) is None
            or type(self.opens) is not int
            or type(self.closes) is not int
            or not 0 <= self.opens < self.closes <= self.opens + 32 * 86400
        ):
            raise ValueError("Exact finite operating policy required")

    @classmethod
    def parse(cls, value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Exact finite operating policy required")
        return cls(**value)

    def values(self):
        self.__post_init__()
        return asdict(self)


class OperatingAuthority:
    def __init__(self, store, policy):
        if type(policy) is not OperatingPolicy:
            raise ValueError("Explicit operating policy required")
        policy.__post_init__()
        self.store, self.policy = store, policy

    @classmethod
    def initialize(cls, store, policy):
        authority = cls(store, policy)
        try:
            if store.operating is not None:
                raise ValueError()
            store.check()
            now = _number(store.clock())
            if now >= policy.closes:
                raise ValueError()
            store._write(
                [
                    store._condition(
                        "meta",
                        "#schema=:schema AND #identity=:identity "
                        "AND attribute_not_exists(#operating_operation) "
                        "AND attribute_not_exists(#operating_manifest)",
                        {
                            ":schema": 1,
                            ":identity": store.identity,
                            ":operation": policy.operation,
                            ":manifest": policy.manifest_sha256,
                        },
                        update="SET #operating_operation=:operation, #operating_manifest=:manifest",
                    ),
                    store._put(
                        KEY,
                        {
                            "schema": 1,
                            "policy": policy.values(),
                            "starts": 0,
                            "invitations": 0,
                            "observed": now,
                            "closed": False,
                            "reason": None,
                        },
                    ),
                ]
            )
            store.operating = policy
            return authority
        except Exception:
            raise LifecycleUnavailable() from None

    def _load(self):
        try:
            store, policy = self.store, self.policy
            store._configuration(store.client, store.table, store.namespace)
            meta, row = store._read("meta"), store._read(KEY)
            if (
                meta is None
                or meta.get("identity") != store.identity
                or meta.get("operating_operation") != policy.operation
                or meta.get("operating_manifest") != policy.manifest_sha256
                or row is None
                or set(row)
                != {
                    "pk",
                    "sk",
                    "schema",
                    "policy",
                    "starts",
                    "invitations",
                    "observed",
                    "closed",
                    "reason",
                }
                or row["policy"] != policy.values()
                or type(row["closed"]) is not bool
                or (row["reason"] not in REASONS if row["closed"] else row["reason"] is not None)
            ):
                raise ValueError()
            _count(row["schema"], 1, minimum=1)
            _count(row["starts"], MAX_STARTS)
            _count(row["invitations"], 10)
            _number(row["observed"])
            now = _number(store.clock())
            if now < row["observed"] or now < store._operating_seen:
                raise ValueError()
            store._operating_seen = now
            return row, now
        except Exception:
            raise LifecycleUnavailable() from None

    def status(self):
        with self.store._operating_lock:
            row, _ = self._load()
            return dict(row)

    def check(self, *, allow_closed=False):
        if type(allow_closed) is not bool:
            raise LifecycleUnavailable()
        with self.store._operating_lock:
            row, now = self._load()
            if not allow_closed and (
                row["closed"] or not self.policy.opens <= now < self.policy.closes
            ):
                raise LifecycleUnavailable()

    def _guard(self, row, now, *, update, extra=None):
        values = {
            ":schema": 1,
            ":policy": self.policy.values(),
            ":observed": row["observed"],
            ":now": now,
            ":closed": row["closed"],
            **(extra or {}),
        }
        return self.store._condition(
            KEY,
            "#schema=:schema AND #policy=:policy AND #observed=:observed AND #closed=:closed",
            values,
            update=update,
        )

    def reserve_start(self, command_id):
        if type(command_id) is not str or re.fullmatch(r"[0-9a-f]{32}", command_id) is None:
            raise LifecycleUnavailable()
        self._reserve(command_id, "starts", MAX_STARTS, "operating-start#")

    def reserve_invitation(self, invitation):
        try:
            _identifier(invitation)
        except Exception:
            raise LifecycleUnavailable() from None
        self._reserve(invitation, "invitations", 10, "operating-invite#")

    def _reserve(self, command_id, counter, maximum, prefix):
        try:
            with self.store._operating_lock:
                row, now = self._load()
                if (
                    row["closed"]
                    or not self.policy.opens <= now < self.policy.closes
                    or row[counter] >= maximum
                ):
                    raise ValueError()
                guard = self._guard(
                    row,
                    now,
                    update=f"SET #observed=:now, #{counter}=:after",
                    extra={":before": row[counter], ":after": row[counter] + 1},
                )
                guard["Update"]["ConditionExpression"] += f" AND #{counter}=:before"
                self.store._write(
                    [
                        self.store._meta_condition(),
                        guard,
                        self.store._put(
                            prefix + command_id,
                            {
                                "operation": self.policy.operation,
                                "manifest": self.policy.manifest_sha256,
                                "reserved": now,
                            },
                        ),
                    ]
                )
        except Exception:
            # A lost success remains charged; no retry or claim of API dispatch.
            raise LifecycleUnavailable() from None

    def close(self, reason):
        try:
            if type(reason) is not str or reason not in REASONS:
                raise ValueError()
            with self.store._operating_lock:
                row, now = self._load()
                if row["closed"]:
                    return
                self.store._write(
                    [
                        self.store._meta_condition(),
                        self._guard(
                            row,
                            now,
                            update="SET #observed=:now, #closed=:yes, #reason=:reason",
                            extra={":yes": True, ":reason": reason},
                        ),
                    ]
                )
        except Exception:
            raise LifecycleUnavailable() from None
