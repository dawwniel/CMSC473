"""Cache public Roblox particle images for the texture retrieval benchmark."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset import load_split


ROOT = Path(__file__).resolve().parents[1]
ASSET_ID = re.compile(r"^(?:rbxassetid://|https?://www\.roblox\.com/asset/\?id=)(\d+)$")


def fetch(asset_id: str, directory: Path) -> tuple[str, str]:
    path = directory / f"{asset_id}.png"
    if path.exists():
        return asset_id, "cached"
    try:
        try:
            with urlopen(f"https://assetdelivery.roblox.com/v1/asset?id={asset_id}", timeout=20) as response:
                data = response.read()
            source = "downloaded"
        except HTTPError as error:
            if error.code != 401:
                raise
            url = ("https://thumbnails.roblox.com/v1/assets?"
                   f"assetIds={asset_id}&size=420x420&format=Png&isCircular=false")
            with urlopen(url, timeout=20) as response:
                result = json.load(response)["data"][0]
            if result["state"] != "Completed" or not result.get("imageUrl"):
                raise ValueError(f"thumbnail state {result['state']}")
            with urlopen(result["imageUrl"], timeout=20) as response:
                data = response.read()
            source = "thumbnail"
        with Image.open(io.BytesIO(data)) as image:
            image.convert("RGBA").save(path)
        return asset_id, source
    except Exception as error:
        return asset_id, f"error: {error}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/texture_images")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")

    textures = {row["emitter"]["properties"]["Texture"] for row in load_split("train")}
    reviewed_ids = set(json.loads((ROOT / "data/cix_prompt_review.json").read_text()))
    manifest = json.loads((ROOT / "data/cix_expansion_manifest.json").read_text())["effects"]
    textures.update(item["texture"] for item in manifest if item["id"] in reviewed_ids)
    ids = sorted({match.group(1) for texture in textures
                  if (match := ASSET_ID.fullmatch(texture))})
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, asset_id, args.output): asset_id for asset_id in ids}
        for future in as_completed(futures):
            asset_id, status = future.result()
            results[asset_id] = status
    report = args.output / "download_report.json"
    report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    counts = {status: sum(value == status for value in results.values())
              for status in ("cached", "downloaded", "thumbnail")}
    failures = [(asset_id, status) for asset_id, status in results.items()
                if status.startswith("error:")]
    print(f"texture IDs={len(ids)} cached={counts['cached']} downloaded={counts['downloaded']} "
          f"thumbnail={counts['thumbnail']} failed={len(failures)}")
    for asset_id, status in sorted(failures)[:10]:
        print(f"  {asset_id}: {status}")


if __name__ == "__main__":
    main()
