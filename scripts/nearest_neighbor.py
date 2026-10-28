"""Score a nearest-neighbor baseline: each prompt copies its closest training prompt's emitter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.tensor_dataset import record_prompts
from src.evaluation.metrics import FIELDS, summarize, values
from src.models.encoder import split_embeddings
from src.models.nearest_neighbor import build_bank, nearest


ROOT = Path(__file__).resolve().parents[1]
DUPLICATE_SIMILARITY = 0.999


def evaluate(split: str, train: list[dict], bank: torch.Tensor, owners: list[tuple[int, int]]) -> tuple[dict, list[dict]]:
    records = load_split(split)
    embeddings = split_embeddings(split)
    queries = torch.stack([embeddings[record["row_hash"], 0] for record in records])
    indices, similarities = nearest(queries, bank)

    matches, predictions = [], []
    for record, index, similarity in zip(records, indices.tolist(), similarities.tolist()):
        record_index, prompt_index = owners[index]
        match = train[record_index]
        predictions.append(match["emitter"])
        truth, guess = values(record["emitter"]), values(match["emitter"])
        matches.append({
            "id": record["id"],
            "row_hash": record["row_hash"],
            "prompt": record["prompt"],
            "match_id": match["id"],
            "match_row_hash": match["row_hash"],
            "match_prompt_index": prompt_index,
            "match_prompt": record_prompts(match)[prompt_index],
            "similarity": similarity,
            "same_family": record["family"] == match["family"],
            "burst_correct": (truth["EmitCount"] > 0) == (guess["EmitCount"] > 0),
            "abs_error": {field: abs(truth[field] - guess[field]) for field in FIELDS},
        })

    scores = summarize([record["emitter"] for record in records], predictions)
    scores["mean_similarity"] = similarities.mean().item()
    scores["near_duplicates"] = int((similarities >= DUPLICATE_SIMILARITY).sum())
    scores["same_family"] = sum(match["same_family"] for match in matches) / len(matches)
    return scores, matches


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/nearest_neighbor.json")
    parser.add_argument("--splits", nargs="+", choices=("train", "validation", "test", "generalization_test"),
                        default=("test", "generalization_test"))
    parser.add_argument("--main-only", action="store_true", help="leave training alternates out of the bank")
    args = parser.parse_args()

    train = load_split("train")
    bank, owners = build_bank(train, split_embeddings("train"), alternates=not args.main_only)

    results = {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for split in args.splits:
        scores, matches = evaluate(split, train, bank, owners)
        results[split] = scores
        path = args.output.with_name(f"{args.output.stem}_matches_{split}.jsonl")
        path.write_text("".join(json.dumps(match) + "\n" for match in matches), encoding="utf-8")
        print(f"saved {path}")
    args.output.write_text(json.dumps({"bank_size": len(owners), **results}, indent=2) + "\n", encoding="utf-8")

    print(f"bank: {len(owners)} training prompts")
    for split, scores in results.items():
        print(f"{split}: n={scores['samples']} burst_accuracy={scores['burst_accuracy']:.3f} "
              f"mean_similarity={scores['mean_similarity']:.3f} same_family={scores['same_family']:.3f} "
              f"near_duplicates={scores['near_duplicates']}")
        for field, error in scores["mae"].items():
            print(f"  {field}: MAE={error:.3f}")
        for field, error in scores["active_mae"].items():
            if error is not None:
                print(f"  {field} when active: MAE={error:.3f}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
