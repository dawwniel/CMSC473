"""Frozen MiniLM prompt encoder and a per-split embedding cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import torch

from ..data.dataset import DATA_DIR, load_split
from ..data.tensor_dataset import record_prompts


ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIR = ROOT / "data/processed/embeddings"


class TextEncoder:
    """Unit-length sentence embeddings. The weights are never trained."""

    def __init__(self, model_name: str = MODEL_NAME, device: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.model.eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

    @property
    def dim(self) -> int:
        return self.model.get_embedding_dimension()

    def encode(self, texts: Sequence[str], batch_size: int = 64) -> torch.Tensor:
        with torch.no_grad():
            vectors = self.model.encode(
                list(texts),
                batch_size=batch_size,
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return vectors.float().cpu()


class PromptEmbeddings:
    """Embeddings for one split, looked up by (row_hash, prompt index)."""

    def __init__(self, model_name: str, keys: list[tuple[str, int]], vectors: torch.Tensor):
        if len(keys) != len(vectors):
            raise ValueError("keys and vectors differ in length")
        self.model_name = model_name
        self.keys = keys
        self.vectors = vectors
        self.index = {key: i for i, key in enumerate(keys)}

    def __getitem__(self, key: tuple[str, int]) -> torch.Tensor:
        return self.vectors[self.index[key]]

    def __len__(self) -> int:
        return len(self.keys)


def _split_prompts(records: list[dict[str, Any]]) -> tuple[list[tuple[str, int]], list[str]]:
    keys, texts = [], []
    for record in records:
        for i, text in enumerate(record_prompts(record)):
            keys.append((record["row_hash"], i))
            texts.append(text)
    return keys, texts


def split_embeddings(
    split: str,
    encoder: TextEncoder | None = None,
    cache_dir: str | Path = EMBEDDING_DIR,
    data_dir: str | Path = DATA_DIR,
    model_name: str = MODEL_NAME,
) -> PromptEmbeddings:
    """Load a split's embeddings from cache, or encode every prompt and save them.

    The cache is rebuilt when the model name or the split's prompts change.
    """
    keys, texts = _split_prompts(load_split(split, data_dir))
    path = Path(cache_dir) / f"{split}.pt"
    if path.exists():
        saved = torch.load(path, weights_only=True)
        saved_keys = [(row_hash, int(i)) for row_hash, i in saved["keys"]]
        if saved["model"] == model_name and saved_keys == keys:
            return PromptEmbeddings(model_name, keys, saved["vectors"])
    encoder = encoder or TextEncoder(model_name)
    if encoder.model_name != model_name:
        raise ValueError(f"encoder uses {encoder.model_name}, expected {model_name}")
    vectors = encoder.encode(texts)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model_name, "keys": keys, "vectors": vectors}, path)
    return PromptEmbeddings(model_name, keys, vectors)
