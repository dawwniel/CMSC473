"""A prompt-to-texture head trained separately from emitter properties."""

from __future__ import annotations

import torch
from torch import nn


class TextureHead(nn.Module):
    def __init__(self, classes: list[str], embedding_dim: int = 384,
                 kind: str = "linear", dropout: float = 0.0):
        super().__init__()
        self.classes = list(classes)
        self.kind = kind
        self.dropout = dropout
        if kind == "linear":
            self.network = nn.Sequential(nn.Dropout(dropout), nn.Linear(embedding_dim, len(classes)))
        elif kind == "mlp":
            self.network = nn.Sequential(
                nn.Linear(embedding_dim, 128), nn.ReLU(), nn.Dropout(dropout),
                nn.Linear(128, len(classes)),
            )
        else:
            raise ValueError(f"unknown texture head: {kind}")

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        return self.network(embeddings)


def load_texture_head(saved: dict) -> TextureHead:
    model = TextureHead(saved["classes"], saved["embedding_dim"],
                        saved["kind"], saved["dropout"])
    model.load_state_dict(saved["model"])
    model.eval()
    return model
