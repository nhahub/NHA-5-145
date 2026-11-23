"""DISPOSABLE Windows browser proof; explicit temporary user-CA trust required."""

import argparse
import hashlib
import http.client
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / ".scratch/cap04-cloud-readiness/probe"
TLS = DIR / "tls"
PANEL = "https://panel.copilot.test:4443"
STORE = "https://store.merchant.test:4443"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROCESSES = []
RUNTIME = False
CONTROL_SECRET = ""
ADMISSION_CODE = ""
RESULT = {"paid_calls": 0, "runtime_source_changes": False, "checks": []}


def command(args, **kwargs):
    return subprocess.run(args, check=True, creationflags=FLAGS, capture_output=True, **kwargs)


def certificates():
    TLS.mkdir(exist_ok=True)
    ssl = shutil.which("openssl")
    assert ssl
    command(
        [
            ssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-days",
            "2",
            "-keyout",
            str(TLS / "ca.key"),
            "-out",
            str(TLS / "ca.pem"),
            "-subj",
            "/CN=Copilot disposable CAP04 probe",
            "-addext",
            "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-addext",
            "nameConstraints=critical,permitted;DNS:copilot.test,permitted;DNS:merchant.test",
        ]
    )
    command(
        [
            ssl,
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-keyout",
            (TLS / "leaf.key").as_posix(),
            "-out",
            str(TLS / "leaf.csr"),
            "-subj",
            "/CN=panel.copilot.test",
        ]
    )
    (TLS / "leaf.ext").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:panel.copilot.test,DNS:store.merchant.test,DNS:store.copilot.test\n"
    )
    command(
        [
            ssl,
            "x509",
            "-req",
            "-in",
            str(TLS / "leaf.csr"),
            "-CA",
            str(TLS / "ca.pem"),
            "-CAkey",
            str(TLS / "ca.key"),
            "-CAcreateserial",
            "-out",
            (TLS / "leaf.pem").as_posix(),
            "-days",
            "2",
            "-extfile",
            str(TLS / "leaf.ext"),
        ]
    )
    der = command([ssl, "x509", "-in", str(TLS / "ca.pem"), "-outform", "DER"]).stdout
    (TLS / "ca.cer").write_bytes(der)
    return hashlib.sha1(der).hexdigest()


def start(args, env, name):
    with open(DIR / f"{name}.log", "wb") as log:
        process = subprocess.Popen(
            args, cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=FLAGS
        )
    PROCESSES.append(process)


def wait_port(port):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        if any(p.poll() is not None for p in PROCESSES):
            raise RuntimeError("Probe service exited; inspect private local logs")
        time.sleep(0.1)
    raise RuntimeError(f"No listener on {port}")


def record(name, data=True):
    RESULT["checks"].append({"name": name, "result": data})
    print(name, json.dumps(data, ensure_ascii=True), flush=True)


def page_for(context):
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send(
        "Network.setCookieControls",
        {
            "enableThirdPartyCookieRestriction": True,
            "disableThirdPartyCookieMetadata": True,
            "disableThirdPartyCookieHeuristics": True,
        },
    )
    return page


def activate_runtime(page):
    if RUNTIME:
        expect(page.locator("#admission-code")).to_be_visible(timeout=15000)
        page.locator("#admission-code").fill(ADMISSION_CODE)
        page.locator(".admission-entry button").click()


def frame_for(page):
    return page.frame_locator("#storefront-frame")


def in_store(page, script, arg=None):
    return frame_for(page).locator("body").evaluate(script, arg)


def state(page):
    return in_store(
        page,
        "async () => {const r=await fetch('/cart/state');"
        " return {status:r.status,body:await r.json()};}",
    )


def navigate(page, path):
    in_store(page, "(_, path) => {location.href=path}", path)


