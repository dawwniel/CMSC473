"""Check that visual ratings use every scheduled prompt as the denominator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.score_visual_feedback import score


class VisualFeedbackTests(unittest.TestCase):
    def test_acceptability_and_missing_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = root / "prompts.json"
            feedback = root / "feedback.jsonl"
            prompts.write_text(json.dumps([{"prompt": "smoke"}, {"prompt": "sparks"}]))
            entries = [
                {"reviewer": "A", "model_id": "one", "rating": "texture_usable",
                 "record": {"prompt": "smoke"}},
                {"reviewer": "A", "model_id": "one", "rating": "texture_fit",
                 "record": {"prompt": "sparks"}},
                {"reviewer": "B", "model_id": "one", "rating": "texture_fit",
                 "record": {"prompt": "smoke"}},
            ]
            feedback.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
            result = score(feedback, prompts)
            self.assertEqual(result["reviewers"]["A"]["acceptable"], 1.0)
            self.assertEqual(result["reviewers"]["B"]["acceptable"], 0.5)
            self.assertEqual(result["reviewers"]["B"]["missing"], 1)
            self.assertFalse(result["reviewers"]["B"]["complete"])
            self.assertEqual(result["unanimous_acceptable"], 0.5)

    def test_first_rating_wins_on_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompts = root / "prompts.json"
            feedback = root / "feedback.jsonl"
            prompts.write_text(json.dumps([{"prompt": "smoke"}]))
            entry = {"reviewer": "A", "rating": "texture_fit", "record": {"prompt": "smoke"}}
            feedback.write_text(json.dumps(entry) + "\n" + json.dumps(entry) + "\n")
            result = score(feedback, prompts)
            self.assertEqual(result["ignored_duplicates"], 1)
            self.assertEqual(result["reviewers"]["A"]["acceptable"], 1.0)


if __name__ == "__main__":
    unittest.main()
