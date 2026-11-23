"""Bounded CAP-07 operator HTTP/SSE driver. No AWS client, provider key or live model path."""

import asyncio
import json
import math
import re
import ssl
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from urllib.parse import urlsplit

import httpx

PANEL, STORE = "https://app.scpilot.tech", "https://store.scpilot.tech"


class SessionWindow:
    def __init__(self, started):
        if type(started) not in {int, float} or not math.isfinite(started):
            raise ValueError("Acceptance window refused")
        self.started, self.end, self.last = started, started + 14400, started
        self.starts, self.reboots, self.startup_started = 0, 0, None

    def authorize(self, phase, now, *, watchdog=True, barriers=True, paused=False):
        if phase == "cleanup":
            return
        if phase not in {"prepare", "start", "reboot", "work"} or (
            type(now) not in {int, float}
            or not math.isfinite(now)
            or not self.last <= now < self.end
            or not watchdog
            or paused
            or phase in {"reboot", "work"}
            and not barriers
        ):
            raise ValueError("Acceptance window refused")
        if phase == "start":
            if self.starts:
                raise ValueError("Acceptance window refused")
            self.starts += 1
        if phase == "reboot":
            if self.reboots or not self.starts or now >= self.started + 135 * 60:
                raise ValueError("Acceptance window refused")
            self.reboots += 1
        if phase == "work" and now >= self.started + 160 * 60:
            raise ValueError("Acceptance window refused")
        self.last = now

    def begin_application(self, now, *, generation):
        self.authorize("prepare", now)
        if generation != 0 or self.startup_started is not None:
            raise ValueError("Acceptance startup refused")
        self.startup_started = now

    def startup_remaining(self, now):
        if self.startup_started is None:
            return 0
        return max(0, min(self.end - now, self.startup_started + 300 - now))

    def idle_reconcile_at(self, last_activity):
        if not self.started <= last_activity <= self.started + 160 * 60:
            raise ValueError("Acceptance idle bound refused")
        return last_activity + 3600


def capacity_safe(sample):
    return (
        sample["mem_available"] >= 256 * 1024**2
        and sample["disk_free"] >= 2 * 1024**3
        and sample["oom_kill"] == 0
        and sample["swap_sustained"] is False
        and sample["memory_full_sustained"] is False
        and sample["cpu_credits"] > 0
    )


class RequestBudget:
    def __init__(self, mode, end_epoch, *, clock=time.time):
        if mode not in {"control", "captured"} or not math.isfinite(end_epoch):
            raise ValueError("Acceptance profile refused")
        self.mode, self.clock, self.count = mode, clock, 0
        self.started = clock()
        self.end = min(end_epoch, self.started + 600)
        self.diagnostic = {"stage": "prepare"}

    def check(self, method, url):
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        p = parsed.path
        allowed = (
            origin == PANEL
            and (
                method == "GET"
                and (p == "/health" or re.fullmatch(r"/sessions/[A-Za-z0-9_-]+/(events|state)", p))
                or method == "POST"
                and (
                    p
                    in {
                        "/shopper/bootstrap",
                        "/shopper/challenge",
                        "/shopper/link",
                        "/shopper/admission",
                        "/sessions",
                    }
                    or re.fullmatch(r"/sessions/[A-Za-z0-9_-]+/stop", p)
                    or self.mode == "captured"
                    and re.fullmatch(r"/sessions/[A-Za-z0-9_-]+/messages", p)
                )
            )
            or origin == STORE
            and (method, p) in {("GET", "/__shopper"), ("POST", "/__copilot/link-ticket")}
        )
        if (
            not allowed
            or parsed.fragment
            or parsed.username
            or parsed.password
            or self.count >= 150
            or not self.started <= self.clock() < self.end
        ):
            raise ValueError("Acceptance request refused")
        self.count += 1


