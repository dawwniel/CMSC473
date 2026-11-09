"""Compare text lookup with image retrieval on held-out development bases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import torch
from PIL import Image, ImageStat
from torch.nn.functional import normalize
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.models.encoder import MODEL_NAME, split_embeddings
from src.models.nearest_neighbor import build_bank


ROOT = Path(__file__).resolve().parents[1]


def texture_id(record: dict) -> str:
    texture = record["emitter"]["properties"]["Texture"]
    matches = re.findall(r"[0-9]+", texture)
    if not matches:
        raise ValueError(f"texture has no numeric asset ID: {texture}")
    return matches[-1]


def representative_image(path: Path, layout: str) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    grid = re.fullmatch(r"Grid(\d+)x(\d+)", layout)
    if grid:
        columns, rows = map(int, grid.groups())
        width, height = image.size
        frames = [image.crop((column * width // columns, row * height // rows,
                              (column + 1) * width // columns,
                              (row + 1) * height // rows))
                  for row in range(rows) for column in range(columns)]
        def visible_mass(frame: Image.Image) -> float:
            alpha = frame.getchannel("A")
            if alpha.getextrema()[0] < 250:
                return ImageStat.Stat(alpha).sum[0]
            return ImageStat.Stat(frame.convert("L")).sum[0]
        image = max(frames, key=visible_mass)
    bounds = image.getchannel("A").getbbox()
    if bounds:
        image = image.crop(bounds)
    background = Image.new("RGBA", image.size, (20, 24, 33, 255))
    return Image.alpha_composite(background, image).convert("RGB")


def rank(scores: torch.Tensor, candidates: list[str], truth: list[str]) -> dict:
    top = scores.topk(min(3, len(candidates)), dim=1).indices.tolist()
    first = [candidates[indexes[0]] for indexes in top]
    return {
        "top1": sum(prediction == actual for prediction, actual in zip(first, truth)) / len(truth),
        "top3": sum(actual in [candidates[i] for i in indexes]
                    for indexes, actual in zip(top, truth)) / len(truth),
        "correct": sum(prediction == actual for prediction, actual in zip(first, truth)),
        "predictions": first,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=ROOT / "checkpoints/texture_images")
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/texture_retrieval_dev.json")
    args = parser.parse_args()
    torch.set_num_threads(min(4, torch.get_num_threads()))

    dev_ids = set(json.loads((ROOT / "data/dev_base_ids.json").read_text())["base_ids"])
    records = load_split("train")
    dev = [row for row in records if row["feature_id"] in dev_ids]
    fit = [row for row in records if row["feature_id"] not in dev_ids]
    candidate_ids = sorted({texture_id(row) for row in fit
                            if (args.images / f"{texture_id(row)}.png").exists()})
    candidate_set = set(candidate_ids)
    fit = [row for row in fit if texture_id(row) in candidate_set]
    layouts = {}
    for row in fit:
        asset_id = texture_id(row)
        layout = row["emitter"]["properties"]["FlipbookLayout"]["value"]
        if asset_id not in layouts or layouts[asset_id] == "None":
            layouts[asset_id] = layout
    truth = [texture_id(row) for row in dev]
    print(f"development effects={len(dev)} bases={len(dev_ids)} "
          f"candidate textures={len(candidate_ids)} unavailable={sum(t not in candidate_set for t in truth)}")

    embeddings = split_embeddings("train", model_name=MODEL_NAME)
    bank, owners = build_bank(fit, embeddings)
    queries = torch.stack([embeddings[row["row_hash"], 0] for row in dev])
    prompt_scores = queries @ bank.T
    text_scores = torch.empty((len(dev), len(candidate_ids)))
    texture_columns = {}
    for column, (record_index, _) in enumerate(owners):
        texture_columns.setdefault(texture_id(fit[record_index]), []).append(column)
    for index, asset_id in enumerate(candidate_ids):
        text_scores[:, index] = prompt_scores[:, texture_columns[asset_id]].max(dim=1).values
    text_result = rank(text_scores, candidate_ids, truth)

    processor = CLIPProcessor.from_pretrained(args.model)
    model = CLIPModel.from_pretrained(args.model).eval()
    image_vectors = []
    with torch.no_grad():
        for start in range(0, len(candidate_ids), 16):
            batch = []
            for asset_id in candidate_ids[start:start + 16]:
                batch.append(representative_image(
                    args.images / f"{asset_id}.png", layouts[asset_id]))
            pixels = processor(images=batch, return_tensors="pt")["pixel_values"]
            features = model.get_image_features(pixel_values=pixels)
            image_vectors.append(normalize(features.pooler_output, dim=1))
            print(f"encoded images {min(start + len(batch), len(candidate_ids))}/{len(candidate_ids)}")
        image_vectors = torch.cat(image_vectors)
        prompt_vectors = []
        for start in range(0, len(dev), 32):
            batch = processor(text=[row["prompt"] for row in dev[start:start + 32]],
                              padding=True, truncation=True, return_tensors="pt")
            features = model.get_text_features(**batch)
            prompt_vectors.append(normalize(features.pooler_output, dim=1))
        clip_scores = torch.cat(prompt_vectors) @ image_vectors.T
    image_result = rank(clip_scores, candidate_ids, truth)

    results = {
        "development_effects": len(dev),
        "development_bases": len(dev_ids),
        "candidate_textures": len(candidate_ids),
        "unavailable_true_texture_effects": sum(t not in candidate_set for t in truth),
        "text_lookup": {key: value for key, value in text_result.items() if key != "predictions"},
        "clip_image_retrieval": {key: value for key, value in image_result.items()
                                 if key != "predictions"},
        "per_effect": [
            {"id": row["id"], "texture": actual, "text_prediction": text_prediction,
             "image_prediction": image_prediction}
            for row, actual, text_prediction, image_prediction in zip(
                dev, truth, text_result["predictions"], image_result["predictions"])
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for name in ("text_lookup", "clip_image_retrieval"):
        result = results[name]
        print(f"{name}: top1={result['top1']:.3f} top3={result['top3']:.3f} "
              f"correct={result['correct']}/{len(dev)}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
