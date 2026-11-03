"""Fit a texture-only head; use --dev to check whole bases before final fit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.tensor_dataset import record_prompts
from src.models.encoder import MODEL_NAME, split_embeddings
from src.models.texture import TextureHead
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def examples(records, embeddings, classes, alternates):
    index = {name: i for i, name in enumerate(classes)}
    vectors, labels = [], []
    for row in records:
        texture = row["emitter"]["properties"]["Texture"]
        count = len(record_prompts(row)) if alternates else 1
        for prompt_index in range(count):
            vectors.append(embeddings[row["row_hash"], prompt_index])
            labels.append(index.get(texture, -1))
    return torch.stack(vectors), torch.tensor(labels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--kind", choices=("linear", "mlp"), default="linear")
    parser.add_argument("--dropout", type=float, default=0.0)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=473)
    parser.add_argument("--checkpoint", type=Path,
                        default=ROOT / "checkpoints/particle_texture.pt")
    args = parser.parse_args()
    if args.epochs < 1 or not 0 <= args.dropout < 1:
        parser.error("epochs must be positive and dropout must be in [0, 1)")
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    records = load_split("train")
    bases = (set(json.loads((ROOT / "data/dev_base_ids.json").read_text())["base_ids"])
             if args.dev else set())
    train = [row for row in records if row["feature_id"] not in bases]
    dev = [row for row in records if row["feature_id"] in bases]
    classes = sorted({row["emitter"]["properties"]["Texture"] for row in train})
    embeddings = split_embeddings("train", model_name=MODEL_NAME)
    vectors, targets = examples(train, embeddings, classes, True)
    if args.dev:
        dev_vectors, dev_targets = examples(dev, embeddings, classes, False)
    model = TextureHead(classes, vectors.shape[1], args.kind, args.dropout)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=0.05)
    for epoch in range(1, args.epochs + 1):
        model.train()
        for indices in torch.randperm(len(vectors)).split(128):
            loss = F.cross_entropy(model(vectors[indices]), targets[indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        if args.dev:
            model.eval()
            with torch.no_grad():
                correct = (model(dev_vectors).argmax(dim=1) == dev_targets).sum().item()
            print(f"epoch={epoch} development_texture={correct}/{len(dev)} ({correct / len(dev):.3f})")
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": model.state_dict(), "classes": classes, "embedding_dim": vectors.shape[1],
        "kind": args.kind, "dropout": args.dropout, "epochs": args.epochs,
        "seed": args.seed, "encoder_name": MODEL_NAME,
        "train_fingerprint": fingerprint(train), "dev_bases": sorted(bases),
    }, args.checkpoint)
    print(f"saved {args.checkpoint}")


if __name__ == "__main__":
    main()
