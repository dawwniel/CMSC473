"""Build a Studio Command Bar preview for one predicted particle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_prediction_check import lua_string


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "checkpoints/prediction.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/preview_command.lua")
    args = parser.parse_args()

    rows = args.input.read_text(encoding="utf-8")
    records = [json.loads(line) for line in rows.splitlines() if line.strip()]
    if len(records) != 1:
        parser.error("preview input must contain exactly one JSONL record")

    importer = (ROOT / "roblox/importer.lua").read_text(encoding="utf-8")
    command = (
        "-- Paste into Roblox Studio's Command Bar. Delete the preview folder when done.\n"
        f"local Importer = (function()\n{importer}\nend)()\n"
        f"local records, problems = Importer.parseJsonl({lua_string(rows)})\n"
        'assert(#problems == 0 and #records == 1, "expected one valid prediction")\n'
        'local record = records[1]\n'
        'local attachment, report = Importer.deserialize(record)\n'
        'assert(attachment, record.id .. ": " .. table.concat(report.errors, " | "))\n'
        'local emitter = attachment:FindFirstChild(record.emitter.name)\n'
        'assert(emitter and emitter:IsA("ParticleEmitter"), "predicted emitter is missing")\n'
        'local camera = assert(workspace.CurrentCamera, "Studio camera is unavailable")\n'
        'local folder = Instance.new("Folder")\n'
        'folder.Name = "Prompt2ParticlesPreview"\n'
        'local anchor = Instance.new("Part")\n'
        'anchor.Name = "PreviewAnchor"\n'
        'anchor.Anchored = true\n'
        'anchor.CanCollide = false\n'
        'anchor.CanTouch = false\n'
        'anchor.CanQuery = false\n'
        'anchor.Transparency = 1\n'
        'anchor.Size = Vector3.new(1, 1, 1)\n'
        'anchor.CFrame = camera.CFrame + camera.CFrame.LookVector * 25\n'
        'attachment.Parent = anchor\n'
        'anchor.Parent = folder\n'
        'folder.Parent = workspace\n'
        'game:GetService("Selection"):Set({anchor})\n'
        'local count = Importer.emitCount(emitter)\n'
        'if count > 0 then\n'
        '  for _ = 1, 3 do\n'
        '    Importer.emit(emitter)\n'
        '    task.wait(0.8)\n'
        '  end\n'
        'end\n'
        'print("Preview ready: Workspace." .. folder.Name .. "; EmitCount=" .. count)\n'
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(command, encoding="utf-8")
    print(f"Wrote {args.output}; paste its contents into Studio's Command Bar.")


if __name__ == "__main__":
    main()
