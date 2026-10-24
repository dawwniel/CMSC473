"""Convert emitters to flat model targets and back.

Nothing here is fitted. Statistics, category lists, and constants come from
the train split in normalize.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .schema import PARTICLE_PROPERTIES


K = 8
UNKNOWN = "<UNK>"
BURST = "Burst"

# name: (transform, low, high). low and high clamp decoded values.
NUMBERS = {
    "Brightness": ("log1p", 0, None),
    "Drag": ("log1p", 0, None),
    "LightEmission": ("none", 0, 1),
    "LightInfluence": ("none", 0, 1),
    "Rate": ("log1p", 0, None),
    "ShapePartial": ("log1p", 0, None),
    "TimeScale": ("none", 0, 1),
    "VelocityInheritance": ("none", 0, 1),
    "ZOffset": ("none", None, None),
}
RANGES = {
    "FlipbookFramerate": ("log1p", 0, None),
    "Lifetime": ("log1p", 0, None),
    "Rotation": ("none", None, None),
    "RotSpeed": ("slog1p", None, None),
    "Speed": ("log1p", 0, None),
}
VECTORS = {
    "Acceleration": ("xyz", "slog1p"),
    "SpreadAngle": ("xy", "none"),
}
# Value transform and clamp. Envelopes share the transform and are clamped at 0.
SEQUENCES = {
    "Size": ("log1p", 0, None),
    "Squash": ("none", -3, 3),
    "Transparency": ("none", 0, 1),
}
COLORS = ("Color",)
ENUMS = (
    "EmissionDirection", "FlipbookLayout", "FlipbookMode", "Orientation",
    "Shape", "ShapeInOut", "ShapeStyle",
)
BOOLEANS = ("Enabled", "FlipbookStartRandom", "LockedToPart", "WindAffectsDrag")
CATEGORIES = ENUMS + ("Texture",)
FLAGS = BOOLEANS + (BURST,)

# Burst emitters only play through Importer.emit(), so Rate is unused for them.
BURST_RATE = 0.0


@dataclass(frozen=True)
class Column:
    name: str
    transform: str = "none"
    low: float | None = None
    high: float | None = None
    # Set when the column only applies to one playback mode.
    mode: str | None = None


@dataclass
class Targets:
    """An emitter as named columns. NaN marks a column that doesn't apply."""

    continuous: dict[str, float] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)


def _check_coverage() -> None:
    groups = [NUMBERS, RANGES, VECTORS, SEQUENCES, COLORS, CATEGORIES, BOOLEANS]
    names = [name for group in groups for name in group]
    if len(names) != len(set(names)) or set(names) != set(PARTICLE_PROPERTIES):
        raise RuntimeError("targets.py does not cover PARTICLE_PROPERTIES exactly once")


_check_coverage()


def continuous_columns(k: int = K) -> list[Column]:
    columns = []
    for name, (transform, low, high) in NUMBERS.items():
        columns.append(Column(name, transform, low, high, "continuous" if name == "Rate" else None))
    columns.append(Column("EmitCount", "log1p", 1, None, "burst"))
    for name, (transform, low, high) in RANGES.items():
        columns += [Column(f"{name}.{end}", transform, low, high) for end in ("min", "max")]
    for name, (axes, transform) in VECTORS.items():
        columns += [Column(f"{name}.{axis}", transform) for axis in axes]
    for name, (transform, low, high) in SEQUENCES.items():
        columns += [Column(f"{name}.value.{i}", transform, low, high) for i in range(k)]
        columns += [Column(f"{name}.envelope.{i}", transform, 0, None) for i in range(k)]
    for name in COLORS:
        columns += [Column(f"{name}.{c}.{i}", "none", 0, 1) for i in range(k) for c in "rgb"]
    return columns


def sample_times(k: int = K) -> np.ndarray:
    return np.linspace(0.0, 1.0, k)


def resample(times: Any, values: Any, k: int = K) -> np.ndarray:
    """Sample a piecewise-linear curve at k even times.

    Repeated keypoint times are a jump; the curve takes the later value there,
    which is what the last keypoint at that time shows.
    """
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    samples = sample_times(k)
    right = np.clip(np.searchsorted(times, samples, side="right"), 1, len(times) - 1)
    left = right - 1
    span = times[right] - times[left]
    # A zero span only happens past the last keypoint, so take the right value.
    weight = np.divide(samples - times[left], span, out=np.ones_like(samples), where=span > 0)
    weight = np.clip(weight, 0.0, 1.0)
    return values[left] + weight * (values[right] - values[left])


