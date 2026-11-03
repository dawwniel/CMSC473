"""Compare full-model predictions, texture fallback, and train-only baselines."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.evaluation.full_metrics import row_errors, summarize_full
from src.models.encoder import split_embeddings
from src.models.full import ParticleFull, decode_full
from src.models.inference import apply_neighbor_textures
from src.models.model import ParticleBaseline, decode_prediction, particle_record, train_defaults
from src.models.nearest_neighbor import build_bank, nearest
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--baseline-checkpoint", type=Path, default=ROOT / "checkpoints/particle_baseline.pt")
    parser.add_argument("--neighbor-texture-threshold", type=float,
                        help="use nearest-neighbor texture below this model confidence")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/full_evaluation.json")
    parser.add_argument("--splits", nargs="+", choices=("validation", "test", "generalization_test"),
                        default=("test", "generalization_test"))
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    normalizer = Normalizer.from_dict(saved["normalizer"])
    train = load_split("train")
    if fingerprint(train) != saved["train_fingerprint"]:
        parser.error("training data changed after this checkpoint; retrain before evaluating")
    model = ParticleFull(normalizer, saved["embedding_dim"], saved["hidden_dim"])
    model.load_state_dict(saved["model"])
    model.eval()
    defaults = train_defaults(normalizer, train)
    constant = normalizer.inverse_transform(
        np.zeros(len(normalizer.continuous)), defaults["categories"], defaults["flags"],
    )
    train_embeddings = split_embeddings("train", model_name=saved["encoder_name"])
    bank, owners = build_bank(train, train_embeddings)

    baseline = None
    if args.baseline_checkpoint.exists():
        prior = torch.load(args.baseline_checkpoint, map_location="cpu", weights_only=True)
        if (prior["encoder_name"] == saved["encoder_name"]
                and prior.get("train_fingerprint") == saved["train_fingerprint"]):
            baseline_normalizer = Normalizer.from_dict(prior["normalizer"])
            baseline = ParticleBaseline(prior["embedding_dim"], prior["hidden_dim"])
            baseline.load_state_dict(prior["model"])
            baseline.eval()
        else:
            print("seven-value checkpoint does not match the current training data; skipping it")

    results = {}
    for split in args.splits:
        records = load_split(split)
        embeddings = split_embeddings(split, model_name=saved["encoder_name"])
        vectors = torch.stack([embeddings[record["row_hash"], 0] for record in records])
        with torch.no_grad():
            output = model(vectors)
        predicted = [decode_full(normalizer, output, i) for i in range(len(records))]
        indices, similarities = nearest(vectors, bank)
        neighbor = [train[owners[index][0]]["emitter"] for index in indices.tolist()]
        neighbor_hybrid = None
        if args.neighbor_texture_threshold is not None:
            confidence = output["categories"]["Texture"].softmax(dim=1).max(dim=1).values
            neighbor_hybrid = copy.deepcopy(predicted)
            apply_neighbor_textures(neighbor_hybrid, confidence, neighbor,
                                    args.neighbor_texture_threshold)
        truth = [record["emitter"] for record in records]
        scores = {
            "full_model": summarize_full(truth, predicted, normalizer),
            "train_constant": summarize_full(truth, [constant] * len(records), normalizer),
            "nearest_neighbor": summarize_full(truth, neighbor, normalizer),
            "neighbor_mean_similarity": similarities.mean().item(),
        }
        if neighbor_hybrid is not None:
            scores["neighbor_texture_hybrid"] = summarize_full(truth, neighbor_hybrid, normalizer)
        if baseline is not None:
            with torch.no_grad():
                prior_output = baseline(vectors)
            prior_predictions = [
                decode_prediction(
                    baseline_normalizer, prior_output["continuous"][i],
                    prior_output["burst_logit"][i], prior["defaults"],
                )
                for i in range(len(records))
            ]
            scores["seven_value_model"] = summarize_full(truth, prior_predictions, normalizer)
        results[split] = scores

        details = []
        for i, record in enumerate(records):
            errors = row_errors(record["emitter"], predicted[i], normalizer)
            details.append({
                "id": record["id"],
                "prompt": record["prompt"],
                "nearest_id": train[owners[indices[i].item()][0]]["id"],
                "nearest_similarity": similarities[i].item(),
                "actual_texture": record["emitter"]["properties"]["Texture"],
                "predicted_texture": predicted[i]["properties"]["Texture"],
                "texture_seen_in_train": record["emitter"]["properties"]["Texture"] in normalizer.classes["Texture"],
                **errors,
                **({
                    "fallback_texture": neighbor_hybrid[i]["properties"]["Texture"],
                    "fallback_used": confidence[i].item() < args.neighbor_texture_threshold,
                    "fallback_texture_correct": (neighbor_hybrid[i]["properties"]["Texture"]
                                                 == record["emitter"]["properties"]["Texture"]),
                } if neighbor_hybrid is not None else {}),
            })
        detail_path = args.output.with_name(f"{args.output.stem}_errors_{split}.jsonl")
        detail_path.write_text("".join(json.dumps(row) + "\n" for row in details), encoding="utf-8")

        selected = sorted(range(len(records)), key=lambda i: details[i]["curve_mae"]["Color"], reverse=True)[:3]
        selected += sorted(range(len(records)), key=lambda i: details[i]["curve_mae"]["Color"])[:3]
        review = []
        for j, i in enumerate(dict.fromkeys(selected), start=1):
            emitter = neighbor_hybrid[i] if neighbor_hybrid is not None else predicted[i]
            row = particle_record(records[i]["prompt"], emitter, f"R{j:03d}", "FullReview")
            row["source_id"] = records[i]["id"]
            review.append(row)
        review_path = args.output.with_name(f"{args.output.stem}_review_{split}.jsonl")
        review_path.write_text("".join(json.dumps(row) + "\n" for row in review), encoding="utf-8")

        print(f"{split}: {len(records)} effects, {scores['full_model']['texture_unseen_in_train']} unseen textures")
        print(f"  per-effect errors: {detail_path}; review predictions: {review_path}")
        for name in ("full_model", "neighbor_texture_hybrid", "seven_value_model", "train_constant", "nearest_neighbor"):
            if name not in scores:
                continue
            report = scores[name]
            seven = report["seven_value_metrics"]
            print(f"  {name}: burst={seven['burst_accuracy']:.3f} "
                  f"texture={report['category_accuracy']['Texture']:.3f} "
                  f"color_curve_mae={report['curve_mae']['Color']:.3f} "
                  f"valid={report['valid_emitters']}/{len(records)}")

    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
