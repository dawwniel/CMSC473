"""Fit target normalization on train and apply it to any split."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from .targets import (
    CATEGORIES, FLAGS, K, UNKNOWN, Targets, continuous_columns, decode_emitter, encode_targets,
)


ROOT = Path(__file__).resolve().parents[2]
NORMALIZER_PATH = ROOT / "data/processed/normalizer.json"
SAVE_VERSION = 1


def forward(transform: str, values: np.ndarray) -> np.ndarray:
    if transform == "log1p":
        return np.log1p(values)
    if transform == "slog1p":
        return np.sign(values) * np.log1p(np.abs(values))
    return values


def inverse(transform: str, values: np.ndarray) -> np.ndarray:
    if transform == "log1p":
        return np.expm1(values)
    if transform == "slog1p":
        return np.sign(values) * np.expm1(np.abs(values))
    return values


class Normalizer:
    """Train-only statistics for every target column.

    Fields with a single value in train are stored as constants and left out
    of the model's targets. Unseen categories map to index 0, UNKNOWN, which
    decodes to the most common train value.
    """

    def __init__(self, k: int = K):
        self.k = k
        self.columns = {column.name: column for column in continuous_columns(k)}
        self.continuous: list[str] = []
        self.mean: dict[str, float] = {}
        self.std: dict[str, float] = {}
        self.classes: dict[str, list[str]] = {}
        self.fallback: dict[str, str] = {}
        self.flags: list[str] = []
        self.constants: dict[str, dict[str, Any]] = {"continuous": {}, "categories": {}, "flags": {}}

    @property
    def categories(self) -> list[str]:
        return list(self.classes)

    def fit(self, records: Iterable[dict[str, Any]]) -> Normalizer:
        records = list(records)
        if not records:
            raise ValueError("cannot fit on no records")
        if any(record.get("split") != "train" for record in records):
            raise ValueError("fit the normalizer on train records only")
        self.__init__(self.k)
        rows = [encode_targets(record["emitter"], self.k) for record in records]

        for name, column in self.columns.items():
            values = np.array([row.continuous[name] for row in rows])
            values = values[~np.isnan(values)]
            if len(values) == 0 or np.all(values == values[0]):
                self.constants["continuous"][name] = float(values[0]) if len(values) else 0.0
                continue
            transformed = forward(column.transform, values)
            std = float(transformed.std())
            self.continuous.append(name)
            self.mean[name] = float(transformed.mean())
            self.std[name] = std if std > 0 else 1.0

        for name in CATEGORIES:
            counts = Counter(row.categories[name] for row in rows)
            if len(counts) == 1:
                self.constants["categories"][name] = next(iter(counts))
                continue
            self.classes[name] = [UNKNOWN] + sorted(counts)
            self.fallback[name] = counts.most_common(1)[0][0]

        for name in FLAGS:
            values = {row.flags[name] for row in rows}
            if len(values) == 1:
                self.constants["flags"][name] = values.pop()
            else:
                self.flags.append(name)
        return self

    def transform(self, record: dict[str, Any]) -> dict[str, np.ndarray]:
        """Model targets for one record.

        `continuous_mask` is 0 for a column that doesn't apply to this
        emitter's playback mode; its value is then 0.
        """
        targets = encode_targets(record["emitter"], self.k)
        raw = np.array([targets.continuous[name] for name in self.continuous])
        mask = ~np.isnan(raw)
        values = np.zeros(len(raw))
        for i, name in enumerate(self.continuous):
            if mask[i]:
                value = forward(self.columns[name].transform, np.array(raw[i]))
                values[i] = (value - self.mean[name]) / self.std[name]
        categories = [
            self._index(name, targets.categories[name]) for name in self.categories
        ]
        return {
            "continuous": values.astype(np.float32),
            "continuous_mask": mask.astype(np.float32),
            "categories": np.array(categories, dtype=np.int64),
            "flags": np.array([targets.flags[name] for name in self.flags], dtype=np.float32),
        }

    def _index(self, name: str, label: str) -> int:
        classes = self.classes[name]
        try:
            return classes.index(label)
        except ValueError:
            return 0

    def inverse_transform(
        self, continuous: Any, categories: Any, flags: Any, name: str = "ParticleEmitter",
    ) -> dict[str, Any]:
        """Decode one prediction to an emitter node.

        `continuous` is normalized values, `categories` is class indices, and
        `flags` is probabilities or 0/1 values, each in this normalizer's order.
        """
        continuous = np.asarray(continuous, dtype=float)
        targets = Targets()
        targets.continuous.update(self.constants["continuous"])
        for i, column in enumerate(self.continuous):
            value = continuous[i] * self.std[column] + self.mean[column]
            targets.continuous[column] = float(inverse(self.columns[column].transform, np.array(value)))
        targets.categories.update(self.constants["categories"])
        for field, index in zip(self.categories, np.asarray(categories).tolist()):
            label = self.classes[field][int(index)]
            targets.categories[field] = self.fallback[field] if label == UNKNOWN else label
        targets.flags.update(self.constants["flags"])
        for field, value in zip(self.flags, np.asarray(flags, dtype=float).tolist()):
            targets.flags[field] = value >= 0.5
        return decode_emitter(targets, self.k, name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SAVE_VERSION,
            "k": self.k,
            "continuous": [
                {"name": name, "mean": self.mean[name], "std": self.std[name]}
                for name in self.continuous
            ],
            "categories": [
                {"name": name, "classes": self.classes[name], "fallback": self.fallback[name]}
                for name in self.categories
            ],
            "flags": self.flags,
            "constants": self.constants,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Normalizer:
        if data.get("version") != SAVE_VERSION:
            raise ValueError(f"expected normalizer version {SAVE_VERSION}")
        normalizer = cls(data["k"])
        for entry in data["continuous"]:
            if entry["name"] not in normalizer.columns:
                raise ValueError(f"unknown continuous column {entry['name']}")
            normalizer.continuous.append(entry["name"])
            normalizer.mean[entry["name"]] = entry["mean"]
            normalizer.std[entry["name"]] = entry["std"]
        for entry in data["categories"]:
            normalizer.classes[entry["name"]] = entry["classes"]
            normalizer.fallback[entry["name"]] = entry["fallback"]
        normalizer.flags = list(data["flags"])
        normalizer.constants = data["constants"]
        return normalizer

    def save(self, path: str | Path = NORMALIZER_PATH) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path = NORMALIZER_PATH) -> Normalizer:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def fit_train(data_dir: str | Path | None = None) -> Normalizer:
    """Fit on the saved train split."""
    from .dataset import DATA_DIR, load_split

    return Normalizer().fit(load_split("train", data_dir or DATA_DIR))
