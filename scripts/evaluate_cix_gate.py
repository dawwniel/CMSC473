"""Check whether CIX description matches separate from older prompts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.dataset import load_split
from src.models.encoder import TextEncoder, split_embeddings
from src.models.nearest_neighbor import build_bank


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra", type=Path, action="append", default=[],
                        help="additional visually reviewed CIX descriptions")
    args = parser.parse_args()
    reviewed = json.loads((ROOT / "data/cix_prompt_review.json").read_text())
    for path in args.extra:
        extra = json.loads(path.read_text(encoding="utf-8"))
        if set(reviewed) & set(extra):
            parser.error("review files contain duplicate effect IDs")
        reviewed.update(extra)
    holdout = json.loads((ROOT / "data/cix_texture_holdout.json").read_text())["queries"]
    old_dev_ids = set(json.loads((ROOT / "data/dev_base_ids.json").read_text())["base_ids"])
    train = load_split("train")
    negatives = [row["prompt"] for row in train if row["feature_id"] in old_dev_ids]
    fit = [row for row in train if row["feature_id"] not in old_dev_ids]
    encoder = TextEncoder(device="cpu")
    catalog_ids = list(reviewed)
    catalog = encoder.encode(list(reviewed.values()))
    positive_vectors = encoder.encode(list(holdout.values()))
    negative_vectors = encoder.encode(negatives)
    positive_cix = (positive_vectors @ catalog.T).max(dim=1).values
    negative_cix = (negative_vectors @ catalog.T).max(dim=1).values
    embeddings = split_embeddings("train", encoder=encoder)
    bank, _ = build_bank(fit, embeddings)
    positive_margin = positive_cix - (positive_vectors @ bank.T).max(dim=1).values
    negative_margin = negative_cix - (negative_vectors @ bank.T).max(dim=1).values
    print(f"catalog textures={len(reviewed)} CIX queries={len(positive_cix)} "
          f"older development prompts={len(negative_cix)}")
    print(f"positive score range={positive_cix.min():.3f}..{positive_cix.max():.3f}")
    print(f"negative score range={negative_cix.min():.3f}..{negative_cix.max():.3f}")
    for threshold in (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        print(f"threshold={threshold:.2f} CIX accepted={(positive_cix >= threshold).sum().item()}/{len(positive_cix)} "
              f"older prompts overridden={(negative_cix >= threshold).sum().item()}/{len(negative_cix)}")
    for margin in (0.0, 0.025, 0.05, 0.075):
        positive = (positive_cix >= 0.65) & (positive_margin >= margin)
        negative = (negative_cix >= 0.65) & (negative_margin >= margin)
        print(f"score>=0.65 margin>={margin:.3f} CIX accepted={positive.sum().item()}/{len(positive)} "
              f"older prompts overridden={negative.sum().item()}/{len(negative)}")
    selected = (positive_cix >= 0.65) & (positive_margin >= 0)
    winners = (positive_vectors @ catalog.T).argmax(dim=1).tolist()
    hits = sum(accepted and catalog_ids[winner] == target for accepted, winner, target in
               zip(selected.tolist(), winners, holdout))
    print(f"selected CIX gate exact hits={hits}/{len(holdout)}")
    full_bank, _ = build_bank(train, embeddings)
    for split in ("test", "generalization_test"):
        vectors = encoder.encode([row["prompt"] for row in load_split(split)])
        cix = (vectors @ catalog.T).max(dim=1).values
        base = (vectors @ full_bank.T).max(dim=1).values
        activated = (cix >= 0.65) & (cix >= base)
        print(f"{split} catalog overrides={activated.sum().item()}/{len(vectors)}")


if __name__ == "__main__":
    main()
