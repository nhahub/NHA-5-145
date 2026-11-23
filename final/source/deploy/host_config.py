"""Restricted immutable host inputs. No environment, credential or SDK activation."""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from agent.admission.dynamodb import _identifier
from agent.admission.runtime import FIELDS, AdmissionPolicy
from agent.inference.config import REQUIRED, configured_guard
from agent.lifecycle.operating import OperatingPolicy
from agent.llm.config import load_llm_settings
from deploy.artifact import verify
from deploy.host_files import ORIGINS, _pairs, _read_private
from deploy.host_files import _file_metadata as _file_metadata
from deploy.host_files import _parent_metadata as _parent_metadata

AGENT_STATE_FILE = "/var/lib/shopping-copilot/agent/agent-state.sqlite"


@dataclass(frozen=True)
class HostSettings:
    release: Path
    fingerprint: str
    catalogue: Path
    table: str
    namespace: str
    invitation_identity: str
    lifecycle_identity: str
    inference: Mapping[str, str] = field(repr=False)
    admission_limits: Mapping[str, int]
    service_secret: str = field(repr=False)
    readiness_secret: bytes = field(repr=False)
    private_files: tuple[Path, ...] = field(default=(), repr=False)
    provider: str = "bedrock"
    model: str = "openai.gpt-oss-20b-1:0"
    provider_key: str = field(default="", repr=False)
    operating: OperatingPolicy | None = None
    operating_attempt_ceiling: int | None = None

    def __post_init__(self):
        try:
            self._validate()
            return
        except Exception:
            pass
        raise ValueError("Host configuration refused")

    def _validate(self):
        if self.operating is not None:
            if type(self.operating) is not OperatingPolicy or self.provider != "openrouter":
                raise ValueError()
            self.operating.__post_init__()
            if (
                type(self.operating_attempt_ceiling) is not int
                or not 1 <= self.operating_attempt_ceiling <= 1_000_000
            ):
                raise ValueError()
            if (
                not isinstance(self.admission_limits, Mapping)
                or not 1 <= self.admission_limits.get("maximum_sessions", 0) <= 8
            ):
                raise ValueError()
        elif self.operating_attempt_ceiling is not None:
            raise ValueError()
        for value, pattern in (
            (self.table, r"[A-Za-z0-9_.-]{3,255}"),
            (self.namespace, r"[A-Za-z0-9_-]{1,64}"),
            (self.fingerprint, r"[0-9a-f]{64}"),
        ):
            if type(value) is not str or re.fullmatch(pattern, value) is None:
                raise ValueError()
        _identifier(self.invitation_identity)
        _identifier(self.lifecycle_identity)
        if (
            type(self.provider) is not str
            or type(self.model) is not str
            or type(self.provider_key) is not str
            or (self.provider, self.model)
            not in {
                ("bedrock", "openai.gpt-oss-20b-1:0"),
                ("openrouter", "google/gemini-3.5-flash-lite"),
            }
            or (
                re.fullmatch(r"[!-~]{32,256}", self.provider_key) is None
                if self.provider == "openrouter"
                else self.provider_key != ""
            )
        ):
            raise ValueError()
        if (
            type(self.service_secret) is not str
            or re.fullmatch(r"[!-~]{32,128}", self.service_secret) is None
            or type(self.readiness_secret) is not bytes
            or not 32 <= len(self.readiness_secret) <= 64
            or not isinstance(self.inference, Mapping)
            or set(self.inference) != set(REQUIRED)
            or any(type(value) is not str or not value.strip() for value in self.inference.values())
            or not isinstance(self.admission_limits, Mapping)
            or set(self.admission_limits) != set(FIELDS)
        ):
            raise ValueError()
        object.__setattr__(self, "inference", MappingProxyType(dict(self.inference)))
        object.__setattr__(self, "admission_limits", MappingProxyType(dict(self.admission_limits)))
        AdmissionPolicy(object(), **self.admission_limits)
        _identifier(self.inference["INFERENCE_LEDGER_ID"])
        paths = [self.catalogue, Path(self.inference["INFERENCE_LEDGER_PATH"]), *self.private_files]
        if (
            not isinstance(self.release, Path)
            or not self.release.is_absolute()
            or any(not isinstance(path, Path) or not path.is_absolute() for path in paths)
        ):
            raise ValueError()
        release = self.release.resolve(strict=True)
        resolved = [path.resolve(strict=True) for path in paths]
        if (
            not release.is_dir()
            or len(set(resolved)) != len(paths)
            or any(not path.is_file() or path.is_relative_to(release) for path in resolved)
        ):
            raise ValueError()
        manifest = verify(release)
        if (
            hashlib.sha256((release / "release.json").read_bytes()).hexdigest() != self.fingerprint
            or manifest.get("local_rehearsal") is not False
            or manifest.get("public_origins") != ORIGINS
        ):
            raise ValueError()
        object.__setattr__(self, "release", release)
        object.__setattr__(self, "catalogue", resolved[0])
        object.__setattr__(self, "private_files", tuple(resolved[2:]))
        # Reuse existing allowance/price/queue validation, without any model construction.
        values = self.environment()
        configured_guard(object(), load_llm_settings(values), values)

    def environment(self):
        return {
            **self.inference,
            "COPILOT_ENV": "production",
            "LLM_PROVIDER": self.provider,
            "LLM_MODEL": self.model,
            **(
                {
                    "OPENROUTER_API_KEY": self.provider_key,
                    "OPENROUTER_TOTAL_CAP_DOLLARS": "2.00",
                }
                if self.provider == "openrouter"
                else {}
            ),
            "AWS_REGION": "eu-north-1",
            "LLM_TIMEOUT_SECONDS": "20",
            "CATALOGUE_RETRIEVAL_ENABLED": "1",
            "CATALOGUE_RANKING": "lexical",
            "COPILOT_SERVICE_SECRET": self.service_secret,
            "COPILOT_PANEL_ORIGIN": ORIGINS["panel"],
            "COPILOT_STORE_ORIGIN": ORIGINS["store"],
            "COPILOT_AGENT_ORIGIN": ORIGINS["agent"],
            "COPILOT_STORE_PRIVATE_URL": "http://127.0.0.1:4000",
            "COPILOT_CATALOGUE_DB": str(self.catalogue),
            # Saved Copilot sessions: the Agent unit's own writable state folder, never the
            # (read-only) release. Ticket 04 moves this to the DynamoDB state table.
            "AGENT_STATE_FILE": AGENT_STATE_FILE,
        }