def add(page, quantity):
    frame = frame_for(page)
    navigate(page, "/p/shoe-09")
    expect(frame.locator("#product-size")).to_be_visible()
    frame.locator("#product-size").select_option("43")
    frame.locator("#product-color").select_option("blue")
    frame.locator('input[name="quantity"]').fill(str(quantity))
    frame.locator('[data-testid="add-to-cart"]').click()
    expect(frame.locator("#cart-feedback")).to_have_text("تمت الإضافة إلى السلة")


class IsolatedBrowsers:
    """Each Shopper gets an owned profile with explicit browser privacy settings."""

    def __init__(self, playwright, channel):
        self.playwright = playwright
        self.channel = channel

    @contextmanager
    def new_context(self):
        with TemporaryDirectory(prefix="copilot-browser-proof-") as profile:
            default = Path(profile) / "Default"
            default.mkdir()
            (default / "Preferences").write_text(
                json.dumps(
                    {
                        "profile": {"cookie_controls_mode": 1, "block_third_party_cookies": True},
                        "tracking_protection": {"block_all_3pc_toggle_enabled": True},
                    }
                )
            )
            context = self.playwright.chromium.launch_persistent_context(
                profile,
                headless=True,
                channel=None if self.channel == "chromium" else self.channel,
                args=[
                    "--host-resolver-rules=MAP panel.copilot.test 127.0.0.1, "
                    "MAP store.merchant.test 127.0.0.1, MAP store.copilot.test 127.0.0.1",
                    "--no-proxy-server",
                    "--test-third-party-cookie-phaseout",
                ],
            )
            RESULT["browser_version"] = context.browser.version
            try:
                yield context
            finally:
                context.close()


def test(browser):
    for mode in ["strict", "none", "partitioned"]:
        (DIR / "mode.txt").write_text(mode)
        with browser.new_context() as context:
            page = page_for(context)
            errors = []
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)[:160]))
            response = page.goto(PANEL)
            assert response is not None
            assert page.evaluate("window.isSecureContext")
            assert response.security_details()["protocol"] in {"TLS 1.2", "TLS 1.3"}
            expect(frame_for(page).locator("h1")).to_be_visible()
            control = in_store(
                page,
                "async () => {await fetch('/__probe/cookie-control');"
                "return (await fetch('/__probe/cookie-echo')).json()}",
            )
            assert control == {"unpartitioned": False, "partitioned": True}, control
            record(f"{mode}: third-party cookie negative control", control)
            if mode != "partitioned":
                expect(page.locator("#shopper-message")).to_be_disabled()
                assert state(page)["status"] == 401
                record(f"{mode}: linking rejected", {"cart_status": 401, "input_disabled": True})
            else:
                record(
                    "partitioned: browser storage",
                    in_store(
                        page,
                        "() => {try {sessionStorage.setItem('probe','1');"
                        "sessionStorage.removeItem('probe');return 'available'}"
                        "catch(e){return e.name+': '+e.message}}",
                    ),
                )
                record("partitioned: page errors", errors)
                record("partitioned: cart HTTP status", state(page)["status"])
                expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
                record("partitioned: linked")
                record("page errors", errors)
                journey(browser, context, page)


