"""Pair the earlier model with the reviewed CIX texture lookup set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from train_full import fingerprint


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path,
                        default=ROOT / "checkpoints/particle_full_before_cix.pt")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/particle_full.pt")
    args = parser.parse_args()

    saved = torch.load(args.model, map_location="cpu", weights_only=True)
    train = load_split("train")
    saved["neighbor_bank_fingerprint"] = fingerprint(train)
    saved["neighbor_bank_size"] = len(train)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(saved, args.output)
    print(f"saved {args.output} with {len(train)} texture lookup effects")


if __name__ == "__main__":
    main()
