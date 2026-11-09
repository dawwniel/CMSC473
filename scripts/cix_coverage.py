"""Show which CIX image IDs still need a reviewed effect."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    catalog = json.loads((ROOT / "data/cix_catalog.json").read_text(encoding="utf-8"))["entries"]
    pilot = json.loads((ROOT / "data/cix_pilot_review.json").read_text(encoding="utf-8"))["effects"]
    expansion = json.loads((ROOT / "data/cix_expansion_manifest.json").read_text(encoding="utf-8"))["effects"]

    cards_by_image = defaultdict(list)
    for card in catalog:
        cards_by_image[card["galleryImage"]].append(f"{card['kind']}/{card['name']}")

    dataset_images = set()
    for path in (ROOT / "src/data").glob("*/particles_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            dataset_images.add(record["emitter"]["properties"]["Texture"])

    pilot_images = {effect["texture"] for effect in pilot}
    expansion_images = {effect["texture"] for effect in expansion}
    unused = sorted(set(cards_by_image) - dataset_images - pilot_images - expansion_images)
    counts = defaultdict(int)
    for image in unused:
        kind = cards_by_image[image][0].split("/", 1)[0]
        counts[kind] += 1

    print(f"CIX cards: {len(catalog)}")
    print(f"Distinct CIX image IDs: {len(cards_by_image)}")
    print(f"Covered by exported dataset or Studio review sets: {len(set(cards_by_image) - set(unused))}")
    print(f"Unused: {len(unused)} ({counts['Particle']} static, {counts['FlipBook']} flipbook)")
    print("Next unused IDs:")
    for image in unused[:20]:
        print(f"  {image}: {', '.join(cards_by_image[image])}")


if __name__ == "__main__":
    main()
