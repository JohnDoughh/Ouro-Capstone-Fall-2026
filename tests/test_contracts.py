import copy
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.cli import bootstrap_demo
from ouro_eval_lab.contracts import ContractError, validate_evaluator_output
from ouro_eval_lab.fixtures import generate
from ouro_eval_lab.runner import load_json, verify_manifest


class ContractTests(unittest.TestCase):
    def test_bootstrap_is_idempotent_from_empty_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "fixtures"
            db_path = Path(directory) / "lab.db"
            first = bootstrap_demo(root, db_path, 20260825)
            first_manifest = first[0].read_bytes()
            second = bootstrap_demo(root, db_path, 20260825)
            self.assertEqual(first[2], second[2])
            self.assertEqual(first_manifest, second[0].read_bytes())

    def test_seed_is_byte_reproducible_and_manifest_verifies(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            manifest_a, outputs_a = generate(Path(first), 7)
            manifest_b, outputs_b = generate(Path(second), 7)
            self.assertEqual(manifest_a.read_bytes(), manifest_b.read_bytes())
            self.assertEqual(outputs_a.read_bytes(), outputs_b.read_bytes())
            self.assertEqual(verify_manifest(manifest_a)["verified"], 16)

    def test_hash_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = generate(Path(directory), 7)
            artifact = load_json(manifest)["artifacts"][0]
            (Path(directory) / artifact["relative_path"]).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "integrity failure"):
                verify_manifest(manifest)

    def test_private_evaluator_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, outputs = generate(Path(directory), 7)
            output = copy.deepcopy(load_json(outputs)[0])
            output["prompt"] = "must never cross boundary"
            with self.assertRaisesRegex(ContractError, "forbidden/unknown"):
                validate_evaluator_output(output)


if __name__ == "__main__":
    unittest.main()
