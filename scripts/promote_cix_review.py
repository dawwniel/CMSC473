"""Add visually reviewed CIX emitters to the training JSONL file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_jsonl


ROOT = Path(__file__).resolve().parents[1]


def canonical(record: dict) -> str:
    body = {key: value for key, value in record.items() if key != "row_hash"}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    first, second = 2166136261, 5381
    for byte in encoded.encode("utf-8"):
        first ^= byte
        first = (first * 403 + (first << 24)) & 0xFFFFFFFF
        second = (second * 33 + byte) & 0xFFFFFFFF
    record["row_hash"] = f"{first:08x}{second:08x}"
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="canonical export containing the effects being promoted")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "src/data/train/particles_train.jsonl")
    args = parser.parse_args()

    reviewed = json.loads((ROOT / "data/cix_prompt_review.json").read_text(encoding="utf-8"))
    source = {row["feature_id"]: row for row in load_jsonl(args.source)}
    current = load_jsonl(args.output, "train")
    known_ids = {row["id"] for row in current}
    added = []
    for effect_id, prompt in reviewed.items():
        row = source[effect_id]
        if row["id"] in known_ids:
            raise ValueError(f"already in train: {effect_id}")
        row["attachment"]["attributes"]["Split"] = "train"
        row["split"] = "train"
        row["prompt"] = prompt
        labels = [child for child in row["prompt_gui"]["children"]
                  if child["class"] == "TextLabel"]
        if len(labels) != 1:
            raise ValueError(f"expected one prompt label: {effect_id}")
        labels[0]["properties"]["Text"] = prompt
        added.append(row)

    lines = [canonical(row) for row in current + sorted(added, key=lambda x: x["id"])]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    load_jsonl(args.output, "train")
    print(f"added {len(added)} reviewed effects; train now has {len(lines)} rows")


if __name__ == "__main__":
    main()
