"""Compare plain and category-aware models on held-out training bases, then fit v2."""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import ConcatDataset, DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.data.tensor_dataset import ParticleTensorDataset
from src.models.encoder import MODEL_NAME, TextEncoder, split_embeddings
from src.models.full import ParticleFull, full_loss
from src.models.v2 import ParticleV2, group_setup, loss_v2
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]
DEV_SPLIT = ROOT / "data/dev_base_ids.json"


class SelectedDataset(Dataset):
    def __init__(self, base: ParticleTensorDataset, allowed: set[str], group_names: list[str]):
        groups = {name: i for i, name in enumerate(group_names)}
        self.base = base
        self.indices = [
            i for i, (record_index, _) in enumerate(base.items)
            if base.records[record_index]["feature_id"] in allowed
        ]
        self.groups = groups

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, index: int) -> dict:
        item = self.indices[index]
        record_index = self.base.items[item][0]
        record = self.base.records[record_index]
        group = record["attachment"]["attributes"]["Category"]
        return {**self.base[item], "group": torch.tensor(self.groups[group])}


class ExtraPrompts(Dataset):
    def __init__(self, path: Path, records: list[dict], normalizer: Normalizer,
                 groups: list[str]):
        source = json.loads(path.read_text(encoding="utf-8"))
        by_id = {record["id"]: record for record in records}
        labels = {name: i for i, name in enumerate(groups)}
        prompts = []
        targets = []
        for entry in source:
            record = by_id.get(entry["id"])
            if record is None:
                continue  # A dev-held-out base must never enter training.
            for prompt in entry["prompts"]:
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError(f"empty prompt for {entry['id']}")
                prompts.append(prompt)
                targets.append({
                    **{key: torch.from_numpy(value) for key, value in normalizer.transform(record).items()},
                    "group": torch.tensor(labels[record["attachment"]["attributes"]["Category"]]),
                })
        self.vectors = TextEncoder().encode(prompts)
        self.targets = targets

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int) -> dict:
        return {"embedding": self.vectors[index], **self.targets[index]}


def epoch(model, loader, optimizer, mode: str, device: torch.device) -> dict[str, float]:
    model.train(optimizer is not None)
    totals = {}
    for batch in loader:
        batch = {key: value.to(device) for key, value in batch.items()}
        with torch.set_grad_enabled(optimizer is not None):
            output = model(batch["embedding"])
            losses = loss_v2(output, batch, model) if mode == "v2" else full_loss(output, batch, model)
            if optimizer is not None:
                optimizer.zero_grad()
                losses["total"].backward()
                optimizer.step()
        for name, value in losses.items():
            totals[name] = totals.get(name, 0.0) + value.item() * len(batch["embedding"])
    return {name: value / len(loader.dataset) for name, value in totals.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plain", "v2"), default="v2")
    parser.add_argument("--dev", action="store_true", help="hold out 20 bases from the train split")
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=473)
    parser.add_argument("--texture-bias", type=float, default=1.5)
    parser.add_argument("--extra-prompts", type=Path,
                        help="optional train-only paraphrases keyed by record id")
    parser.add_argument("--final-epoch", action="store_true",
                        help="save the last epoch to study late-epoch overfitting")
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    if (min(args.epochs, args.patience, args.batch_size, args.hidden_dim) < 1
            or args.lr <= 0 or not 0 <= args.dropout < 1):
        parser.error("training settings must be positive")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    records = load_split("train")
    dev_bases = set(json.loads(DEV_SPLIT.read_text(encoding="utf-8"))["base_ids"]) if args.dev else set()
    train_records = [record for record in records if record["feature_id"] not in dev_bases]
    validation_records = (
        [record for record in records if record["feature_id"] in dev_bases]
        if args.dev else load_split("validation")
    )
    if not train_records or not validation_records:
        raise ValueError("training and validation must both contain effects")
    normalizer = Normalizer().fit(train_records)
    group_names, texture_mask = group_setup(train_records, normalizer)
    train_embeddings = split_embeddings("train", model_name=MODEL_NAME)
    train_base = ParticleTensorDataset("train", normalizer, train_embeddings)
    train_ids = {record["feature_id"] for record in train_records}
    train_data = SelectedDataset(train_base, train_ids, group_names)
    if args.extra_prompts:
        train_data = ConcatDataset([
            train_data, ExtraPrompts(args.extra_prompts, train_records, normalizer, group_names),
        ])
    if args.dev:
        validation_base = ParticleTensorDataset("train", normalizer, train_embeddings, alternates=False)
        validation_data = SelectedDataset(validation_base, dev_bases, group_names)
    else:
        validation_embeddings = split_embeddings("validation", model_name=MODEL_NAME)
        validation_base = ParticleTensorDataset("validation", normalizer, validation_embeddings)
        validation_ids = {record["feature_id"] for record in validation_records}
        validation_data = SelectedDataset(validation_base, validation_ids, group_names)

    train_loader = DataLoader(
        train_data, batch_size=args.batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
    )
    validation_loader = DataLoader(validation_data, batch_size=args.batch_size)
    embedding_dim = train_embeddings.vectors.shape[1]
    if args.mode == "v2":
        model = ParticleV2(
            normalizer, group_names, texture_mask, embedding_dim, args.hidden_dim, args.texture_bias,
        ).to(device)
    else:
        model = ParticleFull(normalizer, embedding_dim, args.hidden_dim).to(device)
    model.backbone[2].p = args.dropout
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    best_loss = float("inf")
    stale = 0
    print(f"device={device} mode={args.mode} dev={args.dev} train={len(train_data)} "
          f"validation={len(validation_data)} groups={len(group_names)}", flush=True)
    for step in range(1, args.epochs + 1):
        train = epoch(model, train_loader, optimizer, args.mode, device)
        validation = epoch(model, validation_loader, None, args.mode, device)
        if not np.isfinite(validation["total"]):
            raise RuntimeError("validation loss is not finite")
        if validation["total"] < best_loss - 1e-4:
            best_loss = validation["total"]
            best_epoch = step
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
        if step == 1 or step % 10 == 0 or (stale >= args.patience and not args.final_epoch):
            print(f"epoch={step} train={train['total']:.4f} val={validation['total']:.4f} "
                  f"best={best_loss:.4f}", flush=True)
        if stale >= args.patience and not args.final_epoch:
            break

    if args.final_epoch:
        best_state = copy.deepcopy(model.state_dict())
        best_epoch = step
        best_loss = validation["total"]

    checkpoint = args.checkpoint or ROOT / "checkpoints" / (
        f"particle_{args.mode}_dev.pt" if args.dev else f"particle_{args.mode}.pt"
    )
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": best_state,
        "architecture": args.mode,
        "encoder_name": MODEL_NAME,
        "embedding_dim": embedding_dim,
        "hidden_dim": args.hidden_dim,
        "normalizer": normalizer.to_dict(),
        "group_names": group_names,
        "texture_bias": args.texture_bias if args.mode == "v2" else 0.0,
        "dropout": args.dropout,
        "train_fingerprint": fingerprint(train_records),
        "validation_fingerprint": fingerprint(validation_records),
        "dev_bases": sorted(dev_bases),
        "best_epoch": best_epoch,
        "validation_loss": best_loss,
        "seed": args.seed,
        "extra_prompts": str(args.extra_prompts) if args.extra_prompts else None,
    }, checkpoint)
    print(f"saved {checkpoint}; best_epoch={best_epoch}", flush=True)


if __name__ == "__main__":
    main()