def classify_events(text):
    if len(text.encode()) > 1048576:
        return "failed"
    seen = set()
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if ": " in line and not line.startswith(":"):
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("event") == "action":
            action = json.loads(fields.get("data", "{}")).get("action", {})
            return (
                "completed" if action.get("type") in {"navigate", "spotlight", "done"} else "failed"
            )
        if fields.get("event") == "interpretation_paused":
            value = json.loads(fields.get("data", "{}"))
            return "inference_busy" if value.get("reason") == "inference_busy" else "failed"
        if fields.get("event") == "error":
            message = json.loads(fields.get("data", "{}")).get("message")
            return (
                "inference_busy"
                if message
                in {
                    "The assistant is busy. Your request was not sent to the model; retry shortly.",
                    "المساعد مشغول الآن. لم يُرسل طلبك للنموذج؛ جرّب بعد قليل.",
                }
                else "failed"
            )
        seen.add(fields.get("event"))
    return "completed" if {"suggestions", "done"} <= seen else "failed"


async def close_task(client, sid, headers, budget):
    url = PANEL + f"/sessions/{sid}/stop"
    budget.check("POST", url)
    response = await client.post(url, headers=headers)
    if len(response.content) > 4096 or not (
        response.status_code == 202
        or response.status_code == 409
        and response.json() == {"detail": "There is no active Shopping Task"}
    ):
        raise ValueError("Acceptance cleanup refused")


async def captured_outcome(client, url, headers, budget):
    budget.check("GET", url)
    async with client.stream("GET", url, headers=headers) as response:
        if response.status_code != 200:
            raise ValueError("Acceptance stream refused")
        text = ""
        size = 0
        async for chunk in response.aiter_text():
            size += len(chunk.encode())
            if size > 1048576:
                raise ValueError("Acceptance stream bound exceeded")
            text += chunk
            if not text.replace("\r\n", "\n").endswith("\n\n"):
                continue
            outcome = classify_events(text)
            if outcome != "failed":
                return outcome
            if any(
                "event: " + event + "\n" in text.replace("\r\n", "\n")
                for event in ("error", "interpretation_paused", "action", "done", "shopper_reset")
            ):
                return "failed"
    return "failed"


