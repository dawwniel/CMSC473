"""Turn one prompt into a Luau-importable particle record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.normalize import Normalizer
from src.models.encoder import TextEncoder
from src.data.light import is_light_prompt
from src.models.model import ParticleBaseline, decode_prediction, output_row, particle_record


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="description of the effect")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_baseline.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/prediction.jsonl")
    parser.add_argument("--base-bias", type=float, default=None,
                        help="override the checkpoint's LightEmission bias for non-light prompts")
    parser.add_argument("--light-bias", type=float, default=None,
                        help="override the checkpoint's LightEmission bias for light prompts; inf always picks 1")
    args = parser.parse_args()
    if not args.prompt.strip():
        parser.error("prompt cannot be blank")

    torch.set_num_threads(min(4, torch.get_num_threads()))
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    normalizer = Normalizer.from_dict(saved["normalizer"])
    model = ParticleBaseline(saved["embedding_dim"], saved["hidden_dim"])
    model.load_state_dict(saved["model"])
    model.eval()
    base_bias = saved["base_bias"] if args.base_bias is None else args.base_bias
    light_bias = saved["light_bias"] if args.light_bias is None else args.light_bias
    encoder = TextEncoder(saved["encoder_name"], device="cpu")
    with torch.no_grad():
        output = model(encoder.encode([args.prompt]))
        emitter = decode_prediction(
            normalizer, output_row(output, 0), saved["defaults"], args.prompt, base_bias, light_bias,
        )
    record = particle_record(args.prompt, emitter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")

    properties = emitter["properties"]
    count = emitter["attributes"]["EmitCount"]
    print(f"saved {args.output}")
    print(
        f"{record['playback_mode']}: EmitCount={count}, Rate={properties['Rate']:.2f}, "
        f"Speed={properties['Speed']['value']}, Lifetime={properties['Lifetime']['value']}, "
        f"Brightness={properties['Brightness']:.2f}, LightEmission={properties['LightEmission']:g} "
        f"(light prompt: {is_light_prompt(args.prompt)})"
    )


if __name__ == "__main__":
    main()
