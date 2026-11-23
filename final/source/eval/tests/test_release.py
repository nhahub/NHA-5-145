import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def command(*arguments, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "deploy", *map(str, arguments)],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture(scope="module")
def built_release(tmp_path_factory):
    release = tmp_path_factory.mktemp("built-release") / "release"
    workspace_state = ROOT / "node_modules/.pnpm-workspace-state-v1.json"
    before = workspace_state.read_bytes() if workspace_state.exists() else None
    result = command("build", "--output", release, "--local-rehearsal")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (workspace_state.read_bytes() if workspace_state.exists() else None) == before
    return release


def test_built_release_is_self_contained_and_refuses_overwrite(built_release):
    release = built_release
    assert (release / "store/src/server.js").is_file()
    assert (release / "panel/dist/index.html").is_file()
    assert (release / "bridge/dist/runtime.js").is_file()
    assert not (release / ".env").exists()
    assert not (release / "work").exists()
    assert not (release / "agent/tests").exists()
    assert not list(release.rglob("*.sqlite"))
    assert (release / "agent/admission/dynamodb.py").is_file()
    assert (release / "agent/lifecycle/dynamodb.py").is_file()
    assert (release / "agent/lifecycle/executor.py").is_file()
    assert (release / "agent/lifecycle/startup.py").is_file()
    assert (release / "deploy/cloud_access.py").is_file()
    assert (release / "agent/lifecycle/controller.py").is_file()
    assert (release / "agent/lifecycle/lambda_runtime.py").is_file()
    assert (release / "agent/lifecycle/readiness.py").is_file()
    assert (release / "deploy/host_checks.py").is_file()
    assert (release / "deploy/host_config.py").is_file()
    assert (release / "deploy/host_bootstrap.py").is_file()
    assert (release / "deploy/host_agent.py").is_file()
    assert (release / "deploy/host_component.py").is_file()
    for name in ("store.service", "proxy.service", "host.target"):
        relative = "deploy/shopping-copilot-" + name
        assert (release / relative).read_bytes() == (ROOT / relative).read_bytes()
    assert (release / "deploy/shopping-copilot-agent.service").read_bytes() == (
        ROOT / "deploy/shopping-copilot-agent.service"
    ).read_bytes()
    assert not (release / "eval/requirements-cloud.txt").exists()
    assert "moto" not in (release / "requirements.lock").read_text()
    result = command("verify", "--release", release)
    assert result.returncode == 0, result.stdout + result.stderr
    before = (release / "release.json").read_bytes()
    assert command("build", "--output", release, "--local-rehearsal").returncode != 0
    assert (release / "release.json").read_bytes() == before
    # Production dependencies resolve from the artifact, not the checkout.
    environment = {k: v for k, v in os.environ.items() if k != "NODE_PATH"}
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import('express').then(m=>{if(!m.default)process.exit(1)})",
        ],
        cwd=release / "store",
        env=environment,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    manifest = json.loads(before)
    assert manifest["format"] == 1
    assert manifest["catalogue_schema"] == 1


def test_executable_cache_cannot_bypass_artifact_verification(built_release):
    import py_compile
    import shutil

    cache = built_release / "agent/__pycache__"
    try:
        py_compile.compile(str(built_release / "agent/app.py"), doraise=True)
        assert list(cache.glob("*.pyc"))
        assert command("verify", "--release", built_release).returncode != 0
    finally:
        shutil.rmtree(cache)


def test_public_https_profiles_are_packaged_and_modification_is_refused(built_release, tmp_path):
    manifest = json.loads((built_release / "release.json").read_text())
    for name in ("deploy/Caddyfile", "deploy/Caddyfile.public"):
        assert (built_release / name).read_bytes() == (ROOT / name).read_bytes()
        assert name in manifest["files"]
    assert not list(built_release.rglob("*.pem"))
    assert not list(built_release.rglob("*.key"))
    installed = tmp_path / "modified-public-profile"
    assert command("install", "--release", built_release, "--output", installed).returncode == 0
    profile = installed / "deploy/Caddyfile.public"
    profile.write_text(profile.read_text() + "\n# changed after packaging\n")
    assert command("verify", "--release", installed).returncode != 0


