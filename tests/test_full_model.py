import unittest

import torch

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.models.full import ParticleFull, decode_full, full_loss
from src.models.levels import chosen_biases, level_class_weights
from src.data.schema import validate_emitter


class FullModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        records = load_split("train")
        cls.normalizer = Normalizer().fit(records)
        burst = next(row for row in records if row["emitter"]["attributes"]["EmitCount"] > 0)
        steady = next(row for row in records if row["emitter"]["attributes"]["EmitCount"] == 0)
        transformed = [cls.normalizer.transform(row) for row in (burst, steady)]
        cls.batch = {
            name: torch.stack([torch.from_numpy(row[name]) for row in transformed])
            for name in transformed[0]
        }
        cls.batch["light"] = torch.tensor([1.0, 0.0])

    def test_heads_train_and_decode(self):
        model = ParticleFull(self.normalizer)
        output = model(torch.randn(2, 384))
        self.assertEqual(output["continuous"].shape, (2, len(self.normalizer.continuous)))
        self.assertEqual(output["flags"].shape, (2, len(self.normalizer.flags)))
        self.assertEqual(set(output["categories"]), set(self.normalizer.categories))
        self.assertEqual(output["levels"]["LightEmission"].shape, (2, 3))
        losses = full_loss(output, self.batch, model, level_class_weights(2.0), 3.0)
        self.assertTrue(torch.isfinite(losses["total"]))
        self.assertTrue(torch.isfinite(losses["levels"]))
        losses["total"].backward()
        for head in (model.scalars, model.curves, model.flags, model.categories["Texture"],
                     model.levels["LightEmission"]):
            self.assertIsNotNone(head.weight.grad)
        for i in range(2):
            validate_emitter(decode_full(self.normalizer, output, i))

    def test_inactive_rate_and_count_are_masked(self):
        model = ParticleFull(self.normalizer)
        output = model(torch.randn(2, 384))
        before = full_loss(output, self.batch, model)["scalars"]
        modified = dict(output)
        modified["continuous"] = output["continuous"].clone()
        rate = self.normalizer.continuous.index("Rate")
        count = self.normalizer.continuous.index("EmitCount")
        modified["continuous"][0, rate] = 1e4
        modified["continuous"][1, count] = 1e4
        after = full_loss(modified, self.batch, model)["scalars"]
        self.assertEqual(before.item(), after.item())


    def test_light_emission_decodes_to_a_level_with_bias(self):
        model = ParticleFull(self.normalizer)
        output = model(torch.randn(1, 384))
        output["levels"]["LightEmission"] = torch.tensor([[0.0, 2.0, 0.5]])
        plain = decode_full(self.normalizer, output, 0, "glowing orb")
        self.assertEqual(plain["properties"]["LightEmission"], 0.5)
        light = decode_full(self.normalizer, output, 0, "glowing orb", base_bias=0.0, light_bias=2.0)
        self.assertEqual(light["properties"]["LightEmission"], 1.0)
        other = decode_full(self.normalizer, output, 0, "grey smoke", base_bias=0.0, light_bias=2.0)
        self.assertEqual(other["properties"]["LightEmission"], 0.5)
        validate_emitter(light)

    def test_old_checkpoint_has_unbiased_light_emission(self):
        self.assertEqual(chosen_biases({}), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
