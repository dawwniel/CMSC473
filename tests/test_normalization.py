import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.data.dataset import ParticleDataset
from src.data.normalize import Normalizer
from src.data.schema import PARTICLE_PROPERTIES, validate_emitter
from src.data.targets import (
    BOOLEANS, CATEGORIES, COLORS, ENUMS, NUMBERS, RANGES, SEQUENCES, UNKNOWN, VECTORS,
    encode_targets, resample,
)


TRAIN = ParticleDataset("train").records
OTHERS = {
    split: ParticleDataset(split).records
    for split in ("validation", "test", "generalization_test")
}
NORMALIZER = Normalizer().fit(TRAIN)
# Normalized targets are float32, so decoded values carry about 7 significant digits.
CLOSE = {"rtol": 1e-5, "atol": 1e-4}


def burst_row():
    return next(row for row in TRAIN if row["emitter"]["attributes"]["EmitCount"] > 0)


def continuous_row():
    return next(row for row in TRAIN if row["emitter"]["attributes"]["EmitCount"] == 0)


def decode(normalizer, record):
    encoded = normalizer.transform(record)
    return normalizer.inverse_transform(
        encoded["continuous"], encoded["categories"], encoded["flags"], record["emitter"]["name"],
    )


class ResampleTests(unittest.TestCase):
    def test_hits_keypoints_and_interpolates(self):
        values = resample([0, 0.5, 1], [0, 1, 0], 5)
        np.testing.assert_allclose(values, [0, 0.5, 1, 0.5, 0])

    def test_repeated_time_takes_later_value(self):
        np.testing.assert_allclose(resample([0, 0.5, 0.5, 1], [0, 0, 1, 1], 3), [0, 1, 1])
        np.testing.assert_allclose(resample([0, 0, 1], [5, 2, 2], 2), [2, 2])
        np.testing.assert_allclose(resample([0, 1, 1], [0, 0, 3], 2), [0, 3])


class TargetLayoutTests(unittest.TestCase):
    def test_every_property_is_encoded_once(self):
        groups = [NUMBERS, RANGES, VECTORS, SEQUENCES, COLORS, CATEGORIES, BOOLEANS]
        names = [name for group in groups for name in group]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(PARTICLE_PROPERTIES))

    def test_layout_widths(self):
        # K=8: Size, Squash, Transparency have value + envelope, Color has RGB.
        self.assertEqual(len(NORMALIZER.columns), 9 + 1 + 10 + 5 + 3 * 16 + 24)
        self.assertEqual(NORMALIZER.transform(TRAIN[0])["continuous"].shape, (len(NORMALIZER.continuous),))

    def test_constant_fields_are_not_targets(self):
        self.assertEqual(NORMALIZER.constants["flags"], {"Enabled": True, "WindAffectsDrag": False})
        self.assertNotIn("Enabled", NORMALIZER.flags)
        self.assertIn("Burst", NORMALIZER.flags)

    def test_playback_mode_masks(self):
        rate = NORMALIZER.continuous.index("Rate")
        count = NORMALIZER.continuous.index("EmitCount")
        burst = NORMALIZER.transform(burst_row())
        steady = NORMALIZER.transform(continuous_row())
        self.assertEqual((burst["continuous_mask"][rate], burst["continuous_mask"][count]), (0, 1))
        self.assertEqual((steady["continuous_mask"][rate], steady["continuous_mask"][count]), (1, 0))
        self.assertEqual(burst["continuous"][rate], 0)


class FitTests(unittest.TestCase):
    def test_train_columns_are_standardized(self):
        encoded = [NORMALIZER.transform(row) for row in TRAIN]
        values = np.stack([e["continuous"] for e in encoded])
        mask = np.stack([e["continuous_mask"] for e in encoded]).astype(bool)
        for i, name in enumerate(NORMALIZER.continuous):
            with self.subTest(column=name):
                column = values[mask[:, i], i]
                self.assertAlmostEqual(float(column.mean()), 0, places=4)
                self.assertAlmostEqual(float(column.std()), 1, places=4)

    def test_statistics_come_from_train(self):
        values = np.log1p([row["emitter"]["properties"]["Brightness"] for row in TRAIN])
        self.assertAlmostEqual(NORMALIZER.mean["Brightness"], float(values.mean()))
        self.assertAlmostEqual(NORMALIZER.std["Brightness"], float(values.std()))
        textures = {row["emitter"]["properties"]["Texture"] for row in TRAIN}
        self.assertEqual(set(NORMALIZER.classes["Texture"][1:]), textures)

    def test_fit_rejects_other_splits(self):
        with self.assertRaisesRegex(ValueError, "train records only"):
            Normalizer().fit(TRAIN + OTHERS["validation"])

    def test_other_splits_match_train_constants(self):
        # A constant is dropped from the targets, so a different value elsewhere can't be predicted.
        for split, rows in OTHERS.items():
            for record in rows:
                targets = encode_targets(record["emitter"])
                for group, constants in NORMALIZER.constants.items():
                    for name, value in constants.items():
                        got = getattr(targets, group)[name]
                        if isinstance(got, float) and np.isnan(got):
                            continue
                        with self.subTest(split=split, row=record["id"], field=name):
                            self.assertEqual(got, value)

    def test_zero_variance_column_is_a_constant(self):
        rows = copy.deepcopy(TRAIN)
        for row in rows:
            row["emitter"]["properties"]["ZOffset"] = 2.0
        normalizer = Normalizer().fit(rows)
        self.assertNotIn("ZOffset", normalizer.continuous)
        self.assertEqual(normalizer.constants["continuous"]["ZOffset"], 2.0)
        self.assertEqual(decode(normalizer, rows[0])["properties"]["ZOffset"], 2.0)


