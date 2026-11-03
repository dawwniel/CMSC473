"""Write one full-model prediction as a Roblox importer record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.inference import FullPredictor


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="description of the effect")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/full_prediction.jsonl")
    parser.add_argument("--neighbor-texture-threshold", type=float, default=0.6926)
    parser.add_argument("--no-neighbor-texture", action="store_true")
    args = parser.parse_args()
    if not args.prompt.strip():
        parser.error("prompt cannot be blank")

    record = FullPredictor(
        args.checkpoint,
        None if args.no_neighbor_texture else args.neighbor_texture_threshold,
    ).predict(args.prompt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")

    emitter = record["emitter"]
    properties = emitter["properties"]
    print(f"saved {args.output}")
    print(f"{record['playback_mode']}: EmitCount={emitter['attributes']['EmitCount']}, "
          f"Rate={properties['Rate']:.2f}, Texture={properties['Texture']}, "
          f"Speed={properties['Speed']['value']}")


if __name__ == "__main__":
    main()
