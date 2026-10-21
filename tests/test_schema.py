import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from src.data.dataset import ParticleDataset, load_jsonl
from src.data.schema import PARTICLE_PROPERTIES, SchemaError, validate_record


ROOT = Path(__file__).resolve().parents[1]
TRAIN_FILE = ROOT / "src/data/train/particles_train.jsonl"


def first_line():
    with TRAIN_FILE.open(encoding="utf-8") as source:
        return source.readline()


def sample_row():
    return json.loads(first_line())


class SchemaTests(unittest.TestCase):
    def test_property_list_matches_exporter(self):
        source = (ROOT / "roblox/exporter.lua").read_text(encoding="utf-8")
        block = re.search(r"ParticleEmitter\s*=\s*\{(.*?)\n\s*\},", source, re.S)
        self.assertIsNotNone(block)
        exported = set(re.findall(r'"([A-Za-z]+)"', block.group(1)))
        self.assertEqual(exported, set(PARTICLE_PROPERTIES))

    def test_saved_splits(self):
        for split, count in (
            ("train", 987),
            ("validation", 212),
            ("test", 211),
            ("generalization_test", 260),
        ):
            with self.subTest(split=split):
                dataset = ParticleDataset(split)
                self.assertEqual(len(dataset), count)
                self.assertTrue(all(row["split"] == split for row in dataset))
                self.assertGreaterEqual(dataset[0]["emitter"]["attributes"]["EmitCount"], 0)

    def test_generalization_bases_are_held_out(self):
        groups = {}
        all_ids = set()
        for split in ("train", "validation", "test", "generalization_test"):
            rows = ParticleDataset(split)
            groups[split] = {(row["family"], row["feature_id"]) for row in rows}
            ids = {row["id"] for row in rows}
            self.assertEqual(len(ids), len(rows))
            self.assertFalse(all_ids & ids)
            all_ids.update(ids)
        familiar = groups["train"] | groups["validation"] | groups["test"]
        self.assertEqual(len(groups["generalization_test"]), 26)
        self.assertFalse(familiar & groups["generalization_test"])

    def test_rejects_bad_records(self):
        changes = (
            (lambda row: row.update(prompt="  "), "prompt"),
            (lambda row: row.update(split="review"), "split"),
            (lambda row: row["attachment"]["attributes"].update(Split="test"), "attachment.attributes.Split"),
            (lambda row: row.update(id="wrong"), "id"),
            (lambda row: row["emitter"]["properties"].pop("Rate"), "Rate"),
            (lambda row: row["emitter"]["properties"].update(Rate=True), "Rate"),
            (lambda row: row["emitter"]["properties"].update(Rate=float("nan")), "Rate"),
            (lambda row: row["emitter"]["properties"]["Lifetime"].update(value=[2, 1]), "Lifetime"),
            (lambda row: row["emitter"]["properties"]["Shape"].update(enum="NormalId"), "Shape"),
            (lambda row: row["emitter"]["properties"]["Size"]["keypoints"][0].__setitem__(0, .2), "Size"),
            (lambda row: row["emitter"]["attributes"].update(EmitCount=-1), "EmitCount"),
            (lambda row: row["emitter"]["attributes"].update(EmitCount=1.5), "EmitCount"),
            (lambda row: row["prompt_gui"]["children"][0]["properties"].update(Text="wrong"), "prompt_gui"),
        )
        for change, message in changes:
            with self.subTest(message=message, change=change):
                row = sample_row()
                change(row)
                with self.assertRaisesRegex(SchemaError, message):
                    validate_record(row, "train")

    def test_loader_reports_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text(first_line() + "{bad json}\n", encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, r"bad.jsonl:2:"):
                load_jsonl(path, "train")

    def test_loader_rejects_duplicate_ids_and_changed_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            line = first_line()
            path.write_text(line * 2, encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, "duplicate id"):
                load_jsonl(path, "train")

            path.write_text(line.replace('"Rate":0', '"Rate":1', 1), encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, "row_hash does not match"):
                load_jsonl(path, "train")

            path.write_text(
                line.replace('"split":"train"', '"split":"train","split":"test"', 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SchemaError, "duplicate JSON key 'split'"):
                load_jsonl(path, "train")

    def test_loader_checks_file_split(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.jsonl"
            path.write_text(first_line(), encoding="utf-8")
            with self.assertRaisesRegex(SchemaError, "expected test, got train"):
                load_jsonl(path, "test")

    def test_validation_does_not_change_record(self):
        row = sample_row()
        original = copy.deepcopy(row)
        self.assertIs(validate_record(row, "train"), row)
        self.assertEqual(row, original)


if __name__ == "__main__":
    unittest.main()
