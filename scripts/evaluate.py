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
from src.data.targets import LEVELS
from src.models.model import ParticleBaseline, decode_prediction, output_row


ROOT = Path(__file__).resolve().parents[1]


def evaluate(
    split: str, model: ParticleBaseline, saved: dict, normalizer: Normalizer,
    base_bias: float, light_bias: float,
) -> dict:
    records = load_split(split)
    embeddings = split_embeddings(split, model_name=saved["encoder_name"])
    keys = [(record["row_hash"], 0) for record in records]
    vectors = torch.stack([embeddings[key] for key in keys])
    with torch.no_grad():
        outputs = model(vectors)
    defaults = saved["defaults"]
    prompts = [record["prompt"] for record in records]
    predictions = [
        decode_prediction(normalizer, output_row(outputs, i), defaults, prompts[i], base_bias, light_bias)
        for i in range(len(records))
    ]
    majority_burst = defaults["flags"][normalizer.flags.index("Burst")] >= 0.5
    # The constant baseline picks the train majority level with no bias.
    constant_output = {
        "continuous": torch.zeros(len(saved["columns"])),
        "burst_logit": torch.tensor(1.0 if majority_burst else -1.0),
    }
    constant_output["levels"] = {}
    for i, name in enumerate(normalizer.levels):
        logits = torch.zeros(len(LEVELS[name]))
        logits[defaults["levels"][i]] = 1.0
        constant_output["levels"][name] = logits
    constant = decode_prediction(normalizer, constant_output, defaults, "constant")
    actual = [record["emitter"] for record in records]
    return {
        "model": summarize(actual, predictions, prompts),
        "train_constant": summarize(actual, [constant] * len(records), prompts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_baseline.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/evaluation.json")
    parser.add_argument("--splits", nargs="+", choices=("validation", "test", "generalization_test"),
                        default=("test", "generalization_test"))
    parser.add_argument("--base-bias", type=float, default=None,
                        help="override the checkpoint's LightEmission bias for non-light prompts")
    parser.add_argument("--light-bias", type=float, default=None,
                        help="override the checkpoint's LightEmission bias for light prompts; inf always picks 1")
    args = parser.parse_args()

    torch.set_num_threads(min(4, torch.get_num_threads()))
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    normalizer = Normalizer.from_dict(saved["normalizer"])
    model = ParticleBaseline(saved["embedding_dim"], saved["hidden_dim"])
    model.load_state_dict(saved["model"])
    model.eval()

    base_bias = saved["base_bias"] if args.base_bias is None else args.base_bias
    light_bias = saved["light_bias"] if args.light_bias is None else args.light_bias
    results = {
        split: evaluate(split, model, saved, normalizer, base_bias, light_bias) for split in args.splits
    }
    print(f"LightEmission bias: base={base_bias:g} light={light_bias:g}")
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
        for field, level in model_score["levels"].items():
            constant_level = constant_score["levels"][field]
            rate = level["light_favored_rate"]
            recall = level["light_favored_recall"]
            print(
                f"  {field}: accuracy={level['accuracy']:.3f} constant={constant_level['accuracy']:.3f} "
                f"light prompts={level['light_prompts']} "
                f"picked 1={'n/a' if rate is None else f'{rate:.3f}'} "
                f"recall of true 1={'n/a' if recall is None else f'{recall:.3f}'} "
                f"confusion={level['confusion']}"
            )
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
