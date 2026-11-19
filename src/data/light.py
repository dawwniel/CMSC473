"""Spot prompts that describe a light or glow effect.

These effects usually use black-backed textures, which only look right at
LightEmission 1, so training weights them more and picking leans harder to 1.
"""

from __future__ import annotations

import re


# Word stems; a prompt matches if any word starts with one. Edit freely.
LIGHT_WORDS = (
    "light", "glow", "shine", "shini", "shiny", "neon", "bright", "spark",
    "fire", "flame", "flaming", "magic", "energ", "laser", "beam", "aura",
)
_PATTERN = re.compile(r"\b(?:" + "|".join(map(re.escape, LIGHT_WORDS)) + r")", re.IGNORECASE)


def is_light_prompt(text: str) -> bool:
    return bool(_PATTERN.search(text))
