"""Train a color-conditioned head without changing the other full-model heads."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
from functools import lru_cache
from pathlib import Path

import torch
import numpy as np
from PIL import Image
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.data.tensor_dataset import record_prompts
from src.models.color import COLORS, color_cue, replace_prompt_color, requested_color, tint_emitter_color
from src.models.encoder import TextEncoder, split_embeddings
from src.models.full_color import ParticleFullColor


ROOT = Path(__file__).resolve().parents[1]
SWAP_COLORS = ("red", "green", "blue", "yellow", "purple", "cyan")


@lru_cache(maxsize=None)
def tintable_texture(texture: str) -> bool:
    path = ROOT / "checkpoints/texture_images" / (texture.split("/")[-1] + ".png")
    if not path.exists():
        return False
    with Image.open(path) as source:
        image = source.convert("RGBA")
        image.thumbnail((96, 96))
        pixels = np.asarray(image)
        opaque = pixels[:, :, 3] > 64
    if not opaque.any():
        return False
    mean_chroma = np.ptp(pixels[:, :, :3][opaque], axis=1).mean()
    return mean_chroma < 18


def examples(records, embeddings, normalizer, augment: bool):
    vectors, cues, targets = [], [], []
    added_prompts, added_cues, added_targets = [], [], []
    color_indices = [i for i, name in enumerate(normalizer.continuous) if name.startswith("Color.")]
    for index, record in enumerate(records):
        for prompt_index, prompt in enumerate(record_prompts(record) if augment else [record["prompt"]]):
            if requested_color(prompt) is None:
                continue
            vectors.append(embeddings[record["row_hash"], prompt_index])
            cues.append(color_cue(prompt))
            targets.append(torch.from_numpy(normalizer.transform(record)["continuous"])[color_indices])
        if not augment or requested_color(record["prompt"]) is None:
            continue
        if not tintable_texture(record["emitter"]["properties"]["Texture"]):
            continue
        original = requested_color(record["prompt"]).name
        choices = [name for name in SWAP_COLORS if name != original]
        for offset in (0, 2):
            replacement = choices[(index + offset) % len(choices)]
            prompt = replace_prompt_color(record["prompt"], replacement)
            recolored = copy.copy(record)
            recolored["emitter"] = tint_emitter_color(record["emitter"], COLORS[replacement])
            added_prompts.append(prompt)
            added_cues.append(color_cue(prompt))
            added_targets.append(torch.from_numpy(normalizer.transform(recolored)["continuous"])[color_indices])
    if added_prompts:
        encoder = TextEncoder(device="cpu")
        vectors.extend(encoder.encode(added_prompts, batch_size=64))
        cues.extend(added_cues)
        targets.extend(added_targets)
    return torch.stack(vectors), torch.tensor(cues, dtype=torch.float32), torch.stack(targets), len(added_prompts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full_color.pt")
    parser.add_argument("--report", type=Path, default=ROOT / "checkpoints/color_training.json")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--seed", type=int, default=473)
    args = parser.parse_args()
    if args.epochs < 1 or args.patience < 1:
        parser.error("epochs and patience must be positive")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    saved = torch.load(args.base, map_location="cpu", weights_only=True)
    if saved.get("architecture") not in (None, "full"):
        raise ValueError("color training requires a plain full-model checkpoint")
    normalizer = Normalizer.from_dict(saved["normalizer"])
    model = ParticleFullColor(normalizer, saved["embedding_dim"], saved["hidden_dim"])
    loaded = model.load_state_dict(saved["model"], strict=False)
    expected = {"color_mean", "color_std", "color_head.weight", "color_head.bias"}
    if set(loaded.missing_keys) != expected or loaded.unexpected_keys:
        raise ValueError("base checkpoint does not match the color model")
    model.initialize_from_full()
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith("color_head."))
    model.eval()

    train_records = load_split("train")
    validation_records = load_split("validation")
    train_embeddings = split_embeddings("train", model_name=saved["encoder_name"])
    validation_embeddings = split_embeddings("validation", model_name=saved["encoder_name"])
    train_vectors, train_cues, train_targets, augmented = examples(
        train_records, train_embeddings, normalizer, augment=True
    )
    val_vectors, val_cues, val_targets, _ = examples(
        validation_records, validation_embeddings, normalizer, augment=False
    )
    with torch.no_grad():
        train_hidden = model.backbone(train_vectors)
        val_hidden = model.backbone(val_vectors)
        curve_rows = [model.curve_indices.index(index) for index in model.color_indices]
        train_base_color = model.curves(train_hidden)[:, curve_rows]
        val_base_color = model.curves(val_hidden)[:, curve_rows]
        base_val_loss = F.smooth_l1_loss(val_base_color, val_targets).item()
    optimizer = torch.optim.AdamW(model.color_head.parameters(), lr=1e-3)
    best_loss = float("inf")
    stale = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        order = torch.randperm(len(train_hidden))
        for indices in order.split(128):
            conditioned = model.predict_color(train_hidden[indices], train_cues[indices])
            prediction = model.select_color(train_base_color[indices], conditioned, train_cues[indices])
            loss = F.smooth_l1_loss(prediction, train_targets[indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            train_prediction = model.select_color(
                train_base_color, model.predict_color(train_hidden, train_cues), train_cues
            )
            val_prediction = model.select_color(
                val_base_color, model.predict_color(val_hidden, val_cues), val_cues
            )
            train_loss = F.smooth_l1_loss(train_prediction, train_targets).item()
            val_loss = F.smooth_l1_loss(val_prediction, val_targets).item()
        history.append({"epoch": epoch, "train_color_loss": train_loss, "validation_color_loss": val_loss})
        print(f"epoch {epoch:02d} train_color={train_loss:.4f} val_color={val_loss:.4f}")
        if val_loss < best_loss - 1e-4:
            best_loss = val_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                break
    model.load_state_dict(best_state)
    bank_fingerprint = hashlib.sha256(
        "\n".join(record["row_hash"] for record in train_records).encode()
    ).hexdigest()
    checkpoint = {**saved, "architecture": "color_v1", "model": best_state,
                  "neighbor_bank_fingerprint": bank_fingerprint,
                  "neighbor_bank_size": len(train_records),
                  "color_training": {"base_checkpoint": args.base.name, "best_epoch": best_epoch,
                                     "validation_color_loss": best_loss, "augmented_prompts": augmented}}
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.checkpoint)
    report = {"train_explicit_prompts": len(train_vectors) - augmented,
              "augmented_prompts": augmented, "validation_explicit_prompts": len(val_vectors),
              "base_validation_color_loss": base_val_loss,
              "best_epoch": best_epoch, "validation_color_loss": best_loss,
              "history": history}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.checkpoint}; best_epoch={best_epoch} val_color={best_loss:.4f}")


if __name__ == "__main__":
    main()
