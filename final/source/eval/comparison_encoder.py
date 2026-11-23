"""Pinned public encoder, downloaded once and executed entirely on local hardware."""

import hashlib
import time
from pathlib import Path

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class FrozenEncoder:
    def __init__(self, cache: Path):
        import torch
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(4)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        start = time.perf_counter()
        snapshot = Path(
            snapshot_download(
                MODEL,
                revision=REVISION,
                cache_dir=str(cache),
                token=False,
                allow_patterns=["*.json", "*.txt", "model.safetensors", "1_Pooling/*"],
            )
        )
        download_seconds = time.perf_counter() - start
        start = time.perf_counter()
        self.model = SentenceTransformer(
            str(snapshot),
            device=self.device,
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        self.metadata = {
            "model": MODEL,
            "revision": REVISION,
            "device": self.device,
            "cuda_build": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0) if self.device == "cuda" else None,
            "download_or_cache_seconds": download_seconds,
            "initialization_seconds": time.perf_counter() - start,
            "dimensions": self.model.get_sentence_embedding_dimension(),
            "max_seq_length": self.model.max_seq_length,
            "normalize_embeddings": True,
            "files": {
                p.relative_to(snapshot).as_posix(): {
                    "sha256": file_hash(p),
                    "bytes": p.stat().st_size,
                }
                for p in sorted(snapshot.rglob("*"))
                if p.is_file()
            },
        }
        self.metadata["bytes"] = sum(f["bytes"] for f in self.metadata["files"].values())

    def encode(self, texts: list[str]):
        import torch

        result = self.model.encode(
            texts,
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if self.device == "cuda":
            torch.cuda.synchronize()
        return result

    def truncation_count(self, texts: list[str]) -> int:
        tokens = self.model.tokenizer(texts, truncation=False, padding=False)["input_ids"]
        return sum(len(ids) > self.model.max_seq_length for ids in tokens)
