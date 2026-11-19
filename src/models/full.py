"""Predict every variable field in the particle target layout."""

from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.nn import functional as F

from ..data.light import is_light_prompt
from ..data.normalize import Normalizer
from ..data.schema import validate_emitter
from .levels import level_loss, pick_level


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
        self.level_names = list(normalizer.levels)
        self.levels = nn.ModuleDict({
            name: nn.Linear(hidden_dim // 2, len(values))
            for name, values in normalizer.levels.items()
        })

    def _heads(self, hidden: torch.Tensor) -> dict[str, Any]:
        continuous = hidden.new_zeros((len(hidden), self.continuous_dim))
        continuous = continuous.index_copy(1, torch.tensor(self.scalar_indices, device=hidden.device), self.scalars(hidden))
        continuous = continuous.index_copy(1, torch.tensor(self.curve_indices, device=hidden.device), self.curves(hidden))
        return {
            "continuous": continuous,
            "categories": {name: head(hidden) for name, head in self.categories.items()},
            "flags": self.flags(hidden),
            "levels": {name: head(hidden) for name, head in self.levels.items()},
        }

    def forward(self, embedding: torch.Tensor) -> dict[str, Any]:
        return self._heads(self.backbone(embedding))


def full_loss(
    output: dict[str, Any], batch: dict[str, torch.Tensor],
    model: ParticleFull,
    class_weights: dict[str, torch.Tensor] | None = None, light_weight: float = 1.0,
) -> dict[str, torch.Tensor]:
    """Loss terms. `levels` is scaled by 1/log(number of levels), like categories."""
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
    levels = level_loss(output, batch, class_weights, light_weight, normalize=True)
    return {
        "total": scalars + curves + categories + flags + levels,
        "scalars": scalars,
        "curves": curves,
        "categories": categories,
        "flags": flags,
        "levels": levels,
    }


def decode_full(
    normalizer: Normalizer, output: dict[str, Any], index: int = 0, prompt: str = "",
    base_bias: float = 0.0, light_bias: float = 0.0,
) -> dict[str, Any]:
    """Decode row `index`. Level fields use levels.pick_level with these biases;
    pass the prompt so light prompts get `light_bias`."""
    continuous = output["continuous"][index].detach().cpu().numpy().clip(-8, 8)
    categories = [
        output["categories"][name][index].argmax().item()
        for name in normalizer.categories
    ]
    flags = torch.sigmoid(output["flags"][index]).detach().cpu().numpy()
    light = is_light_prompt(prompt)
    levels = [
        pick_level(name, output["levels"][name][index], light, base_bias, light_bias)
        for name in normalizer.levels
    ]
    emitter = normalizer.inverse_transform(continuous, categories, flags, levels)
    validate_emitter(emitter)
    return emitter
