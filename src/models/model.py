"""Small MLP baseline on frozen MiniLM embeddings."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from ..data.normalize import Normalizer
from ..data.schema import validate_emitter
from ..data.targets import BURST, encode_targets
from .heads import BaselineHeads


BASELINE_COLUMNS = (
    "Brightness", "Rate", "EmitCount", "Lifetime.min", "Lifetime.max",
    "Speed.min", "Speed.max",
)


class ParticleBaseline(nn.Module):
    def __init__(self, embedding_dim: int = 384, hidden_dim: int = 128):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
        )
        self.heads = BaselineHeads(hidden_dim // 2, len(BASELINE_COLUMNS))

    def forward(self, embedding: torch.Tensor) -> dict[str, torch.Tensor]:
        return self.heads(self.backbone(embedding))


def target_indices(normalizer: Normalizer) -> tuple[list[int], int]:
    missing = [name for name in BASELINE_COLUMNS if name not in normalizer.continuous]
    if missing or BURST not in normalizer.flags:
        raise ValueError(f"baseline targets missing from normalizer: {missing or [BURST]}")
    return [normalizer.continuous.index(name) for name in BASELINE_COLUMNS], normalizer.flags.index(BURST)


def baseline_loss(
    prediction: dict[str, torch.Tensor], batch: dict[str, torch.Tensor],
    continuous_indices: list[int], burst_index: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    actual = batch["continuous"][:, continuous_indices]
    mask = batch["continuous_mask"][:, continuous_indices]
    error = F.smooth_l1_loss(prediction["continuous"], actual, reduction="none")
    regression = (error * mask).sum() / mask.sum().clamp_min(1)
    burst = F.binary_cross_entropy_with_logits(
        prediction["burst_logit"], batch["flags"][:, burst_index]
    )
    return regression + burst, regression, burst


def train_defaults(normalizer: Normalizer, train_records: list[dict[str, Any]]) -> dict[str, list[float | int]]:
    """Train-only fill values for properties this baseline does not predict."""
    categories = [
        normalizer.classes[name].index(normalizer.fallback[name])
        for name in normalizer.categories
    ]
    rows = [encode_targets(record["emitter"]) for record in train_records]
    flags = [
        float(Counter(row.flags[name] for row in rows).most_common(1)[0][0])
        for name in normalizer.flags
    ]
    return {"categories": categories, "flags": flags}


def decode_prediction(
    normalizer: Normalizer, values: torch.Tensor, burst_logit: torch.Tensor,
    defaults: dict[str, list[float | int]], name: str = "ParticleEmitter",
) -> dict[str, Any]:
    """Fill unmodeled fields with train defaults and decode one prediction."""
    continuous_indices, burst_index = target_indices(normalizer)
    continuous = np.zeros(len(normalizer.continuous), dtype=np.float32)
    continuous[continuous_indices] = values.detach().cpu().numpy()
    flags = np.asarray(defaults["flags"], dtype=np.float32).copy()
    flags[burst_index] = torch.sigmoid(burst_logit.detach()).item()
    emitter = normalizer.inverse_transform(
        continuous, defaults["categories"], flags, name,
    )
    validate_emitter(emitter)
    return emitter


def particle_record(
    prompt: str, emitter: dict[str, Any], attachment_name: str = "PromptEffect",
    family: str = "Generated",
) -> dict[str, Any]:
    """Wrap a predicted emitter in a record the Luau importer can read."""
    if not prompt.strip() or "/" in attachment_name or "/" in family:
        raise ValueError("prompt and path names must be valid")
    validate_emitter(emitter)
    path = [family, attachment_name, emitter["name"]]
    return {
        "formatVersion": 1,
        "id": "/".join(path),
        "path": path,
        "attachment": {"class": "Attachment", "name": attachment_name},
        "emitter": emitter,
        "prompt": prompt,
        "playback_mode": "burst" if emitter["attributes"]["EmitCount"] > 0 else "continuous",
    }
