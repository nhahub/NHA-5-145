"""Validate external runtime state before starting or selecting a release."""

import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values

from agent.admission.runtime import configured_admission
from agent.inference.config import configured_guard
from agent.llm.config import load_llm_settings
from agent.storefront_service import StorefrontService
from deploy.artifact import verify
from deploy.catalogue import catalogue_status


def preflight(release, config, *, local=False, minimum_free_bytes=64 * 1024 * 1024):
    release, config = Path(release).resolve(strict=True), Path(config).resolve(strict=True)
    manifest = verify(release)
    if manifest["local_rehearsal"] != local or config.is_relative_to(release):
        raise ValueError("Release mode or external configuration mismatch")
    if os.name == "posix" and config.stat().st_mode & 0o027:
        raise ValueError("Configuration must not be accessible to other accounts")
    values = dict(dotenv_values(config, interpolate=False))
    if any(value is None for value in values.values()):
        raise ValueError("Configuration requires explicit values")
    expected_mode = "local-rehearsal" if local else "production"
    if (
        values.get("COPILOT_ENV") != expected_mode
        or len(values.get("COPILOT_SERVICE_SECRET", "")) < 32
    ):
        raise ValueError("Explicit runtime mode and service secret required")
    if values.get("COPILOT_STORE_PRIVATE_URL") != "http://127.0.0.1:4000":
        raise ValueError("Storefront must use the fixed private loopback service")
    panel, store = values["COPILOT_PANEL_ORIGIN"], values["COPILOT_STORE_ORIGIN"]
    if manifest.get("public_origins") != {
        "panel": panel,
        "store": store,
        "agent": values.get("COPILOT_AGENT_ORIGIN", panel),
    }:
        raise ValueError("Runtime origins differ from the built Panel")
    if local:
        if (panel, store) != ("http://localhost:4100", "http://localhost:4000"):
            raise ValueError("Local rehearsal uses fixed loopback origins")
        if values.get("LLM_PROVIDER") != "scripted":
            raise ValueError("Local release rehearsal must not perform paid inference")
    elif not panel.startswith("https://") or not store.startswith("https://"):
        raise ValueError("Production requires HTTPS public origins")
    StorefrontService(
        {
            "secret": values["COPILOT_SERVICE_SECRET"],
            "panel_origin": panel,
            "store_origin": store,
            "private_url": values["COPILOT_STORE_PRIVATE_URL"],
        }
    ).validate_configuration()
    paths = [config]
    state_keys = ["COPILOT_CATALOGUE_DB", "ADMISSION_DB_PATH", "INFERENCE_LEDGER_PATH"]
    if any(key.startswith("LIFECYCLE_") for key in values):
        if not local or not values.get("LIFECYCLE_DB_ID"):
            raise ValueError("Lifecycle transport is local rehearsal only")
        state_keys.append("LIFECYCLE_DB_PATH")
    # Saved sessions and carts are mutable state: they live beside the other state files,
    # never in the release tree (which must stay byte-identical to its manifest).
    state_directory = Path(values["COPILOT_CATALOGUE_DB"]).parent
    for key, name in (
        ("AGENT_STATE_FILE", "agent-state.sqlite"),
        ("COPILOT_STATE_DB", "storefront-state.sqlite"),
    ):
        values.setdefault(key, str(state_directory / name))
        saved = Path(values[key])
        if not saved.is_absolute() or saved.resolve().is_relative_to(release) or saved == config:
            raise ValueError("Saved state must be an absolute file outside releases")
    for key in state_keys:
        raw = Path(values[key])
        if not raw.is_absolute():
            raise ValueError("State paths must be absolute")
        path = raw.resolve(strict=True)
        if path.is_relative_to(release) or path in paths or not path.is_file():
            raise ValueError("State must be distinct existing files outside releases")
        paths.append(path)
    if type(minimum_free_bytes) is not int or minimum_free_bytes < 1:
        raise ValueError("Finite disk headroom required")
    for parent in {p.parent for p in paths[1:]}:
        if shutil.disk_usage(parent).free < minimum_free_bytes:
            raise ValueError("Insufficient state disk headroom")
        with NamedTemporaryFile(dir=parent) as probe:
            probe.write(b"release-state-write-check")
            probe.flush()
            os.fsync(probe.fileno())
    catalogue_status(paths[1])
    admission = configured_admission(values)
    if admission is None:
        raise ValueError("Admission is mandatory for release rehearsal")
    if "LIFECYCLE_DB_PATH" in values:
        from agent.lifecycle.work import configured_lifecycle

        configured_lifecycle(values, admission)
    # Configuration and ledger checks only: no provider is constructed or called.
    if not values.get("INFERENCE_LEDGER_PATH"):
        raise ValueError("Durable allowance is mandatory")
    configured_guard(object(), load_llm_settings(values), values)
    values["PYTHONDONTWRITEBYTECODE"] = "1"
    return values
