import unittest

from src.evaluation.metrics import summarize


def emitter(count, rate):
    return {
        "attributes": {"EmitCount": count},
        "properties": {
            "Brightness": 1,
            "Rate": rate,
            "Lifetime": {"value": [1, 2]},
            "Speed": {"value": [3, 4]},
        },
    }


class EvaluationTests(unittest.TestCase):
    def test_mode_and_active_errors(self):
        actual = [emitter(5, 0), emitter(0, 10)]
        predicted = [emitter(3, 0), emitter(2, 0)]
        result = summarize(actual, predicted)
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["burst_accuracy"], 0.5)
        self.assertEqual(result["active_mae"], {"Rate": 10, "EmitCount": 2})
        self.assertEqual(result["mae"]["EmitCount"], 2)


if __name__ == "__main__":
    unittest.main()
