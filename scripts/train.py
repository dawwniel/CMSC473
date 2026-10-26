"""Train the first prompt-to-particle baseline on train and validation only."""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer, inverse
from src.data.tensor_dataset import ParticleTensorDataset
from src.models.encoder import TextEncoder, split_embeddings
from src.models.model import (
    BASELINE_COLUMNS, ParticleBaseline, baseline_loss, decode_prediction,
    particle_record, target_indices, train_defaults,
)


ROOT = Path(__file__).resolve().parents[1]


def run_epoch(model, loader, optimizer, indices, burst_index, device):
    training = optimizer is not None
    model.train(training)
    totals = np.zeros(4, dtype=float)
    for batch in loader:
        batch = {key: value.to(device) for key, value in batch.items()}
        with torch.set_grad_enabled(training):
            prediction = model(batch["embedding"])
            loss, regression, burst = baseline_loss(prediction, batch, indices, burst_index)
            if training:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        size = len(batch["embedding"])
        correct = ((prediction["burst_logit"] >= 0) == (batch["flags"][:, burst_index] >= 0.5)).sum()
        totals += [loss.item() * size, regression.item() * size, burst.item() * size, correct.item()]
    return totals / len(loader.dataset)


def validation_mae(model, loader, normalizer, indices, device):
    totals = np.zeros(len(BASELINE_COLUMNS), dtype=float)
    counts = np.zeros(len(BASELINE_COLUMNS), dtype=float)
    model.eval()
    with torch.no_grad():
        for batch in loader:
            predicted = model(batch["embedding"].to(device))["continuous"].cpu().numpy()
            actual = batch["continuous"][:, indices].numpy()
            masks = batch["continuous_mask"][:, indices].numpy()
            for j, name in enumerate(BASELINE_COLUMNS):
                column = normalizer.columns[name]
                mean, std = normalizer.mean[name], normalizer.std[name]
                before = inverse(column.transform, actual[:, j] * std + mean)
                after = inverse(column.transform, predicted[:, j] * std + mean)
                if column.low is not None:
                    after = np.maximum(after, column.low)
                if column.high is not None:
                    after = np.minimum(after, column.high)
                totals[j] += (np.abs(after - before) * masks[:, j]).sum()
                counts[j] += masks[:, j].sum()
    return {name: float(totals[j] / counts[j]) for j, name in enumerate(BASELINE_COLUMNS)}


def preview_indices(records, per_mode=3):
    selected = []
    used_families = set()
    for burst in (True, False):
        found = 0
        for i, record in enumerate(records):
            family = record["family"]
            is_burst = record["emitter"]["attributes"]["EmitCount"] > 0
            if is_burst == burst and family not in used_families:
                selected.append(i)
                used_families.add(family)
                found += 1
                if found == per_mode:
                    break
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=473)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_baseline.pt")
    parser.add_argument("--preview", type=Path, default=ROOT / "checkpoints/validation_preview.jsonl")
    args = parser.parse_args()
    if args.epochs < 1 or args.patience < 1 or args.batch_size < 1:
        parser.error("epochs, patience, and batch size must be positive")
    if args.hidden_dim < 2:
        parser.error("hidden dimension must be at least 2")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_records = load_split("train")
    normalizer = Normalizer().fit(train_records)
    indices, burst_index = target_indices(normalizer)
    defaults = train_defaults(normalizer, train_records)

    encoder = TextEncoder(device=str(device))
    train_embeddings = split_embeddings("train", encoder)
    validation_embeddings = split_embeddings("validation", encoder)
    train_data = ParticleTensorDataset("train", normalizer, train_embeddings)
    validation_data = ParticleTensorDataset("validation", normalizer, validation_embeddings)
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True, generator=generator)
    validation_loader = DataLoader(validation_data, batch_size=args.batch_size)

    model = ParticleBaseline(encoder.dim, args.hidden_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    best_loss = float("inf")
    best_state = None
    stale_epochs = 0
    print(f"device={device} train={len(train_data)} validation={len(validation_data)} targets={BASELINE_COLUMNS}")
    for epoch in range(1, args.epochs + 1):
        train = run_epoch(model, train_loader, optimizer, indices, burst_index, device)
        validation = run_epoch(model, validation_loader, None, indices, burst_index, device)
        if not np.isfinite(validation[0]):
            raise RuntimeError("validation loss is not finite")
        print(
            f"epoch {epoch:02d} train_loss={train[0]:.4f} val_loss={validation[0]:.4f} "
            f"val_reg={validation[1]:.4f} val_burst_acc={validation[3]:.3f}"
        )
        if validation[0] < best_loss - 1e-4:
            best_loss = validation[0]
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                break

    model.load_state_dict(best_state)
    mae = validation_mae(model, validation_loader, normalizer, indices, device)
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model": best_state,
        "encoder_name": encoder.model_name,
        "embedding_dim": encoder.dim,
        "hidden_dim": args.hidden_dim,
        "normalizer": normalizer.to_dict(),
        "defaults": defaults,
        "columns": list(BASELINE_COLUMNS),
        "best_epoch": best_epoch,
        "validation_loss": float(best_loss),
        "validation_mae": mae,
        "seed": args.seed,
    }, args.checkpoint)

    model.eval()
    previews = []
    with torch.no_grad():
        for number, i in enumerate(preview_indices(validation_data.records), start=1):
            sample = validation_data[i]
            prediction = model(sample["embedding"].unsqueeze(0).to(device))
            emitter = decode_prediction(
                normalizer, prediction["continuous"][0], prediction["burst_logit"][0], defaults,
            )
            previews.append(particle_record(
                validation_data.records[i]["prompt"], emitter, f"V{number:03d}", "BaselinePreview",
            ))
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    args.preview.write_text(
        "\n".join(json.dumps(record, separators=(",", ":")) for record in previews) + "\n",
        encoding="utf-8",
    )
    print(f"best_epoch={best_epoch} val_loss={best_loss:.4f} checkpoint={args.checkpoint}")
    print("validation MAE: " + ", ".join(f"{name}={value:.3f}" for name, value in mae.items()))
    print(f"validated {len(previews)} decoded emitters; preview={args.preview}")


if __name__ == "__main__":
    main()
