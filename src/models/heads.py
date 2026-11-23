"""Output heads for the first text-to-particle model."""

from __future__ import annotations

import torch
from torch import nn

from ..data.targets import LEVELS


class BaselineHeads(nn.Module):
    def __init__(self, hidden_dim: int, continuous_dim: int):
        super().__init__()
        self.continuous = nn.Linear(hidden_dim, continuous_dim)
        self.burst = nn.Linear(hidden_dim, 1)
        # One logit per level for each fixed-level field.
        self.levels = nn.ModuleDict({
            name: nn.Linear(hidden_dim, len(values)) for name, values in LEVELS.items()
        })

    def forward(self, hidden: torch.Tensor) -> dict:
        return {
            "continuous": self.continuous(hidden),
            "burst_logit": self.burst(hidden).squeeze(-1),
            "levels": {name: head(hidden) for name, head in self.levels.items()},
        }
