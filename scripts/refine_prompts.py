"""Prepare reviewed prompt wording and update the matching JSONL rows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import DATA_DIR, _check_hash, load_split
from src.data.schema import validate_record
from src.data.tensor_dataset import record_prompts


ROOT = Path(__file__).resolve().parents[1]
HASH = re.compile(r',"row_hash":"([0-9a-f]{16})"(?=,|})')

# These distinctions were checked against the base effects in Studio.
DESCRIPTIONS = {
    "F002": ("flickering fire", "ragged flickering fire"),
    "F003": ("flickering fire", "curled flickering fire"),
    "F004": ("flame plume", "soft smoky flame plume"),
    "F008": ("flame plume", "compact glowing flame plume"),
    "F010": ("fire arc", "broad smoky fire arc"),
    "F011": ("fire arc", "curling ember fire arc"),
    "F012": ("flame plume", "dense ragged flame plume"),
    "F013": ("flame plume", "rising tongue-like flame plume"),
    "F014": ("flame plume", "pale layered flame plume"),
    "F015": ("flame plume", "flat streaking flame plume"),
    "F019": ("smoke puff", "hollow smoke-ring puff"),
    "F020": ("smoke puff", "round compact smoke puff"),
    "F023": ("smoke puff", "diffuse billowing smoke puff"),
    "F029": ("prismatic smoky mist", "compact prismatic smoky mist"),
    "F032": ("colored smoke", "billowing colored smoke"),
    "F037": ("sparkle cloud", "needle-like sparkle cloud"),
    "F038": ("sparkle cloud", "curled sparkle cloud"),
    "F039": ("sparkle cloud", "orb-like sparkle cloud"),
    "F040": ("sparkle cloud", "long streaking sparkle cloud"),
    "F046": ("lightning arc", "jagged lightning arc"),
    "F048": ("lightning arc", "faint thin lightning arc"),
    "F052": ("electric surge", "angular lattice electric surge"),
    "F053": ("electric surge", "coiled electric surge"),
    "F054": ("electric surge", "thin branching electric surge"),
    "F058": ("electric storm", "diffuse electric storm"),
    "F068": ("healing ring", "jagged healing ring"),
    "F069": ("sword slash", "thick crescent sword slash"),
    "F072": ("healing ring", "smooth circular healing ring"),
    "F073": ("sword slash", "thin layered sword slash"),
    "F075": ("explosion burst", "cloudlike explosion burst"),
    "F077": ("impact flash", "four-pointed impact flash"),
    "F078": ("shockwave ring", "spiky shockwave ring"),
    "F079": ("impact flash", "brief glint impact flash"),
    "F080": ("explosion burst", "thin crescent explosion burst"),
    "F081": ("impact flash", "starburst impact flash"),
    "F082": ("shockwave ring", "smooth circular shockwave ring"),
    "F083": ("shockwave ring", "soft glowing shockwave ring"),
    "F084": ("impact mark", "sharp impact slash mark"),
    "F085": ("impact mark", "lingering impact slash mark"),
    "F088": ("explosion burst", "soft glowing explosion burst"),
    "F090": ("impact mark", "spiky circular impact mark"),
    "F100": ("water stream", "turbulent foamy water stream"),
    "F102": ("water splash", "droplet-filled water splash"),
    "F103": ("water stream", "bubbly water stream"),
    "F129": ("energy wave", "airy energy wave"),
    "F130": ("energy wave", "thin energy wave"),
}


def refine(text: str, feature_id: str) -> str:
    old, new = DESCRIPTIONS[feature_id]
    revised = re.sub(r"\b" + re.escape(old) + r"\b", new, text)
    if revised == text:
        raise ValueError(f"{feature_id}: {old!r} was not found in {text!r}")
    article = "an" if new[0].lower() in "aeiou" else "a"
    revised = re.sub(r"\b(?:a|an) (?=" + re.escape(new) + r"\b)", article + " ", revised)
    return revised


def patches() -> list[dict]:
    changes = []
    for split in ("train", "validation"):
        for record in load_split(split):
            feature_id = record.get("feature_id")
            if feature_id in DESCRIPTIONS:
                old = record_prompts(record)
                replacement = DESCRIPTIONS[feature_id][1]
                if all(re.search(r"\b" + re.escape(replacement) + r"\b", prompt) for prompt in old):
                    continue
                if any(re.search(r"\b" + re.escape(replacement) + r"\b", prompt) for prompt in old):
                    raise ValueError(f"{record['id']}: prompts are only partly refined")
                new = [refine(prompt, feature_id) for prompt in old]
                changes.append({"id": record["id"], "split": split, "old": old, "new": new})
    return changes


def hash_body(body: str) -> str:
    first, second = 2166136261, 5381
    for byte in body.encode("utf-8"):
        first ^= byte
        first = (first * 403 + (first << 24)) & 0xFFFFFFFF
        second = (second * 33 + byte) & 0xFFFFFFFF
    return f"{first:08x}{second:08x}"


def update_line(line: str, patch: dict) -> str:
    for old, new in zip(patch["old"], patch["new"]):
        before = json.dumps(old, ensure_ascii=False)
        after = json.dumps(new, ensure_ascii=False)
        if before not in line:
            raise ValueError(f"{patch['id']}: prompt was not found in canonical row")
        line = line.replace(before, after)
    match = HASH.search(line)
    if match is None:
        raise ValueError(f"{patch['id']}: canonical row hash is missing")
    body = line[:match.start()] + line[match.end():]
    line = line[:match.start(1)] + hash_body(body) + line[match.end(1):]
    record = json.loads(line)
    validate_record(record, patch["split"])
    _check_hash(line, record["row_hash"])
    return line


def update_files(changes: list[dict]) -> None:
    by_id = {change["id"]: change for change in changes}
    for split in ("train", "validation"):
        path = DATA_DIR / split / f"particles_{split}.jsonl"
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            record_id = json.loads(line)["id"]
            rows.append(update_line(line, by_id[record_id]) if record_id in by_id else line)
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        load_split(split)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/prompt_edits.json")
    parser.add_argument("--write-jsonl", action="store_true", help="apply the edits to train and validation JSONL")
    args = parser.parse_args()
    changes = patches()
    if not changes:
        print("prompt edits are already applied")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    if args.write_jsonl:
        update_files(changes)
    print(f"prepared {len(changes)} prompt edits in {args.output}")
    if args.write_jsonl:
        print("updated train and validation JSONL")


if __name__ == "__main__":
    main()
