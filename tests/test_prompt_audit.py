"""Keep ambiguous prompt wording out of the fitted data."""

from __future__ import annotations

import unittest

from scripts.audit_prompts import audit


class PromptAuditTests(unittest.TestCase):
    def test_train_and_validation_have_no_conflicting_wording(self):
        report = audit()
        for conflict in report["conflicts"]:
            splits = {entry["split"] for entry in conflict["entries"]}
            self.assertTrue(splits.isdisjoint({"train", "validation"}), conflict["prompt"])

    def test_heldout_main_prompts_do_not_repeat_train_wording(self):
        report = audit()
        self.assertEqual(report["heldout_main_matching_train_text"], {
            "test": 0,
            "generalization_test": 0,
        })


if __name__ == "__main__":
    unittest.main()
