"""Check that model development cannot borrow official held-out effects."""

import json
import unittest
from pathlib import Path

from src.data.dataset import load_split


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentSplitTests(unittest.TestCase):
    def test_reserved_bases_come_only_from_train(self):
        reserved = set(json.loads((ROOT / "data/dev_base_ids.json").read_text())["base_ids"])
        train = load_split("train")
        self.assertEqual(len(reserved), 20)
        self.assertTrue(reserved <= {row["feature_id"] for row in train})
        self.assertFalse(reserved & {
            row["feature_id"] for row in load_split("generalization_test")
        })
        self.assertEqual(
            len([row for row in train if row["feature_id"] in reserved]), 140
        )

    def test_extra_wordings_reference_train_only(self):
        ids = {row["id"] for row in load_split("train")}
        extra = json.loads((ROOT / "data/extra_train_prompts.json").read_text())
        self.assertTrue(extra)
        self.assertTrue(all(item["id"] in ids and item["prompts"] for item in extra))


if __name__ == "__main__":
    unittest.main()
