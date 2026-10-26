"""Evaluate the saved baseline on held-out particle effects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.evaluation.metrics import summarize
from src.models.encoder import split_embeddings
from src.models.model import ParticleBaseline, decode_prediction


ROOT = Path(__file__).resolve().parents[1]


def evaluate(split: str, model: ParticleBaseline, saved: dict, normalizer: Normalizer) -> dict:
    records = load_split(split)
    embeddings = split_embeddings(split, model_name=saved["encoder_name"])
    keys = [(record["row_hash"], 0) for record in records]
    vectors = torch.stack([embeddings[key] for key in keys])
    with torch.no_grad():
        outputs = model(vectors)
    defaults = saved["defaults"]
    predictions = [
        decode_prediction(normalizer, outputs["continuous"][i], outputs["burst_logit"][i], defaults)
        for i in range(len(records))
    ]
    majority_burst = defaults["flags"][normalizer.flags.index("Burst")] >= 0.5
    constant = decode_prediction(
        normalizer,
        torch.zeros(len(saved["columns"])),
        torch.tensor(1.0 if majority_burst else -1.0),
        defaults,
    )
    actual = [record["emitter"] for record in records]
    return {
        "model": summarize(actual, predictions),
        "train_constant": summarize(actual, [constant] * len(records)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_baseline.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/evaluation.json")
    parser.add_argument("--splits", nargs="+", choices=("validation", "test", "generalization_test"),
                        default=("test", "generalization_test"))
    args = parser.parse_args()

    torch.set_num_threads(min(4, torch.get_num_threads()))
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    normalizer = Normalizer.from_dict(saved["normalizer"])
    model = ParticleBaseline(saved["embedding_dim"], saved["hidden_dim"])
    model.load_state_dict(saved["model"])
    model.eval()

    results = {split: evaluate(split, model, saved, normalizer) for split in args.splits}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for split, scores in results.items():
        model_score = scores["model"]
        constant_score = scores["train_constant"]
        print(f"{split}: n={model_score['samples']} burst_accuracy={model_score['burst_accuracy']:.3f} "
              f"constant={constant_score['burst_accuracy']:.3f}")
        for field, error in model_score["mae"].items():
            print(f"  {field}: MAE={error:.3f} constant={constant_score['mae'][field]:.3f}")
        for field, error in model_score["active_mae"].items():
            if error is not None:
                print(f"  {field} when active: MAE={error:.3f}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
