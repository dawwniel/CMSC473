"""Render held-out CIX queries beside the catalog's closest textures."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.benchmark_texture_retrieval import representative_image


def main() -> None:
    report = json.loads((ROOT / "checkpoints/cix_texture_holdout_evaluation.json").read_text())
    manifest = {item["id"]: item for item in
                json.loads((ROOT / "data/cix_expansion_manifest.json").read_text())["effects"]}
    rows = report["per_query"]
    for start in range(0, len(rows), 5):
        canvas = Image.new("RGB", (840, 1050), (238, 239, 241))
        draw = ImageDraw.Draw(canvas)
        draw.text((12, 8), "True image                 Reviewed first             Reviewed second            Generic first", fill="black")
        for index, row in enumerate(rows[start:start + 5]):
            y = 35 + index * 200
            draw.text((10, y), f"{row['id']}: {row['query'][:110]}", fill="black")
            choices = [row["id"], *row["reviewed_top3"][:2], row["generic_top3"][0]]
            for column, effect_id in enumerate(choices):
                spec = manifest[effect_id]
                asset_id = re.findall(r"[0-9]+", spec["texture"])[-1]
                image = representative_image(
                    ROOT / f"checkpoints/texture_images/{asset_id}.png", spec["layout"])
                image.thumbnail((155, 145), Image.Resampling.LANCZOS)
                x = 10 + column * 205
                canvas.paste(image, (x + (155 - image.width) // 2, y + 20))
                draw.text((x, y + 170), effect_id, fill="black")
        output = ROOT / f"checkpoints/cix_holdout_page_{start // 5 + 1}.png"
        canvas.save(output)
        print(output)


if __name__ == "__main__":
    main()