def test_linux_runtime_lock_is_packaged_and_immutable(built_release, tmp_path):
    manifest = json.loads((built_release / "release.json").read_text())
    for name in ("deploy/linux-runtime.json", "deploy/requirements-linux.lock"):
        packaged = built_release / name
        assert packaged.is_file(), "The release must carry its dedicated Linux runtime inputs"
        assert packaged.read_bytes() == (ROOT / name).read_bytes()
        assert name in manifest["files"]
    assert (built_release / "requirements.lock").read_bytes() == (
        ROOT / "requirements.lock"
    ).read_bytes()
    installed = tmp_path / "modified-linux-lock"
    assert command("install", "--release", built_release, "--output", installed).returncode == 0
    lock = installed / "deploy/requirements-linux.lock"
    lock.write_bytes(lock.read_bytes() + b"# modified after packaging\n")
    assert command("verify", "--release", installed).returncode != 0


def test_drifted_linux_lock_refuses_before_build_tools(tmp_path, monkeypatch):
    from deploy.artifact import build

    source = tmp_path / "source"
    (source / "deploy").mkdir(parents=True)
    for name in ("pyproject.toml", "deploy/linux-runtime.json", "deploy/requirements-linux.lock"):
        (source / name).write_bytes((ROOT / name).read_bytes())
    lock = source / "deploy/requirements-linux.lock"
    lock.write_bytes(lock.read_bytes() + b"unreviewed==1\n")

    def forbidden(*_, **__):
        pytest.fail("Invalid runtime inputs must be refused before invoking build tools")

    monkeypatch.setattr(subprocess, "run", forbidden)
    output = tmp_path / "release"
    with pytest.raises(ValueError, match="^Linux runtime inputs refused$"):
        build(source, output, local=True)
    assert not output.exists()