def test_same_site(browser):
    """Sibling hosts: preserve distinct origins, remove third-party storage dependency."""
    (DIR / "mode.txt").write_text("strict")
    with browser.new_context() as context:
        page = page_for(context)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)[:160]))
        if RUNTIME:
            page.goto("https://panel.copilot.test:4444/__probe/control-page")
        else:
            page.goto(PANEL)
        if not RUNTIME:
            page.evaluate("""() => {
            const f = document.createElement('iframe'); f.id='cookie-control';
            f.src='https://store.merchant.test:4443/__probe/control-frame';
            document.body.appendChild(f);
        }""")
        control_frame = page.frame_locator("#cookie-control")
        expect(control_frame.locator("body")).to_have_text("cookie control")
        control = control_frame.locator("body").evaluate(
            "async () => {await fetch('/__probe/cookie-control');"
            "return (await fetch('/__probe/cookie-echo')).json()}"
        )
        assert control == {"unpartitioned": False, "partitioned": True}
        record("same-site: independent cross-site cookie control", control)
        if RUNTIME:
            response = page.goto(PANEL)
        else:
            page.locator("#cookie-control").evaluate("(element) => element.remove()")
            response = page.goto(PANEL)
        assert response is not None and page.evaluate("window.isSecureContext")
        assert response.security_details()["protocol"] in {"TLS 1.2", "TLS 1.3"}
        activate_runtime(page)
        expect(page.locator("#shopper-message")).to_be_enabled(timeout=15000)
        accessible = in_store(
            page,
            """() => {
            sessionStorage.setItem('layout-probe','saved');
            const retained=sessionStorage.getItem('layout-probe') === 'saved';
            sessionStorage.removeItem('layout-probe');
            let parentReadable=false;
            try {parentReadable=!!parent.document.body} catch(e) {
                if(e.name !== 'SecurityError') throw e;
            }
            return {retained,parentReadable};
        }""",
        )
        assert accessible == {"retained": True, "parentReadable": False}
        assert page.evaluate("document.querySelector('#storefront-frame').contentDocument === null")
        assert errors == [], errors
        record("same-site: journal storage available, DOM boundary preserved", accessible)
        cookies = context.cookies()
        store_cookie = next(c for c in cookies if c["name"] == "copilot_store")
        assert (
            store_cookie["sameSite"] == "Strict"
            and store_cookie["secure"]
            and store_cookie["httpOnly"]
        )
        assert store_cookie["domain"] == "store.copilot.test"
        record("same-site: original Strict host-only Storefront cookie")
        journey(browser, context, page, same_site=True)


def runtime_control(context, operation):
    credential = next(c["value"] for c in context.cookies() if c["name"] == "copilot_agent")
    response = httpx.post(
        "http://127.0.0.1:8002" + operation,
        headers={"x-service-secret": CONTROL_SECRET},
        json={"cookie": "copilot_agent=" + credential},
        timeout=3,
    )
    response.raise_for_status()
    return response.json()