async def exercise(mode, code, snapshot, budget, factory, *, cohort_file=None):
    results = []

    async def send(client, method, url, expected=200, **options):
        budget.check(method, url)
        response = await client.request(method, url, **options)
        if response.status_code != expected or len(response.content) > 1048576:
            budget.diagnostic.update(
                http_status=response.status_code,
                expected_status=expected,
                route=re.sub(r"/sessions/[^/]+/", "/sessions/:id/", urlsplit(url).path),
            )
            raise ValueError("Acceptance HTTP refused")
        return response

    for count in (1, 5, 8):
        budget.diagnostic = {"stage": "setup", "requested": count}
        async with AsyncExitStack() as stack:
            actors = []
            for _ in range(count):
                client = await stack.enter_async_context(factory())
                boot = await send(
                    client, "POST", PANEL + "/shopper/bootstrap", headers={"origin": PANEL}
                )
                headers = {"origin": PANEL, "x-csrf-token": boot.json()["csrf"]}
                challenge = (
                    await send(client, "POST", PANEL + "/shopper/challenge", headers=headers)
                ).json()["challenge"]
                csrf = (await send(client, "GET", STORE + "/__shopper")).json()["csrf"]
                ticket = (
                    await send(
                        client,
                        "POST",
                        STORE + "/__copilot/link-ticket",
                        expected=201,
                        headers={"origin": STORE, "x-csrf-token": csrf},
                        json={"challenge": challenge, "audience": PANEL},
                    )
                ).json()["ticket"]
                await send(
                    client,
                    "POST",
                    PANEL + "/shopper/link",
                    headers=headers,
                    json={"ticket": ticket, "challenge": challenge},
                )
                admission = await send(
                    client,
                    "POST",
                    PANEL + "/shopper/admission",
                    headers=headers,
                    json={"code": code},
                )
                if admission.json() != {"required": True, "admitted": True}:
                    raise ValueError("Acceptance admission refused")
                sid = (
                    await send(
                        client,
                        "POST",
                        PANEL + "/sessions",
                        expected=201,
                        headers=headers,
                        json={"tab_id": f"cap07-{count}-{len(actors)}"},
                    )
                ).json()["session_id"]
                headers["x-tab-id"] = f"cap07-{count}-{len(actors)}"
                actors.append((client, headers, sid))
            if cohort_file is not None:
                cohort_file.write_text(json.dumps({"requested": count}), encoding="utf-8")
            start = time.monotonic()
            budget.diagnostic["stage"] = "consume"

            async def consume(actor):
                client, headers, sid = actor
                if mode == "captured":
                    await send(
                        client,
                        "POST",
                        PANEL + f"/sessions/{sid}/messages",
                        expected=202,
                        headers=headers,
                        json={"text": "Show me shoes", "snapshot": snapshot},
                    )
                    outcome = await captured_outcome(
                        client,
                        PANEL + f"/sessions/{sid}/events?tab_id={headers['x-tab-id']}",
                        headers,
                        budget,
                    )
                else:
                    url = PANEL + f"/sessions/{sid}/events?tab_id={headers['x-tab-id']}"
                    budget.check("GET", url)
                    async with client.stream("GET", url) as response:
                        if response.status_code != 200:
                            raise ValueError("Acceptance stream refused")
                        await asyncio.sleep(0.1)
                    await send(client, "GET", url + "&once=true")
                    outcome = "completed"
                return outcome

            # Real DynamoDB authorization/lease checks are part of this host lane.
            # Keep the operator cohort wait bounded without changing inference queue waits.
            async with asyncio.timeout(30):
                outcomes = await asyncio.gather(*(consume(a) for a in actors))
            if mode == "captured":
                budget.diagnostic["stage"] = "cleanup"
                # The control lane creates no Shopping Task. Captured cleanup is
                # sequential to respect the reserved owner-stop concurrency limit.
                for client, headers, sid in actors:
                    await close_task(client, sid, headers, budget)
            completed, busy = outcomes.count("completed"), outcomes.count("inference_busy")
            budget.diagnostic.update(stage="cohort", outcomes=outcomes)
            expected = (5, 3) if mode == "captured" and count == 8 else (count, 0)
            if (completed, busy) != expected:
                raise ValueError("Acceptance cohort refused")
            results.append(
                {
                    "requested": count,
                    "completed": completed,
                    "inference_busy": busy,
                    "elapsed_seconds": round(time.monotonic() - start, 6),
                }
            )
    return results


def run(profile: Path, receipt: Path) -> int:
    result = {"passed": False, "real_model_posts": 0}
    budget = None
    try:
        data = json.loads(profile.read_bytes())
        if set(data) != {
            "mode",
            "ca_file",
            "invitation_file",
            "snapshot_file",
            "deadline_epoch",
            "cohort_file",
        }:
            raise ValueError()
        mode = data["mode"]
        context = ssl.create_default_context(cafile=data["ca_file"])
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        code = Path(data["invitation_file"]).read_text(encoding="ascii").strip()
        snapshot = (
            json.loads(Path(data["snapshot_file"]).read_bytes()) if mode == "captured" else None
        )
        cohort = Path(data["cohort_file"]) if mode == "captured" else None
        budget = RequestBudget(mode, data["deadline_epoch"])

        def factory():
            return httpx.AsyncClient(
                verify=context,
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(30, connect=5),
                limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            )

        async def work():
            async with asyncio.timeout(600):
                return await exercise(mode, code, snapshot, budget, factory, cohort_file=cohort)

        result.update(mode=mode, cohorts=asyncio.run(work()), requests=budget.count, passed=True)
    except Exception as error:
        result["category"] = "acceptance_refused"
        result["failure"] = {"exception": type(error).__name__}
        if budget is not None:
            result["requests"] = budget.count
            result["failure"].update(budget.diagnostic)
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1]), Path(sys.argv[2])))
