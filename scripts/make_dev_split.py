"""Reserve training-set bases for model development without touching the official splits."""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/dev_base_ids.json"
SEED = 473
COUNT = 20


def choose_bases(records: list[dict], count: int = COUNT, seed: int = SEED) -> list[str]:
    groups = defaultdict(set)
    textures = defaultdict(set)
    base_category = {}
    base_texture = {}
    for record in records:
        base = record["feature_id"]
        category = record["attachment"]["attributes"]["Category"]
        texture = record["emitter"]["properties"]["Texture"]
        groups[category].add(base)
        textures[texture].add(base)
        base_category[base] = category
        base_texture[base] = texture
    rng = random.Random(seed)
    choices = []

    def can_add(base: str) -> bool:
        category = base_category[base]
        texture = base_texture[base]
        category_left = len(groups[category]) - sum(item in groups[category] for item in choices)
        texture_left = len(textures[texture]) - sum(item in textures[texture] for item in choices)
        return base not in choices and category_left > 2 and texture_left > 1

    shared = [sorted(bases) for bases in textures.values() if len(bases) > 1]
    rng.shuffle(shared)
    for bases in shared:
        rng.shuffle(bases)
        for base in bases:
            if can_add(base):
                choices.append(base)
                break
    shared_candidates = sorted({base for bases in shared for base in bases})
    rng.shuffle(shared_candidates)
    for base in shared_candidates:
        if len(choices) >= count - 2:
            break
        if can_add(base):
            choices.append(base)
    unique_candidates = sorted(set(base_category) - set(shared_candidates))
    rng.shuffle(unique_candidates)
    for base in unique_candidates:
        if len(choices) >= count:
            break
        category = base_category[base]
        if len(groups[category]) - sum(item in groups[category] for item in choices) > 2:
            choices.append(base)
    if len(choices) != count or len(set(choices)) != count:
        raise ValueError("could not select the requested number of distinct bases")
    return sorted(choices)


def main() -> None:
    bases = choose_bases(load_split("train"))
    OUTPUT.write_text(json.dumps({"seed": SEED, "base_ids": bases}, indent=2) + "\n", encoding="utf-8")
    print(f"reserved {len(bases)} training bases in {OUTPUT}")


if __name__ == "__main__":
    main()