def journey(browser, context, a, *, same_site=False):
    with browser.new_context() as b_context:
        b = page_for(b_context)
        streams = []
        b.on(
            "response",
            lambda r: streams.append(
                {
                    "query_cursor": parse_qs(urlsplit(r.url).query).get("after", ["0"])[0],
                    "last_event_id": r.request.header_value("last-event-id"),
                }
            )
            if "/events?" in r.url and r.status == 200
            else None,
        )
        b.goto(PANEL)
        activate_runtime(b)
        expect(b.locator("#shopper-message")).to_be_enabled(timeout=15000)
        add(a, 1)
        add(b, 3)
        assert state(a)["body"]["lines"][0]["quantity"] == 1
        assert state(b)["body"]["lines"][0]["quantity"] == 3
        record("two-browser isolated carts")
        # Keep authoritative reads in the iframe: page.request does not model its partition.
        a.reload()
        expect(a.locator("#shopper-message")).to_be_enabled(timeout=15000)
        assert state(a)["body"]["lines"][0]["quantity"] == 1
        record("refresh retains embedded cart")
        top = page_for(context)
        top.goto(STORE)
        top_state = top.evaluate("async () => (await fetch('/cart/state')).json()")
        assert top_state["lines"] == (state(a)["body"]["lines"] if same_site else [])
        assert state(a)["body"]["lines"][0]["quantity"] == 1
        top.close()
        record(
            "top-level Storefront shares cart"
            if same_site
            else "top-level Storefront has separate partition"
        )
        tab = page_for(context)
        tab.goto(PANEL)
        expect(tab.locator("#task-status")).to_contain_text("another tab", timeout=15000)
        assert state(tab)["body"]["lines"][0]["quantity"] == 1
        tab.close()
        record("second Panel tab shares cart but cannot take task")
        # Real model-free Copilot request, bound Confirmation, reconnect and exact Undo.
        navigate(a, "/cart")
        expect(frame_for(a).locator('[data-testid="empty-cart"]')).to_be_visible()
        a.locator("#shopper-message").fill("Empty my cart")
        a.get_by_role("button", name="إرسال", exact=True).click()
        card = a.locator(".confirmation-card")
        expect(card).to_contain_text("Remove every item", timeout=15000)
        assert len(state(a)["body"]["lines"]) == 1
        record("guarded clear awaits Confirmation")
        card.get_by_role("button", name="Confirm", exact=True).click()
        expect(a.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=15000
        )
        assert state(a)["body"]["lines"] == []
        assert state(b)["body"]["lines"][0]["quantity"] == 3
        record("confirmed clear affects only owner")
        # Manual reversible Mutation proves cookie/CSRF/Undo over cross-site HTTPS.
        add(a, 2)
        frame_for(a).locator('[data-testid="undo-cart"]').click()
        expect(frame_for(a).locator("#cart-feedback")).to_contain_text("التراجع")
        assert state(a)["body"]["lines"] == []
        record("Undo restores exact cart")
        # Reconnect a session with an actual Agent Mutation to detect duplicate execution.
        mutations = []
        b.on(
            "request",
            lambda request: mutations.append(request.url)
            if request.method == "POST" and request.url.startswith(STORE + "/cart/")
            else None,
        )
        navigate(b, "/cart")
        expect(frame_for(b).locator('[data-testid="empty-cart"]')).to_be_visible()
        b.locator("#shopper-message").fill("Empty my cart")
        b.get_by_role("button", name="إرسال", exact=True).click()
        confirmation = b.locator(".confirmation-card")
        expect(confirmation).to_contain_text("Remove every item", timeout=15000)
        confirmation.get_by_role("button", name="Confirm", exact=True).click()
        expect(b.locator("#task-status")).to_have_attribute(
            "data-task-state", "completed", timeout=15000
        )
        assert state(b)["body"]["lines"] == []
        mutation_count = len(mutations)
        assert mutation_count > 0
        revision = state(b)["body"]["revision"]
        prior_streams = len(streams)
        cursor = b.evaluate("localStorage.getItem('shopping-copilot.event-cursor')")
        assert int(cursor) > 0
        assert prior_streams >= 1
        disconnected = (
            runtime_control(b_context, "/disconnect")
            if RUNTIME
            else b.evaluate(
                "async () => (await fetch('/__probe/disconnect-sse',{method:'POST'})).json()"
            )
        )
        assert disconnected["disconnected"] == 1, disconnected
        deadline = time.monotonic() + 20
        while len(streams) <= prior_streams and time.monotonic() < deadline:
            b.wait_for_timeout(100)
        assert len(streams) > prior_streams, "SSE did not actually reconnect"
        assert streams[-1]["last_event_id"] == cursor, streams[-1]
        # Observe more than two server event polling intervals after restoration.
        b.wait_for_timeout(1500)
        expect(b.locator("#shopper-message")).to_be_enabled(timeout=15000)
        assert state(b)["body"]["revision"] == revision
        assert len(mutations) == mutation_count
        record(
            "SSE reconnect after Agent Mutation: no duplicate cart request or revision",
            {"new_streams": len(streams) - prior_streams, **streams[-1]},
        )
        # Browser-side hostile Mutation must still fail without CSRF authority.
        denied = in_store(
            b,
            "async () => (await fetch('/cart/items',{method:'POST',"
            "headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({product_id:'shoe-09',quantity:9})})).status",
        )
        assert denied == 403
        record("missing CSRF remains rejected", denied)
        if RUNTIME:
            verify_public_runtime(a, b, b_context)


