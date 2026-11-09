"""Test unseen CIX queries against image and description catalogs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import torch
from torch.nn.functional import normalize
from transformers import CLIPModel, CLIPProcessor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.dataset import load_split
from src.models.encoder import TextEncoder
from scripts.benchmark_texture_retrieval import representative_image


def measure(scores: torch.Tensor, ids: list[str], targets: list[str]) -> dict:
    top = scores.topk(3, dim=1).indices.tolist()
    return {
        "top1": sum(ids[choice[0]] == target for choice, target in zip(top, targets)),
        "top3": sum(target in [ids[i] for i in choice]
                    for choice, target in zip(top, targets)),
        "ranked": [[ids[i] for i in choice] for choice in top],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=ROOT / "checkpoints/texture_images")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/cix_texture_holdout_evaluation.json")
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))

    queries = json.loads((ROOT / "data/cix_texture_holdout.json").read_text())["queries"]
    reviewed = json.loads((ROOT / "data/cix_prompt_review.json").read_text())
    generic = json.loads((ROOT / "data/cix_prompt_before_review.json").read_text())
    manifest = {entry["id"]: entry for entry in
                json.loads((ROOT / "data/cix_expansion_manifest.json").read_text())["effects"]}
    ids = sorted(reviewed)
    targets = list(queries)
    assert set(targets) <= set(ids)
    assert set(ids) == set(generic)
    train_ids = {row["feature_id"] for row in load_split("train")}
    assert not set(targets) & train_ids, "held-out CIX effects are still in train"

    encoder = TextEncoder(device="cpu")
    query_vectors = encoder.encode(list(queries.values()))
    text_scores = {}
    for name, catalog in (("generic", generic), ("reviewed", reviewed)):
        descriptions = encoder.encode([catalog[effect_id] for effect_id in ids])
        text_scores[name] = query_vectors @ descriptions.T

    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").eval()
    image_vectors = []
    with torch.no_grad():
        for start in range(0, len(ids), 12):
            images = []
            for effect_id in ids[start:start + 12]:
                spec = manifest[effect_id]
                asset_id = re.findall(r"[0-9]+", spec["texture"])[-1]
                images.append(representative_image(
                    args.images / f"{asset_id}.png", spec["layout"]))
            pixels = clip_processor(images=images, return_tensors="pt")["pixel_values"]
            image_vectors.append(normalize(
                clip_model.get_image_features(pixel_values=pixels).pooler_output, dim=1))
        image_vectors = torch.cat(image_vectors)
        text_vectors = []
        for start in range(0, len(targets), 12):
            batch = clip_processor(text=list(queries.values())[start:start + 12],
                                   padding=True, truncation=True, return_tensors="pt")
            text_vectors.append(normalize(
                clip_model.get_text_features(**batch).pooler_output, dim=1))
        image_scores = torch.cat(text_vectors) @ image_vectors.T

    scores = {**text_scores, "image": image_scores}
    summary = {name: measure(value, ids, targets) for name, value in scores.items()}
    family_results = {}
    for name, value in scores.items():
        correct = 0
        for row_index, target in enumerate(targets):
            family = manifest[target]["family"]
            choices = [i for i, effect_id in enumerate(ids)
                       if manifest[effect_id]["family"] == family]
            best = max(choices, key=lambda i: value[row_index, i].item())
            correct += ids[best] == target
        family_results[name] = correct
    details = []
    for index, target in enumerate(targets):
        details.append({
            "id": target,
            "family": manifest[target]["family"],
            "query": queries[target],
            "texture": manifest[target]["texture"],
            "generic_top3": summary["generic"]["ranked"][index],
            "reviewed_top3": summary["reviewed"]["ranked"][index],
            "image_top3": summary["image"]["ranked"][index],
        })
    result = {
        "queries": len(targets), "catalog_textures": len(ids),
        "metrics": {name: {key: value for key, value in data.items() if key != "ranked"}
                    for name, data in summary.items()},
        "same_family_top1": family_results,
        "per_query": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name in ("generic", "reviewed", "image"):
        print(f"{name}: top1={result['metrics'][name]['top1']}/{len(targets)} "
              f"top3={result['metrics'][name]['top3']}/{len(targets)} "
              f"same_family={family_results[name]}/{len(targets)}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