def load_host_settings(config_path, *, read_private=_read_private):
    try:
        path = Path(config_path)
        raw = read_private(path, 16384)
        if not path.is_absolute() or type(raw) is not bytes or len(raw) > 16384:
            raise ValueError()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        names = {
            "version",
            "release",
            "fingerprint",
            "catalogue",
            "table",
            "namespace",
            "invitation_identity",
            "lifecycle_identity",
            "service_secret_file",
            "readiness_secret_file",
            "inference",
            "admission_limits",
        }
        if type(data) is not dict or type(data.get("version")) is not int:
            raise ValueError()
        provider, model, provider_key = "bedrock", "openai.gpt-oss-20b-1:0", ""
        provider_files = ()
        if data["version"] in (2, 3):
            names |= {"provider", "model", "provider_key_file"}
        if data["version"] == 3:
            names |= {"operating", "operating_attempt_ceiling"}
        if set(data) != names or data["version"] not in {1, 2, 3}:
            raise ValueError()
        if data["version"] in (2, 3):
            if (
                data["provider"] != "openrouter"
                or data["model"] != "google/gemini-3.5-flash-lite"
                or type(data["provider_key_file"]) is not str
            ):
                raise ValueError()
            provider_path = Path(data["provider_key_file"])
            if not provider_path.is_absolute():
                raise ValueError()
            raw_key = read_private(provider_path, 256)
            if type(raw_key) is not bytes:
                raise ValueError()
            provider, model, provider_key = data["provider"], data["model"], raw_key.decode("ascii")
            provider_files = (provider_path,)
        secret_path, key_path = (
            Path(data["service_secret_file"]),
            Path(data["readiness_secret_file"]),
        )
        if not secret_path.is_absolute() or not key_path.is_absolute():
            raise ValueError()
        secret, key = read_private(secret_path, 128), read_private(key_path, 64)
        return HostSettings(
            release=Path(data["release"]),
            fingerprint=data["fingerprint"],
            catalogue=Path(data["catalogue"]),
            table=data["table"],
            namespace=data["namespace"],
            invitation_identity=data["invitation_identity"],
            lifecycle_identity=data["lifecycle_identity"],
            inference=data["inference"],
            admission_limits=data["admission_limits"],
            service_secret=secret.decode("ascii"),
            readiness_secret=key,
            private_files=(path, secret_path, key_path, *provider_files),
            provider=provider,
            model=model,
            provider_key=provider_key,
            operating=OperatingPolicy.parse(data["operating"]) if data["version"] == 3 else None,
            operating_attempt_ceiling=data["operating_attempt_ceiling"]
            if data["version"] == 3
            else None,
        )
    except Exception:
        pass
    raise ValueError("Host configuration refused")