def encode_targets(emitter: dict[str, Any], k: int = K) -> Targets:
    """Turn a validated emitter node into named target columns."""
    properties = emitter["properties"]
    count = emitter["attributes"]["EmitCount"]
    burst = count > 0
    out = Targets()
    cont = out.continuous

    for name in NUMBERS:
        cont[name] = float(properties[name])
    if burst:
        cont["Rate"] = math.nan
    cont["EmitCount"] = float(count) if burst else math.nan
    for name in RANGES:
        low, high = properties[name]["value"]
        cont[f"{name}.min"], cont[f"{name}.max"] = float(low), float(high)
    for name, (axes, _) in VECTORS.items():
        for axis, value in zip(axes, properties[name]["value"]):
            cont[f"{name}.{axis}"] = float(value)
    for name in SEQUENCES:
        points = np.asarray(properties[name]["keypoints"], dtype=float)
        for part, column in (("value", 1), ("envelope", 2)):
            for i, value in enumerate(resample(points[:, 0], points[:, column], k)):
                cont[f"{name}.{part}.{i}"] = float(value)
    for name in COLORS:
        points = np.asarray(properties[name]["keypoints"], dtype=float)
        for column, channel in enumerate("rgb", start=1):
            for i, value in enumerate(resample(points[:, 0], points[:, column], k)):
                cont[f"{name}.{channel}.{i}"] = float(value)

    for name in ENUMS:
        out.categories[name] = properties[name]["value"]
    out.categories["Texture"] = properties["Texture"]
    for name in BOOLEANS:
        out.flags[name] = bool(properties[name])
    out.flags[BURST] = burst
    return out


def _clamped(columns: dict[str, Column], values: dict[str, float], name: str) -> float:
    column = columns[name]
    value = values[name]
    if column.low is not None:
        value = max(value, column.low)
    if column.high is not None:
        value = min(value, column.high)
    return float(value)


def decode_emitter(targets: Targets, k: int = K, name: str = "ParticleEmitter") -> dict[str, Any]:
    """Build an emitter node that schema.validate_emitter accepts.

    Every column must be present, including the Rate and EmitCount columns for
    both modes; the Burst flag picks which one is used.
    """
    columns = {column.name: column for column in continuous_columns(k)}
    value = lambda column: _clamped(columns, targets.continuous, column)
    times = sample_times(k)
    burst = targets.flags[BURST]
    properties: dict[str, Any] = {}

    for prop in NUMBERS:
        properties[prop] = value(prop)
    if burst:
        properties["Rate"] = BURST_RATE
    for prop in RANGES:
        ends = sorted((value(f"{prop}.min"), value(f"{prop}.max")))
        properties[prop] = {"_type": "NumberRange", "value": ends}
    for prop, (axes, _) in VECTORS.items():
        kind = "Vector3" if len(axes) == 3 else "Vector2"
        properties[prop] = {"_type": kind, "value": [value(f"{prop}.{axis}") for axis in axes]}
    for prop in SEQUENCES:
        properties[prop] = {
            "_type": "NumberSequence",
            "keypoints": [
                [float(times[i]), value(f"{prop}.value.{i}"), value(f"{prop}.envelope.{i}")]
                for i in range(k)
            ],
        }
    for prop in COLORS:
        properties[prop] = {
            "_type": "ColorSequence",
            "keypoints": [
                [float(times[i])] + [value(f"{prop}.{channel}.{i}") for channel in "rgb"]
                for i in range(k)
            ],
        }
    for prop in ENUMS:
        properties[prop] = {
            "_type": "Enum", "enum": PARTICLE_PROPERTIES[prop], "value": targets.categories[prop],
        }
    properties["Texture"] = targets.categories["Texture"]
    for prop in BOOLEANS:
        properties[prop] = bool(targets.flags[prop])

    count = max(1, round(value("EmitCount"))) if burst else 0
    return {
        "class": "ParticleEmitter",
        "name": name,
        "properties": properties,
        "attributes": {"EmitCount": count},
    }
