"""Private finite guardian decisions over an injected, fixed-target control plane."""

from decimal import Decimal
from math import isfinite
from time import time

from agent.lifecycle.operating import MAX_RUN_SECONDS, REASONS

FIELDS = {
    "observed",
    "closed_at",
    "reason",
    "credit_checked",
    "credits",
    "dns_absent",
    "dns_since",
    "dns_checked",
    "released",
    "shutdown",
}
SHUTDOWN = {"fence", "authority", "delivery", "ingress"}


def _number(value):
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise ValueError("Finite guard observation required")
    return value


def _money(value):
    if type(value) is not str:
        raise ValueError("Explicit decimal credit observation required")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise ValueError("Finite credit observation required")
    return amount


class OperatingGuard:
    def __init__(self, backend, *, clock=time):
        self.backend, self.clock = backend, clock

    def handle(self, event):
        if type(event) is not dict or event != {"kind": "guard"}:
            raise ValueError("Fixed private guard event required")
        now, backend = _number(self.clock()), self.backend
        if now > backend.cleanup_end:
            return {"state": "cleanup_expired"}
        record, host, reason, errors = None, None, None, []
        valid_record = False
        try:
            record = backend.read()
            if (
                type(record) is not dict
                or set(record) != FIELDS
                or type(record["released"]) is not bool
                or type(record["shutdown"]) is not dict
                or set(record["shutdown"]) != SHUTDOWN
                or any(type(value) is not bool for value in record["shutdown"].values())
            ):
                raise ValueError()
            for name in ("observed", "credit_checked"):
                if _number(record[name]) > now:
                    raise ValueError()
            for name in ("closed_at", "dns_absent", "dns_since", "dns_checked"):
                if record[name] is not None and _number(record[name]) > now:
                    raise ValueError()
            if record["dns_since"] is not None and (
                record["dns_checked"] is None or record["dns_since"] > record["dns_checked"]
            ):
                raise ValueError()
            _money(record["credits"])
            if record["closed_at"] is not None:
                if record["reason"] not in REASONS:
                    raise ValueError()
                reason = record["reason"]
            elif record["reason"] is not None:
                raise ValueError()
            valid_record = True
            if now >= backend.closes:
                reason = reason or "expired"
            if reason is None:
                authority = backend.authority_status()
                if type(authority) is not dict or type(authority.get("closed")) is not bool:
                    raise ValueError()
                if authority["closed"]:
                    reason = "owner"
            if reason is None and now - record["credit_checked"] >= 86400:
                plan = backend.plan_status()
                credits = _money(plan["credits"])
                if (
                    plan.get("free") is not True
                    or plan.get("active") is not True
                    or (
                        credits < 30
                        or _money(backend.baseline_credits) - credits >= 35
                        or plan.get("within_traffic", True) is not True
                    )
                ):
                    reason = "budget"
                record.update(credit_checked=now, credits=str(credits))
            host = backend.host_status()
            if type(host) is not dict or host.get("state") not in {
                "pending",
                "running",
                "stopping",
                "stopped",
            }:
                raise ValueError()
            if reason is None and host["state"] == "running":
                launched = _number(host["launched"])
                if launched > now:
                    raise ValueError()
                if now - launched >= MAX_RUN_SECONDS:
                    backend.cycle_stop()
                    record["observed"] = now
                    backend.write(record)
                    return {"state": "cycle_stopping", "reason": "runtime"}
            if reason is None:
                record["observed"] = now
                backend.write(record)
                return {"state": "open"}
        except Exception:
            reason = reason or "fault"
            if not valid_record:
                record = None

        # Invalidate continuity durably BEFORE any DNS observation or fallible
        # shutdown work. A lost final write must never restore a previous clock.
        prior_since = None
        shutdown = record["shutdown"] if record is not None else dict.fromkeys(SHUTDOWN, False)
        can_work = getattr(backend, "can_work", lambda minimum: True)
        if record is not None:
            checked = record["dns_checked"]
            if checked is not None and 0 <= now - checked <= 360:
                prior_since = record["dns_since"]
            if not record["released"]:
                record["dns_since"] = None
            record["observed"] = now
            if record["closed_at"] is None:
                record.update(closed_at=now, reason=reason)
            try:
                backend.write(record)
            except Exception:
                errors.append("dns_checkpoint")

        # Each action is independent. An unavailable table never suppresses Stop.
        def checkpoint(name, action, *, confirmed=False):
            if shutdown[name]:
                return
            if not can_work(8000):
                return
            try:
                outcome = action()
                if not confirmed or outcome is True:
                    shutdown[name] = True
                    if record is not None:
                        backend.write(record)
            except Exception:
                errors.append(name)

        checkpoint("fence", backend.fence)
        # Physical Stop is independent of checkpoint success, including a failed
        # table, IAM fence or receipt write. Reobserve the host on every tick.
        try:
            backend.stop()
        except Exception:
            errors.append("stop")
        checkpoint("authority", lambda: backend.close_authority(reason))
        checkpoint("delivery", backend.close_delivery, confirmed=True)
        delivery_closed = shutdown["delivery"]
        if record is None or now < record.get("observed", now + 1):
            return {"state": "unverified", "reason": reason}
        record.update(observed=now)
        stopped = host is not None and host["state"] == "stopped"
        if stopped:
            checkpoint("ingress", backend.close_ingress)
        if (
            stopped
            and delivery_closed
            and all(shutdown.values())
            and not errors
            and can_work(22000)
        ):
            ready_to_release = False
            try:
                if not record["released"]:
                    absent = backend.dns_absent() is True
                    completed = _number(self.clock())
                    if not now <= completed <= backend.cleanup_end:
                        raise ValueError("DNS completion clock unavailable")
                    record["dns_checked"] = completed
                    if absent:
                        if record["dns_absent"] is None:
                            record["dns_absent"] = completed
                        record["dns_since"] = prior_since if prior_since is not None else completed
                        if completed - record["dns_since"] >= 7200:
                            ready_to_release = True
                    else:
                        # Preserve the first proof for audit, but never release on
                        # its clock after a positive or uncertain DNS observation.
                        record["dns_since"] = None
            except Exception:
                record["dns_since"] = None
                errors.append("cleanup")
            if ready_to_release:
                try:
                    backend.write(record)
                    record["released"] = backend.release() is True
                except Exception:
                    errors.append("release")
        try:
            backend.write(record)
        except Exception:
            errors.append("receipt")
        return {"state": "unverified" if errors else "closing", "reason": reason}
