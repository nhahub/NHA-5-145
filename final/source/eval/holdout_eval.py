"""Evaluate the frozen synthetic holdout without fitting or automatic paid retries."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from numbers import Integral
from pathlib import Path

FAILURE = "__failure__"
CAP = Decimal("0.20")
SOURCE_FILES = (
    "eval/holdout_eval.py",
    "eval/holdout_release.py",
    "eval/comparison_encoder.py",
    "agent/llm/openrouter.py",
    "agent/llm/config.py",
    "agent/llm/contract.py",
    "agent/llm/provider_schema.py",
)


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save_json(path, value):
    """Flush the replacement before renaming; a paid attempt always follows this write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def exclusive_lock(path):
    """A crashed process leaves the lock for explicit operator investigation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError(
            "Experiment is locked; investigate a stale lock before resuming"
        ) from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        path.unlink()


def decimal_cost(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return cost if cost.is_finite() and cost >= 0 else None


class BudgetExceeded(ValueError):
    """The next reservation would exceed the fixed experiment allowance."""


class BudgetLedger:
    def __init__(self, path, binding):
        self.path = Path(path)
        self.data = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {"version": 1, "cap_usd": str(CAP), "binding": binding, "attempts": {}}
        )
        if self.data["binding"] != binding or self.data["cap_usd"] != str(CAP):
            raise ValueError("Experiment binding changed; resume refused")
        for attempt in self.attempts.values():
            if decimal_cost(attempt["reservation_usd"]) is None:
                raise ValueError("Invalid persisted reservation")
            if (
                attempt["actual_cost_usd"] is not None
                and decimal_cost(attempt["actual_cost_usd"]) is None
            ):
                raise ValueError("Invalid persisted cost")
            if attempt["status"] == "inflight":
                attempt.update(
                    status="interrupted",
                    result={"prediction": FAILURE, "failure_category": "interrupted"},
                )
        self.persist()

    @property
    def attempts(self):
        return self.data["attempts"]

    @property
    def exposure(self):
        return sum(
            (Decimal(a["actual_cost_usd"] or a["reservation_usd"]) for a in self.attempts.values()),
            Decimal(0),
        )

    def persist(self):
        self.data["spent_plus_reserved_usd"] = str(self.exposure)
        save_json(self.path, self.data)

    def reserve(self, case_id, amount):
        if case_id in self.attempts:
            raise ValueError("Case was already attempted; replay refused")
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            raise ValueError("Reservation must be a positive finite Decimal")
        if self.exposure + amount > CAP:
            raise BudgetExceeded("Fixed $0.20 experiment allowance exhausted")
        self.attempts[case_id] = {
            "status": "inflight",
            "reservation_usd": str(amount),
            "actual_cost_usd": None,
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.persist()

    def finish(self, case_id, cost, result):
        attempt = self.attempts[case_id]
        if attempt["status"] != "inflight":
            raise ValueError("Only an inflight attempt can finish")
        actual = decimal_cost(cost)
        attempt.update(
            status="complete",
            actual_cost_usd=str(actual) if actual is not None else None,
            result=result,
        )
        self.persist()


def resolve_under(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Artifact path leaves its approved root")
    return path


def verify_artifacts(protocol, root, artifact_root):
    """Verify every family and selection report before any deserialization or API call."""
    hashes = {}
    for family in protocol["families"]:
        for field, hash_field, base in (
            ("artifact", "sha256", artifact_root),
            ("selection_report", "selection_report_sha256", root),
        ):
            path = resolve_under(base, family[field])
            actual = digest(path)
            if actual != family[hash_field]:
                raise ValueError(f"Frozen {field} hash mismatch: {family['family']}")
            hashes[family[field]] = actual
    return hashes


def validate_output(text, labels):
    result = json.loads(text)
    if not isinstance(result, dict) or set(result) != {"intent"} or result["intent"] not in labels:
        raise ValueError("Invalid intent output")
    return result["intent"]


def make_request(protocol, record):
    from agent.llm.contract import LLMMessage, LLMRequest

    settings = protocol["llm"]
    return LLMRequest(
        system=settings["system"],
        messages=(LLMMessage("shopper", record["input"]["message"]),),
        response_schema=settings["response_schema"],
        response_validator=lambda text: validate_output(text, protocol["labels"]),
        prompt_version="synthetic-holdout-20261009",
        temperature=settings["temperature"],
        max_tokens=settings["max_tokens"],
        attempt_id=record["case_id"],
        provider_attempt_limit=1,
    )


def request_reservation(request, model):
    """Match the existing client's byte bound, including its exact JSON serialization."""
    from agent.llm.provider_schema import openrouter_response_schema

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.messages[0].content},
        ],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "stream": False,
        "reasoning": {"enabled": False},
        "provider": {
            "sort": "latency",
            "require_parameters": True,
            "max_price": {"prompt": 0.3, "completion": 2.5},
        },
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "shopping_intent",
                "strict": True,
                "schema": openrouter_response_schema(request.response_schema),
            },
        },
    }
    return (
        (Decimal(len(json.dumps(payload).encode()) + 4096) * Decimal("0.3"))
        + Decimal(request.max_tokens) * Decimal("2.5")
    ) / Decimal(1_000_000)


