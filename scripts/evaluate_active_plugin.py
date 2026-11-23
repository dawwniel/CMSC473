"""Score the Studio plugin's active inference path on the existing test splits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.dataset import load_split
from src.evaluation.full_metrics import summarize_full
from src.models.inference import FullPredictor


def main() -> None:
    predictor = FullPredictor(
        ROOT / "checkpoints/particle_full_color.pt",
        neighbor_texture_threshold=0.6926,
    )
    results = {}
    for split in ("test", "generalization_test"):
        records = load_split(split)
        outputs = predictor.predict_many([row["prompt"] for row in records])
        scores = summarize_full(
            [row["emitter"] for row in records],
            [row["emitter"] for row in outputs],
            predictor.normalizer,
        )
        results[split] = {
            "n": len(records),
            "texture_accuracy": scores["category_accuracy"]["Texture"],
            "burst_accuracy": scores["seven_value_metrics"]["burst_accuracy"],
            "size_mae": scores["curve_mae"]["Size.value"],
            "color_mae": scores["curve_mae"]["Color"],
            "valid_emitters": scores["valid_emitters"],
        }
    output = ROOT / "docs/active_plugin_scores.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
