"""Select a texture source using familiar and reserved-base development effects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.models.encoder import split_embeddings
from src.models.inference import model_from_checkpoint
from src.models.nearest_neighbor import build_bank, nearest


ROOT = Path(__file__).resolve().parents[1]


def model_textures(path, vectors):
    saved = torch.load(path, map_location="cpu", weights_only=True)
    normalizer = Normalizer.from_dict(saved["normalizer"])
    model = model_from_checkpoint(saved, normalizer)
    with torch.no_grad():
        logits = model(vectors)["categories"]["Texture"]
    indices = logits.argmax(dim=1).tolist()
    classes = normalizer.classes["Texture"]
    choices = [normalizer.fallback["Texture"] if classes[i] == "<UNK>" else classes[i]
               for i in indices]
    confidence = logits.softmax(dim=1).max(dim=1).values.tolist()
    return choices, confidence


def group(records, embeddings, bank_records, late_path, early_path):
    vectors = torch.stack([embeddings[row["row_hash"], 0] for row in records])
    bank, owners = build_bank(bank_records, split_embeddings("train"))
    indices, similarity = nearest(vectors, bank)
    neighbor = [bank_records[owners[i][0]]["emitter"]["properties"]["Texture"]
                for i in indices.tolist()]
    late, confidence = model_textures(late_path, vectors)
    early, _ = model_textures(early_path, vectors)
    truth = [row["emitter"]["properties"]["Texture"] for row in records]
    return {"truth": truth, "late": late, "early": early, "neighbor": neighbor,
            "similarity": similarity.tolist(), "confidence": confidence}


def accuracy(group, candidate, feature, threshold):
    return sum(
        (late if value >= threshold else choice) == truth
        for truth, late, choice, value in zip(
            group["truth"], group["late"], group[candidate], group[feature]
        )
    ) / len(group["truth"])


def main():
    torch.set_num_threads(min(4, torch.get_num_threads()))
    bases = set(json.loads((ROOT / "data/dev_base_ids.json").read_text())["base_ids"])
    train = load_split("train")
    fit = [row for row in train if row["feature_id"] not in bases]
    dev = [row for row in train if row["feature_id"] in bases]
    validation = load_split("validation")
    groups = {
        "familiar": group(
            validation, split_embeddings("validation"), train,
            ROOT / "checkpoints/particle_full.pt", ROOT / "checkpoints/particle_plain_early.pt",
        ),
        "new_base": group(
            dev, split_embeddings("train"), fit,
            ROOT / "checkpoints/particle_plain_late_dev.pt",
            ROOT / "checkpoints/particle_plain_dev.pt",
        ),
    }
    for name, data in groups.items():
        print(name, len(data["truth"]))
        for choice in ("late", "early", "neighbor"):
            print(f"  {choice}: {sum(a == b for a, b in zip(data['truth'], data[choice])) / len(data['truth']):.3f}")
        for feature in ("similarity", "confidence"):
            vals = sorted(data[feature])
            print(f"  {feature}: p10={vals[len(vals)//10]:.3f} median={vals[len(vals)//2]:.3f} p90={vals[len(vals)*9//10]:.3f}")
    results = []
    for candidate in ("early", "neighbor"):
        for feature in ("similarity", "confidence"):
            values = sorted(set(groups["familiar"][feature] + groups["new_base"][feature]))
            for threshold in [0.0, *values, 1.1]:
                scores = {name: accuracy(data, candidate, feature, threshold)
                          for name, data in groups.items()}
                results.append({"candidate": candidate, "feature": feature,
                                "threshold": threshold, "scores": scores,
                                "balanced": sum(scores.values()) / 2})
    for candidate in ("early", "neighbor"):
        for feature in ("similarity", "confidence"):
            choices = [row for row in results if row["candidate"] == candidate and row["feature"] == feature]
            best = max(choices, key=lambda row: (row["balanced"], row["scores"]["new_base"]))
            print(f"{candidate} by {feature}: threshold={best['threshold']:.4f} "
                  f"familiar={best['scores']['familiar']:.3f} "
                  f"new_base={best['scores']['new_base']:.3f} balanced={best['balanced']:.3f}")
    path = ROOT / "checkpoints/texture_gate_development.json"
    path.write_text(json.dumps({"groups": groups, "results": results}, indent=2) + "\n")
    print(f"saved {path}")


if __name__ == "__main__":
    main()