def verify_public_runtime(a, b, context):
    for base, path in [
        (PANEL, "/step"),
        (PANEL, "/__test/advance-time"),
        (PANEL, "/__probe/disconnect-sse"),
        (PANEL, "/docs"),
        (STORE, "/__test/reset"),
        (STORE, "/__internal/shopper/validate"),
        (STORE, "/%5f%5finternal/shopper/validate"),
    ]:
        script = "async () => (await fetch(" + json.dumps(path) + ",{method:'POST'})).status"
        status = in_store(b, script) if base == STORE else b.evaluate(script)
        assert status == 404, (path, status)
    trust = ssl.create_default_context(cafile=str(TLS / "ca.pem"))
    with (
        socket.create_connection(("127.0.0.1", 4443), timeout=3) as connection,
        trust.wrap_socket(connection, server_hostname="panel.copilot.test") as secured,
    ):
        secured.sendall(
            b"GET /health HTTP/1.1\r\nHost: foreign.example\r\nConnection: close\r\n\r\n"
        )
        hostile = http.client.HTTPResponse(secured)
        hostile.begin()
        assert hostile.status == 421
    record("production proxy rejects private/test routes and foreign Host")

    for page in (a, b):
        for target in (PANEL + "/", STORE + "/cart"):
            script = (
                "async () => {const r=await fetch("
                + json.dumps(urlsplit(target).path)
                + "); return {status:r.status,cache:r.headers.get('cache-control'),"
                + "age:r.headers.get('age')}}"
            )
            response = in_store(page, script) if target.startswith(STORE) else page.evaluate(script)
            assert response == {"status": 200, "cache": "no-store", "age": None}
    assert state(a)["body"]["lines"] == [] and state(b)["body"]["lines"] == []
    record("personal HTML and carts remain uncached and isolated")

    heartbeat = b.evaluate(r"""async () => {
        const sid=localStorage.getItem('shopping-copilot.session-id');
        const tab=sessionStorage.getItem('shopping-copilot.tab-id');
        const cursor=localStorage.getItem('shopping-copilot.event-cursor');
        const control=new AbortController();
        const timer=setTimeout(()=>control.abort(),15000);
        const started=performance.now(); let reader;
        try {
            const events=`/sessions/${sid}/events?after=${cursor}`;
            const response=await fetch(`${events}&tab_id=${encodeURIComponent(tab)}`,
                {signal:control.signal});
            if(response.status!==200) throw Error('SSE read failed');
            reader=response.body.getReader();
            const decoder=new TextDecoder(); let buffer=''; const times=[];
            while(times.length<2) {
                const next=await reader.read();
                if(next.done) throw Error('SSE ended before heartbeat');
                buffer+=decoder.decode(next.value,{stream:true});
                if(buffer.length>65536) throw Error('Unexpected SSE payload size');
                const parts=buffer.split('\n\n'); buffer=parts.pop();
                for(const part of parts)
                    if(part===': keepalive') times.push(performance.now()-started);
            }
            return {status:response.status, first_ms:Math.round(times[0]),
                gap_ms:Math.round(times[1]-times[0])};
        } finally {clearTimeout(timer); if(reader) await reader.cancel(); control.abort()}
    }""")
    assert heartbeat["status"] == 200 and heartbeat["first_ms"] < 3000
    assert 9000 <= heartbeat["gap_ms"] <= 14000
    record("SSE initial and periodic keepalive received by browser through Caddy", heartbeat)

    add(b, 1)
    navigate(b, "/cart")
    revision = state(b)["body"]["revision"]
    b.locator("#shopper-message").fill("Empty my cart")
    b.get_by_role("button", name="إرسال", exact=True).click()
    expect(b.locator(".confirmation-card")).to_contain_text("Remove every item", timeout=15000)
    b.locator("#stop-task").click()
    expect(b.locator("#task-status")).to_have_attribute(
        "data-task-state", "cancelled", timeout=15000
    )
    expect(b.locator("#shopper-message")).to_be_enabled()
    assert state(b)["body"]["revision"] == revision
    assert state(b)["body"]["lines"][0]["quantity"] == 1
    record("Stop cancels pending Confirmation without changing cart")


