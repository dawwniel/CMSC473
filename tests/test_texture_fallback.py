import unittest

import torch

from src.models.inference import apply_neighbor_textures


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


if __name__ == "__main__":
    unittest.main()
