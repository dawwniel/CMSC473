"""Category-aware particle model with more weight on visible properties."""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from ..data.normalize import Normalizer
from .full import ParticleFull


def group_setup(records: list[dict], normalizer: Normalizer) -> tuple[list[str], torch.Tensor]:
    names = sorted({record["attachment"]["attributes"]["Category"] for record in records})
    group_index = {name: i for i, name in enumerate(names)}
    texture_classes = normalizer.classes["Texture"]
    index = {name: i for i, name in enumerate(texture_classes)}
    mask = torch.zeros(len(names), len(texture_classes))
    for record in records:
        group = record["attachment"]["attributes"]["Category"]
        texture = record["emitter"]["properties"]["Texture"]
        mask[group_index[group], index[texture]] = 1
    return names, mask


class ParticleV2(ParticleFull):
    def __init__(
        self, normalizer: Normalizer, group_names: list[str], texture_mask: torch.Tensor,
        embedding_dim: int = 384, hidden_dim: int = 256, texture_bias: float = 1.5,
    ):
        super().__init__(normalizer, embedding_dim, hidden_dim)
        if texture_mask.shape != (len(group_names), len(normalizer.classes["Texture"])):
            raise ValueError("texture mask shape does not match groups and textures")
        self.group_names = list(group_names)
        self.normalizer_names = list(normalizer.continuous)
        self.texture_bias = texture_bias
        self.group_head = nn.Linear(hidden_dim // 2, len(group_names))
        self.register_buffer("texture_mask", texture_mask.float())

    def forward(self, embedding: torch.Tensor) -> dict:
        hidden = self.backbone(embedding)
        output = self._heads(hidden)
        group_logits = self.group_head(hidden)
        compatible = torch.softmax(group_logits, dim=1) @ self.texture_mask
        output["categories"]["Texture"] = (
            output["categories"]["Texture"]
            + self.texture_bias * torch.log(compatible.clamp_min(1e-4))
        )
        output["group"] = group_logits
        return output


def loss_v2(output: dict, batch: dict[str, torch.Tensor], model: ParticleV2) -> dict:
    errors = F.smooth_l1_loss(output["continuous"], batch["continuous"], reduction="none")
    mask = batch["continuous_mask"]

    def column_weight(name: str) -> float:
        if name.startswith("Size.value."):
            return 3.0
        if name.startswith("Transparency.value.") or name.startswith("Color."):
            return 2.0
        if name.startswith(("Speed.", "SpreadAngle.")) or name in {"Brightness", "Rate", "EmitCount"}:
            return 1.5
        return 1.0

    weights = errors.new_tensor([column_weight(name) for name in model.normalizer_names])

    def group_error(indices: list[int]) -> torch.Tensor:
        weighted = mask[:, indices] * weights[indices]
        return (errors[:, indices] * weighted).sum() / weighted.sum().clamp_min(1)

    scalars = group_error(model.scalar_indices)
    curves = group_error(model.curve_indices)
    category_weights = {"Texture": 4.0, "FlipbookLayout": 2.0, "FlipbookMode": 2.0}
    category_errors = []
    weight_sum = 0.0
    for i, name in enumerate(model.category_names):
        logits = output["categories"][name]
        weight = category_weights.get(name, 1.0)
        category_errors.append(
            weight * F.cross_entropy(logits, batch["categories"][:, i]) / math.log(logits.shape[1])
        )
        weight_sum += weight
    categories = torch.stack(category_errors).sum() / weight_sum
    flags = F.binary_cross_entropy_with_logits(output["flags"], batch["flags"])
    groups = F.cross_entropy(output["group"], batch["group"]) / math.log(len(model.group_names))
    return {
        "total": scalars + curves + categories + flags + 0.4 * groups,
        "scalars": scalars,
        "curves": curves,
        "categories": categories,
        "flags": flags,
        "groups": groups,
    }