def cleanup(processes, thumb, tls, report, result):
    """Attempt every cleanup independently; report any failure without hiding later work."""
    errors = []
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception as error:
                errors.append("service stop: " + type(error).__name__)
        except Exception as error:
            errors.append("service stop: " + type(error).__name__)
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception as retry_error:
                errors.append("service kill: " + type(retry_error).__name__)
    try:
        command(["certutil", "-user", "-delstore", "Root", thumb])
    except Exception as error:
        errors.append("certificate removal: " + type(error).__name__)
    result["temporary_ca_removed"] = False
    try:
        result["temporary_ca_removed"] = (
            subprocess.run(
                ["certutil", "-user", "-store", "Root", thumb],
                capture_output=True,
                creationflags=FLAGS,
            ).returncode
            != 0
        )
        if not result["temporary_ca_removed"]:
            errors.append("certificate remains; consult trust-cleanup.json")
    except Exception as error:
        errors.append("certificate verification: " + type(error).__name__)
    for name in ["ca.key", "leaf.key"]:
        try:
            (tls / name).unlink(missing_ok=True)
        except Exception as error:
            errors.append("private key removal: " + type(error).__name__)
    result["cleanup_errors"] = errors
    if errors:
        result["outcome"] = "failed"
    # Persist even when an earlier cleanup step failed. A write failure still raises.
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf8")
    if errors:
        raise RuntimeError("Probe cleanup failed: " + "; ".join(errors))


