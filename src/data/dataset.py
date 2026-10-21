"""Read particle JSONL files written by the Roblox exporter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import SPLITS, SchemaError, validate_record


DATA_DIR = Path(__file__).resolve().parent
_HASH_FIELD = re.compile(rb',"row_hash":"([0-9a-f]{16})"(?=,|})')


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SchemaError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise SchemaError(f"invalid JSON number {value}")


def _check_hash(line: str, stored: str) -> None:
    data = line.encode("utf-8")
    match = _HASH_FIELD.search(data)
    if not match or match.group(1).decode("ascii") != stored:
        raise SchemaError("row_hash is missing from the canonical JSON line")
    body = data[:match.start()] + data[match.end():]
    first, second = 2166136261, 5381
    for byte in body:
        first ^= byte
        first = (first * 403 + (first << 24)) & 0xFFFFFFFF
        second = (second * 33 + byte) & 0xFFFFFFFF
    if stored != f"{first:08x}{second:08x}":
        raise SchemaError("row_hash does not match the JSON line")


def load_jsonl(path: str | Path, expected_split: str | None = None) -> list[dict[str, Any]]:
    """Load a file, reporting malformed rows with their line numbers."""
    path = Path(path)
    records = []
    seen = set()
    with path.open(encoding="utf-8") as source:
        for line_number, raw in enumerate(source, start=1):
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            try:
                record = json.loads(
                    line, object_pairs_hook=_unique_keys, parse_constant=_invalid_constant
                )
                validate_record(record, expected_split)
                _check_hash(line, record["row_hash"])
                if record["id"] in seen:
                    raise SchemaError(f"duplicate id {record['id']}")
            except (json.JSONDecodeError, SchemaError) as error:
                raise SchemaError(f"{path}:{line_number}: {error}") from error
            records.append(record)
            seen.add(record["id"])
    return records


def load_split(split: str, data_dir: str | Path = DATA_DIR) -> list[dict[str, Any]]:
    if not isinstance(split, str) or split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {', '.join(sorted(SPLITS))}")
    path = Path(data_dir) / split / f"particles_{split}.jsonl"
    return load_jsonl(path, expected_split=split)


class ParticleDataset:
    """In-memory dataset for one fixed split."""

    def __init__(self, split: str, data_dir: str | Path = DATA_DIR):
        self.split = split
        self.records = load_split(split, data_dir)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.records[index]
