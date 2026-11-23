"""Color-conditioned head on top of the frozen full particle model."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from ..data.normalize import Normalizer
from .full import ParticleFull


class ParticleFullColor(ParticleFull):
    def __init__(self, normalizer: Normalizer, embedding_dim: int = 384, hidden_dim: int = 256):
        super().__init__(normalizer, embedding_dim, hidden_dim)
        self.color_indices = [
            i for i, name in enumerate(normalizer.continuous) if name.startswith("Color.")
        ]
        self.color_head = nn.Linear(hidden_dim // 2 + 4, len(self.color_indices))
        self.register_buffer("color_mean", torch.tensor([
            normalizer.mean[normalizer.continuous[i]] for i in self.color_indices
        ], dtype=torch.float32))
        self.register_buffer("color_std", torch.tensor([
            normalizer.std[normalizer.continuous[i]] for i in self.color_indices
        ], dtype=torch.float32))

    def initialize_from_full(self) -> None:
        """Start from the old color rows so other outputs remain untouched."""
        curve_rows = [self.curve_indices.index(index) for index in self.color_indices]
        with torch.no_grad():
            self.color_head.weight.zero_()
            self.color_head.weight[:, :self.curves.in_features] = self.curves.weight[curve_rows]
            self.color_head.bias.copy_(self.curves.bias[curve_rows])

    def forward(self, embedding: torch.Tensor, color_cue: torch.Tensor | None = None):
        hidden = self.backbone(embedding)
        output = self._heads(hidden)
        if color_cue is None:
            return output
        if color_cue.shape != (len(embedding), 4):
            raise ValueError("color cue must have shape [batch, 4]")
        if (color_cue[:, 3:4] > 0.5).any():
            color = self.predict_color(hidden, color_cue)
            indices = torch.tensor(self.color_indices, device=hidden.device)
            original = output["continuous"].index_select(1, indices)
            chosen = self.select_color(original, color, color_cue)
            output["continuous"] = output["continuous"].index_copy(1, indices, chosen)
        return output

    def select_color(self, original: torch.Tensor, conditioned: torch.Tensor,
                     color_cue: torch.Tensor) -> torch.Tensor:
        """Keep an already matching shade; correct a conflicting hue."""
        rgb = (original * self.color_std + self.color_mean)[:, :3].clamp(0, 1)
        target = color_cue[:, :3]
        chroma = rgb - rgb.mean(dim=1, keepdim=True)
        target_chroma = target - target.mean(dim=1, keepdim=True)
        similarity = F.cosine_similarity(chroma, target_chroma, dim=1)
        saturation = (rgb.amax(dim=1) - rgb.amin(dim=1)) / rgb.amax(dim=1).clamp_min(1e-6)
        target_saturation = ((target.amax(dim=1) - target.amin(dim=1)) /
                             target.amax(dim=1).clamp_min(1e-6))
        matching = torch.where(target_saturation < 0.05, saturation < 0.15,
                               (similarity >= 0.75) & (saturation >= 0.15))
        correct = (color_cue[:, 3] > 0.5) & ~matching
        return torch.where(correct[:, None], conditioned, original)

    def predict_color(self, hidden: torch.Tensor, color_cue: torch.Tensor) -> torch.Tensor:
        """Learn brightness over life while honoring an explicit requested hue."""
        normalized = self.color_head(torch.cat((hidden, color_cue), dim=1))
        raw = (normalized * self.color_std + self.color_mean).reshape(len(hidden), -1, 3)
        brightness = raw.clamp(0, 1).amax(dim=2, keepdim=True)
        rgb = color_cue[:, :3]
        ratio = rgb / rgb.amax(dim=1, keepdim=True).clamp_min(1e-6)
        tinted = (brightness * ratio[:, None, :]).flatten(1)
        return (tinted - self.color_mean) / self.color_std
