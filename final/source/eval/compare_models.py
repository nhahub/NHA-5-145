"""Seven-family offline development comparison; never imported by the runtime."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import time
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import confusion_matrix
from threadpoolctl import threadpool_limits

from eval.baseline_pilot import metrics
from eval.comparison_models import configurations, fit, select
from eval.pilot_data import digest, load_release

PROTOCOL = "docs/cap03-model-comparison-protocol.md"


def save_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def evaluate_family(train, valid, labels, configs, output, encoder=None, features=None) -> dict:
    family = configs[0]["family"]
    train_text, valid_text = [r["text"] for r in train], [r["text"] for r in valid]
    xtrain, xvalid = features if features is not None else (train_text, valid_text)
    targets = [labels.index(r["label"]) for r in train]
    truth = [r["label"] for r in valid]
    trials, models = [], {}
    trial_path = output / f"{family}-trials.json"
    for config in configs:
        trial = {"config": config}
        try:
            model, fitting = fit(xtrain, targets, config)
            predicted = [labels[int(i)] for i in model.predict(xvalid)]
            trial.update(**fitting, **metrics(truth, predicted, labels), predictions=predicted)
            models[config["index"]] = model
        except Exception as error:
            trial.update(error=f"{type(error).__name__}: {error}", converged=False)
        trials.append(trial)
        save_json(trial_path, {"status": "running", "trials": trials})
    chosen = select(trials)
    if chosen is None:
        result = {"family": family, "status": "unavailable", "trials": trials}
        save_json(trial_path, result)
        return result
    model = models[chosen["config"]["index"]]
    predicted = chosen["predictions"]
    artifact = output / f"{family}.joblib"
    joblib.dump(
        {"model": model, "labels": labels, "encoder": encoder.metadata if encoder else None},
        artifact,
    )
    start = time.perf_counter()
    loaded = joblib.load(artifact)  # Only the artifact just created by this process.
    reload_ms = (time.perf_counter() - start) * 1000
    if [loaded["labels"][int(i)] for i in loaded["model"].predict(xvalid)] != predicted:
        raise ValueError("Reloaded artifact changed predictions")

    def predict_text(text):
        inputs = encoder.encode([text]) if encoder else [text]
        return labels[int(model.predict(inputs)[0])]

    predict_text(valid_text[0])
    latencies = []
    for text, expected in zip(valid_text, predicted, strict=True):
        start = time.perf_counter()
        actual = predict_text(text)
        latencies.append((time.perf_counter() - start) * 1000)
        if actual != expected:
            raise ValueError("Single-message inference differs from batch prediction")
    rows = [
        {**r, "predicted": p, "correct": r["label"] == p, "warm_latency_ms": ms}
        for r, p, ms in zip(valid, predicted, latencies, strict=True)
    ]
    result = {
        "family": family,
        "status": "complete",
        "trials": trials,
        "selected_config": chosen["config"],
        "validation": metrics(truth, predicted, labels),
        "predictions": rows,
        "per_language": {
            lang: metrics(
                [r["label"] for r in rows if r["language"] == lang],
                [r["predicted"] for r in rows if r["language"] == lang],
                labels,
            )
            for lang in sorted({r["language"] for r in rows})
        },
        "confusion_matrices": {
            name: confusion_matrix(truth, predicted, labels=labels, normalize=norm).tolist()
            for name, norm in (("raw", None), ("row_normalized", "true"))
        },
        "latency_ms": {
            "sample_count": len(latencies),
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
            "includes_encoder": encoder is not None,
        },
        "artifact_reload_ms_warm_os_cache": reload_ms,
        "artifact_reload_verified": True,
        "artifact_bytes": artifact.stat().st_size,
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "shared_encoder_bytes": encoder.metadata["bytes"] if encoder else 0,
    }
    save_json(trial_path, result)
    return result


def run(release_path: Path, output: Path, root: Path, phase="all") -> dict:
    data = load_release(release_path, root)
    output.mkdir(parents=True, exist_ok=False)
    configs = [
        c
        for c in configurations()
        if phase == "all" or c["family"].startswith("embedding") == (phase == "embeddings")
    ]
    train = [r for r in data["records"] if r["split"] == "train"]
    valid = [r for r in data["records"] if r["split"] == "validation"]
    report = {
        "status": "running",
        "kind": "exploratory_synthetic_development_only",
        "unseen_count": 0,
        "inference_api_calls": 0,
        "llm_comparison": "not_run",
        "release_sha256": data["_loaded_sha256"],
        "phase": phase,
        "labels": data["labels"],
        "configs": configs,
        "families": [],
        "counts": {
            s: dict(Counter(r["label"] for r in data["records"] if r["split"] == s))
            for s in ("train", "validation")
        },
        "source_hashes": {
            n: digest(root / n)
            for n in (
                PROTOCOL,
                "eval/compare_models.py",
                "eval/comparison_models.py",
                "eval/comparison_encoder.py",
                "eval/pilot_data.py",
                "eval/baseline_pilot.py",
            )
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "threads": 4,
            "packages": {
                p: importlib.metadata.version(p)
                for p in (
                    "scikit-learn",
                    "numpy",
                    "scipy",
                    "joblib",
                    "xgboost",
                    "torch",
                    "sentence-transformers",
                    "transformers",
                    "huggingface-hub",
                )
            },
        },
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "invocation": {
            "release": release_path.resolve().relative_to(root).as_posix(),
            "output": output.resolve().relative_to(root).as_posix(),
            "phase": phase,
        },
        "limitations": [
            "Previously inspected synthetic validation; not independent gold or unseen",
            "Unequal small tuning budgets and different pretrained representations",
            "No seed-variance or runtime safety claim; local compute cost unmeasured",
        ],
    }
    report_path = output / "report.json"
    save_json(report_path, report)
    encoder, features = None, None
    try:
        with threadpool_limits(limits=4):
            for family in dict.fromkeys(c["family"] for c in configs):
                embedding = family.startswith("embedding")
                if embedding and encoder is None:
                    from eval.comparison_encoder import FrozenEncoder

                    encoder = FrozenEncoder(root / "outputs/model-cache")
                    start = time.perf_counter()
                    features = tuple(
                        encoder.encode([r["text"] for r in rows]) for rows in (train, valid)
                    )
                    report["embedding_preparation_seconds"] = time.perf_counter() - start
                    report["encoder"] = encoder.metadata
                    feature_path = output / "embeddings.npz"
                    np.savez_compressed(feature_path, train=features[0], validation=features[1])
                    report["embedding_artifact"] = {
                        "file": feature_path.name,
                        "sha256": hashlib.sha256(feature_path.read_bytes()).hexdigest(),
                        "release_sha256": data["_loaded_sha256"],
                        "encoder_revision": encoder.metadata["revision"],
                        "case_ids": {
                            s: [r["case_id"] for r in rows]
                            for s, rows in (("train", train), ("validation", valid))
                        },
                        "shapes": {
                            s: list(x.shape)
                            for s, x in zip(("train", "validation"), features, strict=True)
                        },
                    }
                    report["truncated"] = {
                        s: encoder.truncation_count([r["text"] for r in rows])
                        for s, rows in (("train", train), ("validation", valid))
                    }
                    save_json(report_path, report)
                result = evaluate_family(
                    train,
                    valid,
                    data["labels"],
                    [c for c in configs if c["family"] == family],
                    output,
                    encoder if embedding else None,
                    features if embedding else None,
                )
                report["families"].append(result)
                save_json(report_path, report)
                print(
                    json.dumps(
                        {
                            "family": family,
                            "status": result["status"],
                            "macro_f1": result.get("validation", {}).get("macro_f1"),
                        }
                    ),
                    flush=True,
                )
        report["status"] = (
            "complete"
            if all(f["status"] == "complete" for f in report["families"])
            else "completed_with_failures"
        )
    except Exception as error:
        report.update(status="incomplete", error=f"{type(error).__name__}: {error}")
        save_json(report_path, report)
        raise
    save_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "classical", "embeddings"), default="all")
    args = parser.parse_args()
    run(args.release, args.output, Path(__file__).resolve().parents[1], args.phase)


if __name__ == "__main__":
    main()
