"""Output heads for the first text-to-particle model."""

from __future__ import annotations

import torch
from torch import nn


class BaselineHeads(nn.Module):
    def __init__(self, hidden_dim: int, continuous_dim: int):
        super().__init__()
        self.continuous = nn.Linear(hidden_dim, continuous_dim)
        self.burst = nn.Linear(hidden_dim, 1)

    def forward(self, hidden: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            "continuous": self.continuous(hidden),
            "burst_logit": self.burst(hidden).squeeze(-1),
        }
