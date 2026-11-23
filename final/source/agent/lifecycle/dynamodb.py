"""Durable decision/command handoff only; never dispatches an EC2 operation."""

import copy
import re
from time import time
from uuid import uuid4

from agent.admission.dynamodb import _count, _encode, _identifier, _number
from agent.lifecycle.store import (
    COOLDOWN_SECONDS,
    DRAIN_SECONDS,
    IDLE_SECONDS,
    START_DEADLINE_SECONDS,
    START_GRACE_SECONDS,
    WORK_LEASE_SECONDS,
    LifecycleUnavailable,
)

KEY = "lifecycle#host"
STATES = {"stopped", "starting", "ready", "draining", "stopping", "unhealthy", "failed"}
TIME_FIELDS = {"observed", "activity", "deadline", "changed", "grace"}


def _hex(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ValueError("Bounded authority token required")
    return value


class DynamoLifecycle:
    @staticmethod
    def initialize(invitations):
        identity = str(uuid4())
        try:
            invitations._configuration(invitations.client, invitations.table, invitations.namespace)
            invitations._metadata()
            if invitations._read(KEY) is not None:
                raise ValueError("Lifecycle already initialized")
            now = _number(invitations.clock())
            row = {
                "schema": 1,
                "identity": identity,
                "revision": 0,
                "generation": 0,
                "state": "stopped",
                "observed": now,
                "activity": 0,
                "deadline": 0,
                "changed": 0,
                "grace": 0,
                "invitation": None,
                "leases": {},
                "command": None,
                "recoverable": True,
                "healthy": False,
            }
            invitations._write(
                [
                    invitations._condition(
                        "meta",
                        "#schema=:schema AND #identity=:identity "
                        "AND attribute_not_exists(#lifecycle_identity)",
                        {":schema": 1, ":identity": invitations.identity, ":new": identity},
                        update="SET #lifecycle_identity=:new",
                    ),
                    invitations._put(KEY, row),
                ]
            )
            return identity
        except Exception:
            raise LifecycleUnavailable() from None

    def __init__(self, invitations, identity, *, clock=time):
        try:
            self.identity = _identifier(identity)
        except Exception:
            raise LifecycleUnavailable() from None
        self.invitations, self.clock = invitations, clock
        self._load()

    def _load(self):
        try:
            store = self.invitations
            store._configuration(store.client, store.table, store.namespace)
            store._metadata()
            if store._read("meta").get("lifecycle_identity") != self.identity:
                raise ValueError("Mismatched lifecycle initialization marker")
            row = store._read(KEY)
            if row is None or set(row) != {
                "pk",
                "sk",
                "schema",
                "identity",
                "revision",
                "generation",
                "state",
                *TIME_FIELDS,
                "invitation",
                "leases",
                "command",
                "recoverable",
                "healthy",
            }:
                raise ValueError("Invalid lifecycle record")
            _count(row["schema"], 1, minimum=1)
            if row["identity"] != self.identity or row["state"] not in STATES:
                raise ValueError("Mismatched lifecycle identity/state")
            _count(row["revision"], 2**53 - 1)
            _count(row["generation"], 2**53 - 1)
            for key in TIME_FIELDS:
                _number(row[key])
            if (
                row["activity"] > row["observed"]
                or row["changed"] > row["observed"]
                or row["deadline"] > row["observed"] + START_DEADLINE_SECONDS
                or row["grace"] > row["observed"] + START_GRACE_SECONDS
            ):
                raise ValueError("Invalid lifecycle time bounds")
            if row["invitation"] is not None:
                _identifier(row["invitation"])
            if (
                type(row["recoverable"]) is not bool
                or type(row["healthy"]) is not bool
                or type(row["leases"]) is not dict
            ):
                raise ValueError("Invalid lifecycle bounds")
            if (
                row["state"] == "ready"
                and not row["healthy"]
                or (
                    row["state"] in {"stopped", "starting", "stopping", "failed", "unhealthy"}
                    and row["healthy"]
                )
            ):
                raise ValueError("Invalid admission health")
            if len(row["leases"]) > 128:
                raise ValueError("Too many work leases")
            for token, expiry in row["leases"].items():
                _hex(token)
                _number(expiry)
                if expiry > row["observed"] + WORK_LEASE_SECONDS:
                    raise ValueError("Invalid lease horizon")
            command = row["command"]
            if command is not None:
                if type(command) is not dict or set(command) != {
                    "id",
                    "operation",
                    "generation",
                    "status",
                    "claim",
                }:
                    raise ValueError("Invalid command shape")
                _hex(command["id"])
                _count(command["generation"], 2**53 - 1, minimum=1)
                if command["generation"] != row["generation"]:
                    raise ValueError("Invalid command generation")
                if command["operation"] not in {"start", "stop"} or command["status"] not in {
                    "pending",
                    "claimed",
                    "acknowledged",
                    "uncertain",
                }:
                    raise ValueError("Invalid command state")
                if command["status"] == "pending":
                    if command["claim"] is not None:
                        raise ValueError("Pending command already claimed")
                else:
                    _hex(command["claim"])
            if (
                row["state"] in {"ready", "draining", "unhealthy", "stopped"}
                and command is not None
            ):
                raise ValueError("Unsettled command cannot admit work or restart")
            if row["state"] in {"starting", "stopping"}:
                operation = "start" if row["state"] == "starting" else "stop"
                if (
                    command is None
                    or command["operation"] != operation
                    or command["status"] == "uncertain"
                ):
                    raise ValueError("Invalid transitioning command")
            if row["state"] in {"stopped", "starting", "stopping", "failed"} and row["leases"]:
                raise ValueError("Unexpected work authority outside admitted states")
            if row["recoverable"] and (
                command is not None or row["state"] not in {"stopped", "failed"}
            ):
                raise ValueError("Unsettled authority cannot be recoverable")
            if row["state"] != "stopped" and row["generation"] < 1:
                raise ValueError("Missing lifecycle generation")
            now = self._now()
            if now < row["observed"]:
                raise ValueError("Clock moved backward")
            return row, now
        except Exception:
            raise LifecycleUnavailable() from None

    def _now(self):
        try:
            return _number(self.clock())
        except Exception:
            raise LifecycleUnavailable() from None

    @staticmethod
    def _view(row, now):
        return {
            "state": row["state"],
            "generation": int(row["generation"]),
            "remaining_seconds": max(0, int(row["deadline"] - now))
            if row["state"] == "starting"
            else 0,
            "retry_after": COOLDOWN_SECONDS if row["state"] == "failed" else 5,
        }

    def _save(self, before, row, now, *, conditions=()):
        if row["revision"] >= 2**53 - 1:
            raise LifecycleUnavailable()
        row["revision"] += 1
        row["observed"] = now
        if row["state"] in {"stopped", "starting", "stopping", "failed", "unhealthy"}:
            row["healthy"] = False
        store = self.invitations
        try:
            store._write(
                [
                    store._condition(
                        "meta",
                        "#schema=:schema AND #identity=:identity "
                        "AND #lifecycle_identity=:lifecycle",
                        {":schema": 1, ":identity": store.identity, ":lifecycle": self.identity},
                    ),
                    {
                        "Put": {
                            "TableName": store.table,
                            "Item": _encode(row),
                            "ConditionExpression": (
                                "#schema=:schema AND #identity=:identity AND #revision=:revision"
                            ),
                            "ExpressionAttributeNames": {
                                "#schema": "schema",
                                "#identity": "identity",
                                "#revision": "revision",
                            },
                            "ExpressionAttributeValues": _encode(
                                {
                                    ":schema": 1,
                                    ":identity": self.identity,
                                    ":revision": before["revision"],
                                }
                            ),
                        }
                    },
                    *conditions,
                ]
            )
        except Exception:
            raise LifecycleUnavailable() from None

    def _snapshot(self):
        before, now = self._load()
        row = copy.deepcopy(before)
        row["leases"] = {token: expiry for token, expiry in row["leases"].items() if expiry >= now}
        return before, row, now

    @staticmethod
    def _intent(operation, generation):
        return {
            "id": uuid4().hex,
            "operation": operation,
            "generation": generation,
            "status": "pending",
            "claim": None,
        }

    def status(self):
        row, now = self._load()
        return self._view(row, now)

    def request_stop(self, *, generation):
        """Trusted runtime ceiling, not a public caller-selected shutdown route."""
        before, row, now = self._snapshot()
        if type(generation) is not int or generation != row["generation"]:
            raise LifecycleUnavailable()
        if row["state"] in {"stopping", "stopped"}:
            return
        if row["state"] not in {"ready", "draining", "unhealthy"} or row["command"] is not None:
            raise LifecycleUnavailable()
        row.update(state="stopping", healthy=False, changed=now, recoverable=False, leases={})
        row["command"] = self._intent("stop", generation)
        self._save(before, row, now)

    def observation_token(self):
        row, _ = self._load()
        return {"generation": int(row["generation"]), "revision": int(row["revision"])}

    def check_work(self, *, generation):
        row, _ = self._load()
        if (
            type(generation) is not int
            or generation != row["generation"]
            or row["state"] not in {"ready", "draining"}
            or not row["healthy"]
        ):
            raise LifecycleUnavailable()

    def wake(self, code):
        try:
            self.invitations._metadata()
            invitation = self.invitations._code(code)
            return self._start(invitation)
        except Exception:
            raise LifecycleUnavailable() from None

    def manual_start(self):
        return self._start(None)

    def _start(self, invitation):
        before, row, now = self._snapshot()
        if row["state"] == "failed" and (
            not row["recoverable"] or now - row["changed"] < COOLDOWN_SECONDS
        ):
            raise LifecycleUnavailable()
        if row["state"] in {"stopped", "failed"}:
            if row["command"] is not None:
                raise LifecycleUnavailable()
            row.update(
                state="starting",
                generation=row["generation"] + 1,
                activity=now,
                deadline=now + START_DEADLINE_SECONDS,
                changed=now,
                grace=0,
                invitation=invitation["id"] if invitation else None,
                leases={},
                recoverable=False,
            )
            row["command"] = self._intent("start", row["generation"])
        conditions = [self.invitations._active_condition(invitation)] if invitation else []
        self._save(before, row, now, conditions=conditions)
        return self._view(row, now)

    def begin_work(self, *, meaningful=False, generation):
        before, row, now = self._snapshot()
        if (
            type(generation) is not int
            or generation != row["generation"]
            or type(meaningful) is not bool
            or row["state"] not in {"ready", "draining"}
            or not row["healthy"]
            or len(row["leases"]) >= 128
        ):
            raise LifecycleUnavailable()
        token = uuid4().hex
        row["leases"][token] = now + WORK_LEASE_SECONDS
        if meaningful:
            row.update(state="ready", activity=now, changed=now)
        self._save(before, row, now)
        if self._now() > row["leases"][token]:
            raise LifecycleUnavailable()
        return token

    def renew_work(self, token):
        try:
            _hex(token)
        except Exception:
            raise LifecycleUnavailable() from None
        before, row, now = self._snapshot()
        if row["state"] not in {"ready", "draining", "unhealthy"} or token not in row["leases"]:
            raise LifecycleUnavailable()
        row["leases"][token] = now + WORK_LEASE_SECONDS
        self._save(before, row, now)
        if self._now() > row["leases"][token]:
            raise LifecycleUnavailable()

    def end_work(self, token, *, generation):
        before, row, now = self._snapshot()
        if type(generation) is not int or generation != row["generation"]:
            raise LifecycleUnavailable()
        try:
            _hex(token)
        except Exception:
            raise LifecycleUnavailable() from None
        row["leases"].pop(token, None)
        self._save(before, row, now)

    def claim_command(self, *, operation=None, generation=None):
        if (
            operation is not None
            and (type(operation) is not str or operation not in {"start", "stop"})
            or generation is not None
            and (type(generation) is not int or not 1 <= generation <= 2**53 - 1)
        ):
            raise LifecycleUnavailable()
        before, row, now = self._snapshot()
        if generation is not None and row["generation"] != generation:
            raise LifecycleUnavailable()
        command = row["command"]
        if (
            command is None
            or command["status"] != "pending"
            or operation is not None
            and command["operation"] != operation
        ):
            return None
        conditions = []
        if command["operation"] == "start":
            if row["state"] != "starting" or now >= row["deadline"]:
                raise LifecycleUnavailable()
            if row["invitation"]:
                try:
                    invitation = self.invitations._invitation(row["invitation"])
                    if not self.invitations._active(invitation):
                        raise LifecycleUnavailable()
                    conditions.append(self.invitations._active_condition(invitation))
                except Exception:
                    raise LifecycleUnavailable() from None
        command.update(status="claimed", claim=uuid4().hex)
        self._save(before, row, now, conditions=conditions)
        if command["operation"] == "start" and self._now() >= row["deadline"]:
            # Claim persists; another dispatcher must not inherit the lost receipt.
            raise LifecycleUnavailable()
        if (
            command["operation"] == "start"
            and row["invitation"]
            and not self.invitations.valid_invitation(row["invitation"])
        ):
            raise LifecycleUnavailable()
        return {
            key: int(value) if key == "generation" else value
            for key, value in command.items()
            if key != "status"
        }

    def check_command(self, receipt):
        row, now = self._load()
        command = row["command"]
        if (
            type(receipt) is not dict
            or command is None
            or command["status"] != "claimed"
            or type(receipt.get("generation")) is not int
            or receipt != {key: value for key, value in command.items() if key != "status"}
        ):
            raise LifecycleUnavailable()
        if command["operation"] == "start" and (
            row["state"] != "starting"
            or now >= row["deadline"]
            or row["invitation"]
            and not self.invitations.valid_invitation(row["invitation"])
            or self._now() >= row["deadline"]
        ):
            raise LifecycleUnavailable()

    def complete_command(self, receipt, *, certain):
        before, row, now = self._snapshot()
        command = row["command"]
        if type(certain) is not bool or type(receipt) is not dict or command is None:
            raise LifecycleUnavailable()
        expected = {key: value for key, value in command.items() if key != "status"}
        if (
            command["status"] != "claimed"
            or receipt != expected
            or type(receipt.get("generation")) is not int
        ):
            raise LifecycleUnavailable()
        if not certain:
            command["status"] = "uncertain"
            row.update(state="failed", changed=now, recoverable=False)
        else:
            command["status"] = "acknowledged"
            if command["operation"] == "start" and (
                row["state"] == "failed" or now >= row["deadline"]
            ):
                row.update(state="failed", changed=now, recoverable=False)
                row["command"] = self._intent("stop", row["generation"])
        self._save(before, row, now)

    def reconcile(self, token, *, instance_state, healthy):
        before, row, now = self._snapshot()
        if (
            type(token) is not dict
            or set(token) != {"generation", "revision"}
            or any(type(value) is not int for value in token.values())
            or token != {"generation": row["generation"], "revision": row["revision"]}
            or type(instance_state) is not str
            or instance_state not in {"stopped", "pending", "running", "stopping", "unknown"}
            or type(healthy) is not bool
            or (healthy and instance_state != "running")
        ):
            raise LifecycleUnavailable()
        command = row["command"]
        acknowledged = command is not None and command["status"] == "acknowledged"
        if row["state"] == "starting":
            if now >= row["deadline"]:
                row.update(state="failed", changed=now, recoverable=False)
                if command["status"] == "pending":
                    row.update(command=None, recoverable=instance_state == "stopped")
                elif acknowledged:
                    row["command"] = self._intent("stop", row["generation"])
            elif acknowledged and instance_state == "running" and healthy:
                row.update(
                    state="ready",
                    activity=now,
                    changed=now,
                    grace=now + START_GRACE_SECONDS,
                    command=None,
                    healthy=True,
                )
        elif row["state"] in {"ready", "draining", "unhealthy"}:
            row["healthy"] = instance_state == "running" and healthy
            busy = bool(row["leases"])
            idle = now - row["activity"] >= IDLE_SECONDS
            if busy or not idle or now < row["grace"]:
                desired = "ready" if instance_state == "running" and healthy else "unhealthy"
                if desired != row["state"]:
                    row.update(state=desired, changed=now)
            elif row["state"] != "draining":
                row.update(state="draining", changed=now)
            elif now - row["changed"] >= DRAIN_SECONDS:
                row.update(state="stopping", changed=now, recoverable=False)
                row["command"] = self._intent("stop", row["generation"])
        elif row["state"] == "stopping":
            if acknowledged and instance_state == "stopped":
                row.update(state="stopped", changed=now, command=None, recoverable=True)
            elif now - row["changed"] >= 120:
                row.update(state="failed", changed=now, recoverable=False)
        elif (
            row["state"] == "failed"
            and instance_state == "stopped"
            and (command is None or acknowledged and command["operation"] == "stop")
        ):
            row.update(command=None, recoverable=True)
        self._save(before, row, now)
        return self._view(row, now)
