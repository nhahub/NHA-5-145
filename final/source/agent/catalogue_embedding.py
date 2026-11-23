"""Optional local CPU encoder. Lexical mode never imports these dependencies."""

from pathlib import Path

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


class CatalogueEncoder:
    def __init__(self, cache: Path):
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer

        snapshot = snapshot_download(
            MODEL,
            revision=REVISION,
            cache_dir=str(cache),
            local_files_only=True,
            token=False,
            allow_patterns=["*.json", "*.txt", "model.safetensors", "1_Pooling/*"],
        )
        self.model = SentenceTransformer(
            snapshot,
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        ).tolist()

    def query(self, text: str) -> dict:
        return {"model": MODEL, "model_revision": REVISION, "vector": self.encode([text])[0]}
