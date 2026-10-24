"""Encode and cache MiniLM embeddings for every split.

Run from the CMSC473 directory:

    python scripts/test_embedding.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.schema import SPLITS
from src.models.encoder import TextEncoder, split_embeddings


def main() -> None:
    encoder = TextEncoder()
    print(f"{encoder.model_name} on {encoder.device}, {encoder.dim} dimensions")
    for split in sorted(SPLITS):
        embeddings = split_embeddings(split, encoder)
        print(f"{split}: {len(embeddings)} prompts, shape {tuple(embeddings.vectors.shape)}")


if __name__ == "__main__":
    main()
