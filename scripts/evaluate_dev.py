"""Score models and nearest neighbor on bases reserved from the train split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.evaluation.full_metrics import summarize_full
from src.models.encoder import split_embeddings
from src.models.full import decode_full
from src.models.inference import model_from_checkpoint
from src.models.nearest_neighbor import build_bank, nearest
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plain", type=Path, default=ROOT / "checkpoints/particle_plain_dev.pt")
    parser.add_argument("--v2", type=Path, default=ROOT / "checkpoints/particle_v2_dev.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/dev_comparison.json")
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    dev_bases = set(json.loads((ROOT / "data/dev_base_ids.json").read_text(encoding="utf-8"))["base_ids"])
    records = load_split("train")
    fitted = [record for record in records if record["feature_id"] not in dev_bases]
    heldout = [record for record in records if record["feature_id"] in dev_bases]
    embeddings = split_embeddings("train")
    vectors = torch.stack([embeddings[record["row_hash"], 0] for record in heldout])
    bank, owners = build_bank(fitted, embeddings)
    indices, _ = nearest(vectors, bank)
    actual = [record["emitter"] for record in heldout]
    normalizer = Normalizer.from_dict(torch.load(args.plain, map_location="cpu", weights_only=True)["normalizer"])
    neighbor = [fitted[owners[i][0]]["emitter"] for i in indices.tolist()]
    scores = {"nearest_neighbor": summarize_full(actual, neighbor, normalizer)}

    for name, path in (("plain", args.plain), ("v2", args.v2)):
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if saved["train_fingerprint"] != fingerprint(fitted) or saved["validation_fingerprint"] != fingerprint(heldout):
            parser.error(f"{path} was trained on different development data")
        normalizer = Normalizer.from_dict(saved["normalizer"])
        model = model_from_checkpoint(saved, normalizer)
        with torch.no_grad():
            output = model(vectors)
        predicted = [decode_full(normalizer, output, i) for i in range(len(heldout))]
        scores[name] = summarize_full(actual, predicted, normalizer)
        if "group" in output:
            correct = sum(
                saved["group_names"][i] == record["attachment"]["attributes"]["Category"]
                for i, record in zip(output["group"].argmax(dim=1).tolist(), heldout)
            )
            scores[name]["group_accuracy"] = correct / len(heldout)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    print(f"development effects={len(heldout)} bases={len(dev_bases)}")
    for name, result in scores.items():
        print(f"{name}: texture={result['category_accuracy']['Texture']:.3f} "
              f"seen_texture={result['texture_known_accuracy']:.3f} "
              f"unseen={result['texture_unseen_in_train']} "
              f"burst={result['seven_value_metrics']['burst_accuracy']:.3f} "
              f"size_mae={result['curve_mae']['Size.value']:.3f} "
              f"color_mae={result['curve_mae']['Color']:.3f}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
