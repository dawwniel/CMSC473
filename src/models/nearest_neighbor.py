"""Nearest-neighbor baseline: copy the emitter of the most similar training prompt."""

from __future__ import annotations

from typing import Any

import torch

from ..data.tensor_dataset import record_prompts


def build_bank(
    records: list[dict[str, Any]], embeddings: Any, alternates: bool = True
) -> tuple[torch.Tensor, list[tuple[int, int]]]:
    """Stack the prompt vectors of `records` and remember (record index, prompt index) for each row."""
    owners, vectors = [], []
    for record_index, record in enumerate(records):
        count = len(record_prompts(record)) if alternates else 1
        for prompt_index in range(count):
            owners.append((record_index, prompt_index))
            vectors.append(embeddings[record["row_hash"], prompt_index])
    return torch.stack(vectors), owners


def nearest(queries: torch.Tensor, bank: torch.Tensor, tolerance: float = 1e-3) -> tuple[torch.Tensor, torch.Tensor]:
    """Bank row with the highest cosine similarity for each query, and that similarity.

    Inputs must be unit length, so the dot product is the cosine. Ties go to the lowest row.
    """
    for name, vectors in (("queries", queries), ("bank", bank)):
        norms = vectors.norm(dim=1)
        if not torch.allclose(norms, torch.ones_like(norms), atol=tolerance):
            raise ValueError(f"{name} are not unit length; cosine would not equal the dot product")
    similarities, indices = (queries @ bank.T).max(dim=1)
    return indices, similarities
