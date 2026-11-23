"""Read explicit prompt colors and tint an emitter's Color sequence."""

from __future__ import annotations

import colorsys
import copy
import math
import re
from dataclasses import dataclass
from typing import Any


COLORS: dict[str, tuple[float, float, float]] = {
    "red": (0.95, 0.17, 0.14),
    "orange": (1.0, 0.43, 0.09),
    "yellow": (1.0, 0.88, 0.17),
    "green": (0.14, 0.88, 0.25),
    "blue": (0.20, 0.48, 1.0),
    "purple": (0.60, 0.29, 0.92),
    "pink": (1.0, 0.42, 0.69),
    "cyan": (0.12, 0.88, 0.94),
    "teal": (0.09, 0.72, 0.68),
    "white": (1.0, 1.0, 1.0),
}
ALIASES = {"violet": "purple", "lime": "green", "aqua": "cyan", "turquoise": "teal"}
WORDS = {**{name: name for name in COLORS}, **ALIASES}
COLOR_RE = re.compile(r"\b(" + "|".join(map(re.escape, WORDS)) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class ColorRequest:
    name: str
    rgb: tuple[float, float, float]


def requested_color(prompt: str) -> ColorRequest | None:
    """Return one unambiguous named color, leaving multicolor prompts alone."""
    names = {WORDS[match.group().lower()] for match in COLOR_RE.finditer(prompt)}
    if len(names) != 1:
        return None
    name = names.pop()
    return ColorRequest(name, COLORS[name])


def color_cue(prompt: str) -> tuple[float, float, float, float]:
    request = requested_color(prompt)
    return (*request.rgb, 1.0) if request else (0.0, 0.0, 0.0, 0.0)


def replace_prompt_color(prompt: str, new_name: str) -> str:
    if requested_color(prompt) is None or new_name not in COLORS:
        raise ValueError("prompt must have one color and replacement must be known")
    return COLOR_RE.sub(new_name, prompt)


def tint_emitter_color(emitter: dict[str, Any], rgb: tuple[float, float, float]) -> dict[str, Any]:
    """Change hue and saturation while retaining each keypoint's brightness."""
    result = copy.deepcopy(emitter)
    hue, saturation, _ = colorsys.rgb_to_hsv(*rgb)
    points = result["properties"]["Color"]["keypoints"]
    for point in points:
        brightness = max(point[1:4])
        point[1:4] = colorsys.hsv_to_rgb(hue, saturation, brightness)
    return result


def emitter_color_matches(emitter: dict[str, Any], rgb: tuple[float, float, float]) -> bool:
    """Test whether the first Color keypoint already has the requested hue."""
    actual = emitter["properties"]["Color"]["keypoints"][0][1:4]
    saturation = (max(actual) - min(actual)) / max(max(actual), 1e-6)
    target_saturation = (max(rgb) - min(rgb)) / max(max(rgb), 1e-6)
    if target_saturation < 0.05:
        return saturation < 0.15
    if saturation < 0.15:
        return False
    a = [value - sum(actual) / 3 for value in actual]
    b = [value - sum(rgb) / 3 for value in rgb]
    dot = sum(left * right for left, right in zip(a, b))
    norm = math.sqrt(sum(value * value for value in a) * sum(value * value for value in b))
    return norm > 0 and dot / norm >= 0.75
