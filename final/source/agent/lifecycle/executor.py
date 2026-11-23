"""Injected single-dispatch EC2 worker; no factory, credentials or scheduling."""

import re
from contextlib import suppress

from agent.lifecycle.store import LifecycleUnavailable

STATES = {"pending": 0, "running": 16, "stopping": 64, "stopped": 80}


def _state_name(state):
    names = {**STATES, "shutting-down": 32, "terminated": 48}
    if (
        type(state) is not dict
        or type(state.get("Name")) is not str
        or state["Name"] not in names
        or type(state.get("Code")) is not int
        or not 0 <= state["Code"] <= 65535
        or state["Code"] & 255 != names[state["Name"]]
    ):
        return None
    return state["Name"]


class EC2CommandExecutor:
    def __init__(self, lifecycle, client, instance_id, *, operating=None):
        if not isinstance(instance_id, str) or re.fullmatch(r"i-[0-9a-f]{17}", instance_id) is None:
            raise LifecycleUnavailable()
        self.lifecycle, self.client, self.instance_id = lifecycle, client, instance_id
        self.operating = operating
        configured = getattr(getattr(lifecycle, "invitations", None), "operating", None)
        if configured is not None or operating is not None:
            from agent.lifecycle.operating import OperatingAuthority

            if (
                type(operating) is not OperatingAuthority
                or operating.store is not lifecycle.invitations
                or operating.policy != configured
                or operating.policy.instance != instance_id
            ):
                raise LifecycleUnavailable()
        self._configuration()

    def _configuration(self):
        try:
            client = self.client
            config = client.meta.config
            attempts = (config.retries or {}).get("total_max_attempts")
            if (
                client.meta.service_model.service_name != "ec2"
                or client.meta.region_name != "eu-north-1"
                or client.meta.endpoint_url != "https://ec2.eu-north-1.amazonaws.com"
                or type(attempts) is not int
                or attempts != 1
                or type(config.connect_timeout) not in {int, float}
                or type(config.read_timeout) not in {int, float}
                or not 0 < config.connect_timeout <= 5
                or not 0 < config.read_timeout <= 15
                or not isinstance(self.instance_id, str)
                or re.fullmatch(r"i-[0-9a-f]{17}", self.instance_id) is None
            ):
                raise ValueError("Bounded fixed Stockholm EC2 configuration required")
        except Exception:
            raise LifecycleUnavailable() from None

    def _acknowledged(self, operation, response):
        if type(response) is not dict:
            return False
        metadata = response.get("ResponseMetadata")
        if type(metadata) is not dict or metadata.get("HTTPStatusCode") != 200:
            return False
        key = "StartingInstances" if operation == "start" else "StoppingInstances"
        items = response.get(key)
        if type(items) is not list or len(items) != 1 or type(items[0]) is not dict:
            return False
        item = items[0]
        if item.get("InstanceId") != self.instance_id:
            return False
        allowed = (
            ({"stopped", "pending", "running"}, {"pending", "running"})
            if operation == "start"
            else (set(STATES), {"stopping", "stopped"})
        )
        for key, names in zip(("PreviousState", "CurrentState"), allowed, strict=True):
            state = item.get(key)
            if _state_name(state) not in names:
                return False
        return True

    def execute_once(self, *, operation=None, generation=None):
        self._configuration()
        filters = {}
        if operation is not None:
            filters["operation"] = operation
        if generation is not None:
            filters["generation"] = generation
        receipt = self.lifecycle.claim_command(**filters)
        if receipt is None:
            return None
        # Nothing can reclaim this intent if execution pauses here. This is not
        # an atomic EC2 generation/revocation fence across the network boundary.
        self.lifecycle.check_command(receipt)
        self._configuration()
        if receipt["operation"] == "start" and self.operating is not None:
            try:
                self.operating.reserve_start(receipt["id"])
                self.operating.check()
            except Exception:
                with suppress(Exception):
                    self.lifecycle.complete_command(receipt, certain=False)
                raise LifecycleUnavailable() from None
        certain = False
        try:
            method = (
                self.client.start_instances
                if receipt["operation"] == "start"
                else self.client.stop_instances
            )
            response = method(InstanceIds=[self.instance_id])
            certain = self._acknowledged(receipt["operation"], response)
        except Exception:
            # A timeout/error can follow a committed AWS change. Never retry.
            pass
        try:
            self.lifecycle.complete_command(receipt, certain=certain)
        except Exception:
            raise LifecycleUnavailable() from None
        return "acknowledged" if certain else "uncertain"
