import os
import tempfile
import unittest
from pathlib import Path

import torch

from src.data.dataset import ParticleDataset
from src.data.normalize import Normalizer
from src.data.tensor_dataset import ParticleTensorDataset, record_prompts


SLOW = unittest.skipUnless(os.getenv("RUN_SLOW"), "set RUN_SLOW=1 to load MiniLM")


class PromptTests(unittest.TestCase):
    def test_main_prompt_comes_first(self):
        record = ParticleDataset("train")[0]
        prompts = record_prompts(record)
        self.assertEqual(prompts[0], record["prompt"])
        self.assertEqual(len(prompts), 3)


class FakeEmbeddings:
    def __getitem__(self, key):
        row_hash, index = key
        return torch.full((384,), float(index))


class TensorDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normalizer = Normalizer().fit(ParticleDataset("train").records)

    def test_train_uses_alternates_and_others_do_not(self):
        train = ParticleTensorDataset("train", self.normalizer, FakeEmbeddings())
        validation = ParticleTensorDataset("validation", self.normalizer, FakeEmbeddings())
        self.assertEqual(len(train), 3 * 987)
        self.assertEqual(len(validation), 212)
        self.assertTrue(all(item[1][0] == 0 for item in validation.items))

    def test_batches(self):
        dataset = ParticleTensorDataset("validation", self.normalizer, FakeEmbeddings())
        batch = next(iter(torch.utils.data.DataLoader(dataset, batch_size=4)))
        self.assertEqual(batch["embedding"].shape, (4, 384))
        self.assertEqual(batch["continuous"].shape, (4, len(self.normalizer.continuous)))
        self.assertEqual(batch["continuous_mask"].shape, batch["continuous"].shape)
        self.assertEqual(batch["categories"].dtype, torch.int64)
        self.assertEqual(batch["flags"].shape, (4, len(self.normalizer.flags)))


@SLOW
class EncoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.models.encoder import TextEncoder

        cls.encoder = TextEncoder()

    def test_shape_and_unit_length(self):
        vectors = self.encoder.encode(["fast blue sparks", "slow smoke"])
        self.assertEqual(vectors.shape, (2, 384))
        self.assertEqual(vectors.dtype, torch.float32)
        torch.testing.assert_close(vectors.norm(dim=1), torch.ones(2))

    def test_frozen_and_repeatable(self):
        self.assertFalse(any(p.requires_grad for p in self.encoder.model.parameters()))
        texts = ["fast blue sparks", "a thick slow cloud of grey smoke drifting up"]
        torch.testing.assert_close(self.encoder.encode(texts), self.encoder.encode(texts))
        single = torch.cat([self.encoder.encode([text]) for text in texts])
        torch.testing.assert_close(single, self.encoder.encode(texts), atol=1e-5, rtol=1e-4)

    def test_similar_prompts_are_closer(self):
        a, b, c = self.encoder.encode(["fast blue sparks", "quick azure sparkles", "thick slow smoke"])
        self.assertGreater(float(a @ b), float(a @ c))

    def test_cache_matches_fresh_encoding(self):
        from src.models.encoder import split_embeddings

        with tempfile.TemporaryDirectory() as directory:
            fresh = split_embeddings("validation", self.encoder, directory)
            cached = split_embeddings("validation", None, directory)
            path = Path(directory) / "validation.pt"
            saved = torch.load(path, weights_only=True)
            torch.save({**saved, "model": "other", "vectors": saved["vectors"] * 0}, path)
            rebuilt = split_embeddings("validation", self.encoder, directory)
        self.assertEqual(len(fresh), 3 * 212)
        torch.testing.assert_close(cached.vectors, fresh.vectors)
        torch.testing.assert_close(rebuilt.vectors, fresh.vectors)
        record = ParticleDataset("validation")[0]
        expected = self.encoder.encode(record_prompts(record))
        torch.testing.assert_close(fresh[record["row_hash"], 0], expected[0], atol=1e-5, rtol=1e-4)

    def test_batches_from_real_embeddings(self):
        from src.models.encoder import split_embeddings

        normalizer = Normalizer().fit(ParticleDataset("train").records)
        with tempfile.TemporaryDirectory() as directory:
            embeddings = split_embeddings("validation", self.encoder, directory)
        dataset = ParticleTensorDataset("validation", normalizer, embeddings)
        batch = next(iter(torch.utils.data.DataLoader(dataset, batch_size=8)))
        self.assertEqual(batch["embedding"].shape, (8, self.encoder.dim))
        self.assertEqual(batch["embedding"].dtype, torch.float32)
        torch.testing.assert_close(batch["embedding"].norm(dim=1), torch.ones(8))
        self.assertEqual(batch["continuous"].shape, (8, len(normalizer.continuous)))


if __name__ == "__main__":
    unittest.main()
