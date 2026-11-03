"""Property-level errors for full emitter predictions."""

from __future__ import annotations

import math
from typing import Any

from ..data.normalize import Normalizer
from ..data.schema import validate_emitter
from ..data.targets import CATEGORIES, FLAGS, encode_targets
from .metrics import summarize


CURVE_GROUPS = (
    "Size.value", "Size.envelope", "Squash.value", "Squash.envelope",
    "Transparency.value", "Transparency.envelope", "Color",
)


def row_errors(source: dict[str, Any], result: dict[str, Any], normalizer: Normalizer) -> dict[str, Any]:
    truth = encode_targets(source, normalizer.k)
    guess = encode_targets(result, normalizer.k)
    errors = {}
    for name in normalizer.continuous:
        before = truth.continuous[name]
        if not math.isnan(before):
            after = guess.continuous[name]
            errors[name] = abs(before - (0.0 if math.isnan(after) else after))
    return {
        "numeric_abs_error": {
            name: error for name, error in errors.items()
            if not name.startswith(("Size.", "Squash.", "Transparency.", "Color."))
        },
        "curve_mae": {
            group: sum(error for name, error in errors.items() if name.startswith(group + "."))
            / sum(name.startswith(group + ".") for name in errors)
            for group in CURVE_GROUPS
        },
        "category_correct": {
            name: truth.categories[name] == guess.categories[name] for name in CATEGORIES
        },
        "flag_correct": {name: truth.flags[name] == guess.flags[name] for name in FLAGS},
    }


def summarize_full(
    actual: list[dict[str, Any]], predicted: list[dict[str, Any]],
    normalizer: Normalizer,
) -> dict[str, Any]:
    if not actual or len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same nonzero length")

    sums = {name: 0.0 for name in normalizer.continuous}
    counts = {name: 0 for name in sums}
    categories = {name: 0 for name in CATEGORIES}
    flags = {name: 0 for name in FLAGS}
    known_textures = set(normalizer.classes.get("Texture", []))
    known_count = known_correct = 0
    valid_count = 0
    for source, result in zip(actual, predicted):
        validate_emitter(result)
        valid_count += 1
        truth = encode_targets(source, normalizer.k)
        guess = encode_targets(result, normalizer.k)
        for name in sums:
            before = truth.continuous[name]
            if not math.isnan(before):
                after = guess.continuous[name]
                if math.isnan(after):
                    after = 0.0  # The predicted playback mode disabled this field.
                sums[name] += abs(before - after)
                counts[name] += 1
        for name in CATEGORIES:
            categories[name] += truth.categories[name] == guess.categories[name]
        for name in FLAGS:
            flags[name] += truth.flags[name] == guess.flags[name]
        if truth.categories["Texture"] in known_textures:
            known_count += 1
            known_correct += truth.categories["Texture"] == guess.categories["Texture"]

    count = len(actual)
    mae = {name: sums[name] / counts[name] if counts[name] else None for name in sums}
    curves = {}
    for group in CURVE_GROUPS:
        names = [name for name in sums if name.startswith(group + ".")]
        curves[group] = sum(sums[name] for name in names) / sum(counts[name] for name in names)
    return {
        "samples": count,
        "valid_emitters": valid_count,
        "seven_value_metrics": summarize(actual, predicted),
        "numeric_mae": {
            name: mae[name] for name in sums
            if not name.startswith(("Size.", "Squash.", "Transparency.", "Color."))
        },
        "curve_mae": curves,
        "category_accuracy": {name: categories[name] / count for name in CATEGORIES},
        "flag_accuracy": {name: flags[name] / count for name in FLAGS},
        "texture_seen_in_train": known_count,
        "texture_unseen_in_train": count - known_count,
        "texture_known_accuracy": known_correct / known_count if known_count else None,
    }
