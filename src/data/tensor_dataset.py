"""Pair cached prompt embeddings with normalized targets for training."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset

from .dataset import DATA_DIR, load_split
from .normalize import Normalizer


def record_prompts(record: dict[str, Any]) -> list[str]:
    """The main prompt, then its alternates. Index 0 is always the main prompt."""
    alternates = record["attachment"].get("attributes", {}).get("PromptAlternates")
    extra = alternates["value"] if alternates else []
    return [record["prompt"]] + [text for text in extra if isinstance(text, str) and text.strip()]


class ParticleTensorDataset(Dataset):
    """One item per (record, prompt).

    Train uses every prompt by default. Other splits use only the main prompt,
    so each effect is scored once.
    """

    def __init__(
        self,
        split: str,
        normalizer: Normalizer,
        embeddings: Any,
        alternates: bool | None = None,
        data_dir: str | Path = DATA_DIR,
    ):
        self.split = split
        self.records = load_split(split, data_dir)
        alternates = split == "train" if alternates is None else alternates
        self.targets = [
            {name: torch.from_numpy(value) for name, value in normalizer.transform(record).items()}
            for record in self.records
        ]
        self.items = []
        for index, record in enumerate(self.records):
            count = len(record_prompts(record)) if alternates else 1
            for prompt_index in range(count):
                self.items.append((index, embeddings[record["row_hash"], prompt_index]))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        record_index, embedding = self.items[index]
        return {"embedding": embedding, **self.targets[record_index]}
