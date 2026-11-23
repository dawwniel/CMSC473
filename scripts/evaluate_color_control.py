"""Compare color-channel error before and after the explicit-color model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.models.color import color_cue, requested_color
from src.models.encoder import split_embeddings
from src.models.inference import model_from_checkpoint


ROOT = Path(__file__).resolve().parents[1]


def evaluate_split(name: str, normalizer: Normalizer, base, color, encoder_name: str) -> dict:
    records = [record for record in load_split(name) if requested_color(record["prompt"])]
    embeddings = split_embeddings(name, model_name=encoder_name)
    vectors = torch.stack([embeddings[record["row_hash"], 0] for record in records])
    cues = torch.tensor([color_cue(record["prompt"]) for record in records], dtype=torch.float32)
    indices = [i for i, field in enumerate(normalizer.continuous) if field.startswith("Color.")]
    targets = torch.stack([
        torch.from_numpy(normalizer.transform(record)["continuous"])[indices] for record in records
    ])
    with torch.no_grad():
        base_output = base(vectors)
        color_output = color(vectors, cues)
    other = [i for i in range(len(normalizer.continuous)) if i not in indices]
    torch.testing.assert_close(base_output["continuous"][:, other],
                               color_output["continuous"][:, other])
    torch.testing.assert_close(base_output["flags"], color_output["flags"])
    for field in normalizer.categories:
        torch.testing.assert_close(base_output["categories"][field],
                                   color_output["categories"][field])
    mean = torch.tensor([normalizer.mean[normalizer.continuous[i]] for i in indices])
    std = torch.tensor([normalizer.std[normalizer.continuous[i]] for i in indices])
    truth = targets * std + mean
    result = {"split": name, "color_explicit_prompts": len(records),
              "other_heads_identical": True}
    for label, output in (("base", base_output), ("color_model", color_output)):
        predicted = output["continuous"][:, indices]
        result[label] = {
            "normalized_smooth_l1": F.smooth_l1_loss(predicted, targets).item(),
            "rgb_mae": ((predicted * std + mean).clamp(0, 1) - truth).abs().mean().item(),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--color", type=Path, default=ROOT / "checkpoints/particle_full_color.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/color_control_evaluation.json")
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    base_saved = torch.load(args.base, map_location="cpu", weights_only=True)
    color_saved = torch.load(args.color, map_location="cpu", weights_only=True)
    if base_saved["normalizer"] != color_saved["normalizer"]:
        raise ValueError("checkpoints use different target normalization")
    normalizer = Normalizer.from_dict(base_saved["normalizer"])
    base = model_from_checkpoint(base_saved, normalizer)
    color = model_from_checkpoint(color_saved, normalizer)
    results = [evaluate_split(split, normalizer, base, color, base_saved["encoder_name"])
               for split in ("validation", "test", "generalization_test")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"{result['split']}: n={result['color_explicit_prompts']} "
              f"RGB MAE {result['base']['rgb_mae']:.4f} -> {result['color_model']['rgb_mae']:.4f}; "
              f"other heads identical={result['other_heads_identical']}")


if __name__ == "__main__":
    main()
