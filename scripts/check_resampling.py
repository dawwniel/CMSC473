"""Report how closely K resampled points reproduce the saved train curves.

Run from the CMSC473 directory:

    python scripts/check_resampling.py --k 4 6 8 12 16
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split
from src.data.targets import COLORS, SEQUENCES, resample, sample_times


DENSE = 1001


def curve_error(points: np.ndarray, column: int, k: int) -> tuple[float, float]:
    """Mean and largest gap between the original curve and its K-point rebuild."""
    original = resample(points[:, 0], points[:, column], DENSE)
    rebuilt = np.interp(np.linspace(0, 1, DENSE), sample_times(k), resample(points[:, 0], points[:, column], k))
    gap = np.abs(original - rebuilt)
    return float(gap.mean()), float(gap.max())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--k", type=int, nargs="+", default=[8])
    args = parser.parse_args()
    records = load_split("train")

    curves = []
    for name in SEQUENCES:
        curves += [(f"{name}.value", name, 1), (f"{name}.envelope", name, 2)]
    for name in COLORS:
        curves += [(f"{name}.{channel}", name, i) for i, channel in enumerate("rgb", start=1)]

    # Errors are a fraction of the curve's train range. "mean" averages each
    # row's mean gap; "worst" counts rows whose largest gap exceeds 5%.
    print(f"{'curve':22} {'K':>3} {'mean':>7} {'p95':>7} {'worst>5%':>9}")
    for label, prop, column in curves:
        points = [np.asarray(r["emitter"]["properties"][prop]["keypoints"], dtype=float) for r in records]
        values = np.concatenate([p[:, column] for p in points])
        scale = max(float(values.max() - values.min()), 1e-9)
        for k in args.k:
            errors = np.array([curve_error(p, column, k) for p in points]) / scale
            mean, worst = errors[:, 0], errors[:, 1]
            print(
                f"{label:22} {k:>3} {mean.mean():7.2%} {np.percentile(mean, 95):7.2%} "
                f"{int((worst > 0.05).sum()):>5}/{len(points)}"
            )


if __name__ == "__main__":
    main()
