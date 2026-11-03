import unittest

from src.data.dataset import load_split
from src.data.normalize import Normalizer
from src.evaluation.full_metrics import row_errors, summarize_full


class FullEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        records = load_split("train")
        cls.normalizer = Normalizer().fit(records)
        cls.burst = next(row["emitter"] for row in records if row["emitter"]["attributes"]["EmitCount"] > 0)
        cls.steady = next(row["emitter"] for row in records if row["emitter"]["attributes"]["EmitCount"] == 0)

    def test_identical_emitters_have_zero_error(self):
        report = summarize_full([self.burst, self.steady], [self.burst, self.steady], self.normalizer)
        self.assertEqual(report["valid_emitters"], 2)
        self.assertEqual(report["category_accuracy"]["Texture"], 1)
        self.assertEqual(report["curve_mae"]["Color"], 0)
        self.assertEqual(report["seven_value_metrics"]["burst_accuracy"], 1)

    def test_mode_mistake_counts_active_error(self):
        errors = row_errors(self.burst, self.steady, self.normalizer)
        self.assertEqual(errors["numeric_abs_error"]["EmitCount"], self.burst["attributes"]["EmitCount"])
        self.assertFalse(errors["flag_correct"]["Burst"])


if __name__ == "__main__":
    unittest.main()
