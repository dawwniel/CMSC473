"""Keep a predicted texture paired with its recorded sprite-sheet grid."""

from __future__ import annotations

from typing import Any


def texture_layout_index(train: list[dict[str, Any]],
                         cix_effects: list[dict[str, Any]]) -> dict[str, str]:
    layouts: dict[str, str] = {}

    def add(texture: str, layout: str) -> None:
        previous = layouts.setdefault(texture, layout)
        if previous != layout:
            raise ValueError(f"texture {texture} has conflicting flipbook layouts: {previous}, {layout}")

    for record in train:
        properties = record["emitter"]["properties"]
        add(properties["Texture"], properties["FlipbookLayout"]["value"])
    for effect in cix_effects:
        add(effect["texture"], effect["layout"])
    return layouts


def align_flipbook_layouts(emitters: list[dict[str, Any]],
                           layouts: dict[str, str]) -> int:
    """Correct the grid after all model, neighbor, and catalog texture choices."""
    changed = 0
    for emitter in emitters:
        properties = emitter["properties"]
        texture = properties["Texture"]
        if texture not in layouts:
            raise ValueError(f"no verified flipbook layout for texture {texture}")
        expected = layouts[texture]
        if properties["FlipbookLayout"]["value"] != expected:
            properties["FlipbookLayout"]["value"] = expected
            changed += 1
    return changed
