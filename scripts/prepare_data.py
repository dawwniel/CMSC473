"""Fit the normalizer on train, save it, and cache MiniLM embeddings for every split.

Run from the CMSC473 directory:

    python scripts/prepare_data.py

Validation, test, and generalization_test are only transformed with the saved
train statistics; nothing is fitted on them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import NORMALIZER_PATH, Normalizer, fit_train
from src.data.tensor_dataset import ParticleTensorDataset
from src.models.encoder import TextEncoder, split_embeddings


SPLIT_ORDER = ("train", "validation", "test", "generalization_test")
# Normalized values past this are reported; they are kept as they are.
OUTLIER_Z = 5.0


def summarize(split: str, normalizer: Normalizer, embeddings) -> None:
    records = load_split(split)
    encoded = [normalizer.transform(record) for record in records]
    values = np.stack([e["continuous"] for e in encoded])
    mask = np.stack([e["continuous_mask"] for e in encoded]).astype(bool)
    categories = np.stack([e["categories"] for e in encoded])
    unknown = {
        name: int(count)
        for name, count in zip(normalizer.categories, (categories == 0).sum(axis=0))
        if count
    }
    outliers = int((np.abs(values[mask]) > OUTLIER_Z).sum())
    items = len(ParticleTensorDataset(split, normalizer, embeddings))
    print(
        f"{split}: {len(records)} rows, {items} items, "
        f"embeddings {tuple(embeddings.vectors.shape)}, continuous {values.shape}, "
        f"|z|>{OUTLIER_Z:g}: {outliers}, unknown categories: {unknown or 'none'}"
    )


def main() -> None:
    normalizer = fit_train()
    normalizer.save()
    loaded = Normalizer.load()
    print(
        f"normalizer saved to {NORMALIZER_PATH}: {len(loaded.continuous)} continuous, "
        f"{len(loaded.categories)} categories, {len(loaded.flags)} flags"
    )

    encoder = TextEncoder()
    print(f"{encoder.model_name} on {encoder.device}, {encoder.dim} dimensions")
    for split in SPLIT_ORDER:
        summarize(split, loaded, split_embeddings(split, encoder))


if __name__ == "__main__":
    main()