async def evaluate_llm(records, protocol, client, ledger):
    from agent.llm.openrouter import generation_id

    for record in records:
        case_id = record["case_id"]
        if case_id in ledger.attempts:
            continue
        request = make_request(protocol, record)
        try:
            ledger.reserve(case_id, request_reservation(request, protocol["llm"]["model"]))
        except BudgetExceeded:
            break
        start = time.perf_counter()
        metadata_offset = len(client.call_metadata)
        result = {"prediction": FAILURE, "failure_category": None}
        try:
            pieces = [chunk.text or "" async for chunk in client.complete(request)]
            result["prediction"] = validate_output("".join(pieces), protocol["labels"])
        except Exception:
            # Provider exception strings may contain credentials, URLs or arbitrary content.
            result["failure_category"] = "request_or_output_failure"
        result["latency_ms"] = (time.perf_counter() - start) * 1000
        metadata = client.call_metadata[-1] if len(client.call_metadata) > metadata_offset else None
        usage = metadata.usage if metadata else None
        cost = usage.get("cost") if isinstance(usage, dict) else None
        result["generation_id"] = generation_id(metadata.generation_id) if metadata else None
        if metadata:
            result["provider_latency_ms"] = metadata.latency_ms
            if metadata.failure_category in {
                "budget",
                "throttled",
                "http",
                "timeout",
                "network",
                "invalid_response",
            }:
                result["failure_category"] = metadata.failure_category
        result["usage"] = {
            key: value
            for key, value in (usage or {}).items()
            if key in {"cost", "prompt_tokens", "completion_tokens", "total_tokens"}
            and isinstance(value, int | float)
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        }
        ledger.finish(case_id, cost, result)


