"""Explicit local-only recovery of encoder startup failures; never rerun predictions."""

import argparse
import json
import os
import time
from pathlib import Path

from eval.holdout_eval import digest, predict_local, save_json, verify_artifacts
from eval.holdout_release import load_frozen_release


def recoverable(family):
    attempts = family["attempts"]
    return bool(attempts) and all(
        row.get("status") == "startup_failure" for row in attempts.values()
    )


class CachedEncoder:
    def __init__(self, cache, expected):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer

        from eval.comparison_encoder import MODEL, REVISION

        if expected["model"] != MODEL or expected["revision"] != REVISION:
            raise ValueError("Encoder identity changed")
        torch.set_num_threads(4)
        # Original training downloaded this precise subset, not ONNX/OpenVINO alternatives.
        snapshot = Path(
            snapshot_download(
                MODEL,
                revision=REVISION,
                cache_dir=str(cache),
                token=False,
                local_files_only=True,
                allow_patterns=list(expected["files"]),
            )
        )
        for name, metadata in expected["files"].items():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Unsafe encoder manifest path")
            if digest(snapshot / name) != metadata["sha256"]:
                raise ValueError("Encoder bytes changed")
        self.model = SentenceTransformer(
            str(snapshot),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        self.metadata = {**expected, "device": "cpu", "threads": 4}

    def encode(self, texts):
        return self.model.encode(
            texts,
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )


def recover(release, initial, output, artifact_root, cache):
    import joblib
    from threadpoolctl import threadpool_limits

    root = Path(__file__).resolve().parents[1]
    data = load_frozen_release(release, root)
    verify_artifacts(data["protocol"], root, artifact_root)
    state = json.loads(initial.read_text(encoding="utf-8"))
    binding = state["binding"]
    for key in ("release_sha256", "protocol_sha256", "records_sha256", "review_sha256"):
        if binding[key] != data[key]:
            raise ValueError("Release identity changed")
    for path, expected in binding["source_hashes"].items():
        if digest(root / path) != expected:
            raise ValueError("Original evaluation source changed")
    if output.exists():
        raise ValueError("Recovery already exists; no replay")
    output.mkdir(parents=True)
    recovery = {
        "reason": "offline snapshot required unused alternative export files",
        "initial_sha256": digest(initial),
        "source_sha256": digest(Path(__file__)),
        "families": {},
    }
    save_json(output / "recovery.json", recovery)
    with threadpool_limits(limits=4):
        for family in data["protocol"]["families"]:
            name = family["family"]
            original = state["families"][name]
            if not recoverable(original):
                continue
            if not name.startswith("embedding_"):
                raise ValueError("Unexpected startup recovery family")
            start = time.perf_counter()
            bundle = joblib.load(artifact_root / family["artifact"])
            if bundle["labels"] != data["protocol"]["labels"]:
                raise ValueError("Label order changed")
            encoder = CachedEncoder(cache, bundle["encoder"])
            result = {
                "attempts": {},
                "startups": [
                    {"load_ms": (time.perf_counter() - start) * 1000, "encoder": encoder.metadata}
                ],
                "recovered_from": "startup failure before any predictions",
            }
            predict_local(bundle, encoder, "Show me a pair of shoes", bundle["labels"])
            recovery["families"][name] = result
            for row in data["records"]:
                cid = row["case_id"]
                attempt = {"status": "inflight", "prediction": "__failure__"}
                result["attempts"][cid] = attempt
                save_json(output / "recovery.json", recovery)
                start = time.perf_counter()
                try:
                    attempt["prediction"] = predict_local(
                        bundle, encoder, row["input"]["message"], bundle["labels"]
                    )
                    attempt["failure_category"] = None
                except Exception as error:
                    attempt["failure_category"] = type(error).__name__
                attempt.update(status="complete", latency_ms=(time.perf_counter() - start) * 1000)
                save_json(output / "recovery.json", recovery)
            state["families"][name] = result
    state["recovery"] = {
        "source_sha256": recovery["source_sha256"],
        "initial_sha256": recovery["initial_sha256"],
        "note": (
            "Five original family results retained verbatim; "
            "two encoder families first predicted after cache-only startup repair."
        ),
    }
    save_json(output / "offline.json", state)
    return state


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--initial", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--artifact-root", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    args = p.parse_args()
    recover(args.release, args.initial, args.output, args.artifact_root, args.cache)
    print("Offline startup recovery complete; original evidence preserved.")
