"""Explicit pinned local model evidence. No network, approval or allowance mutation."""

import hashlib
import json
import math
import stat
from dataclasses import dataclass
from pathlib import Path
from time import time

from agent.llm.config import load_llm_settings
from deploy.host_config import HostSettings
from deploy.host_files import _pairs, _read_private, production_release

ACCEPTED_REPORT_SHA256 = "7a168063cc6b179cd484e7c6098923a8592b737752dd3908e0dd3a0e1853fd98"
RECONCILIATION_SHA256 = "8ae076766b9ac6609b437007f363e1ddd95676a19e99d315f8dffc05112fb9a9"
REFUSAL = "Provider qualification refused"
FIELDS = {
    "version",
    "provider",
    "model",
    "release_fingerprint",
    "configuration_fingerprint",
    "accepted_report_sha256",
    "reconciliation_sha256",
    "provider_key_sha256",
    "ledger_identity",
    "issued_at",
    "expires_at",
}
METADATA = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_uid",
    "st_nlink",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _interval(issued, expires):
    if (
        type(issued) is not int
        or type(expires) is not int
        or not 0 <= issued < expires <= issued + 60 * 86400
    ):
        raise ValueError()


def _profile(settings):
    if type(settings) is not HostSettings or (settings.provider, settings.model) != (
        "openrouter",
        "google/gemini-3.5-flash-lite",
    ):
        raise ValueError()
    llm = load_llm_settings(settings.environment())
    if (
        llm.endpoint != "https://openrouter.ai/api/v1"
        or llm.timeout_seconds != 30
        or llm.stream is not False
        or llm.openrouter_total_limit != 2
    ):
        raise ValueError()
    return {
        "provider": llm.provider,
        "model": llm.model,
        "endpoint": llm.endpoint,
        "timeout_seconds": llm.timeout_seconds,
        "stream": llm.stream,
        "reasoning": {"effort": "minimal", "exclude": True},
        "non_resetting_cap_usd": "2.00",
        "price_ceiling": ["0.3", "2.5"],
        "contract": "intent-v32/schema9/advice-v4",
        "limits": {
            "input_bytes": 256000,
            "protocol_bytes": 4096,
            "output_tokens": 2048,
            "adapter_request_usd": "0.02",
        },
        "inference": dict(settings.inference),
        **(
            {
                "operating": settings.operating.values(),
                "operating_attempt_ceiling": settings.operating_attempt_ceiling,
            }
            if settings.operating is not None
            else {}
        ),
    }


def configuration_fingerprint(settings):
    try:
        return _sha(json.dumps(_profile(settings), sort_keys=True, separators=(",", ":")).encode())
    except Exception:
        pass
    raise ValueError(REFUSAL)


def candidate_binding(settings, *, issued_at, expires_at):
    try:
        _interval(issued_at, expires_at)
        if settings.operating is not None and not (
            settings.operating.opens <= issued_at < expires_at <= settings.operating.closes
        ):
            raise ValueError()
        data = {
            "version": 1,
            "provider": settings.provider,
            "model": settings.model,
            "release_fingerprint": settings.fingerprint,
            "configuration_fingerprint": configuration_fingerprint(settings),
            "accepted_report_sha256": ACCEPTED_REPORT_SHA256,
            "reconciliation_sha256": RECONCILIATION_SHA256,
            "provider_key_sha256": _sha(settings.provider_key.encode("ascii")),
            "ledger_identity": settings.inference["INFERENCE_LEDGER_ID"],
            "issued_at": issued_at,
            "expires_at": expires_at,
        }
        return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    except Exception:
        pass
    raise ValueError(REFUSAL)


def _metadata(info):
    return tuple(getattr(info, name) for name in METADATA)


def _entry(path, limit, reader):
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError()
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError()
    raw = reader(path, limit)
    after = path.lstat()
    if (
        type(raw) is not bytes
        or len(raw) > limit
        or len(raw) != before.st_size
        or _metadata(before) != _metadata(after)
    ):
        raise ValueError()
    return raw, (_metadata(after), _sha(raw))


@dataclass(frozen=True, repr=False)
class BindingSnapshot:
    stamps: tuple
    issued_at: int
    expires_at: int

    def __repr__(self):
        return "BindingSnapshot()"


