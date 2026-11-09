"""Score independently written prompts for the reserved CIX effects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.models.encoder import TextEncoder, split_embeddings
from src.models.nearest_neighbor import build_bank


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path,
                        default=ROOT / "data/cix_new_holdout_prompts.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/cix_new_holdout_evaluation.json")
    args = parser.parse_args()
    targets = json.loads((ROOT / "data/cix_new_holdout_ids.json").read_text())["effect_ids"]
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    if set(queries) != set(targets) or any(not isinstance(queries[key], str) or
                                           not queries[key].strip() for key in targets):
        parser.error("provide one nonempty prompt for each reserved effect ID")
    if len({queries[key].casefold().strip() for key in targets}) != len(targets):
        parser.error("reserved query prompts must have distinct wording")
    catalog = {}
    for path in ("cix_prompt_review.json", "cix_second_prompt_review.json",
                 "cix_new_holdout_catalog.json"):
        more = json.loads((ROOT / "data" / path).read_text(encoding="utf-8"))
        if set(catalog) & set(more):
            parser.error("duplicate CIX catalog ID")
        catalog.update(more)
    if any(queries[key].casefold().strip() == catalog[key].casefold().strip()
           for key in targets):
        parser.error("a query copies its catalog description exactly")
    train = load_split("train")
    if set(targets) & {row["feature_id"] for row in train}:
        parser.error("reserved effects entered training")

    torch.set_num_threads(min(4, torch.get_num_threads()))
    encoder = TextEncoder(device="cpu")
    ids = list(catalog)
    query_vectors = encoder.encode([queries[key] for key in targets])
    descriptions = encoder.encode(list(catalog.values()))
    scores = query_vectors @ descriptions.T
    ranked = scores.topk(3, dim=1).indices.tolist()
    top1 = sum(ids[choices[0]] == target for choices, target in zip(ranked, targets))
    top3 = sum(target in [ids[i] for i in choices]
               for choices, target in zip(ranked, targets))
    bank, _ = build_bank(train, split_embeddings("train", encoder=encoder))
    best_catalog = scores.max(dim=1).values
    best_training = (query_vectors @ bank.T).max(dim=1).values
    selected = (best_catalog >= 0.65) & (best_catalog >= best_training)
    plugin_hits = sum(selected[i].item() and ids[choices[0]] == target
                      for i, (choices, target) in enumerate(zip(ranked, targets)))
    result = {
        "n": len(targets), "catalog_size": len(ids),
        "catalog_top1": top1, "catalog_top3": top3,
        "plugin_catalog_selected": int(selected.sum().item()),
        "plugin_catalog_correct": plugin_hits,
        "per_effect": [
            {"id": target, "query": queries[target],
             "top3": [ids[i] for i in choices], "plugin_selected": bool(selected[index].item())}
            for index, (target, choices) in enumerate(zip(targets, ranked))
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"catalog top1={top1}/{len(targets)} top3={top3}/{len(targets)} "
          f"plugin correct={plugin_hits}/{len(targets)}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
