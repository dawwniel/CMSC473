"""Make small contact sheets for judging texture retrieval errors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.dataset import load_split
from scripts.benchmark_texture_retrieval import representative_image, texture_id


REPORT = ROOT / "checkpoints/texture_retrieval_dev.json"
IMAGES = ROOT / "checkpoints/texture_images"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = report["per_effect"]
    records = {row["id"]: row for row in load_split("train")}
    layouts = {}
    for row in records.values():
        asset_id = texture_id(row)
        layout = row["emitter"]["properties"]["FlipbookLayout"]["value"]
        if asset_id not in layouts or layouts[asset_id] == "None":
            layouts[asset_id] = layout
    first = {}
    for row in rows:
        base = records[row["id"]]["feature_id"]
        first.setdefault(base, row)

    selected = list(first.values())
    for page in range(0, len(selected), 5):
        canvas = Image.new("RGB", (690, 1000), (238, 239, 241))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 6), "True texture              Text lookup               CLIP image", fill="black")
        for index, row in enumerate(selected[page:page + 5]):
            y = 35 + index * 190
            record = records[row["id"]]
            draw.text((10, y), f"{record['feature_id']}  {record['prompt'][:92]}", fill="black")
            for column, key in enumerate(("texture", "text_prediction", "image_prediction")):
                asset_id = row[key]
                preview = representative_image(IMAGES / f"{asset_id}.png", layouts[asset_id])
                preview.thumbnail((155, 135), Image.Resampling.LANCZOS)
                x = 12 + column * 225
                canvas.paste(preview, (x + (155 - preview.width) // 2, y + 20))
                draw.text((x, y + 158), asset_id, fill="black")
        path = ROOT / f"checkpoints/texture_review_page_{page // 5 + 1}.png"
        canvas.save(path)
        print(path)


if __name__ == "__main__":
    main()
