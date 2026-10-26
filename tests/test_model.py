import unittest

import torch

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.models.model import (
    BASELINE_COLUMNS, ParticleBaseline, baseline_loss, decode_prediction,
    particle_record, target_indices, train_defaults,
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
        prediction = model(embedding)
        self.assertEqual(prediction["continuous"].shape, (4, len(BASELINE_COLUMNS)))
        self.assertEqual(prediction["burst_logit"].shape, (4,))
        loss, _, _ = baseline_loss(prediction, batch, self.indices, self.burst_index)
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
        prediction = {
            "continuous": batch["continuous"][:, self.indices].clone(),
            "burst_logit": torch.tensor([2.0, -2.0]),
        }
        original, _, _ = baseline_loss(prediction, batch, self.indices, self.burst_index)
        prediction["continuous"][0, BASELINE_COLUMNS.index("Rate")] = 1e6
        prediction["continuous"][1, BASELINE_COLUMNS.index("EmitCount")] = 1e6
        masked, _, _ = baseline_loss(prediction, batch, self.indices, self.burst_index)
        self.assertEqual(original.item(), masked.item())

    def test_decoded_predictions_are_valid_emitters(self):
        for burst in (False, True):
            record = next(
                row for row in self.records
                if (row["emitter"]["attributes"]["EmitCount"] > 0) == burst
            )
            encoded = self.normalizer.transform(record)
            values = torch.from_numpy(encoded["continuous"][self.indices])
            logit = torch.tensor(8.0 if burst else -8.0)
            emitter = decode_prediction(self.normalizer, values, logit, self.defaults)
            validate_emitter(emitter)
            count = emitter["attributes"]["EmitCount"]
            self.assertEqual(count > 0, burst)
            if burst:
                self.assertEqual(emitter["properties"]["Rate"], 0)
            wrapped = particle_record("test sparks", emitter)
            self.assertEqual(wrapped["id"], "Generated/PromptEffect/ParticleEmitter")
            self.assertEqual(wrapped["playback_mode"], "burst" if burst else "continuous")


if __name__ == "__main__":
    unittest.main()
