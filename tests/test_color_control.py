import unittest

import torch

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.models.color import color_cue, requested_color, tint_emitter_color
from src.models.full_color import ParticleFullColor


class ColorControlTests(unittest.TestCase):
    def test_named_color_and_ambiguous_prompt(self):
        self.assertEqual(requested_color("Bright green flame").name, "green")
        self.assertIsNone(requested_color("red and blue sparks"))
        self.assertIsNone(requested_color("bright sparks"))
        self.assertEqual(color_cue("green flame")[-1], 1.0)

    def test_tint_preserves_original_and_brightness(self):
        original = {"properties": {"Color": {"keypoints": [[0, 0.8, 0.5, 0.2], [1, 0.4, 0.2, 0.1]]}}}
        tinted = tint_emitter_color(original, requested_color("green flame").rgb)
        self.assertEqual(original["properties"]["Color"]["keypoints"][0][1:], [0.8, 0.5, 0.2])
        self.assertAlmostEqual(max(tinted["properties"]["Color"]["keypoints"][0][1:]), 0.8)
        self.assertGreater(tinted["properties"]["Color"]["keypoints"][0][2],
                           tinted["properties"]["Color"]["keypoints"][0][1])

    def test_cue_changes_only_color_channels(self):
        torch.manual_seed(473)
        normalizer = Normalizer().fit(load_split("train"))
        model = ParticleFullColor(normalizer)
        model.initialize_from_full()
        model.eval()
        embedding = torch.randn(1, 384)
        cue = torch.tensor([color_cue("green flame")])
        with torch.no_grad():
            original = model(embedding)
            colored = model(embedding, cue)
        other = [i for i in range(len(normalizer.continuous)) if i not in model.color_indices]
        torch.testing.assert_close(original["continuous"][:, other], colored["continuous"][:, other])
        torch.testing.assert_close(original["flags"], colored["flags"])
        for name in normalizer.categories:
            torch.testing.assert_close(original["categories"][name], colored["categories"][name])
        decoded = normalizer.inverse_transform(
            colored["continuous"][0].numpy().clip(-8, 8),
            [colored["categories"][name][0].argmax().item() for name in normalizer.categories],
            colored["flags"][0].sigmoid().numpy(),
        )
        for point in decoded["properties"]["Color"]["keypoints"]:
            self.assertGreaterEqual(point[2], point[1])
            self.assertGreaterEqual(point[2], point[3])


if __name__ == "__main__":
    unittest.main()
