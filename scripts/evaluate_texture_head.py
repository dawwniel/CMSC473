"""Score a texture-only checkpoint against the official dataset splits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.models.encoder import split_embeddings
from src.models.texture import load_texture_head
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path,
                        default=ROOT / "checkpoints/particle_texture.pt")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/texture_head_evaluation.json")
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))

    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    train = load_split("train")
    if saved["train_fingerprint"] != fingerprint(train):
        parser.error("texture head was trained on different data")
    model = load_texture_head(saved)
    classes = saved["classes"]
    results = {}
    for split in ("validation", "test", "generalization_test"):
        records = load_split(split)
        embeddings = split_embeddings(split, model_name=saved["encoder_name"])
        vectors = torch.stack([embeddings[row["row_hash"], 0] for row in records])
        with torch.no_grad():
            scores = model(vectors)
        top = scores.topk(min(3, len(classes)), dim=1).indices.tolist()
        truth = [row["emitter"]["properties"]["Texture"] for row in records]
        results[split] = {
            "n": len(records),
            "top1": sum(classes[indexes[0]] == actual
                        for indexes, actual in zip(top, truth)) / len(records),
            "top3": sum(actual in [classes[i] for i in indexes]
                        for indexes, actual in zip(top, truth)) / len(records),
            "unseen": sum(actual not in classes for actual in truth),
        }
        print(f"{split}: n={len(records)} top1={results[split]['top1']:.3f} "
              f"top3={results[split]['top3']:.3f} unseen={results[split]['unseen']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