class LocalFrozenEncoder:
    """Load only the pre-existing, hash-verified pinned CPU encoder cache."""

    def __init__(self, cache, expected):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from eval.comparison_encoder import MODEL, REVISION

        if expected["model"] != MODEL or expected["revision"] != REVISION:
            raise ValueError("Frozen encoder model or revision mismatch")
        import torch
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(4)
        snapshot = Path(
            snapshot_download(
                MODEL, revision=REVISION, cache_dir=str(cache), token=False, local_files_only=True
            )
        )
        for name, info in expected["files"].items():
            # HF snapshots legitimately contain symlinks to the cache blob directory.
            candidate = snapshot / name
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Invalid cached encoder file path")
            if digest(candidate) != info["sha256"]:
                raise ValueError("Cached encoder file hash mismatch")
        self.model = SentenceTransformer(
            str(snapshot),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        self.metadata = {
            key: expected[key]
            for key in (
                "model",
                "revision",
                "dimensions",
                "max_seq_length",
                "normalize_embeddings",
                "files",
                "bytes",
            )
        }
        self.metadata.update(device="cpu", threads=4, cuda_build=torch.version.cuda, gpu_name=None)

    def encode(self, texts):
        return self.model.encode(
            texts,
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )


def predict_local(bundle, encoder, message, labels):
    inputs = encoder.encode([message]) if encoder is not None else [message]
    prediction = bundle["model"].predict(inputs)[0]
    if isinstance(prediction, bool) or not isinstance(prediction, Integral):
        raise ValueError("Artifact returned a non-index prediction")
    if not 0 <= prediction < len(labels):
        raise ValueError("Artifact returned an invalid label index")
    return labels[int(prediction)]


def environment():
    packages = {}
    for name in (
        "scikit-learn",
        "numpy",
        "scipy",
        "joblib",
        "xgboost",
        "torch",
        "sentence-transformers",
        "transformers",
        "huggingface-hub",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "threads": 4,
        "device": "cpu",
        "packages": packages,
    }


def git_head(root):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def read_state(path, binding, initial):
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state["binding"] != binding:
            raise ValueError("Run binding changed; output will not be overwritten")
        return state
    state = {"binding": binding, "environment": environment(), **initial}
    save_json(path, state)
    return state


def evaluate_offline(data, output, artifact_root, encoder_cache, binding):
    import joblib
    from threadpoolctl import threadpool_limits

    protocol, records = data["protocol"], data["records"]
    labels = protocol["labels"]
    path = output / "offline.json"
    state = read_state(path, binding, {"families": {}})
    with threadpool_limits(limits=4):
        for family in protocol["families"]:
            name = family["family"]
            result = state["families"].setdefault(name, {"attempts": {}, "startups": []})
            attempts = result["attempts"]
            for row in attempts.values():
                if row["status"] == "inflight":
                    row.update(
                        status="interrupted", prediction=FAILURE, failure_category="interrupted"
                    )
            if len(attempts) == len(records):
                save_json(path, state)
                continue
            started = time.perf_counter()
            startup = {"started_at": datetime.now(UTC).isoformat()}
            result["startups"].append(startup)
            save_json(path, state)
            try:
                bundle = joblib.load(resolve_under(artifact_root, family["artifact"]))
                if bundle["labels"] != labels:
                    raise ValueError("Artifact label order differs from frozen protocol")
                embedding = name.startswith("embedding_")
                if bool(bundle["encoder"]) != embedding:
                    raise ValueError("Artifact encoder differs from selected family")
                encoder = (
                    LocalFrozenEncoder(encoder_cache, bundle["encoder"]) if embedding else None
                )
                startup["load_ms"] = (time.perf_counter() - started) * 1000
                warm_start = time.perf_counter()
                predict_local(bundle, encoder, "Show me a pair of shoes", labels)
                startup["warmup_ms"] = (time.perf_counter() - warm_start) * 1000
                if encoder:
                    startup["encoder"] = encoder.metadata
            except Exception as error:
                startup.update(
                    failure_category=type(error).__name__,
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
                for record in records:
                    attempts.setdefault(
                        record["case_id"],
                        {
                            "status": "startup_failure",
                            "prediction": FAILURE,
                            "failure_category": "startup_failure",
                        },
                    )
                save_json(path, state)
                continue
            save_json(path, state)
            for record in records:
                case_id = record["case_id"]
                if case_id in attempts:
                    continue
                row = {"status": "inflight", "prediction": FAILURE}
                attempts[case_id] = row
                save_json(path, state)
                start = time.perf_counter()
                try:
                    row["prediction"] = predict_local(
                        bundle, encoder, record["input"]["message"], labels
                    )
                    row["failure_category"] = None
                except Exception as error:
                    row["failure_category"] = type(error).__name__
                row.update(status="complete", latency_ms=(time.perf_counter() - start) * 1000)
                save_json(path, state)
    return state


def percentile(values, percent):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * percent / 100
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def score(records, predictions, labels):
    by_id = {row["case_id"]: row for row in predictions}
    if len(by_id) != len(predictions) or set(by_id) - {r["case_id"] for r in records}:
        raise ValueError("Duplicate or unknown prediction case")
    matrix = [[0] * (len(labels) + 1) for _ in labels]
    latencies = []
    missing = []
    attempted = 0
    for record in records:
        row = by_id.get(record["case_id"], {})
        if not row:
            missing.append(record["case_id"])
        elif row.get("status") != "startup_failure":
            attempted += 1
        prediction = row.get("prediction")
        column = labels.index(prediction) if prediction in labels else len(labels)
        matrix[labels.index(record["expected"]["intent"])][column] += 1
        latency = row.get("latency_ms")
        if isinstance(latency, int | float) and math.isfinite(latency) and latency >= 0:
            latencies.append(latency)
    precision, recall, f1 = [], [], []
    for index in range(len(labels)):
        tp, actual, predicted = (
            matrix[index][index],
            sum(matrix[index]),
            sum(row[index] for row in matrix),
        )
        precision.append(tp / predicted if predicted else 0)
        recall.append(tp / actual if actual else 0)
        f1.append(2 * tp / (actual + predicted) if actual + predicted else 0)
    return {
        "status": "complete" if attempted == len(records) else "incomplete",
        "attempted_count": attempted,
        "unattempted_count": len(records) - attempted,
        "count": len(records),
        "accuracy": sum(matrix[i][i] for i in range(len(labels))) / len(records) if records else 0,
        "per_class": {
            label: {
                "precision": precision[i],
                "recall": recall[i],
                "f1": f1[i],
                "support": sum(matrix[i]),
            }
            for i, label in enumerate(labels)
        },
        "macro_precision": sum(precision) / len(labels),
        "macro_recall": sum(recall) / len(labels),
        "macro_f1": sum(f1) / len(labels),
        "failure_count": sum(row[-1] for row in matrix),
        "missing_attempts": missing,
        "confusion_matrix": matrix,
        "confusion_matrix_row_normalized": [
            [value / sum(row) if sum(row) else 0 for value in row] for row in matrix
        ],
        "truth_labels": labels,
        "prediction_labels": [*labels, FAILURE],
        "latency_ms": {
            "sample_count": len(latencies),
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
        },
    }


def report_results(data, output, binding, ledger_path):
    target = output / "report.json"
    if target.exists():
        raise ValueError("Report already exists; refusing to overwrite evidence")
    contenders = {}
    local = output / "offline.json"
    if local.exists():
        state = read_state(local, binding, {})
        for family, result in state["families"].items():
            contenders[family] = [
                {"case_id": key, **row} for key, row in result["attempts"].items()
            ]
    ledger = None
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger["binding"] != binding:
            raise ValueError("Paid ledger binding changed")
        contenders["llm"] = [
            {"case_id": key, "status": a["status"], **a.get("result", {"prediction": FAILURE})}
            for key, a in ledger["attempts"].items()
        ]
    expected = [f["family"] for f in data["protocol"]["families"]] + ["llm"]
    records, labels = data["records"], data["protocol"]["labels"]
    results = {}
    for name in expected:
        rows = contenders.get(name, [])
        results[name] = {
            **score(records, rows, labels),
            "per_language": {
                language: score(
                    [r for r in records if r["language_group"] == language],
                    [
                        r
                        for r in rows
                        if r["case_id"]
                        in {x["case_id"] for x in records if x["language_group"] == language}
                    ],
                    labels,
                )
                for language in data["protocol"]["languages"]
            },
        }
    result = {
        "kind": "synthetic_holdout",
        "binding": binding,
        "results": results,
        "paid_ledger": ledger,
        "limitations": [
            "Language-model-generated synthetic data; not independent human data",
            "No population generalisation or runtime safety claim",
            "Local cost unmeasured; unknown API cost retains full reservation",
        ],
    }
    attempts = ledger["attempts"] if ledger else {}
    known = sum(
        (
            Decimal(a["actual_cost_usd"])
            for a in attempts.values()
            if a["actual_cost_usd"] is not None
        ),
        Decimal(0),
    )
    held = sum(
        (Decimal(a["reservation_usd"]) for a in attempts.values() if a["actual_cost_usd"] is None),
        Decimal(0),
    )
    result["cost"] = {
        "known_actual_usd": str(known),
        "held_unknown_cost_usd": str(held),
        "spent_plus_reserved_usd": str(known + held),
        "cap_usd": str(CAP),
        "unknown_cost_count": sum(a["actual_cost_usd"] is None for a in attempts.values()),
        "attempt_count": len(attempts),
    }
    result["provenance"] = json.loads((output / "run.json").read_text(encoding="utf-8"))
    save_json(target, result)
    return result


def run(command, release, output, artifact_root, encoder_cache, root=None):
    from eval.holdout_release import load_frozen_release

    root = Path(root or Path(__file__).resolve().parents[1])
    data = load_frozen_release(Path(release), root)
    artifacts = verify_artifacts(data["protocol"], root, artifact_root)
    binding = {key: value for key, value in data.items() if key.endswith("_sha256")}
    binding.update(
        artifact_hashes=artifacts,
        source_hashes={name: digest(root / name) for name in SOURCE_FILES},
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = Path(artifact_root) / "outputs/holdout-20261009/llm-ledger.json"
    lock_path = (
        ledger_path.with_suffix(".lock") if command in {"llm", "report"} else output / ".lock"
    )
    with exclusive_lock(lock_path):
        run_path = output / "run.json"
        provenance = read_state(run_path, binding, {"invocations": []})
        provenance["invocations"].append(
            {
                "command": command,
                "git_head": git_head(root),
                "started_at": datetime.now(UTC).isoformat(),
                "binding": binding,
            }
        )
        save_json(run_path, provenance)
        if command == "offline":
            return evaluate_offline(data, output, artifact_root, encoder_cache, binding)
        if command == "report":
            return report_results(data, output, binding, ledger_path)
        from agent.llm.config import load_llm_settings
        from agent.llm.openrouter import OpenRouterClient

        settings = load_llm_settings(os.environ)
        if settings.provider != "openrouter" or settings.model != data["protocol"]["llm"]["model"]:
            raise ValueError("LLM provider/model differs from frozen protocol")
        if settings.stream or not 0 < settings.openrouter_total_limit <= 2:
            raise ValueError("LLM settings differ from frozen budget/protocol")
        ledger = BudgetLedger(ledger_path, binding)
        client = OpenRouterClient(settings)
        try:
            asyncio.run(evaluate_llm(data["records"], data["protocol"], client, ledger))
        finally:
            save_json(output / "llm.json", ledger.data)
        return ledger.data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("offline", "llm", "report"))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, default=Path("D:/agent depi"))
    parser.add_argument(
        "--encoder-cache", type=Path, default=Path("D:/agent depi/outputs/model-cache")
    )
    args = parser.parse_args()
    run(args.command, args.release, args.output, args.artifact_root, args.encoder_cache)
    print(json.dumps({"command": args.command, "evidence": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
