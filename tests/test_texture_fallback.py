import unittest

import torch

from src.models.inference import (apply_catalog_textures, apply_neighbor_textures,
                                  exact_texture_index)


class TextureFallbackTests(unittest.TestCase):
    def test_only_uncertain_texture_changes(self):
        emitters = [
            {"properties": {"Texture": "model_a", "Rate": 3}},
            {"properties": {"Texture": "model_b", "Rate": 5}},
        ]
        neighbors = [
            {"properties": {"Texture": "neighbor_a", "Rate": 99}},
            {"properties": {"Texture": "neighbor_b", "Rate": 99}},
        ]
        apply_neighbor_textures(emitters, torch.tensor([0.6, 0.8]), neighbors, 0.6926)
        self.assertEqual(emitters[0]["properties"], {"Texture": "neighbor_a", "Rate": 3})
        self.assertEqual(emitters[1]["properties"], {"Texture": "model_b", "Rate": 5})

    def test_rejects_length_mismatch(self):
        with self.assertRaises(ValueError):
            apply_neighbor_textures([], torch.tensor([0.5]), [], 0.6926)

    def test_exact_prompt_requires_one_texture(self):
        first = {"prompt": "Blue sparks", "emitter": {"properties": {"Texture": "a"}}}
        same = {"prompt": "  blue   SPARKS  ", "emitter": {"properties": {"Texture": "a"}}}
        different = {"prompt": "blue sparks", "emitter": {"properties": {"Texture": "b"}}}
        self.assertEqual(exact_texture_index([first, same]), {"blue sparks": "a"})
        with self.assertRaises(ValueError):
            exact_texture_index([first, different])

    def test_catalog_uses_only_stronger_described_match(self):
        emitters = [{"properties": {"Texture": "old", "Rate": 3}},
                    {"properties": {"Texture": "old", "Rate": 5}}]
        scores = torch.tensor([[0.72, 0.61], [0.68, 0.60]])
        nearest_scores = torch.tensor([0.70, 0.75])
        apply_catalog_textures(emitters, scores, nearest_scores, ["cix_a", "cix_b"])
        self.assertEqual(emitters[0]["properties"], {"Texture": "cix_a", "Rate": 3})
        self.assertEqual(emitters[1]["properties"], {"Texture": "old", "Rate": 5})


if __name__ == "__main__":
    unittest.main()
