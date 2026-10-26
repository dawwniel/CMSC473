"""Build a Studio Command Bar check for predicted particle records."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def lua_string(text: str) -> str:
    for count in range(8):
        marks = "=" * count
        closing = f"]{marks}]"
        if closing not in text:
            return f"[{marks}[{text}{closing}"
    raise ValueError("could not quote prediction JSONL for Luau")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "checkpoints/validation_preview.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/import_check.lua")
    args = parser.parse_args()
    importer = (ROOT / "roblox/importer.lua").read_text(encoding="utf-8")
    rows = args.input.read_text(encoding="utf-8")
    command = (
        "-- Paste into Studio's Command Bar. The emitters stay detached.\n"
        f"local Importer = (function()\n{importer}\nend)()\n"
        f"local records, problems = Importer.parseJsonl({lua_string(rows)})\n"
        'assert(#problems == 0, "prediction JSONL did not parse")\n'
        'assert(#records > 0, "no prediction records")\n'
        'for _, record in ipairs(records) do\n'
        '  local emitter, report = Importer.deserializeEmitter(record)\n'
        '  assert(emitter, record.id .. ": " .. table.concat(report.errors, " | "))\n'
        '  emitter:Destroy()\n'
        'end\n'
        'print("Imported " .. #records .. " predicted emitters")\n'
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(command, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
