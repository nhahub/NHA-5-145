"""One trusted observation/command tick; no scheduler or caller-selected target."""

from contextlib import suppress

from agent.lifecycle.executor import EC2CommandExecutor, _state_name
from agent.lifecycle.store import LifecycleUnavailable


def is_tick(event):
    return type(event) is dict and set(event) == {"kind"} and event["kind"] == "tick"


class ControlObserver:
    def __init__(self, lifecycle, client, instance, probe, *, operating=None):
        self.lifecycle, self.client, self.instance, self.probe = lifecycle, client, instance, probe
        self._executor = EC2CommandExecutor(lifecycle, client, instance, operating=operating)

    def observe(self, generation):
        self._executor._configuration()
        token = self.lifecycle.observation_token()
        if type(generation) is not int or token["generation"] != generation:
            raise LifecycleUnavailable()
        self._executor._configuration()
        state = "unknown"
        try:
            response = self.client.describe_instances(InstanceIds=[self.instance])
            reservations = response.get("Reservations")
            if (
                response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200
                or response.get("NextToken")
                or type(reservations) is not list
                or len(reservations) != 1
            ):
                raise ValueError("Uncertain host observation")
            instances = reservations[0].get("Instances")
            if (
                type(instances) is not list
                or len(instances) != 1
                or instances[0].get("InstanceId") != self.instance
            ):
                raise ValueError("Mismatched designated host")
            name = _state_name(instances[0].get("State"))
            if name in {"pending", "running", "stopped", "stopping"}:
                state = name
        except Exception:
            state = "unknown"
        healthy = False
        if state == "running":
            with suppress(Exception):
                healthy = self.probe.check(generation) is True
        return self.lifecycle.reconcile(token, instance_state=state, healthy=healthy)


class ControlWorker:
    def __init__(self, lifecycle, executor, observer):
        if (
            executor.lifecycle is not lifecycle
            or observer.lifecycle is not lifecycle
            or executor.client is not observer.client
            or executor.instance_id != observer.instance
        ):
            raise LifecycleUnavailable()
        self.lifecycle, self.executor, self.observer = lifecycle, executor, observer

    def handle(self, event):
        if is_tick(event):
            status = self.lifecycle.status()
            if status["state"] == "stopped":
                return status
            generation = status["generation"]
            if type(generation) is not int or not 1 <= generation <= 2**53 - 1:
                raise LifecycleUnavailable()
            # Observe first: an expired pending start must become a failed intent,
            # not be rescued after its deadline. Existing claim checks revalidate
            # invitation/deadline/generation before dispatch. No new wake here.
            self.observer.observe(generation)
            self.executor.execute_once(generation=generation)
            return self.lifecycle.status()
        if (
            type(event) is not dict
            or set(event) != {"kind", "generation"}
            or type(event["kind"]) is not str
            or event["kind"] not in {"dispatch", "observe"}
            or type(event["generation"]) is not int
            or not 1 <= event["generation"] <= 2**53 - 1
        ):
            raise LifecycleUnavailable()
        generation = event["generation"]
        if self.lifecycle.status()["generation"] != generation:
            raise LifecycleUnavailable()
        if event["kind"] == "dispatch":
            self.executor.execute_once(generation=generation)
            self.observer.observe(generation)
        else:
            self.observer.observe(generation)
            self.executor.execute_once(operation="stop", generation=generation)
        return self.lifecycle.status()