def main():
    global STORE, RUNTIME, CONTROL_SECRET, ADMISSION_CODE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-temporary-user-ca", action="store_true")
    parser.add_argument("--channel", choices=["chromium", "chrome", "msedge"], default="chromium")
    parser.add_argument("--layout", choices=["cross-site", "same-site"], default="cross-site")
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Use configured application builds and Caddy, no asset rewriting",
    )
    args = parser.parse_args()
    RUNTIME = args.runtime
    if RUNTIME and args.layout != "same-site":
        parser.error("Runtime rehearsal requires the approved same-site layout")
    RESULT["runtime_source_changes"] = RUNTIME
    RESULT["production_runtime"] = RUNTIME
    if args.layout == "same-site":
        STORE = "https://store.copilot.test:4443"
    RESULT["layout"] = args.layout
    if os.name != "nt" or not args.allow_temporary_user_ca:
        parser.error("Windows only; requires explicit --allow-temporary-user-ca approval")
    DIR.mkdir(parents=True, exist_ok=True)
    RESULT["channel"] = args.channel
    RESULT["tls_verification"] = "default browser trust; no certificate bypass"
    RESULT["cookie_control"] = (
        "profile third-party blocking plus CDP/phaseout, verified with iframe negative control"
    )
    ports = (4000, 8000, 4443, 8001, 8002, 4444) if RUNTIME else (4000, 8000, 4443)
    for port in ports:
        with socket.socket() as s:
            assert s.connect_ex(("127.0.0.1", port)) != 0, (
                f"Port {port} is occupied; leave existing service alone"
            )
    thumb = certificates()
    RESULT["temporary_ca_thumbprint"] = thumb
    (DIR / "trust-cleanup.json").write_text(
        json.dumps({"thumbprint": thumb, "store": "CurrentUser Root"})
    )
    try:
        command(["certutil", "-user", "-addstore", "Root", str(TLS / "ca.cer")])
        env = dict(os.environ)
        env.update(
            LLM_PROVIDER="scripted",
            LLM_MODEL="scripted-v1",
            COPILOT_EVALUATION="1",
            COPILOT_SERVICE_SECRET=secrets.token_hex(32),
            COPILOT_STORE_ORIGIN=STORE,
            COPILOT_PANEL_ORIGIN=PANEL,
            COPILOT_STORE_PRIVATE_URL="http://127.0.0.1:4000",
            COPILOT_CATALOGUE_DB=str(DIR / "catalogue.sqlite"),
            COPILOT_PROBE_LAYOUT=args.layout,
        )
        CONTROL_SECRET = env["COPILOT_SERVICE_SECRET"]
        if RUNTIME:
            # Keep the documented direct-file CLI independent of editable installs.
            sys.path.insert(0, str(ROOT))
            from agent.admission.runtime import FIELDS
            from agent.admission.store import InvitationStore

            admission_path = DIR / ("admission-" + secrets.token_hex(8) + ".sqlite")
            admission_identity = InvitationStore.initialize(admission_path)
            admission = InvitationStore(admission_path, admission_identity)
            _, ADMISSION_CODE = admission.issue(
                time.time() - 1, time.time() + 1800, redemptions=4, sessions=40
            )
            env.update(ADMISSION_DB_PATH=str(admission_path), ADMISSION_DB_ID=admission_identity)
            limits = dict(
                maximum_bytes=2621440,
                global_rate=1000,
                browser_rate=120,
                maximum_requests=16,
                maximum_streams=16,
                maximum_sessions=20,
                browser_sessions=2,
            )
            env.update({"ADMISSION_" + name: str(limits[key]) for key, name in FIELDS.items()})
            env.update(
                COPILOT_ENV="production",
                COPILOT_TLS_CERT=(TLS / "leaf.pem").as_posix(),
                COPILOT_TLS_KEY=(TLS / "leaf.key").as_posix(),
                COPILOT_PANEL_ROOT=(ROOT / "panel/dist").as_posix(),
                COPILOT_AGENT_UPSTREAM="127.0.0.1:8001",
                COPILOT_CADDY_STORAGE=(DIR / "caddy-storage").as_posix(),
            )
            # The build receives public origins through the actual Vite configuration.
            pnpm = shutil.which("pnpm")
            command(
                [pnpm, "--filter", "@shopping-copilot/bridge", "build"],
                env=env,
                shell=os.name == "nt",
            )
            command(
                [pnpm, "--filter", "@shopping-copilot/panel", "build"],
                env=env,
                shell=os.name == "nt",
            )
        node = shutil.which("node")
        command(
            [
                node,
                "store/node_modules/tsx/dist/cli.mjs",
                "store/scripts/catalogue-import.ts",
                "--database",
                str(DIR / "catalogue.sqlite"),
            ],
            env=env,
        )
        agent_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
        if RUNTIME:
            agent_command.append("--no-access-log")
        start(agent_command, env, "agent")
        start([node, "store/node_modules/tsx/dist/cli.mjs", "store/src/server.ts"], env, "store")
        (DIR / "mode.txt").write_text("strict")
        if RUNTIME:
            caddy = str(DIR.parent / "tools/caddy.exe")
            command(
                [
                    caddy,
                    "validate",
                    "--config",
                    str(ROOT / "deploy/Caddyfile"),
                    "--adapter",
                    "caddyfile",
                ],
                env=env,
            )
            start(
                [node, str(Path(__file__).with_name("cap04_runtime_control.mjs"))],
                env,
                "runtime-control",
            )
            start(
                [
                    caddy,
                    "run",
                    "--config",
                    str(ROOT / "deploy/Caddyfile"),
                    "--adapter",
                    "caddyfile",
                ],
                env,
                "caddy",
            )
        else:
            start([node, str(Path(__file__).with_name("cap04_https_proxy.mjs"))], env, "proxy")
        for port in ports:
            wait_port(port)
        with sync_playwright() as pw:
            experiment = test_same_site if args.layout == "same-site" else test
            experiment(IsolatedBrowsers(pw, args.channel))
        RESULT["outcome"] = "passed"
    except Exception as error:
        RESULT["outcome"] = "failed"
        # Browser exceptions can include full request headers on later lines.
        RESULT["error"] = type(error).__name__ + ": " + str(error).split("\n", 1)[0][:300]
        raise
    finally:
        cleanup(
            PROCESSES,
            thumb,
            TLS,
            DIR / f"result-{args.channel}-{args.layout}{'-runtime' if RUNTIME else ''}.json",
            RESULT,
        )


if __name__ == "__main__":
    main()
