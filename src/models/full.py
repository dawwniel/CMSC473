"""Predict every variable field in the particle target layout."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

from ..data.normalize import Normalizer
from ..data.schema import validate_emitter


CURVE_PREFIXES = ("Size.", "Squash.", "Transparency.", "Color.")


class ParticleFull(nn.Module):
    def __init__(self, normalizer: Normalizer, embedding_dim: int = 384, hidden_dim: int = 256):
        super().__init__()
        self.scalar_indices = [
            i for i, name in enumerate(normalizer.continuous)
            if not name.startswith(CURVE_PREFIXES)
        ]
        self.curve_indices = [
            i for i, name in enumerate(normalizer.continuous)
            if name.startswith(CURVE_PREFIXES)
        ]
        self.category_names = normalizer.categories
        self.flag_names = list(normalizer.flags)
        self.continuous_dim = len(normalizer.continuous)
        self.backbone = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
        )
        self.scalars = nn.Linear(hidden_dim // 2, len(self.scalar_indices))
        self.curves = nn.Linear(hidden_dim // 2, len(self.curve_indices))
        self.categories = nn.ModuleDict({
            name: nn.Linear(hidden_dim // 2, len(normalizer.classes[name]))
            for name in self.category_names
        })
        self.flags = nn.Linear(hidden_dim // 2, len(self.flag_names))

    def _heads(self, hidden: torch.Tensor) -> dict[str, Any]:
        continuous = hidden.new_zeros((len(hidden), self.continuous_dim))
        continuous = continuous.index_copy(1, torch.tensor(self.scalar_indices, device=hidden.device), self.scalars(hidden))
        continuous = continuous.index_copy(1, torch.tensor(self.curve_indices, device=hidden.device), self.curves(hidden))
        return {
            "continuous": continuous,
            "categories": {name: head(hidden) for name, head in self.categories.items()},
            "flags": self.flags(hidden),
        }

    def forward(self, embedding: torch.Tensor) -> dict[str, Any]:
        return self._heads(self.backbone(embedding))


def full_loss(
    output: dict[str, Any], batch: dict[str, torch.Tensor],
    model: ParticleFull,
) -> dict[str, torch.Tensor]:
    error = F.smooth_l1_loss(output["continuous"], batch["continuous"], reduction="none")
    mask = batch["continuous_mask"]

    def masked_group(indices: list[int]) -> torch.Tensor:
        selected = mask[:, indices]
        return (error[:, indices] * selected).sum() / selected.sum().clamp_min(1)

    scalars = masked_group(model.scalar_indices)
    curves = masked_group(model.curve_indices)
    category_errors = []
    for i, name in enumerate(model.category_names):
        logits = output["categories"][name]
        category_errors.append(F.cross_entropy(logits, batch["categories"][:, i]) / torch.log(torch.tensor(logits.shape[1], device=logits.device)))
    categories = torch.stack(category_errors).mean()
    flags = F.binary_cross_entropy_with_logits(output["flags"], batch["flags"])
    return {
        "total": scalars + curves + categories + flags,
        "scalars": scalars,
        "curves": curves,
        "categories": categories,
        "flags": flags,
    }


def decode_full(normalizer: Normalizer, output: dict[str, Any], index: int = 0) -> dict[str, Any]:
    continuous = output["continuous"][index].detach().cpu().numpy().clip(-8, 8)
    categories = [
        output["categories"][name][index].argmax().item()
        for name in normalizer.categories
    ]
    flags = torch.sigmoid(output["flags"][index]).detach().cpu().numpy()
    emitter = normalizer.inverse_transform(continuous, categories, flags)
    validate_emitter(emitter)
    return emitter