@dataclass(frozen=True, repr=False)
class ProviderBinding:
    settings: HostSettings
    _path: Path
    _expected: str
    _reader: object
    _clock: object
    _initial: BindingSnapshot | None = None

    def __repr__(self):
        return "ProviderBinding()"

    def _startup(self):
        settings = self.settings
        production_release(settings.release, settings.fingerprint)
        if len(settings.private_files) != 4:
            raise ValueError()
        evidence_paths = (
            self._path,
            self._path.parent / "accepted-report.json",
            self._path.parent / "reconciliation.json",
        )
        protected_paths = (*evidence_paths, *settings.private_files)
        private = tuple(
            _entry(path, limit, self._reader)
            for path, limit in zip(
                protected_paths,
                (16384, 1024**2, 1024**2, 16384, 128, 64, 256),
                strict=True,
            )
        )
        paths = (
            *protected_paths,
            settings.catalogue,
            Path(settings.inference["INFERENCE_LEDGER_PATH"]),
        )
        resolved = [path.resolve(strict=True) for path in paths]
        identities = [(path.stat().st_dev, path.stat().st_ino) for path in paths]
        if (
            len(set(resolved)) != len(paths)
            or len(set(identities)) != len(paths)
            or any(path.is_relative_to(settings.release) for path in resolved[:7])
        ):
            raise ValueError()
        binding_raw, report_raw, reconciliation_raw, config_raw, service, readiness, key = (
            entry[0] for entry in private
        )
        if _sha(binding_raw) != self._expected:
            raise ValueError()
        binding = json.loads(binding_raw, object_pairs_hook=_pairs)
        if (
            type(binding) is not dict
            or set(binding) != FIELDS
            or type(binding["version"]) is not int
        ):
            raise ValueError()
        _interval(binding["issued_at"], binding["expires_at"])
        now = self._clock()
        if (
            type(now) not in {int, float}
            or not math.isfinite(now)
            or not binding["issued_at"] <= now < binding["expires_at"]
        ):
            raise ValueError()
        if binding != json.loads(
            candidate_binding(
                settings, issued_at=binding["issued_at"], expires_at=binding["expires_at"]
            )
        ):
            raise ValueError()
        if (_sha(report_raw), _sha(reconciliation_raw)) != (
            ACCEPTED_REPORT_SHA256,
            RECONCILIATION_SHA256,
        ):
            raise ValueError()
        report, reconciliation, config = (
            json.loads(raw, object_pairs_hook=_pairs)
            for raw in (report_raw, reconciliation_raw, config_raw)
        )
        if (
            report["model"] != settings.model
            or report["accepted_for_local_replacement"] is not True
            or report["automated_passed"] is not True
            or report["milestone_summary"]["gate_passed"] is not True
            or reconciliation["runtime_qualification_granted"] is not False
            or reconciliation["status"]
            != "verified_offline_attribution_not_current_host_qualification"
            or reconciliation["accepted_report"]["sha256"] != ACCEPTED_REPORT_SHA256
        ):
            raise ValueError()
        expected_config = {
            "version": 3 if settings.operating is not None else 2,
            "provider": settings.provider,
            "model": settings.model,
            "fingerprint": settings.fingerprint,
            "table": settings.table,
            "namespace": settings.namespace,
            "invitation_identity": settings.invitation_identity,
            "lifecycle_identity": settings.lifecycle_identity,
            "inference": dict(settings.inference),
            "admission_limits": dict(settings.admission_limits),
            **(
                {
                    "operating": settings.operating.values(),
                    "operating_attempt_ceiling": settings.operating_attempt_ceiling,
                }
                if settings.operating is not None
                else {}
            ),
        }
        path_fields = {
            "release": settings.release,
            "catalogue": settings.catalogue,
            "service_secret_file": settings.private_files[1],
            "readiness_secret_file": settings.private_files[2],
            "provider_key_file": settings.private_files[3],
        }
        if (
            set(config) != set(expected_config) | set(path_fields)
            or any(config[name] != value for name, value in expected_config.items())
            or any(
                not Path(config[name]).is_absolute()
                or Path(config[name]).resolve(strict=True) != value
                for name, value in path_fields.items()
            )
        ):
            raise ValueError()
        if (service, readiness, key) != (
            settings.service_secret.encode("ascii"),
            settings.readiness_secret,
            settings.provider_key.encode("ascii"),
        ):
            raise ValueError()
        # Later private reads must not leave an earlier file's captured metadata stale.
        if any(
            _metadata(path.lstat()) != entry[1][0]
            for path, entry in zip(protected_paths, private, strict=True)
        ):
            raise ValueError()
        return BindingSnapshot(
            tuple(entry[1] for entry in private), binding["issued_at"], binding["expires_at"]
        )

    def snapshot(self):
        try:
            captured = self._initial
            now = self._clock()
            if (
                type(captured) is not BindingSnapshot
                or type(now) not in {int, float}
                or not math.isfinite(now)
                or not captured.issued_at <= now < captured.expires_at
            ):
                raise ValueError()
            return captured
        except Exception:
            pass
        raise ValueError(REFUSAL)


def load_provider_binding(
    settings, path, expected_sha256, *, read_private=_read_private, clock=time
):
    try:
        configuration_fingerprint(settings)
        if (
            type(expected_sha256) is not str
            or len(expected_sha256) != 64
            or any(value not in "0123456789abcdef" for value in expected_sha256)
        ):
            raise ValueError()
        binding = ProviderBinding(settings, Path(path), expected_sha256, read_private, clock)
        object.__setattr__(binding, "_initial", binding._startup())
        return binding
    except Exception:
        pass
    raise ValueError(REFUSAL)
