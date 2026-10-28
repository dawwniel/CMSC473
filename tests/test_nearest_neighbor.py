import unittest

import torch

from src.models.nearest_neighbor import build_bank, nearest


def record(row_hash, alternates=()):
    attributes = {"PromptAlternates": {"value": list(alternates)}} if alternates else {}
    return {"row_hash": row_hash, "prompt": row_hash, "attachment": {"attributes": attributes}}


class FakeEmbeddings:
    def __init__(self, table):
        self.table = table

    def __getitem__(self, key):
        return torch.tensor(self.table[key])


class NearestNeighborTests(unittest.TestCase):
    def test_picks_highest_cosine(self):
        bank = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        queries = torch.tensor([[0.6, 0.8], [0.8, 0.6]])
        indices, similarities = nearest(queries, bank)
        self.assertEqual(indices.tolist(), [1, 0])
        self.assertTrue(torch.allclose(similarities, torch.tensor([0.8, 0.8])))

    def test_ties_go_to_first_row(self):
        bank = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
        indices, _ = nearest(torch.tensor([[1.0, 0.0]]), bank)
        self.assertEqual(indices.tolist(), [0])

    def test_rejects_unnormalized_vectors(self):
        with self.assertRaises(ValueError):
            nearest(torch.tensor([[2.0, 0.0]]), torch.tensor([[1.0, 0.0]]))

    def test_bank_maps_rows_to_records(self):
        records = [record("a", ["a alt"]), record("b")]
        embeddings = FakeEmbeddings({("a", 0): [1.0, 0.0], ("a", 1): [0.0, 1.0], ("b", 0): [0.6, 0.8]})
        bank, owners = build_bank(records, embeddings)
        self.assertEqual(owners, [(0, 0), (0, 1), (1, 0)])
        self.assertEqual(bank.shape, (3, 2))
        _, owners = build_bank(records, embeddings, alternates=False)
        self.assertEqual(owners, [(0, 0), (1, 0)])


if __name__ == "__main__":
    unittest.main()
