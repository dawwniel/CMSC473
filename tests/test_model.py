import unittest

import numpy as np
import torch

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.data.light import is_light_prompt
from src.models.model import (
    BASELINE_COLUMNS, ParticleBaseline, baseline_loss, decode_prediction, level_class_weights,
    output_row, particle_record, pick_level, target_indices, train_defaults, tune_biases,
)
from src.data.schema import validate_emitter


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_split("train")
        cls.normalizer = Normalizer().fit(cls.records)
        cls.indices, cls.burst_index = target_indices(cls.normalizer)
        cls.defaults = train_defaults(cls.normalizer, cls.records)

    def test_output_shapes_and_optimizer_step(self):
        torch.manual_seed(473)
        model = ParticleBaseline()
        embedding = torch.randn(4, 384)
        targets = self.normalizer.transform(self.records[0])
        batch = {
            key: torch.from_numpy(value).unsqueeze(0).repeat(4, 1)
            for key, value in targets.items()
        }
        batch["light"] = torch.tensor([0.0, 1.0, 0.0, 1.0])
        prediction = model(embedding)
        self.assertEqual(prediction["continuous"].shape, (4, len(BASELINE_COLUMNS)))
        self.assertEqual(prediction["burst_logit"].shape, (4,))
        self.assertEqual(prediction["levels"]["LightEmission"].shape, (4, 3))
        loss, _, _, level = baseline_loss(
            prediction, batch, self.indices, self.burst_index, level_class_weights(2.0), 3.0,
        )
        self.assertTrue(torch.isfinite(level))
        self.assertTrue(torch.isfinite(loss))
        before = model.heads.continuous.weight.detach().clone()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        self.assertFalse(torch.equal(before, model.heads.continuous.weight))

    def test_masked_targets_do_not_affect_loss(self):
        burst = next(row for row in self.records if row["emitter"]["attributes"]["EmitCount"] > 0)
        steady = next(row for row in self.records if row["emitter"]["attributes"]["EmitCount"] == 0)
        transformed = [self.normalizer.transform(row) for row in (burst, steady)]
        batch = {
            key: torch.stack([torch.from_numpy(row[key]) for row in transformed])
            for key in transformed[0]
        }
        batch["light"] = torch.zeros(2)
        prediction = {
            "continuous": batch["continuous"][:, self.indices].clone(),
            "burst_logit": torch.tensor([2.0, -2.0]),
            "levels": {"LightEmission": torch.zeros(2, 3)},
        }
        original, _, _, _ = baseline_loss(prediction, batch, self.indices, self.burst_index)
        prediction["continuous"][0, BASELINE_COLUMNS.index("Rate")] = 1e6
        prediction["continuous"][1, BASELINE_COLUMNS.index("EmitCount")] = 1e6
        masked, _, _, _ = baseline_loss(prediction, batch, self.indices, self.burst_index)
        self.assertEqual(original.item(), masked.item())

    def test_decoded_predictions_are_valid_emitters(self):
        for burst in (False, True):
            record = next(
                row for row in self.records
                if (row["emitter"]["attributes"]["EmitCount"] > 0) == burst
            )
            encoded = self.normalizer.transform(record)
            prediction = {
                "continuous": torch.from_numpy(encoded["continuous"][self.indices]),
                "burst_logit": torch.tensor(8.0 if burst else -8.0),
                "levels": {"LightEmission": torch.tensor([0.0, 3.0, 0.0])},
            }
            emitter = decode_prediction(self.normalizer, prediction, self.defaults, "smoke puff")
            self.assertEqual(emitter["properties"]["LightEmission"], 0.5)
            validate_emitter(emitter)
            count = emitter["attributes"]["EmitCount"]
            self.assertEqual(count > 0, burst)
            if burst:
                self.assertEqual(emitter["properties"]["Rate"], 0)
            wrapped = particle_record("test sparks", emitter)
            self.assertEqual(wrapped["id"], "Generated/PromptEffect/ParticleEmitter")
            self.assertEqual(wrapped["playback_mode"], "burst" if burst else "continuous")



class LightEmissionTests(unittest.TestCase):
    def test_light_prompts(self):
        for text in ("A glowing orb", "neon LIGHT trail", "sparks fly", "Fireball", "laser beams"):
            self.assertTrue(is_light_prompt(text), text)
        for text in ("grey smoke puff", "dust kicks up", "flight trail", "falling leaves"):
            self.assertFalse(is_light_prompt(text), text)

    def test_bias_can_flip_to_favored_but_half_stays_possible(self):
        logits = torch.tensor([0.0, 2.0, 0.5])
        self.assertEqual(pick_level("LightEmission", logits, light=False, base_bias=0.5, light_bias=2.0), 1)
        self.assertEqual(pick_level("LightEmission", logits, light=True, base_bias=0.5, light_bias=2.0), 2)
        confident = torch.tensor([0.0, 9.0, 0.0])
        self.assertEqual(pick_level("LightEmission", confident, light=True, light_bias=2.0), 1)
        self.assertEqual(pick_level("LightEmission", confident, light=True, light_bias=float("inf")), 2)

    def test_weights_raise_the_loss_of_missing_favored_on_light_prompts(self):
        batch = {
            "continuous": torch.zeros(2, 1), "continuous_mask": torch.zeros(2, 1),
            "flags": torch.zeros(2, 1), "levels": torch.tensor([[2], [1]]),
            "light": torch.tensor([1.0, 0.0]),
        }
        # Both items predict 0.5; the first item's true 1 is the black-square miss.
        prediction = {
            "continuous": torch.zeros(2, 1), "burst_logit": torch.zeros(2),
            "levels": {"LightEmission": torch.tensor([[0.0, 3.0, 0.0], [0.0, 3.0, 0.0]])},
        }
        plain = baseline_loss(prediction, batch, [0], 0)[3]
        weighted = baseline_loss(prediction, batch, [0], 0, level_class_weights(2.0), 3.0)[3]
        self.assertGreater(weighted.item(), plain.item())

    def test_tuned_light_bias_meets_recall(self):
        rng = np.random.default_rng(0)
        logits = rng.normal(size=(200, 3))
        targets = rng.integers(0, 3, size=200)
        light = rng.random(200) < 0.4
        tuned = tune_biases("LightEmission", logits, targets, light, light_recall=0.95)
        self.assertGreaterEqual(tuned["light_bias"], tuned["base_bias"])
        wanted = light & (targets == 2)
        scores = logits[wanted].copy()
        scores[:, 2] += tuned["light_bias"]
        self.assertGreaterEqual((scores.argmax(1) == 2).mean(), 0.95)

    def test_output_row(self):
        output = ParticleBaseline()(torch.randn(3, 384))
        row = output_row(output, 1)
        self.assertEqual(row["levels"]["LightEmission"].shape, (3,))


if __name__ == "__main__":
    unittest.main()
