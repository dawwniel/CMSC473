"""Find prompts that describe more than one emitter configuration."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.tensor_dataset import record_prompts


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "validation", "test", "generalization_test")


def key(text: str) -> str:
    return " ".join(text.casefold().split())


def emitter_key(record: dict) -> str:
    emitter = record["emitter"]
    return json.dumps(
        [emitter["properties"], emitter["attributes"]["EmitCount"]],
        sort_keys=True,
        separators=(",", ":"),
    )


def audit() -> dict:
    groups = defaultdict(list)
    for split in SPLITS:
        for record in load_split(split):
            for prompt_index, prompt in enumerate(record_prompts(record)):
                groups[key(prompt)].append({
                    "id": record["id"],
                    "split": split,
                    "prompt_index": prompt_index,
                    "prompt": prompt,
                    "emitter_key": emitter_key(record),
                })

    conflicts = []
    for prompt, entries in groups.items():
        if len({entry["id"] for entry in entries}) < 2:
            continue
        if len({entry["emitter_key"] for entry in entries}) < 2:
            continue
        conflicts.append({
            "prompt": prompt,
            "entries": [
                {field: value for field, value in entry.items() if field != "emitter_key"}
                for entry in entries
            ],
        })

    heldout_main = {}
    train_prompts = {prompt for prompt, entries in groups.items() if any(e["split"] == "train" for e in entries)}
    for split in ("test", "generalization_test"):
        heldout_main[split] = sum(
            key(record["prompt"]) in train_prompts for record in load_split(split)
        )
    return {
        "conflicting_prompt_groups": len(conflicts),
        "heldout_main_matching_train_text": heldout_main,
        "conflicts": sorted(conflicts, key=lambda group: group["prompt"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/prompt_audit.json")
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"conflicting prompt groups: {report['conflicting_prompt_groups']}")
    for split, count in report["heldout_main_matching_train_text"].items():
        print(f"{split} main prompts matching any train wording: {count}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