class RoundTripTests(unittest.TestCase):
    def assert_same_emitter(self, record, decoded):
        original = record["emitter"]
        validate_emitter(decoded)
        self.assertEqual(decoded["attributes"], original["attributes"])
        for name, value in original["properties"].items():
            got = decoded["properties"][name]
            with self.subTest(row=record["id"], property=name):
                if name in SEQUENCES or name in COLORS:
                    continue
                if name == "Rate" and original["attributes"]["EmitCount"] > 0:
                    self.assertEqual(got, 0.0)
                elif isinstance(value, dict) and "value" in value and value["_type"] != "Enum":
                    np.testing.assert_allclose(got["value"], value["value"], **CLOSE)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    np.testing.assert_allclose(got, value, **CLOSE)
                else:
                    self.assertEqual(got, value)

    def test_train_rows_round_trip(self):
        for record in TRAIN:
            self.assert_same_emitter(record, decode(NORMALIZER, record))

    def test_curves_match_their_resampled_points(self):
        for record in TRAIN[:200]:
            expected = encode_targets(record["emitter"]).continuous
            got = encode_targets(decode(NORMALIZER, record)).continuous
            for name, value in expected.items():
                if not np.isnan(value):
                    np.testing.assert_allclose(got[name], value, **CLOSE, err_msg=f"{record['id']} {name}")

    def test_other_splits_decode_to_valid_emitters(self):
        for split, rows in OTHERS.items():
            for record in rows:
                with self.subTest(split=split, row=record["id"]):
                    validate_emitter(decode(NORMALIZER, record))

    def test_unseen_texture_decodes_to_train_fallback(self):
        record = copy.deepcopy(TRAIN[0])
        record["emitter"]["properties"]["Texture"] = "rbxassetid://0"
        index = NORMALIZER.categories.index("Texture")
        self.assertEqual(NORMALIZER.transform(record)["categories"][index], 0)
        texture = decode(NORMALIZER, record)["properties"]["Texture"]
        self.assertEqual(texture, NORMALIZER.fallback["Texture"])
        self.assertIn(texture, {row["emitter"]["properties"]["Texture"] for row in TRAIN})

    def test_generalization_has_unseen_textures(self):
        index = NORMALIZER.categories.index("Texture")
        unknown = sum(
            NORMALIZER.transform(row)["categories"][index] == 0 for row in OTHERS["generalization_test"]
        )
        self.assertEqual(unknown, 10)
        self.assertEqual(NORMALIZER.classes["Texture"][0], UNKNOWN)
        self.assertEqual(len(NORMALIZER.classes["Texture"]), 122)

    def test_decoded_values_are_clamped(self):
        record = continuous_row()
        encoded = NORMALIZER.transform(record)
        wild = np.full_like(encoded["continuous"], -50.0)
        decoded = NORMALIZER.inverse_transform(wild, encoded["categories"], encoded["flags"])
        validate_emitter(decoded)
        self.assertGreaterEqual(decoded["properties"]["Brightness"], 0)
        self.assertTrue(all(p[2] >= 0 for p in decoded["properties"]["Size"]["keypoints"]))

    def test_burst_count_is_a_whole_number(self):
        record = burst_row()
        encoded = NORMALIZER.transform(record)
        count = NORMALIZER.continuous.index("EmitCount")
        encoded["continuous"][count] += 0.37
        decoded = NORMALIZER.inverse_transform(
            encoded["continuous"], encoded["categories"], encoded["flags"],
        )
        self.assertIsInstance(decoded["attributes"]["EmitCount"], int)
        self.assertGreaterEqual(decoded["attributes"]["EmitCount"], 1)


class SaveTests(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normalizer.json"
            NORMALIZER.save(path)
            loaded = Normalizer.load(path)
        self.assertEqual(loaded.to_dict(), NORMALIZER.to_dict())
        for record in TRAIN[:20]:
            np.testing.assert_array_equal(
                loaded.transform(record)["continuous"], NORMALIZER.transform(record)["continuous"],
            )


if __name__ == "__main__":
    unittest.main()
