"""Metrics for decoded particle emitters."""

from __future__ import annotations

from typing import Any


FIELDS = ("Brightness", "Rate", "EmitCount", "Lifetime.min", "Lifetime.max", "Speed.min", "Speed.max")


def values(emitter: dict[str, Any]) -> dict[str, float]:
    properties = emitter["properties"]
    return {
        "Brightness": properties["Brightness"],
        "Rate": properties["Rate"],
        "EmitCount": emitter["attributes"]["EmitCount"],
        "Lifetime.min": properties["Lifetime"]["value"][0],
        "Lifetime.max": properties["Lifetime"]["value"][1],
        "Speed.min": properties["Speed"]["value"][0],
        "Speed.max": properties["Speed"]["value"][1],
    }


def summarize(actual: list[dict[str, Any]], predicted: list[dict[str, Any]]) -> dict[str, Any]:
    if not actual or len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same nonzero length")

    errors = {field: 0.0 for field in FIELDS}
    active_errors = {field: 0.0 for field in ("Rate", "EmitCount")}
    active_counts = {field: 0 for field in active_errors}
    correct_mode = 0
    actual_bursts = 0
    predicted_bursts = 0

    for source, result in zip(actual, predicted):
        truth, guess = values(source), values(result)
        burst = truth["EmitCount"] > 0
        guessed_burst = guess["EmitCount"] > 0
        actual_bursts += burst
        predicted_bursts += guessed_burst
        correct_mode += burst == guessed_burst
        for field in FIELDS:
            difference = abs(truth[field] - guess[field])
            errors[field] += difference
            if (field == "EmitCount" and burst) or (field == "Rate" and not burst):
                active_errors[field] += difference
                active_counts[field] += 1

    count = len(actual)
    return {
        "samples": count,
        "burst_accuracy": correct_mode / count,
        "actual_bursts": actual_bursts,
        "predicted_bursts": predicted_bursts,
        "mae": {field: errors[field] / count for field in FIELDS},
        "active_mae": {
            field: active_errors[field] / active_counts[field] if active_counts[field] else None
            for field in active_errors
        },
    }
