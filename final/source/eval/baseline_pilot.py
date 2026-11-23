"""Reproducible offline TF-IDF pilot. No provider calls or runtime integration."""

import argparse
import hashlib
import importlib.metadata
import itertools
import json
import platform
import subprocess
import time
import warnings
from collections import Counter
from pathlib import Path

import joblib
import matplotlib
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline

from eval.pilot_data import digest, load_release

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def candidate_configs() -> list[dict]:
    return [
        {"features": features, "C": c, "class_weight": weight}
        for features, c, weight in itertools.product(
            ("word", "char_wb"), (0.1, 1.0, 10.0), (None, "balanced")
        )
    ]


def fit_candidate(rows: list[dict], config: dict) -> tuple[Pipeline, dict]:
    tfidf = TfidfVectorizer(
        analyzer=config["features"],
        ngram_range=(1, 2) if config["features"] == "word" else (3, 5),
        token_pattern=r"(?u)\b\w+\b" if config["features"] == "word" else None,
        stop_words=None,
    )
    model = Pipeline(
        [
            ("tfidf", tfidf),
            (
                "classifier",
                LogisticRegression(
                    C=config["C"],
                    class_weight=config["class_weight"],
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=42,
                ),
            ),
        ]
    )
    start = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model.fit([r["text"] for r in rows], [r["label"] for r in rows])
    return model, {
        "training_seconds": time.perf_counter() - start,
        "converged": not any(issubclass(w.category, ConvergenceWarning) for w in captured),
        "warnings": [str(w.message) for w in captured],
    }


def select_best(trials: list[dict]) -> dict:
    usable = [t for t in trials if t["converged"]]
    if not usable:
        raise ValueError("No converged candidate")
    return min(
        usable,
        key=lambda t: (
            -t["macro_f1"],
            -t["accuracy"],
            t["config"]["features"] != "word",
            t["config"]["C"],
            t["config"]["class_weight"] is not None,
        ),
    )


def metrics(truth: list[str], predicted: list[str], labels: list[str]) -> dict:
    return {
        "count": len(truth),
        "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1": float(
            f1_score(truth, predicted, labels=labels, average="macro", zero_division=0)
        ),
        "classification": classification_report(
            truth,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
    }


def run(release_path: Path, output: Path, root: Path) -> dict:
    data = load_release(release_path, root)
    if output.exists():
        raise ValueError("Use a new output directory to preserve previous experiment evidence")
    output.mkdir(parents=True)
    labels = data["labels"]
    train = [r for r in data["records"] if r["split"] == "train"]
    valid = [r for r in data["records"] if r["split"] == "validation"]
    truth = [r["label"] for r in valid]
    models, trials = [], []
    for config in candidate_configs():
        model, fitting = fit_candidate(train, config)
        predicted = model.predict([r["text"] for r in valid]).tolist()
        trial = {
            "config": config,
            **fitting,
            **metrics(truth, predicted, labels),
            "predictions": predicted,
        }
        models.append(model)
        trials.append(trial)
    selected = select_best(trials)
    model = models[trials.index(selected)]
    predicted = selected["predictions"]
    majority = Counter(r["label"] for r in train).most_common(1)[0][0]
    latencies = []
    model.predict([valid[0]["text"]])
    for row in valid:
        start = time.perf_counter()
        model.predict([row["text"]])
        latencies.append((time.perf_counter() - start) * 1000)
    predictions = [
        {**row, "predicted": pred, "correct": row["label"] == pred, "warm_latency_ms": latency}
        for row, pred, latency in zip(valid, predicted, latencies, strict=True)
    ]
    joblib.dump(model, output / "model.joblib")
    start = time.perf_counter()
    reloaded = joblib.load(output / "model.joblib")  # Only our just-created trusted artifact.
    load_ms = (time.perf_counter() - start) * 1000
    if reloaded.predict([r["text"] for r in valid]).tolist() != predicted:
        raise ValueError("Reloaded artifact changed predictions")
    matrices = {}
    for normalize in (None, "true"):
        matrix = confusion_matrix(truth, predicted, labels=labels, normalize=normalize)
        key = "raw" if normalize is None else "row_normalized"
        matrices[key] = matrix.tolist()
        fig, ax = plt.subplots(figsize=(11, 9))
        im = ax.imshow(matrix, cmap="Blues", vmin=0)
        ax.set(
            xticks=range(len(labels)),
            yticks=range(len(labels)),
            xticklabels=labels,
            yticklabels=labels,
            xlabel="Predicted intent",
            ylabel="Annotated intent",
            title=f"Synthetic development validation - {key.replace('_', ' ')}",
        )
        plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
        for i, j in itertools.product(range(len(labels)), repeat=2):
            value = f"{matrix[i, j]:.2f}" if normalize else str(matrix[i, j])
            ax.text(
                j,
                i,
                value,
                ha="center",
                va="center",
                fontsize=8,
                color="white" if matrix[i, j] > matrix.max() / 2 else "black",
            )
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(output / f"confusion-{key}.png", dpi=150)
        plt.close(fig)
    report = {
        "kind": "exploratory_synthetic_development_only",
        "unseen_count": 0,
        "llm_comparison": "not_run",
        "inference_api_calls": 0,
        "release_sha256": data["_loaded_sha256"],
        "invocation": {
            "cwd": ".",
            "argv": [
                "python",
                "-m",
                "eval.baseline_pilot",
                "--release",
                release_path.resolve().relative_to(root.resolve()).as_posix(),
                "--output",
                output.resolve().relative_to(root.resolve()).as_posix(),
            ],
            "rerun_note": "Choose a fresh output directory; existing evidence is preserved.",
        },
        "labels": labels,
        "counts": {
            s: dict(Counter(r["label"] for r in data["records"] if r["split"] == s))
            for s in ("train", "validation")
        },
        "trials": trials,
        "selected_config": selected["config"],
        "validation": metrics(truth, predicted, labels),
        "majority_baseline": {"label": majority, **metrics(truth, [majority] * len(valid), labels)},
        "per_language": {
            lang: metrics(
                [r["label"] for r in predictions if r["language"] == lang],
                [r["predicted"] for r in predictions if r["language"] == lang],
                labels,
            )
            for lang in sorted({r["language"] for r in predictions})
        },
        "confusion_matrices": matrices,
        "predictions": predictions,
        "warm_single_message_latency_ms": {
            "sample_count": len(latencies),
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
        },
        "artifact_load_ms_warm_os_cache": load_ms,
        "model_sha256": hashlib.sha256((output / "model.joblib").read_bytes()).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "packages": {
                n: importlib.metadata.version(n)
                for n in ("scikit-learn", "numpy", "scipy", "joblib", "matplotlib")
            },
        },
        "source_hashes": {
            n: digest(root / n)
            for n in (
                "eval/baseline_pilot.py",
                "eval/pilot_data.py",
                "docs/cap03-pilot-protocol.md",
            )
        },
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "limitations": [
            "Synthetic exposed data; draft annotations, not independent human gold",
            "Validation selected the model; not an unbiased test score",
            "Rare and absent classes; no same-input LLM comparison",
            "No conversation, Constraint extraction or browser safety claim",
            "No inference API fee; local compute cost is unmeasured",
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.release, args.output, Path(__file__).resolve().parents[1])
    print(
        json.dumps(
            {
                "selected": result["selected_config"],
                "validation": {
                    k: result["validation"][k] for k in ("count", "accuracy", "macro_f1")
                },
                "unseen_count": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
