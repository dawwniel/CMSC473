import copy
import json
import unittest
from pathlib import Path

from src.data.dataset import load_split
from src.models.texture_layout import align_flipbook_layouts, texture_layout_index


class TextureLayoutTests(unittest.TestCase):
    def test_all_saved_textures_have_one_layout(self):
        root = Path(__file__).resolve().parents[1]
        train = load_split("train")
        effects = json.loads((root / "data/cix_expansion_manifest.json").read_text())["effects"]
        layouts = texture_layout_index(train, effects)
        self.assertNotIn("rbxassetid://9295449811", layouts)
        self.assertNotIn("rbxassetid://18636212277", layouts)
        self.assertEqual(len(effects), 572)
        for effect_id in ("N052", "N119", "N186"):
            effect = next(item for item in effects if item["id"] == effect_id)
            self.assertEqual(effect["layout"], "Grid4x4")
            self.assertEqual(layouts[effect["texture"]], "Grid4x4")

    def test_texture_override_corrects_grid_without_changing_blending(self):
        emitter = {"properties": {
            "Texture": "rbxassetid://one",
            "FlipbookLayout": {"_type": "Enum", "enum": "ParticleFlipbookLayout", "value": "Grid8x8"},
            "LightEmission": 0.2,
        }}
        before = copy.deepcopy(emitter)
        self.assertEqual(align_flipbook_layouts([emitter], {"rbxassetid://one": "Grid4x4"}), 1)
        self.assertEqual(emitter["properties"]["FlipbookLayout"]["value"], "Grid4x4")
        self.assertEqual(emitter["properties"]["LightEmission"], before["properties"]["LightEmission"])

    def test_conflicting_layout_is_rejected(self):
        record = {"emitter": {"properties": {
            "Texture": "asset", "FlipbookLayout": {"value": "Grid4x4"},
        }}}
        with self.assertRaises(ValueError):
            texture_layout_index([record], [{"texture": "asset", "layout": "Grid8x8"}])


if __name__ == "__main__":
    unittest.main()
