"""Keep the selected CIX texture development effects out of model training."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_jsonl


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "src/data/train/particles_train.jsonl"


def main() -> None:
    holdout = set(json.loads((ROOT / "data/cix_texture_holdout.json").read_text())["queries"])
    rows = load_jsonl(TRAIN, "train")
    kept = [row for row in rows if row["feature_id"] not in holdout]
    removed = len(rows) - len(kept)
    if removed not in (0, len(holdout)):
        raise ValueError(f"expected 0 or {len(holdout)} held-out rows, found {removed}")
    if removed:
        TRAIN.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")) for row in kept) + "\n",
                         encoding="utf-8", newline="\n")
        load_jsonl(TRAIN, "train")
    print(f"held out {len(holdout)} CIX effects; train has {len(kept)} rows")


if __name__ == "__main__":
    main()