def seed_catalogue(path):
    result = subprocess.run(
        [
            "node",
            str(ROOT / "store/node_modules/tsx/dist/cli.mjs"),
            str(ROOT / "store/scripts/catalogue-import.ts"),
            "--database",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()


def test_catalogue_backup_restore_is_consistent_exclusive_and_never_ledger(tmp_path):
    source, backup, restored = [
        tmp_path / name for name in ("live.sqlite", "backup.sqlite", "restored.sqlite")
    ]
    seed_catalogue(source)
    with sqlite3.connect(source) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("UPDATE catalogue_meta SET revision=7")
        database.execute("UPDATE products SET product_type='rehearsal' WHERE id='shoe-09'")
        database.commit()
        result = command("backup", "--catalogue", source, "--output", backup)
        assert result.returncode == 0, result.stdout + result.stderr
        record = json.loads(result.stdout)
        assert record["revision"] == 7
        assert command("restore", "--catalogue", backup, "--output", restored).returncode == 0
    with sqlite3.connect(restored) as database:
        assert database.execute("SELECT revision FROM catalogue_meta").fetchone()[0] == 7
        assert (
            database.execute("SELECT product_type FROM products WHERE id='shoe-09'").fetchone()[0]
            == "rehearsal"
        )
    before = source.read_bytes()
    assert command("restore", "--catalogue", backup, "--output", source).returncode != 0
    assert source.read_bytes() == before
    from decimal import Decimal

    from agent.inference.ledger import AllowanceLedger

    ledger = tmp_path / "allowance.sqlite"
    identity = AllowanceLedger.initialize(ledger, Decimal("1"))
    AllowanceLedger(ledger, identity).reserve("uncertain", Decimal("0.20"))
    assert (
        command("restore", "--catalogue", ledger, "--output", tmp_path / "bad.sqlite").returncode
        != 0
    )
    assert not (tmp_path / "bad.sqlite").exists()
    assert AllowanceLedger(ledger, identity).status()["accounted_usd"] == "0.200000000"


def configure_state(directory):
    from decimal import Decimal

    from agent.admission.runtime import FIELDS, AdmissionPolicy
    from agent.admission.store import InvitationStore
    from agent.inference.ledger import AllowanceLedger

    directory.mkdir()
    catalogue = directory / "catalogue.sqlite"
    seed_catalogue(catalogue)
    admission = directory / "admission.sqlite"
    admission_id = InvitationStore.initialize(admission)
    policy = AdmissionPolicy(InvitationStore(admission, admission_id))
    ledger = directory / "allowance.sqlite"
    ledger_id = AllowanceLedger.initialize(ledger, Decimal("1"))
    AllowanceLedger(ledger, ledger_id).reserve("uncertain-before-release", Decimal("0.2"))
    values = {
        "COPILOT_ENV": "local-rehearsal",
        "COPILOT_SERVICE_SECRET": "release-only-fictional-" * 3,
        "COPILOT_PANEL_ORIGIN": "http://localhost:4100",
        "COPILOT_STORE_ORIGIN": "http://localhost:4000",
        "COPILOT_AGENT_ORIGIN": "http://localhost:8000",
        "COPILOT_STORE_PRIVATE_URL": "http://127.0.0.1:4000",
        "COPILOT_CATALOGUE_DB": str(catalogue),
        "LLM_PROVIDER": "scripted",
        "LLM_MODEL": "scripted-v1",
        "ADMISSION_DB_PATH": str(admission),
        "ADMISSION_DB_ID": admission_id,
        "INFERENCE_LEDGER_PATH": str(ledger),
        "INFERENCE_LEDGER_ID": ledger_id,
        "INFERENCE_PROVIDER": "scripted",
        "INFERENCE_MODEL": "scripted-v1",
        "INFERENCE_INPUT_USD_PER_MILLION": "1",
        "INFERENCE_OUTPUT_USD_PER_MILLION": "1",
        "INFERENCE_MAX_ACTIVE": "2",
        "INFERENCE_MAX_WAITING": "2",
        "INFERENCE_WAIT_SECONDS": "1",
        "INFERENCE_MAXIMUM_PAGES": "1024",
    }
    values.update({"ADMISSION_" + name: str(getattr(policy, key)) for key, name in FIELDS.items()})
    config = directory / "runtime.env"
    config.write_text(
        "".join(f"{k}='{v.replace(chr(92), '/')}'\n" for k, v in values.items()), encoding="utf-8"
    )
    config.chmod(0o600)
    return config, values


def test_preflight_refuses_incompatible_missing_internal_state_and_low_disk(
    built_release, tmp_path
):
    config, values = configure_state(tmp_path / "state")
    base = ("check", "--release", built_release, "--config", config, "--local-rehearsal")
    assert command(*base).returncode == 0
    assert command(*base, "--minimum-free-bytes", str(2**63 - 1)).returncode != 0
    catalogue = Path(values["COPILOT_CATALOGUE_DB"])
    with sqlite3.connect(catalogue) as db:
        db.execute("UPDATE catalogue_meta SET schema_version=2")
    assert command(*base).returncode != 0
    with sqlite3.connect(catalogue) as db:
        db.execute("UPDATE catalogue_meta SET schema_version=1")
    Path(values["INFERENCE_LEDGER_PATH"]).unlink()
    result = command(*base)
    assert result.returncode != 0
    assert values["COPILOT_SERVICE_SECRET"] not in result.stdout + result.stderr
    assert not Path(values["INFERENCE_LEDGER_PATH"]).exists()


def test_runtime_starts_built_services_and_closes_after_health_failure(built_release, tmp_path):
    import httpx

    from deploy.runtime import ReleaseRuntime

    config, values = configure_state(tmp_path / "state")
    logs = tmp_path / "logs"
    with ReleaseRuntime(built_release, config, logs, local=True) as runtime:
        assert httpx.get("http://127.0.0.1:8000/health").status_code == 200
        assert httpx.get("http://127.0.0.1:4100/").status_code == 200
        assert httpx.get("http://127.0.0.1:4100/release.json").status_code == 404
        runtime.processes["store"].kill()
        runtime.processes["store"].wait(timeout=5)
        with pytest.raises(RuntimeError):
            runtime.check_health()
    assert all(process.poll() is not None for process in runtime.processes.values())
    text = "".join(path.read_text() for path in logs.glob("*.jsonl*"))
    assert "unhealthy" in text
    assert values["COPILOT_SERVICE_SECRET"] not in text
    assert "Traceback" not in text


def test_diagnostics_have_fixed_vocabulary_bounded_size_and_retention(tmp_path):
    from deploy.diagnostics import Diagnostics

    logs = tmp_path / "logs"
    diagnostics = Diagnostics(logs, maximum_bytes=256, backups=2)
    for _ in range(100):
        diagnostics.record("ready", "agent")
    paths = list(logs.glob("runtime.jsonl*"))
    assert len(paths) <= 3
    assert all(path.stat().st_size <= 256 for path in paths)
    before = {p.name: p.read_bytes() for p in paths}
    with pytest.raises(ValueError):
        diagnostics.record("token=fictional-SECRET", "agent")
    assert before == {p.name: p.read_bytes() for p in paths}
    old = logs / "runtime.jsonl.2"
    os.utime(old, (1, 1))
    Diagnostics(logs, maximum_bytes=256, backups=2)
    assert not old.exists()


def test_production_built_release_blocks_test_routes_and_uses_external_history(
    tmp_path, monkeypatch
):
    import httpx

    from agent.inference.ledger import AllowanceLedger
    from deploy.runtime import ReleaseRuntime

    monkeypatch.setenv("COPILOT_PANEL_ORIGIN", "https://app.scpilot.tech")
    monkeypatch.setenv("COPILOT_STORE_ORIGIN", "https://store.scpilot.tech")
    monkeypatch.setenv("COPILOT_AGENT_ORIGIN", "https://app.scpilot.tech")
    release = tmp_path / "production-release"
    result = command("build", "--output", release)
    assert result.returncode == 0, result.stdout + result.stderr
    config, values = configure_state(tmp_path / "state")
    values.update(
        COPILOT_ENV="production",
        COPILOT_PANEL_ORIGIN="https://app.scpilot.tech",
        COPILOT_STORE_ORIGIN="https://store.scpilot.tech",
        COPILOT_AGENT_ORIGIN="https://app.scpilot.tech",
    )
    config.write_text(
        "".join(f"{k}='{v.replace(chr(92), '/')}'\n" for k, v in values.items()), encoding="utf-8"
    )
    ledger = AllowanceLedger(Path(values["INFERENCE_LEDGER_PATH"]), values["INFERENCE_LEDGER_ID"])
    before = ledger.status()
    for _ in range(2):
        with ReleaseRuntime(release, config, tmp_path / "logs"):
            assert httpx.get("http://127.0.0.1:8000/health").status_code == 200
            assert httpx.post("http://127.0.0.1:8000/step", json={}).status_code == 404
            assert httpx.post("http://127.0.0.1:4000/__test/reset").status_code == 404
    assert ledger.status() == before


def test_modified_release_and_internal_state_refuse_before_start(built_release, tmp_path):
    from deploy.runtime import ReleaseRuntime

    damaged = tmp_path / "damaged"
    assert command("install", "--release", built_release, "--output", damaged).returncode == 0
    with (damaged / "agent/app.py").open("a") as stream:
        stream.write("\n# unexpected artifact change\n")
    config, values = configure_state(tmp_path / "state")
    assert command("verify", "--release", damaged).returncode != 0
    with pytest.raises((ValueError, OSError)):
        ReleaseRuntime(damaged, config, tmp_path / "logs", local=True)
    # A perfectly valid database still cannot be placed inside an artifact.
    (damaged / "agent/app.py").write_bytes((built_release / "agent/app.py").read_bytes())
    values["COPILOT_CATALOGUE_DB"] = str(damaged / "catalogue.sqlite")
    Path(values["COPILOT_CATALOGUE_DB"]).write_bytes(
        (Path(config).parent / "catalogue.sqlite").read_bytes()
    )
    config.write_text(
        "".join(f"{k}='{v.replace(chr(92), '/')}'\n" for k, v in values.items()), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        ReleaseRuntime(damaged, config, tmp_path / "logs", local=True)


def test_saved_shopper_state_lives_beside_other_state_never_in_the_release(built_release, tmp_path):
    from deploy.configuration import preflight

    config, values = configure_state(tmp_path / "state")
    chosen = preflight(built_release, config, local=True)
    state = tmp_path / "state"
    assert Path(chosen["AGENT_STATE_FILE"]) == state / "agent-state.sqlite"
    assert Path(chosen["COPILOT_STATE_DB"]) == state / "storefront-state.sqlite"
    values["AGENT_STATE_FILE"] = (built_release / "work/agent-state.sqlite").as_posix()
    config.write_text(
        "".join(f"{k}='{v.replace(chr(92), '/')}'\n" for k, v in values.items()), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        preflight(built_release, config, local=True)


def test_rollback_selects_installed_code_without_rewinding_quotas(built_release, tmp_path):
    from decimal import Decimal
    from time import time

    from agent.admission.store import AdmissionDenied, InvitationStore
    from agent.inference.ledger import AllowanceLedger
    from deploy.runtime import ReleaseRuntime

    config, values = configure_state(tmp_path / "state")
    candidate = tmp_path / "candidate"
    assert command("install", "--release", built_release, "--output", candidate).returncode == 0
    ledger = AllowanceLedger(Path(values["INFERENCE_LEDGER_PATH"]), values["INFERENCE_LEDGER_ID"])
    invites = InvitationStore(Path(values["ADMISSION_DB_PATH"]), values["ADMISSION_DB_ID"])
    _, code = invites.issue(time() - 1, time() + 600, redemptions=1, sessions=2)
    invites.redeem(code, "disposable-rollback-subject")
    invites.allocate_session("disposable-rollback-subject")
    with ReleaseRuntime(candidate, config, tmp_path / "logs", local=True):
        ledger.reserve("uncertain-in-new-release", Decimal("0.10"))
        invites.allocate_session("disposable-rollback-subject")
    with ReleaseRuntime(built_release, config, tmp_path / "logs", local=True):
        assert ledger.status()["accounted_usd"] == "0.300000000"
        assert ledger.status()["uncertain"] == 2
        assert invites.status()[0]["used_sessions"] == 2
        assert invites.status()[0]["used_redemptions"] == 1
        with pytest.raises(AdmissionDenied):
            invites.allocate_session("disposable-rollback-subject")


def test_built_browser_restarts_preserve_cart_and_reject_old_authority(built_release, tmp_path):
    from time import time

    from playwright.sync_api import expect, sync_playwright

    from agent.admission.store import InvitationStore
    from agent.inference.ledger import AllowanceLedger
    from deploy.runtime import ReleaseRuntime
    from eval.browser_http import browser_post

    config, values = configure_state(tmp_path / "state")
    invites = InvitationStore(Path(values["ADMISSION_DB_PATH"]), values["ADMISSION_DB_ID"])
    _, code = invites.issue(time() - 1, time() + 600, redemptions=5, sessions=20)
    ledger = AllowanceLedger(Path(values["INFERENCE_LEDGER_PATH"]), values["INFERENCE_LEDGER_ID"])
    before = ledger.status()
    with (
        ReleaseRuntime(built_release, config, tmp_path / "logs", local=True) as runtime,
        sync_playwright() as pw,
    ):
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            def activate():
                page.goto("http://localhost:4100/")
                expect(page.locator("#admission-code")).to_be_visible(timeout=15000)
                page.locator("#admission-code").fill(code)
                page.locator(".admission-entry button").click()
                expect(page.locator("#shopper-message")).to_be_enabled()

            activate()
            frame = page.frame(url=re.compile(r"^http://localhost:4000/"))
            assert frame is not None
            frame.goto("http://localhost:4000/p/shoe-09")
            frame.locator("#product-size").select_option("43")
            frame.locator("#product-color").select_option("blue")
            captured = []

            def lose_result(route):
                captured.append(route.request.post_data_json)
                route.abort()

            page.route("**/sessions/*/action-results", lose_result)
            old_session = page.evaluate("localStorage.getItem('shopping-copilot.session-id')")
            page.locator("#shopper-message").fill("Add this to my cart")
            page.get_by_role("button", name="إرسال", exact=True).click()
            expect(frame.locator("#mini-cart-count")).to_have_text("1")
            expect(page.locator("#task-status")).to_have_attribute("data-task-state", "paused")
            assert len(captured) == 1
            applied = page.request.get("http://localhost:4000/cart/state").json()
            runtime.restart("agent")
            page.unroute("**/sessions/*/action-results")
            activate()
            # The session now survives the restart (saved state). The work that was cut off
            # is ended and reported as interrupted, never run again by itself and never left
            # for Retry: the message box is usable at once.
            expect(page.locator("#conversation")).to_contain_text("interrupted")
            expect(page.locator("#retry-task")).to_have_count(0)
            cart = page.request.get("http://localhost:4000/cart/state").json()
            assert cart["lines"] == applied["lines"] and cart["revision"] == applied["revision"]
            session = page.evaluate("localStorage.getItem('shopping-copilot.session-id')")
            tab = page.evaluate("sessionStorage.getItem('shopping-copilot.tab-id')")
            assert session == old_session
            # The result that was lost before the restart is not applied afterwards: the
            # interrupted task is no longer the active one.
            late = browser_post(
                page,
                f"http://localhost:8000/sessions/{session}/action-results",
                data=captured[0],
                headers={"x-tab-id": tab},
            )
            assert late.status in {404, 409}, late.status
            assert (
                page.request.get("http://localhost:4000/cart/state").json()["lines"]
                == applied["lines"]
            )
            frame = page.frame(url=re.compile(r"^http://localhost:4000/"))
            assert frame is not None
            frame.goto("http://localhost:4000/cart")
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال", exact=True).click()
            expect(page.locator(".confirmation-card")).to_be_visible()
            state = page.request.get(
                f"http://localhost:8000/sessions/{session}/state?tab_id=release-observer"
            ).json()
            snapshot = frame.locator("body").evaluate("() => window.__copilot.snapshot()")
            task = state["task"]
            stale_answer = {
                "question_id": task["pending_question"]["action_id"],
                "text": "Confirm",
                "snapshot": snapshot,
            }
            runtime.restart("agent")
            activate()
            # The open Confirmation is expired by the restart: the task is ended as
            # interrupted and the old answer can no longer approve anything.
            expect(page.locator("#retry-task")).to_have_count(0)
            stale = browser_post(
                page,
                f"http://localhost:8000/sessions/{session}/tasks/{task['task_id']}/answers",
                data=stale_answer,
                headers={"x-tab-id": tab},
            )
            assert stale.status in {404, 409}, stale.status
            assert (
                page.request.get("http://localhost:4000/cart/state").json()["lines"]
                == applied["lines"]
            )
            # A fresh reversible edit supplies a live Undo before Storefront reset.
            current = page.request.get("http://localhost:4000/cart/state").json()
            edit = browser_post(
                page,
                "http://localhost:4000/cart/quantity",
                data={
                    "product_id": "shoe-09",
                    "size": "43",
                    "color": "blue",
                    "quantity": 2,
                    "revision": current["revision"],
                    "operation_id": "before-store-restart",
                },
            ).json()
            undo = edit["undo"]["id"]
            current_after_edit = page.request.get("http://localhost:4000/cart/state").json()
            # Capture an actually registered Confirmation at the transport seam,
            # after its explicit click but before the Storefront can apply it.
            from urllib.parse import parse_qs

            confirmations = []

            def lose_guarded_request(route):
                confirmations.append(parse_qs(route.request.post_data))
                page.evaluate("window.__releaseGuardedBlocked = true")
                route.abort()

            frame = page.frame(url=re.compile(r"^http://localhost:4000/"))
            assert frame is not None
            frame.goto("http://localhost:4000/cart")
            page.route("**/cart/clear", lose_guarded_request)
            page.locator("#shopper-message").fill("Empty my cart")
            page.get_by_role("button", name="إرسال", exact=True).click()
            expect(page.locator(".confirmation-card")).to_be_visible()
            page.locator(".confirmation-card").get_by_role(
                "button", name="Confirm", exact=True
            ).click()
            page.wait_for_function("window.__releaseGuardedBlocked === true")
            assert len(confirmations) == 1
            token = confirmations[0]["copilot_confirmation"][0]
            runtime.restart("store")
            page.unroute("**/cart/clear")
            # The Shopper's cart now survives a Storefront restart (saved state); what must
            # not survive is the short-lived authority: the Undo and the Confirmation.
            page.goto("http://localhost:4100/")
            entry = page.locator("#admission-code")
            expect(entry.or_(page.locator("#task-status"))).to_be_visible(timeout=15000)
            if entry.is_visible():
                entry.fill(code)
                page.locator(".admission-entry button").click()
            kept = page.request.get("http://localhost:4000/cart/state").json()
            assert kept["lines"] == current_after_edit["lines"] and kept["lines"] != []
            assert (
                browser_post(
                    page,
                    "http://localhost:4000/cart/undo",
                    data={"undo_id": undo, "revision": 0, "operation_id": "old-store-undo"},
                ).status
                == 409
            )
            assert (
                browser_post(
                    page,
                    "http://localhost:4000/cart/clear",
                    data={
                        "copilot_confirmation": token,
                        "cart_revision": 0,
                    },
                ).status
                == 403
            )
            after = ledger.status()
            assert after["identity"] == before["identity"]
            assert after["accounted_usd"] == before["accounted_usd"] == "0.200000000"
            assert after["uncertain"] == 1
            # Three code entries: the first visit and one after each Agent restart. The
            # Storefront restart needed none, because the Shopper's link survives it.
            assert invites.status()[0]["used_redemptions"] == 3
        finally:
            browser.close()
