"""Fixed-level fields (LightEmission): weighted loss, biased picking, bias tuning.

Every model outputs `output["levels"][name]`, one logit per level in
targets.LEVELS[name]. Training can weight the FAVORED level and light prompts
more; picking adds a bias to the FAVORED level, larger for light prompts.
"""

from __future__ import annotations

import argparse
import math
from typing import Any

import numpy as np
import torch
from torch.nn import functional as F

from ..data.targets import FAVORED, LEVELS


# Grid searched when tuning a bias on validation.
BIAS_GRID = np.round(np.arange(0.0, 10.0001, 0.1), 1)


def level_class_weights(favored_weight: float) -> dict[str, torch.Tensor]:
    """Cross-entropy class weights: `favored_weight` on each field's FAVORED level."""
    weights = {}
    for name, levels in LEVELS.items():
        weight = torch.ones(len(levels))
        weight[levels.index(FAVORED[name])] = favored_weight
        weights[name] = weight
    return weights


def level_loss(
    output: dict[str, Any], batch: dict[str, torch.Tensor],
    class_weights: dict[str, torch.Tensor] | None = None, light_weight: float = 1.0,
    normalize: bool = False,
) -> torch.Tensor:
    """Weighted cross-entropy over the level fields.

    Items whose prompt is a light prompt count `light_weight` times as much.
    Each field's weighted mean divides by its total weight, as torch does for
    class weights. Fields are summed, or with `normalize` each is divided by
    log(number of levels) and the fields are averaged, matching how the full
    model scales its category losses.
    """
    total = None
    for i, name in enumerate(LEVELS):
        logits = output["levels"][name]
        target = batch["levels"][:, i]
        if class_weights is None:
            class_weight = logits.new_ones(logits.shape[1])
        else:
            class_weight = class_weights[name].to(logits.device)
        weight = class_weight[target] * (1.0 + (light_weight - 1.0) * batch["light"])
        error = F.cross_entropy(logits, target, reduction="none")
        field = (error * weight).sum() / weight.sum().clamp_min(1e-8)
        if normalize:
            field = field / math.log(logits.shape[1])
        total = field if total is None else total + field
    return total / len(LEVELS) if normalize else total


def pick_level(
    name: str, logits: torch.Tensor, light: bool, base_bias: float = 0.0, light_bias: float = 0.0,
) -> int:
    """Highest-scoring level after adding a bias to the FAVORED level.

    Light prompts get `light_bias`, every other prompt gets `base_bias`. An
    infinite bias always picks the favored level.
    """
    favored = LEVELS[name].index(FAVORED[name])
    bias = light_bias if light else base_bias
    if bias == float("inf"):
        return favored
    scores = logits.detach().cpu().double().clone()
    scores[favored] += bias
    return int(scores.argmax())


def biased_choices(logits: np.ndarray, favored: int, bias: float) -> np.ndarray:
    if bias == float("inf"):
        return np.full(len(logits), favored)
    scores = logits.astype(float).copy()
    scores[:, favored] += bias
    return scores.argmax(axis=1)


def tune_biases(
    name: str, logits: np.ndarray, targets: np.ndarray, light: np.ndarray, light_recall: float = 0.98,
) -> dict[str, float]:
    """Pick biases for one level field from validation outputs.

    base_bias: the grid value with the best accuracy on non-light prompts,
    taking the larger bias on a tie. light_bias: the smallest grid value at
    least base_bias where, among light prompts whose true level is the favored
    one, at least `light_recall` are picked as favored. That miss is the one
    that shows black squares.
    """
    favored = LEVELS[name].index(FAVORED[name])
    light = light.astype(bool)
    other = ~light
    base_bias = 0.0
    if other.any():
        best = -1.0
        for bias in BIAS_GRID:
            accuracy = float((biased_choices(logits[other], favored, bias) == targets[other]).mean())
            if accuracy >= best:
                best, base_bias = accuracy, float(bias)
    wanted = light & (targets == favored)
    light_bias = float(BIAS_GRID[-1])
    if wanted.any():
        for bias in BIAS_GRID[BIAS_GRID >= base_bias]:
            recall = float((biased_choices(logits[wanted], favored, bias) == favored).mean())
            if recall >= light_recall:
                light_bias = float(bias)
                break
    return {"base_bias": base_bias, "light_bias": light_bias}


def validation_levels(model, loader, device) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Logits, true level indices, and light flags for each level field."""
    model.eval()
    logits = {name: [] for name in LEVELS}
    targets = {name: [] for name in LEVELS}
    light = []
    with torch.no_grad():
        for batch in loader:
            output = model(batch["embedding"].to(device))
            for i, name in enumerate(LEVELS):
                logits[name].append(output["levels"][name].cpu().numpy())
                targets[name].append(batch["levels"][:, i].numpy())
            light.append(batch["light"].numpy())
    light = np.concatenate(light)
    return {
        name: (np.concatenate(logits[name]), np.concatenate(targets[name]), light)
        for name in LEVELS
    }


def level_accuracy(output: dict[str, Any], batch: dict[str, torch.Tensor]) -> float:
    """Unbiased argmax accuracy, averaged over the level fields."""
    return sum(
        (output["levels"][name].argmax(1) == batch["levels"][:, i]).float().mean().item()
        for i, name in enumerate(LEVELS)
    ) / len(LEVELS)


def add_training_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--favored-weight", type=float, default=2.0,
                        help="cross-entropy class weight on LightEmission 1 (others are 1)")
    parser.add_argument("--light-weight", type=float, default=3.0,
                        help="LightEmission loss multiplier for items with a light prompt")
    parser.add_argument("--light-recall", type=float, default=0.98,
                        help="tuning target: share of light prompts truly at 1 that must be picked as 1")
    add_bias_args(parser, "tuned on validation if unset")


def check_training_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.favored_weight <= 0 or args.light_weight <= 0:
        parser.error("weights must be positive")
    if not 0 < args.light_recall <= 1:
        parser.error("light recall must be in (0, 1]")


def add_bias_args(parser: argparse.ArgumentParser, unset: str = "the checkpoint's value if unset") -> None:
    parser.add_argument("--base-bias", type=float, default=None,
                        help=f"logit bias toward LightEmission 1 for non-light prompts; {unset}")
    parser.add_argument("--light-bias", type=float, default=None,
                        help=f"logit bias toward LightEmission 1 for light prompts; {unset}; inf always picks 1")


def tune_and_choose(model, loader, device, args: argparse.Namespace) -> dict[str, Any]:
    """Tune biases on `loader`, then apply any --base-bias/--light-bias override.

    One bias pair is shared by every level field; LightEmission is the only one.
    The result goes into the checkpoint as is.
    """
    tuned = {
        name: tune_biases(name, *values, args.light_recall)
        for name, values in validation_levels(model, loader, device).items()
    }
    first = tuned[next(iter(LEVELS))]
    return {
        "base_bias": first["base_bias"] if args.base_bias is None else args.base_bias,
        "light_bias": first["light_bias"] if args.light_bias is None else args.light_bias,
        "tuned_biases": tuned,
        "favored_weight": args.favored_weight,
        "light_weight": args.light_weight,
    }


def chosen_biases(saved: dict[str, Any], args: argparse.Namespace | None = None) -> tuple[float, float]:
    """Checkpoint biases, defaulting to unbiased decoding for older checkpoints."""
    base = saved.get("base_bias", 0.0)
    light = saved.get("light_bias", 0.0)
    if args is not None and args.base_bias is not None:
        base = args.base_bias
    if args is not None and args.light_bias is not None:
        light = args.light_bias
    return base, light
