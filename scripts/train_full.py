"""Train the full particle model on train, selecting the checkpoint on validation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.data.tensor_dataset import ParticleTensorDataset
from src.models.encoder import MODEL_NAME, split_embeddings
from src.evaluation.metrics import level_summary
from src.models.full import ParticleFull, decode_full, full_loss
from src.models.levels import (
    add_training_args, check_training_args, level_class_weights, tune_and_choose,
)
from src.models.model import particle_record


ROOT = Path(__file__).resolve().parents[1]


def run_epoch(model, loader, optimizer, device, class_weights=None, light_weight=1.0):
    training = optimizer is not None
    model.train(training)
    totals = {name: 0.0 for name in ("total", "scalars", "curves", "categories", "flags", "levels")}
    for batch in loader:
        batch = {name: value.to(device) for name, value in batch.items()}
        with torch.set_grad_enabled(training):
            losses = full_loss(model(batch["embedding"]), batch, model, class_weights, light_weight)
            if training:
                optimizer.zero_grad()
                losses["total"].backward()
                optimizer.step()
        for name, value in losses.items():
            totals[name] += value.item() * len(batch["embedding"])
    return {name: value / len(loader.dataset) for name, value in totals.items()}


def fingerprint(records):
    return hashlib.sha256("\n".join(record["row_hash"] for record in records).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=473)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--preview", type=Path, default=ROOT / "checkpoints/full_validation_preview.jsonl")
    add_training_args(parser)
    args = parser.parse_args()
    check_training_args(parser, args)
    if min(args.epochs, args.patience, args.batch_size, args.hidden_dim) < 1 or args.lr <= 0:
        parser.error("epochs, patience, batch size, hidden dimension, and learning rate must be positive")
    if args.hidden_dim < 2:
        parser.error("hidden dimension must be at least 2")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_records = load_split("train")
    validation_records = load_split("validation")
    normalizer = Normalizer().fit(train_records)
    train_embeddings = split_embeddings("train", model_name=MODEL_NAME)
    validation_embeddings = split_embeddings("validation", model_name=MODEL_NAME)
    train_data = ParticleTensorDataset("train", normalizer, train_embeddings)
    validation_data = ParticleTensorDataset("validation", normalizer, validation_embeddings)
    train_loader = DataLoader(
        train_data, batch_size=args.batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
    )
    validation_loader = DataLoader(validation_data, batch_size=args.batch_size)
    embedding_dim = train_embeddings.vectors.shape[1]
    model = ParticleFull(normalizer, embedding_dim, args.hidden_dim).to(device)
    class_weights = {name: w.to(device) for name, w in level_class_weights(args.favored_weight).items()}
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    best_loss = float("inf")
    stale = 0
    print(f"device={device} train_effects={len(train_records)} train_prompts={len(train_data)} "
          f"validation={len(validation_data)} outputs={len(normalizer.continuous)} numeric, "
          f"{len(normalizer.categories)} categorical, {len(normalizer.flags)} flags")
    for epoch in range(1, args.epochs + 1):
        train = run_epoch(model, train_loader, optimizer, device, class_weights, args.light_weight)
        validation = run_epoch(model, validation_loader, None, device, class_weights, args.light_weight)
        if not np.isfinite(validation["total"]):
            raise RuntimeError("validation loss is not finite")
        print(f"epoch {epoch:02d} train={train['total']:.4f} val={validation['total']:.4f} "
              f"scalar={validation['scalars']:.4f} curve={validation['curves']:.4f} "
              f"category={validation['categories']:.4f} flags={validation['flags']:.4f} "
              f"levels={validation['levels']:.4f}")
        if validation["total"] < best_loss - 1e-4:
            best_loss = validation["total"]
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    bias = tune_and_choose(model, validation_loader, device, args)
    base_bias, light_bias = bias["base_bias"], bias["light_bias"]
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": best_state,
        "encoder_name": MODEL_NAME,
        "embedding_dim": embedding_dim,
        "hidden_dim": args.hidden_dim,
        "normalizer": normalizer.to_dict(),
        "train_fingerprint": fingerprint(train_records),
        "validation_fingerprint": fingerprint(validation_records),
        "best_epoch": best_epoch,
        "validation_loss": best_loss,
        "seed": args.seed,
        **bias,
    }, args.checkpoint)

    previews = []
    with torch.no_grad():
        for i in np.linspace(0, len(validation_data) - 1, 12, dtype=int):
            sample = validation_data[int(i)]
            output = model(sample["embedding"].unsqueeze(0).to(device))
            prompt = validation_records[int(i)]["prompt"]
            emitter = decode_full(normalizer, output, 0, prompt, base_bias, light_bias)
            previews.append(particle_record(prompt, emitter, f"V{len(previews) + 1:03d}", "FullPreview"))
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    args.preview.write_text(
        "\n".join(json.dumps(record, separators=(",", ":")) for record in previews) + "\n",
        encoding="utf-8",
    )
    with torch.no_grad():
        output = model(torch.stack([item[1] for item in validation_data.items]).to(device))
    prompts = [record["prompt"] for record in validation_records]
    decoded = [decode_full(normalizer, output, i, prompts[i], base_bias, light_bias)
               for i in range(len(prompts))]
    levels = level_summary("LightEmission", [r["emitter"] for r in validation_records], decoded, prompts)
    tuned = bias["tuned_biases"]["LightEmission"]
    print(f"best_epoch={best_epoch} val_loss={best_loss:.4f} checkpoint={args.checkpoint}")
    print(f"LightEmission bias toward 1: base={base_bias:g} light={light_bias:g} (tuned {tuned})")
    print(f"validation LightEmission: accuracy={levels['accuracy']:.3f} "
          f"light prompts={levels['light_prompts']} picked 1={levels['light_favored_rate']:.3f} "
          f"recall of true 1={levels['light_favored_recall']:.3f} confusion={levels['confusion']}")
    print(f"validated {len(previews)} decoded emitters; preview={args.preview}")


if __name__ == "__main__":
    main()
