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
from ..data.light import is_light_prompt
from ..data.targets import BURST, encode_targets
from .heads import BaselineHeads
from .levels import (  # noqa: F401  (re-exported for older imports)
    level_class_weights, level_loss, pick_level, tune_biases,
)


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
    prediction: dict[str, Any], batch: dict[str, torch.Tensor],
    continuous_indices: list[int], burst_index: int,
    class_weights: dict[str, torch.Tensor] | None = None, light_weight: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Total, regression, burst, and level losses. See levels.level_loss."""
    actual = batch["continuous"][:, continuous_indices]
    mask = batch["continuous_mask"][:, continuous_indices]
    error = F.smooth_l1_loss(prediction["continuous"], actual, reduction="none")
    regression = (error * mask).sum() / mask.sum().clamp_min(1)
    burst = F.binary_cross_entropy_with_logits(
        prediction["burst_logit"], batch["flags"][:, burst_index]
    )
    level = level_loss(prediction, batch, class_weights, light_weight)
    return regression + burst + level, regression, burst, level


def output_row(output: dict[str, Any], i: int) -> dict[str, Any]:
    """Row i of a batched output; nested dicts (categories, levels) are sliced too."""
    return {
        key: output_row(value, i) if isinstance(value, dict) else value[i]
        for key, value in output.items()
    }


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
    levels = [
        Counter(row.levels[name] for row in rows).most_common(1)[0][0]
        for name in normalizer.levels
    ]
    return {"categories": categories, "flags": flags, "levels": levels}


def decode_prediction(
    normalizer: Normalizer, prediction: dict[str, torch.Tensor],
    defaults: dict[str, list[float | int]], prompt: str,
    base_bias: float = 0.0, light_bias: float = 0.0, name: str = "ParticleEmitter",
) -> dict[str, Any]:
    """Fill unmodeled fields with train defaults and decode one prediction.

    `prediction` is one row of the model's output (see output_row).
    """
    continuous_indices, burst_index = target_indices(normalizer)
    continuous = np.zeros(len(normalizer.continuous), dtype=np.float32)
    continuous[continuous_indices] = prediction["continuous"].detach().cpu().numpy()
    flags = np.asarray(defaults["flags"], dtype=np.float32).copy()
    flags[burst_index] = torch.sigmoid(prediction["burst_logit"].detach()).item()
    light = is_light_prompt(prompt)
    levels = [
        pick_level(field, prediction["levels"][field], light, base_bias, light_bias)
        for field in normalizer.levels
    ]
    emitter = normalizer.inverse_transform(
        continuous, defaults["categories"], flags, levels, name,
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
