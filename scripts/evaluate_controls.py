"""Check whether simple wording changes move the intended emitter property."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.inference import FullPredictor


ROOT = Path(__file__).resolve().parents[1]
MIN_CHANGE = {
    "Speed.max": 1.0,
    "Size.max": 0.5,
    "Density": 2.0,
    "Lifetime.max": 0.2,
    "SpreadAngle.max": 15.0,
    "Brightness": 0.5,
}


def measure(record: dict, name: str) -> float:
    emitter = record["emitter"]
    props = emitter["properties"]
    if name == "Speed.max" or name == "Lifetime.max":
        return props[name.split(".")[0]]["value"][1]
    if name == "Size.max":
        return max(point[1] for point in props["Size"]["keypoints"])
    if name == "Density":
        return emitter["attributes"]["EmitCount"] or props["Rate"]
    if name == "SpreadAngle.max":
        return max(props["SpreadAngle"]["value"])
    return props[name]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/controlled_evaluation.json")
    args = parser.parse_args()
    pairs = json.loads((ROOT / "data/controlled_prompts.json").read_text(encoding="utf-8"))
    predictor = FullPredictor(args.checkpoint)
    records = predictor.predict_many([prompt for pair in pairs for prompt in (pair["low"], pair["high"])])
    results = []
    for i, pair in enumerate(pairs):
        before, after = records[2 * i], records[2 * i + 1]
        low = measure(before, pair["measure"])
        high = measure(after, pair["measure"])
        delta = high - low
        results.append({**pair, "low_value": low, "high_value": high, "delta": delta,
                        "passes": delta >= MIN_CHANGE[pair["measure"]]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(item['passes'] for item in results)}/{len(results)} controlled changes passed; {args.output}")
    for item in results:
        print(f"  {item['measure']}: {item['delta']:+.2f} "
              f"{'PASS' if item['passes'] else 'MISS'} | {item['high']}")


if __name__ == "__main__":
    main()
