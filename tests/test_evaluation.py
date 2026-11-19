import unittest

from src.evaluation.metrics import summarize


def emitter(count, rate, light=1.0):
    return {
        "attributes": {"EmitCount": count},
        "properties": {
            "Brightness": 1,
            "LightEmission": light,
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

    def test_light_emission_levels(self):
        # Actual 0.35 snaps to 0.5; the glowing prompt that truly uses 1 got 0.5.
        actual = [emitter(0, 1, 1.0), emitter(0, 1, 0.35), emitter(0, 1, 0.0)]
        predicted = [emitter(0, 1, 0.5), emitter(0, 1, 0.5), emitter(0, 1, 1.0)]
        prompts = ["glowing orb", "grey smoke", "dust"]
        levels = summarize(actual, predicted, prompts)["levels"]["LightEmission"]
        self.assertAlmostEqual(levels["accuracy"], 1 / 3)
        self.assertEqual(levels["confusion"], [[0, 0, 1], [0, 1, 0], [0, 1, 0]])
        self.assertEqual(levels["light_prompts"], 1)
        self.assertEqual(levels["light_favored_rate"], 0.0)
        self.assertEqual(levels["light_favored_recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
