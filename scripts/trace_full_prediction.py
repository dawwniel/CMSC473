"""Save the intermediate values for one full-model prediction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.inference import FullPredictor
from src.models.color import color_cue, requested_color
from src.models.full import decode_full
from src.models.full_color import ParticleFullColor


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full_color.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "presentation/prompt_trace.json")
    args = parser.parse_args()

    predictor = FullPredictor(args.checkpoint, neighbor_texture_threshold=0.6926)
    with torch.no_grad():
        embedding = predictor.encoder.encode([args.prompt])
        hidden = predictor.model.backbone(embedding)
        if isinstance(predictor.model, ParticleFullColor):
            heads = predictor.model(embedding, torch.tensor([color_cue(args.prompt)]))
        else:
            heads = predictor.model(embedding)
    normalizer = predictor.normalizer
    continuous = heads["continuous"][0].tolist()
    categories = {}
    for name, logits in heads["categories"].items():
        values = logits[0]
        probabilities = values.softmax(dim=0)
        winner = int(probabilities.argmax())
        categories[name] = {
            "selected": normalizer.classes[name][winner],
            "confidence": probabilities[winner].item(),
            "classes": [
                {"name": label, "logit": logit, "probability": probability}
                for label, logit, probability in zip(
                    normalizer.classes[name], values.tolist(), probabilities.tolist()
                )
            ],
        }
    flag_logits = heads["flags"][0]
    flag_probabilities = flag_logits.sigmoid()
    record = predictor.predict(args.prompt)
    trace = {
        "prompt": args.prompt,
        "checkpoint": args.checkpoint.name,
        "encoder": predictor.encoder.model_name,
        "embedding": embedding[0].tolist(),
        "embedding_length": embedding.shape[1],
        "embedding_l2_norm": embedding[0].norm().item(),
        "backbone_128": hidden[0].tolist(),
        "color_cue": color_cue(args.prompt),
        "requested_color": requested_color(args.prompt).name if requested_color(args.prompt) else None,
        "model_emitter": decode_full(normalizer, heads),
        "model_color_method": "keep matching shade; project conflicting hue from explicit color cue",
        "heads": {
            "numbers_normalized": {
                normalizer.continuous[i]: continuous[i]
                for i in predictor.model.scalar_indices
            },
            "curves_normalized": {
                normalizer.continuous[i]: continuous[i]
                for i in predictor.model.curve_indices
            },
            "categories": categories,
            "flags": {
                name: {
                    "logit": flag_logits[i].item(),
                    "probability": flag_probabilities[i].item(),
                    "selected": flag_probabilities[i].item() >= 0.5,
                }
                for i, name in enumerate(normalizer.flags)
            },
        },
        "final_record": record,
        "texture_changed_after_head": (
            categories["Texture"]["selected"] != record["emitter"]["properties"]["Texture"]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {args.output}")
    print(f"Embedding: {trace['embedding_length']} values, L2 norm {trace['embedding_l2_norm']:.6f}")
    print(f"Final texture: {record['emitter']['properties']['Texture']}")


if __name__ == "__main__":
    main()
